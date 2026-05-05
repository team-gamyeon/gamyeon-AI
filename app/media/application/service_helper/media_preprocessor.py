"""
영상 전처리 파이프라인

1. S3 다운로드    s3_key → 로컬 임시 파일
2. 파일 검증      허용 포맷, 크기 상한, ffprobe 메타데이터
3. 오디오 추출    ffmpeg → WAV (Whisper 최적화)

임시 파일 관리:
- /tmp/media/{interview_id}/{question_id}/
- 파이프라인 완료 후 service.py에서 일괄 제거
"""
from __future__ import annotations

import json
import logging
import subprocess
import shutil

from dataclasses import dataclass
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.exceptions import (
    MediaDownloadError,
    MediaValidationError,
    AudioExtractionError,
)

logger = logging.getLogger(__name__)

# 허용 포맷
_ALLOWED_EXTENSIONS = {".webm", ".mp4"}

# 파일 크기 상한 (100MB)
_MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024


@dataclass(frozen=True)
class MediaMeta:
    """
    S2 ffprobe 추출 메타데이터 — Value Object

    duration_ms: answer_duration_ms 대체값
    TimeScore.calculate() 직접 입력
    """
    local_path:  str
    duration_ms: int      # ffprobe 추출 실제 영상 길이
    file_size:   int      # bytes
    format_name: str      # "webm" | "mp4"


@dataclass(frozen=True)
class ExtractedAudio:
    """S3 오디오 추출 결과 — Value Object."""
    wav_path:    str
    duration_ms: int      # MediaMeta에서 전달


class MediaPreprocessor:
    """
    S1~S3 영상 전처리 파이프라인.
    service.py에서 주입받아 사용.
    """

    def __init__(
        self,
        s3_bucket:  str,
        s3_client=  None,       # 테스트 주입용
        tmp_dir:    str = "/tmp/media",
    ) -> None:
        self._bucket   = s3_bucket
        self._s3       = s3_client or boto3.client("s3")
        self._tmp_dir  = Path(tmp_dir)

    def preprocess(
        self,
        s3_key:      str,
        interview_id: int,
        question_id:  int,
    ) -> ExtractedAudio:
        """
        S1~S3 전처리 통합 실행.

        Returns:
            ExtractedAudio:
            - wav_path:    Whisper STT 입력 경로
            - duration_ms: TimeScore.calculate() 입력값

        Raises:
            MediaDownloadError:   S3 다운로드 실패
            MediaValidationError: 포맷/크기 검증 실패
            AudioExtractionError: ffmpeg 추출 실패
        """
        work_dir = self._work_dir(interview_id, question_id)
        work_dir.mkdir(parents=True, exist_ok=True)

        # S1: S3 다운로드
        local_path = self._download(s3_key, work_dir)

        # S2: 검증 + 메타데이터 추출
        meta = self._validate_and_analyze(local_path)

        # S3: 오디오 추출 (리먹싱된 경우 meta.local_path 사용)
        wav_path = self._extract_audio(meta.local_path, work_dir)

        logger.info(
            "전처리 완료 interview_id=%d question_id=%d"
            " duration_ms=%d format=%s size=%d",
            interview_id, question_id,
            meta.duration_ms, meta.format_name, meta.file_size,
        )

        return ExtractedAudio(
            wav_path=   wav_path,
            duration_ms=meta.duration_ms,
        )

    def cleanup(self, interview_id: int, question_id: int) -> None:
        """
        임시 파일 일괄 제거.
        service.py 파이프라인 완료 후 호출.
        성공/실패 무관하게 finally에서 호출.
        """
        work_dir = self._work_dir(interview_id, question_id)
        try:
            shutil.rmtree(work_dir, ignore_errors=True)
            logger.debug("임시 파일 제거 완료 dir=%s", work_dir)
        except Exception as e:
            logger.warning("임시 파일 제거 실패 dir=%s error=%s", work_dir, e)

    def _download(self, s3_key: str, work_dir: Path) -> str:
        """
        S3 → 로컬 다운로드
        s3_key에서 파일명 추출하여 저장
        """
        filename   = Path(s3_key).name
        local_path = str(work_dir / filename)

        try:
            self._s3.download_file(
                self._bucket,
                s3_key,
                local_path,
            )
            size = Path(local_path).stat().st_size
            logger.info(
                "S3 다운로드 완료 key=%s size=%d", s3_key, size,
            )
            return local_path

        except (BotoCoreError, ClientError) as e:
            raise MediaDownloadError(
                f"S3 다운로드 실패: bucket={self._bucket} key={s3_key} error={e}"
            )

    def _validate_and_analyze(self, local_path: str) -> MediaMeta:
        """
        포맷/크기 검증 + ffprobe 메타데이터 추출

        검증 항목:
        - 허용 확장자 (webm / mp4)
        - 파일 크기 상한
        - ffprobe 실행 가능 여부 (손상 파일 감지)
        """
        path = Path(local_path)

        # 확장자 검증
        if path.suffix.lower() not in _ALLOWED_EXTENSIONS:
            raise MediaValidationError(
                f"허용되지 않은 포맷: {path.suffix}"
                f" (허용: {_ALLOWED_EXTENSIONS})"
            )

        # 파일 크기 검증
        file_size = path.stat().st_size
        if file_size > _MAX_FILE_SIZE_BYTES:
            raise MediaValidationError(
                f"파일 크기 초과: {file_size} bytes"
                f" (상한: {_MAX_FILE_SIZE_BYTES} bytes)"
            )

        # ffprobe 메타데이터 추출
        return self._run_ffprobe(local_path, file_size)

    def _run_ffprobe(self, local_path: str, file_size: int) -> MediaMeta:
        """
        ffprobe로 영상 메타데이터 추출
        duration → answer_duration_ms 산출

        브라우저 MediaRecorder WebM은 컨테이너 헤더에 duration이 없을 수 있음.
        format duration 없으면 streams[0] duration으로 fallback.
        """
        cmd = [
            "ffprobe",
            "-v",            "error",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            local_path,
        ]

        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
            )
            data        = json.loads(result.stdout)
            format_name = Path(local_path).suffix.lstrip(".")

            # format duration 우선, 없으면 streams fallback
            raw_duration = data.get("format", {}).get("duration")
            if not raw_duration or raw_duration == "N/A":
                streams = data.get("streams", [])
                for stream in streams:
                    stream_dur = stream.get("duration")
                    if stream_dur and stream_dur != "N/A":
                        raw_duration = stream_dur
                        logger.warning(
                            "format duration 없음 → stream duration 사용 path=%s duration=%s",
                            local_path, raw_duration,
                        )
                        break

            if not raw_duration or raw_duration == "N/A":
                # 브라우저 WebM은 헤더에 duration이 없음 → 리먹싱으로 복구
                local_path, raw_duration = self._remux_and_get_duration(
                    local_path, data
                )
                if not raw_duration or raw_duration == "N/A":
                    raise MediaValidationError(
                        f"영상 duration 추출 불가: {local_path}"
                    )

            duration_s = float(raw_duration)

            logger.info(
                "ffprobe 완료 duration=%.3fs format=%s",
                duration_s, format_name,
            )

            return MediaMeta(
                local_path=  local_path,
                duration_ms= int(duration_s * 1000),
                file_size=   file_size,
                format_name= format_name,
            )

        except subprocess.CalledProcessError as e:
            raise MediaValidationError(
                f"ffprobe 실패 (손상 파일 가능성): {local_path} "
                f"stderr={e.stderr.decode('utf-8', errors='ignore')}"
            )

    def _remux_and_get_duration(
        self, local_path: str, original_data: dict
    ) -> tuple[str, str | None]:
        """
        브라우저 WebM duration 헤더 복구.

        MediaRecorder로 녹화된 WebM은 seekable=false 컨테이너로 저장되어
        duration 메타데이터가 없음. ffmpeg -c copy 리먹싱으로 전체 파일을
        스캔해 컨테이너를 재작성하면 duration이 채워짐.
        """
        path = Path(local_path)
        fixed_path = str(path.parent / f"_fixed{path.suffix}")

        try:
            subprocess.run(
                ["ffmpeg", "-i", local_path, "-c", "copy", "-y", fixed_path],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            logger.warning(
                "WebM 리먹싱 실패, 원본 유지 path=%s stderr=%s",
                local_path, e.stderr.decode("utf-8", errors="ignore"),
            )
            return local_path, None

        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-print_format", "json",
                    "-show_format", "-show_streams",
                    fixed_path,
                ],
                check=True,
                capture_output=True,
            )
            data = json.loads(result.stdout)
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            return fixed_path, None

        raw_duration = data.get("format", {}).get("duration")
        if not raw_duration or raw_duration == "N/A":
            for stream in data.get("streams", []):
                d = stream.get("duration")
                if d and d != "N/A":
                    raw_duration = d
                    break

        logger.info(
            "WebM 리먹싱 완료 path=%s duration=%s", fixed_path, raw_duration,
        )
        return fixed_path, raw_duration

    def _extract_audio(self, local_path: str, work_dir: Path) -> str:
        """
        ffmpeg 영상 → WAV 변환

        설정:
        - ac 1:     모노 채널 (Whisper 권장)
        - ar 16000: 16kHz 샘플레이트 (Whisper 최적)
        - vn:       비디오 스트림 제외
        - y:        기존 파일 덮어쓰기
        """
        wav_path = str(work_dir / "extracted.wav")

        cmd = [
            "ffmpeg",
            "-i",  local_path,
            "-ac", "1",
            "-ar", "16000",
            "-vn",
            "-y",
            wav_path,
        ]

        try:
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
            )
            logger.info(
                "오디오 추출 완료 wav=%s", wav_path,
            )
            return wav_path

        except subprocess.CalledProcessError as e:
            raise AudioExtractionError(
                f"ffmpeg 오디오 추출 실패: {local_path} "
                f"stderr={e.stderr.decode('utf-8', errors='ignore')}"
            )

    def _work_dir(self, interview_id: int, question_id: int) -> Path:
        """임시 작업 디렉토리 경로"""
        return self._tmp_dir / str(interview_id) / str(question_id)
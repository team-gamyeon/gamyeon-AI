from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from app.media.application.port import STTPort, TranscriptCorrectionPort
from app.media.application.port.gaze_buffer_port import GazeBufferPort
from app.media.application.port.scoring_config_port import ScoringConfigPort
from app.media.application.service_helper.gaze_aggregator import GazeAggregator
from app.media.application.service_helper.keyword_extractor import KeywordExtractor
from app.media.application.service_helper.media_preprocessor import MediaPreprocessor
from app.media.domain import (
    CorrectionResult,  # Correction
    GazeResult,  # Gaze
    KeywordResult,  # Keyword
    MediaProcessingResult,  # Pipeline
    ReliabilityFactors,
    ScoringConfig,  # Scoring
    STTResult,  # STT
    TimeScore,
    TranscriptState,  # Transcript
    reliability,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 서비스 입력 커맨드 (Inbound DTO 대신 순수 도메인 커맨드)
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class ProcessMediaCommand:
    """
    POST /internal/media/process 수신 데이터를
    서비스 레이어로 전달하는 커맨드 객체

    router.py에서 schema → command 변환 후 service 호출
    """

    interview_id: int
    question_id: int
    s3_key: str
    tech_stack: tuple[str, ...]
    question_content: str
    interview_type: str = "default"


# ──────────────────────────────────────────────
# 메인 서비스
# ──────────────────────────────────────────────


class MediaService:
    """
    Media 파이프라인 오케스트레이터.

    포트 주입:
    - stt_port:         STTPort
    - correction_port:  TranscriptCorrectionPort
    - gaze_buffer:      GazeBufferPort
    - scoring_config:   ScoringConfigPort

    도메인 서비스 주입:
    - keyword_extractor: KeywordExtractor (CPU 기반, 외부 API 없음)
    - gaze_aggregator:   GazeAggregator   (순수 계산, 외부 API 없음)
    """

    def __init__(
        self,
        stt_port: STTPort,
        correction_port: TranscriptCorrectionPort,
        gaze_buffer: GazeBufferPort,
        scoring_config: ScoringConfigPort,
        keyword_extractor: KeywordExtractor,
        gaze_aggregator: GazeAggregator,
        media_preprocessor: MediaPreprocessor,
    ) -> None:
        self._stt = stt_port
        self._correction = correction_port
        self._gaze_buffer = gaze_buffer
        self._scoring = scoring_config
        self._keywords = keyword_extractor
        self._gaze_agg = gaze_aggregator
        self._preprocessor = media_preprocessor

    # ──────────────────────────────────────────
    # Public: 파이프라인 진입점
    # ──────────────────────────────────────────

    async def process(
        self,
        command: ProcessMediaCommand,
    ) -> MediaProcessingResult:
        """
        파이프라인 실행 후 MediaProcessingResult 반환.

        성공 시 MediaProcessingResult 반환.
        나머지 단계 실패는 Degraded 처리 후 계속 진행.

        Raises:
            MediaDownloadError:   S3 다운로드 실패
            MediaValidationError: 포맷/크기/ffprobe 실패
            AudioExtractionError: ffmpeg 오디오 추출 실패
            STTTranscriptionError: Whisper STT 실패
        """
        logger.info(
            "파이프라인 시작 interview_id=%s question_id=%s",
            command.interview_id,
            command.question_id,
        )

        try:
            # 영상 전처리, duration_ms는 ffprobe에서 추출
            extracted = await asyncio.to_thread(
                self._preprocessor.preprocess,
                command.s3_key,
                command.interview_id,
                command.question_id,
            )

            # STT
            stt_result = await self._run_stt(
                command=command,
                wav_path=extracted.wav_path,
            )

            # LLM CoT 교정
            correction_result = await self._run_correction(stt_result, command)

            # TranscriptState 조립
            transcript = self._build_transcript(stt_result, correction_result)

            # fan-out 병렬 실행
            keyword_result, gaze_result = await asyncio.gather(
                self._run_keyword_extraction(transcript),
                self._run_gaze_aggregation(command, extracted.duration_ms),
            )

            # S8: 점수 산출
            config = await self._scoring.get_config(command.interview_type)
            time_score, reliability_score = self._run_scoring(
                stt_result=stt_result,
                gaze_result=gaze_result,
                answer_duration_ms=extracted.duration_ms,
                config=config,
            )

            # 최종 집계
            degraded = (
                transcript.degraded  # S5 실패
                or gaze_result.is_empty  # S7 Gaze 미수신
            )

            result = MediaProcessingResult(
                interview_id=command.interview_id,
                question_id=command.question_id,
                question_content=command.question_content,
                transcript=transcript,
                keywords=keyword_result,
                gaze=gaze_result,
                time=time_score,
                reliability=reliability_score,
                degraded=degraded,
            )

            logger.info(
                "파이프라인 완료 interview_id=%s question_id=%s degraded=%s",
                command.interview_id,
                command.question_id,
                degraded,
            )

            return result

        finally:
            # 성공/실패 무관하게 임시 파일 제거
            self._preprocessor.cleanup(
                interview_id=command.interview_id,
                question_id=command.question_id,
            )

    async def buffer_gaze_segment(self, segment) -> None:
        """
        POST /internal/media/gaze/segment 수신 시 호출.
        GazeBufferPort에 위임.
        """
        await self._gaze_buffer.push(segment)

    # ──────────────────────────────────────────
    # Private: 단계별 실행 메서드
    # ──────────────────────────────────────────

    async def _run_stt(self, command: ProcessMediaCommand, wav_path: str) -> STTResult:
        """
        Whisper STT
        실패 시 STTTranscriptionError → 파이프라인 FAILED
        language_probability < 0.5 → 경고 로그 + 처리 계속
        """
        result = await self._stt.transcribe(
            audio_path=wav_path,
            tech_stack=list(command.tech_stack),
        )

        if result.is_low_confidence:
            logger.warning(
                "STT 신뢰도 낮음 interview_id=%s question_id=%s"
                " language_probability=%.3f",
                command.interview_id,
                command.question_id,
                result.language_probability,
            )

        logger.info(
            "STT 완료 interview_id=%s question_id=%s" " model=%s words=%d",
            command.interview_id,
            command.question_id,
            result.stt_model_used.value,
            len(result.word_timestamps),
        )

        return result

    async def _run_correction(
        self,
        stt_result: STTResult,
        command: ProcessMediaCommand,
    ) -> CorrectionResult:
        """
        S5: LLM CoT 통합 교정
        실패 시 Degraded Mode 자동 강등 (예외 미전파)
        """
        result = await self._correction.correct(
            raw_transcript=stt_result.raw_transcript,
            tech_stack=list(command.tech_stack),
        )

        if result.degraded:
            logger.warning(
                "S5 LLM 교정 Degraded interview_id=%s question_id=%s",
                command.interview_id,
                command.question_id,
            )
        else:
            logger.info(
                "S5 LLM 교정 완료 interview_id=%s question_id=%s"
                " phonetic=%d term=%d",
                command.interview_id,
                command.question_id,
                result.phonetic_correction_count,
                result.term_correction_count,
            )

        return result

    def _build_transcript(
        self,
        stt_result: STTResult,
        correction_result: CorrectionResult,
    ) -> TranscriptState:
        """
        S4 + S5 결과를 TranscriptState VO로 조립
        두 AR의 값을 읽기만 하고 새 불변 객체 생성
        """
        return TranscriptState(
            raw_transcript=stt_result.raw_transcript,
            corrected_transcript=correction_result.corrected_transcript,
            word_timestamps=stt_result.word_timestamps,
            corrections=correction_result.corrections,
            language_probability=stt_result.language_probability,
            stt_model_used=stt_result.stt_model_used,
            phonetic_corrected=correction_result.phonetic_corrected,
            degraded=correction_result.degraded,
        )

    async def _run_keyword_extraction(
        self,
        transcript: TranscriptState,
    ) -> KeywordResult:
        """
        S6: 키워드 추출 (CPU, 외부 API 없음)
        실패 시 빈 tuple 반환, 파이프라인 계속 진행
        """
        try:
            result = await self._keywords.extract(
                text=transcript.corrected_transcript,
            )
            logger.info(
                "키워드 추출 완료 candidates=%d",
                len(result.candidates),
            )
            return result
        except Exception as e:
            logger.warning("키워드 추출 실패 — 빈 결과 반환: %s", e)
            return KeywordResult(candidates=())

    async def _run_gaze_aggregation(
        self, command: ProcessMediaCommand, answer_duration_ms: int
    ) -> GazeResult:
        """
        S7: Gaze 집계.
        버퍼에서 pop_all() 후 GazeAggregator에 위임
        세그먼트 0개 → is_empty=True → Degraded 판단.
        """
        segments = await self._gaze_buffer.pop_all(command.question_id)

        if not segments:
            logger.warning(
                "Gaze 세그먼트 없음 question_id=%s",
                command.question_id,
            )

        result = self._gaze_agg.aggregate(
            segments=segments,
            answer_duration_ms=answer_duration_ms,
        )

        logger.info(
            "Gaze 집계 완료 gaze_score=%s coverage=%.3f",
            result.gaze_score,
            result.summary.segment_coverage,
        )

        return result

    def _run_scoring(
        self,
        stt_result: STTResult,
        gaze_result: GazeResult,
        answer_duration_ms: int,
        config: ScoringConfig,
    ) -> tuple[TimeScore, reliability]:
        """
        S8: 시간 점수 + 신뢰도 점수 산출.
        ScoringConfig 정책 기반.
        도메인 calculate() 직접 호출.
        """
        time_score = TimeScore.calculate(
            answer_duration_ms=answer_duration_ms,
            config=config,
        )

        factors = ReliabilityFactors(
            question_success_rate=1.0,
            segment_coverage=gaze_result.summary.segment_coverage,
            avg_word_confidence=stt_result.avg_word_confidence,
        )
        reliability_score = reliability.calculate(
            factors=factors,
            config=config,
        )

        logger.info(
            "점수 산출 완료 time=%d reliability=%d grade=%s",
            time_score.time_score,
            reliability_score.score,
            reliability_score.grade.value,
        )

        return time_score, reliability_score

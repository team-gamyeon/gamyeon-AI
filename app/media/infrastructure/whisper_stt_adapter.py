"""STTPort 구현체

faster-whisper 기반 STT 엔진
OOM fallback 정책:
1. large-v3 시도 → VRAM OOM → medium 1회 재시도
2. medium도 실패 → STTTranscriptionError 발생

initial_prompt:
1. tech_stack 기반으로 구성 -> 없을시 일반
2. Whisper가 기술 용어를 더 정확하게 인식하도록 힌트 제공
"""

from __future__ import annotations

import logging
import asyncio
from pathlib import Path

from faster_whisper import WhisperModel

from app.media.application.port.stt_port import STTPort
from app.media.domain import (
    STTResult, STTModelType,
    WordTimestamp,
)
from app.core.exceptions import STTTranscriptionError

logger = logging.getLogger(__name__)

# 모델 로드 순서 (OOM fallback)
_MODEL_SEQUENCE = [
    # STTModelType.MEDIUM,
    STTModelType.SMALL,
]

_MODEL_NAME_MAP = {
    # STTModelType.MEDIUM: "medium",
    STTModelType.SMALL: "small",
}


class WhisperSTTAdapter(STTPort):
    """
    faster-whisper STTPort 구현체

    모델은 최초 호출 시 lazy load
    VRAM OOM 발생 시 medium으로 자동 fallback
    """

    def __init__(self, device: str = "cuda", compute_type: str = "int8") -> None:
        self._device       = device
        self._compute_type = compute_type
        self._models: dict[STTModelType, WhisperModel] = {}

    async def transcribe(
        self,
        audio_path: str,
        tech_stack: list[str],
    ) -> STTResult:
        """
        STTPort.transcribe() 구현
        OOM 발생 시 medium fallback 1회
        """
        if not Path(audio_path).exists():
            raise STTTranscriptionError(
                f"WAV 파일 없음: {audio_path}"
            )

        prompt  = self._build_initial_prompt(tech_stack)
        last_ex = None

        for model_type in _MODEL_SEQUENCE:
            try:
                model  = self._get_model(model_type)
                result = await asyncio.to_thread(
                    self._run_transcription,
                    model, audio_path, prompt, model_type
                )
                
                logger.info(
                    "STT 완료 model=%s words=%d lang_prob=%.3f",
                    model_type.value,
                    len(result.word_timestamps),
                    result.language_probability,
                )
                return result

            except MemoryError as e:
                logger.warning(
                    "STT VRAM OOM model=%s — fallback 시도",
                    model_type.value,
                )
                last_ex = e
                continue

            except Exception as e:
                logger.error("STT 실패 model=%s error=%s", model_type.value, e)
                last_ex = e
                break

        raise STTTranscriptionError(
            f"faster-whisper 전체 fallback 실패: {last_ex}"
        )

    # ──────────────────────────────────────────
    # Private
    # ──────────────────────────────────────────

    def _get_model(self, model_type: STTModelType) -> WhisperModel:
        """모델 lazy load — 최초 요청 시 1회 로드"""
        if model_type not in self._models:
            logger.info("Whisper 모델 로드 model=%s", model_type.value)
            self._models[model_type] = WhisperModel(
                _MODEL_NAME_MAP[model_type],
                device=self._device,
                compute_type=self._compute_type,
            )
        return self._models[model_type]

    def _run_transcription(
        self,
        model: WhisperModel,
        audio_path: str,
        prompt: str,
        model_type: STTModelType,
    ) -> STTResult:
        """
        faster-whisper transcribe() 호출 및 STTResult 변환

        word_timestamps=True: 단어 단위 타임스탬프 활성화
        temperature=0.0: 결정적 출력 (재현성 보장)
        beam_size=5, best_of=5: 정확도 최적화
        """
        segments, info = model.transcribe(
            audio_path,
            language="ko",
            temperature=0.0,
            beam_size=5,
            best_of=5,
            word_timestamps=True,
            initial_prompt=prompt,
        )

        raw_words:   list[WordTimestamp] = []
        raw_text_parts: list[str]        = []

        for segment in segments:
            raw_text_parts.append(segment.text.strip())
            if segment.words:
                for word in segment.words:
                    raw_words.append(
                        WordTimestamp(
                            word=word.word.strip(),
                            start=word.start,
                            end=word.end,
                            probability=word.probability,
                        )
                    )

        return STTResult(
            raw_transcript=      " ".join(raw_text_parts).strip(),
            word_timestamps=     raw_words,
            language_probability=info.language_probability,
            stt_model_used=      model_type,
        )

    def _build_initial_prompt(self, tech_stack: list[str]) -> str:
        """
        tech_stack 기반 initial_prompt 구성
        Whisper가 기술 용어를 정확하게 인식하도록 힌트 제공

        예) ["Redis", "Docker", "JPA"]
            → "Redis, Docker, JPA를 활용한 기술 면접 답변입니다"
        """
        if not tech_stack:
            return "기술 면접 답변입니다."
        terms = ", ".join(tech_stack)
        return f"{terms}를 활용한 기술 면접 답변입니다."
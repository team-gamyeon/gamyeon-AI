"""
Media 모듈 FastAPI 의존성 주입 설정

헥사고날 원칙:
- service.py는 포트 인터페이스만 의존
- DI에서 구현체를 포트에 바인딩
- 구현체 교체 시 이 파일만 수정

싱글턴 전략:
- 모델 로드 비용이 큰 어댑터 (Whisper, Okt)는
- 애플리케이션 시작 시 1회만 생성
- FastAPI lifespan 또는 lru_cache 활용
"""
from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.media.application.service                           import MediaService
from app.media.application.service_helper.gaze_aggregator    import GazeAggregator
from app.media.application.service_helper.media_preprocessor import MediaPreprocessor
from app.media.infrastructure.whisper_stt_adapter            import WhisperSTTAdapter
from app.media.infrastructure.gpt_mini_adapter               import GptMiniAdapter
from app.media.infrastructure.inmemory_gaze_buffer           import InMemoryGazeBuffer
from app.media.infrastructure.env_scoring_config             import EnvScoringConfigAdapter
from app.media.infrastructure.keyword_extractor_impl         import KeywordExtractorImpl
from app.media.application.usecase                           import ProcessMediaUseCase
from app.media.infrastructure.spring_webhook_adapter         import SpringWebhookAdapter
from app.media.infrastructure.media_event_adapter            import MediaEventAdapter

# 싱글턴 어댑터 (애플리케이션 생명주기와 동일)
@lru_cache(maxsize=1)
def _get_whisper_adapter() -> WhisperSTTAdapter:
    """
    Whisper 모델 어댑터 싱글턴
    lru_cache로 애플리케이션 당 1회만 생성
    모델 lazy load는 어댑터 내부에서 처리
    """
    return WhisperSTTAdapter(
        device=settings.WHISPER_DEVICE,
        compute_type=settings.WHISPER_COMPUTE_TYPE,
    )

@lru_cache(maxsize=1)
def _get_gpt_mini_adapter() -> GptMiniAdapter:
    return GptMiniAdapter(
        api_key=settings.OPENAI_API_KEY,
        model=settings.LLM_MODEL,
        timeout=settings.LLM_TIMEOUT_SECONDS,
    )

@lru_cache(maxsize=1)
def _get_gaze_buffer() -> InMemoryGazeBuffer:
    """
    인메모리 Gaze 버퍼 싱글턴.
    MVP-2: RedisGazeBuffer로 교체 시 이 함수만 수정.
    """
    return InMemoryGazeBuffer()

@lru_cache(maxsize=1)
def _get_env_scoring_adapter() -> EnvScoringConfigAdapter:
    return EnvScoringConfigAdapter()

@lru_cache(maxsize=1)
def _get_keyword_extractor() -> KeywordExtractorImpl:
    """konlpy Okt 싱글턴 (초기 로드 비용 절감)."""
    return KeywordExtractorImpl()

@lru_cache(maxsize=1)
def _get_gaze_aggregator() -> GazeAggregator:
    return GazeAggregator()

@lru_cache(maxsize=1)
def _get_spring_webhook_adapter() -> SpringWebhookAdapter:
    return SpringWebhookAdapter()

@lru_cache(maxsize=1)
def _get_media_event_adapter() -> MediaEventAdapter:
    return MediaEventAdapter()

@lru_cache(maxsize=1)
def _get_media_preprocessor() -> MediaPreprocessor:
    return MediaPreprocessor(s3_bucket=settings.S3_BUCKET)

# ── lru_cache 직접 조립 (Depends 컨텍스트 밖 호출용) ──────────────
@lru_cache(maxsize=1)
def _build_media_service() -> MediaService:
    """
    어댑터를 직접 조립하는 싱글턴 팩토리.

    Depends 없이 lru_cache 어댑터를 직접 호출해 MediaService를 생성.
    get_process_media_usecase()처럼 FastAPI 컨텍스트 밖에서 호출할 때 사용.
    어댑터 교체는 이 파일의 각 _get_*() 함수만 수정하면 됨.
    """
    return MediaService(
        stt_port=          _get_whisper_adapter(),
        correction_port=   _get_gpt_mini_adapter(),
        gaze_buffer=       _get_gaze_buffer(),
        scoring_config=    _get_env_scoring_adapter(),
        keyword_extractor= _get_keyword_extractor(),
        gaze_aggregator=   _get_gaze_aggregator(),
        media_preprocessor=_get_media_preprocessor(),
    )

@lru_cache(maxsize=1)
def get_process_media_usecase() -> ProcessMediaUseCase:
    """
    ProcessMediaUseCase 싱글턴.

    _build_media_service()를 직접 호출해 Depends 객체가 주입되는 문제 방지.
    router.py에서 Depends(get_process_media_usecase)로 사용.
    """
    return ProcessMediaUseCase(
        service=      _build_media_service(),
        webhook_port= _get_spring_webhook_adapter(),
        event_port=   _get_media_event_adapter(),
    )

# ── FastAPI Depends 진입점 ──────────────────────────────────────────
def get_media_service() -> MediaService:
    """
    router.py의 Depends 진입점.

    내부에서 _build_media_service() 싱글턴을 반환하므로
    매 요청마다 새 인스턴스를 만들지 않음.

    router.py 사용 예:
        service: MediaService = Depends(get_media_service)
    """
    return _build_media_service()
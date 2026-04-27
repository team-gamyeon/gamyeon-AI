from app.core.config import settings
from app.media.application.port.scoring_config_port import ScoringConfigPort
from app.media.domain import ScoringConfig


class EnvScoringConfigAdapter(ScoringConfigPort):
    """ScoringConfigPort 구현체 — .env 환경변수 기반."""

    async def get_config(self, interview_type: str = "default") -> ScoringConfig:
        return ScoringConfig(
            limit_ms=settings.SCORING_LIMIT_MS,
            question_success_rate_weight=settings.SCORING_QUESTION_SUCCESS_RATE_WEIGHT,
            segment_coverage_weight=settings.SCORING_SEGMENT_COVERAGE_WEIGHT,
            avg_word_confidence_weight=settings.SCORING_AVG_WORD_CONFIDENCE_WEIGHT,
        )

from __future__ import annotations
from dataclasses import dataclass
from typing import Self

from .._shared.normalizer import r3

from .scoring_config import ScoringConfig

@dataclass(frozen=True)
class TimeScore :
    """
    S8 시간 점수 계산 결과 — Value Object.
    ratio: answer_duration_ms ÷ limit_ms → r3() 적용.
    """
    time_score:         int
    answer_duration_ms: int
    limit_ms:           int
    ratio:              float

    def __post_init__(self) -> None :
        object.__setattr__(self, 'ratio', r3(self.ratio))

    @classmethod
    def calculate(
        cls,
        answer_duration_ms: int,
        config: ScoringConfig,
    ) -> Self :
        """ScoringConfig 정책 기반 시간 점수 산출."""
        ratio = answer_duration_ms / config.limit_ms
        score = int(100 - abs(1 - ratio) * 100)
        score = max(0, min(100, score))
        return cls(
            time_score=score,
            answer_duration_ms=answer_duration_ms,
            limit_ms=config.limit_ms,
            ratio=ratio,
        )
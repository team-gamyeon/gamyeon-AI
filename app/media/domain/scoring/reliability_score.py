# app/media/domain/scoring/aggregate.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Self

from .reliability_factors import ReliabilityFactors
from .reliability_grade import ReliabilityGrade
from .scoring_config import ScoringConfig


@dataclass(frozen=True)
class reliability:
    """
    S8 신뢰도 점수 — Aggregate Root
    외부는 reliability만 참조
    내부 ReliabilityFactors를 직접 생성하지 않음
    """

    score: int
    grade: ReliabilityGrade
    factors: ReliabilityFactors

    @classmethod
    def calculate(
        cls,
        factors: ReliabilityFactors,
        config: ScoringConfig,
    ) -> Self:
        """ScoringConfig 정책 기반 신뢰도 점수 산출."""
        raw = (
            factors.question_success_rate * config.question_success_rate_weight
            + factors.segment_coverage * config.segment_coverage_weight
            + factors.avg_word_confidence * config.avg_word_confidence_weight
        )
        score = max(0, min(100, int(raw)))
        return cls(
            score=score, grade=ReliabilityGrade.from_score(score), factors=factors
        )

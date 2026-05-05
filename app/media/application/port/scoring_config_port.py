from abc import ABC, abstractmethod

from app.media.domain import ScoringConfig


class ScoringConfigPort(ABC):
    """점수 산출 정책 조회 추상화 포트."""

    @abstractmethod
    async def get_config(self, interview_type: str = "default") -> ScoringConfig:
        ...
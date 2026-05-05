"""
Webhook 재시도 정책 Value Object.
frozen=True: 정책값 불변 보장.

기본값: max_attempts=3, backoff_seconds=2.0
→ 2s → 4s → 8s 지수 백오프
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class RetryPolicy:
    """
    Webhook 전송 재시도 정책 VO.

    max_attempts:    최대 시도 횟수 (초기 시도 포함).
    backoff_seconds: 지수 백오프 초기값 (초).
                    1회 실패 후 backoff_seconds
                    2회 실패 후 backoff_seconds * 2
                    3회 실패 후 backoff_seconds * 4
    timeout_seconds: 단건 요청 타임아웃.
    """
    max_attempts:    int   = 3
    backoff_seconds: float = 2.0
    timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError(
                f"max_attempts는 1 이상이어야 함: {self.max_attempts}"
            )
        if self.backoff_seconds <= 0:
            raise ValueError(
                f"backoff_seconds는 0 초과여야 함: {self.backoff_seconds}"
            )

    @property
    def wait_seconds(self) -> list[float]:
        """
        각 재시도 대기 시간 목록.
        예) max_attempts=3, backoff=2.0
            → [2.0, 4.0, 8.0]
        """
        return [
            self.backoff_seconds * (2 ** i)
            for i in range(self.max_attempts)
        ]
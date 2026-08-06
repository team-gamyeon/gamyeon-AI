"""
공통 Webhook 전송 컴포넌트.

tenacity 기반 재시도 + 구조화 로그 DLQ.

사용처: webhook으로 spring server에 전달하는 부분들

MVP1: 3회 실패 시 구조화 JSON 로그 파일 출력
MVP2: Grafana Loki 수집 (로그 출력 방식만 변경)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from tenacity import (
    RetryError,
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .retry_policy import RetryPolicy

logger = logging.getLogger(__name__)
dlq_logger = logging.getLogger("dlq")  # DLQ 전용 로거 -> MVP-2: Loki 핸들러 교체


class WebhookSender:
    """
    범용 Webhook 전송 컴포넌트

    식별자 구조 무관
    payload를 그대로 전송하고 기록
    target으로 도메인/이벤트 유형 식별

    재시도 정책:
    - tenacity 지수 백오프 (기본 2s → 4s → 8s)
    - 재시도 대상: 네트워크 오류, 5xx 응답
    - 재시도 제외: 4xx 응답 (클라이언트 오류 — 재시도 무의미)

    DLQ(Dead Letter Queue):
    - MVP1: dlq_logger → 파일 핸들러 (JSON 구조화 로그)
    - MVP2: dlq_logger 핸들러를 Loki로 교체
        WebhookSender 코드 변경 없음
    """

    def __init__(
        self, policy: RetryPolicy | None = None, internal_api_key: str = ""
    ) -> None:
        self._policy = policy or RetryPolicy()
        self._internal_api_key = internal_api_key

    async def send(self, url: str, payload: dict[str, Any], target: str) -> None:
        """
        Webhook 전송 진입점

        Args:
            url:          전송 대상 엔드포인트
            payload:      전송 페이로드
            target:       로깅 식별자 (spring_webhook / internal_event)

        Raises:
            없음. 최종 실패 시 DLQ 로그 기록 후 반환
        """
        try:
            await self._send_with_retry(url, payload, target)

        except RetryError as e:
            self._write_dlq_log(
                target=target,
                url=url,
                payload=payload,
                retry_count=self._policy.max_attempts,
                last_error=str(e.last_attempt.exception()),
            )

        except Exception as e:
            # 재시도 대상 외 예외 (4xx 등)
            logger.error("Webhook 전송 불가 target=%s error=%s", target, e)
            self._write_dlq_log(
                target=target,
                url=url,
                payload=payload,
                retry_count=0,
                last_error=str(e),
            )

    # Private
    async def _send_with_retry(
        self, url: str, payload: dict[str, Any], target: str
    ) -> None:
        """
        tenacity 재시도 래퍼.
        RetryPolicy 값을 tenacity 데코레이터에 동적 적용.
        """

        @retry(
            retry=retry_if_exception_type(
                (httpx.TransportError, httpx.TimeoutException, _RetryableError)
            ),
            stop=stop_after_attempt(self._policy.max_attempts),
            wait=wait_exponential(
                multiplier=self._policy.backoff_seconds,
                min=self._policy.backoff_seconds,
            ),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=False,  # RetryError로 래핑
        )
        async def _attempt() -> None:
            async with httpx.AsyncClient(
                timeout=self._policy.timeout_seconds
            ) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "X-Internal-API-Key": self._internal_api_key,
                    },
                )

                if response.status_code >= 500:
                    raise _RetryableError(f"5xx 응답: {response.status_code}")

                if response.status_code >= 400:
                    raise _NonRetryableError(f"4xx 응답: {response.status_code}")

            logger.info(
                "Webhook 전송 성공 target=%s",
                target,
            )

        await _attempt()

    def _write_dlq_log(
        self,
        target: str,
        url: str,
        payload: dict[str, Any],
        retry_count: int,
        last_error: str,
    ) -> None:
        """
        DLQ 구조화 로그 기록.

        MVP-1: dlq_logger → 파일 핸들러 출력.
        MVP-2: dlq_logger 핸들러 → Loki 교체. 이 메서드 코드 변경 없음.

        grep 복구 예시:
          grep "webhook_dead_letter" /var/log/dlq/dlq.log
          grep '"target": "spring_webhook"' /var/log/dlq/dlq.log
          grep '"intvId": "123"' /var/log/dlq/dlq.log | jq .
          grep '"reportId": "456"' /var/log/dlq/dlq.log | jq .
        """
        dlq_logger.critical(
            json.dumps(
                {
                    "event": "webhook_dead_letter",
                    "target": target,
                    "url": url,
                    "payload": payload,
                    "retry_count": retry_count,
                    "last_error": last_error,
                    "failed_at": datetime.now(timezone.utc).isoformat(),
                },
                ensure_ascii=False,
                default=str,  # 모르는 데이터 타입이 나오면 일단 문자열로 강제 변환
            )
        )


# 내부 예외 (tenacity 재시도 분기용) -> Exception 부분이 공통으로 생기면 이전 예정


class _RetryableError(Exception):
    """5xx — 재시도 대상."""


class _NonRetryableError(Exception):
    """4xx — 재시도 제외."""

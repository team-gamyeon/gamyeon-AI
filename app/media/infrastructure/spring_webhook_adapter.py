from __future__ import annotations

import logging

from app.core.config import settings
from app.core.webhook import RetryPolicy, WebhookSender
from app.media.application.port.result_webhook_port import ResultWebhookPort
from app.media.domain.pipeline.media_processing_result import MediaProcessingResult
from app.media.interface.schema.webhook import WebhookFailedPayload

logger = logging.getLogger(__name__)


class SpringWebhookAdapter(ResultWebhookPort):
    """
    ResultWebhookPort 구현체

    WebhookSender 기반 Spring Boot 결과 전송
    """

    def __init__(self, policy: RetryPolicy | None = None) -> None:
        self._sender = WebhookSender(
            policy=policy or RetryPolicy(),
            internal_api_key=settings.INTERNAL_API_KEY,
        )

    async def send_success(self, result: MediaProcessingResult) -> None:
        """
        성공시 전송

        args:
            MediaProcessingResult: Media 프로세싱 결과
        """
        payload = result.to_spring_webhook_payload().model_dump(by_alias=True)

        logger.info(
            "Webhook 전송 시작 (DONE) url=%s interview_id=%s question_id=%s"
            " degraded=%s corrected_transcript=%s keyword_count=%d",
            settings.SPRING_WEBHOOK_URL,
            result.interview_id,
            result.question_id,
            result.degraded,
            result.transcript.corrected_transcript,
            len(result.keywords.candidates),
        )

        await self._sender.send(
            url=settings.SPRING_WEBHOOK_URL,
            payload=payload,
            target="spring_webhook",
        )

        logger.info(
            "Webhook 전송 완료 (DONE) interview_id=%s question_id=%s",
            result.interview_id,
            result.question_id,
        )

    async def send_failed(
        self,
        interview_id: int,
        question_id: int,
        error_code: str,
        message: str,
    ) -> None:
        """
        실패시 전송

        args:
            interview_id: 면접 ID
            question_id:  질문 ID
            error_code:   에러 코드
            message:      에러 상세 메세지
        """
        logger.warning(
            "Webhook 전송 시작 (FAILED) url=%s interview_id=%s question_id=%s"
            " error_code=%s message=%s",
            settings.SPRING_WEBHOOK_URL,
            interview_id,
            question_id,
            error_code,
            message,
        )

        await self._sender.send(
            url=settings.SPRING_WEBHOOK_URL,
            payload=WebhookFailedPayload(
                intvId=interview_id,
                questionSetId=question_id,
                errorMessage=message,
            ).model_dump(by_alias=True),
            target="spring_webhook_failed",
        )

        logger.info(
            "Webhook 전송 완료 (FAILED) interview_id=%s question_id=%s",
            interview_id,
            question_id,
        )

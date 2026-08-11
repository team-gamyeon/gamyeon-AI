# app/report/infrastructure/di.py
from functools import lru_cache
from app.report.application.service import ReportService
from app.report.infrastructure.static_score_adapter import StaticScoreAdapter
from app.report.infrastructure.webhook_callback_adapter import WebhookCallbackAdapter
from app.core.webhook.webhook_sender import WebhookSender
from app.core.config import settings

@lru_cache
def get_webhook_sender() -> WebhookSender:
    return WebhookSender(internal_api_key=settings.INTERNAL_API_KEY)

@lru_cache
def get_callback_adapter() -> WebhookCallbackAdapter:
    return WebhookCallbackAdapter(sender=get_webhook_sender())

def get_report_service() -> ReportService:
    return ReportService(
        adapter=StaticScoreAdapter(),
        callback_port=get_callback_adapter(),
    )

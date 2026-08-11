import asyncio

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.webhook.webhook_sender import WebhookSender
from app.feedback.application.service import FeedbackService
from app.feedback.infrastructure.langchain_feedback_adapter import LangchainFeedbackAdapter
from app.feedback.infrastructure.prompt_provider import FeedbackPromptProvider
from app.feedback.infrastructure.webhook_callback_adapter import FeedbackWebhookCallbackAdapter

load_dotenv()

# 동시 LLM 호출 수 상한.
# 운영 환경에서 다수 사용자가 동시에 면접을 종료할 때 OpenAI TPM 한도 초과 방지.
# 값은 FEEDBACK_LLM_CONCURRENCY 환경변수로 조정 가능하며 기본값은 3.
_LLM_SEMAPHORE: asyncio.Semaphore | None = None


def get_llm_semaphore() -> asyncio.Semaphore:
    # 세마포어는 이벤트 루프가 생성된 이후에 초기화해야 한다.
    # 모듈 임포트 시점이 아닌 함수 호출 시점에 초기화한다.
    global _LLM_SEMAPHORE
    if _LLM_SEMAPHORE is None:
        _LLM_SEMAPHORE = asyncio.Semaphore(settings.FEEDBACK_LLM_CONCURRENCY)
    return _LLM_SEMAPHORE


def _get_llm() -> ChatOpenAI:
    # 모델 교체는 이 한 줄만 수정한다.
    # request_timeout: LLM 응답이 지연될 경우 요청 큐 누적 방지.
    # max_retries=0: 재시도는 adapter(_invoke_with_retry)에서 직접 제어한다.
    return ChatOpenAI(
        model=settings.LLM_MODEL,
        temperature=0.0,
        request_timeout=settings.FEEDBACK_LLM_TIMEOUT_SEC,
        max_retries=0,
    )


def get_feedback_service() -> FeedbackService:
    port = LangchainFeedbackAdapter(
        llm=_get_llm(),
        prompt_provider=FeedbackPromptProvider(),
        semaphore=get_llm_semaphore(),
    )
    sender = WebhookSender(internal_api_key=settings.INTERNAL_API_KEY)
    callback = FeedbackWebhookCallbackAdapter(sender)
    return FeedbackService(feedback_port=port, callback=callback)
from langchain_openai import ChatOpenAI

from app.question.application.port.s3_download_port import S3DownloadPort
from app.question.application.port.pdf_extract_port import PdfExtractPort
from app.question.application.port.structuring_port import StructuringPort
from app.question.application.port.question_gen_port import QuestionGenPort
from app.question.application.port.callback_port import CallbackPort

from app.question.infrastructure.local_file_adapter import LocalFileAdapter
from app.question.infrastructure.pymupdf_adapter import PyMuPDFAdapter
from app.question.infrastructure.llm_structuring_adapter import LLMStructuringAdapter
from app.question.infrastructure.llm_question_gen_adapter import LLMQuestionGenAdapter
from app.question.infrastructure.webhook_callback_adapter import WebhookCallbackAdapter
from app.question.infrastructure.structuring_prompt_provider import StructuringPromptProvider
from app.question.infrastructure.question_gen_prompt_provider import QuestionGenPromptProvider
from app.question.application.service import QuestionService
from app.core.webhook.webhook_sender import WebhookSender
from app.question.infrastructure.s3_download_adapter import S3DownloadAdapter

def get_question_service() -> QuestionService:
    return QuestionService(
        s3_download_port=  get_s3_download_port(),
        pdf_extract_port=  PyMuPDFAdapter(),
        structuring_port=  _get_structuring_port(),
        question_gen_port= _get_question_gen_port(),
        callback_port=     _get_callback_port(),
    )


def get_s3_download_port() -> S3DownloadPort:
    #return LocalFileAdapter()
    return S3DownloadAdapter(timeout=60.0) # PDF가 클 수 있으므로 60초 넉넉히 설정


def _get_structuring_port() -> StructuringPort:
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.0,
        timeout=settings.LLM_TIMEOUT_SECONDS,  
        max_retries=2,                         
    )
    prompt_provider = StructuringPromptProvider(version="v1")
    return LLMStructuringAdapter(llm=llm, prompt_provider=prompt_provider)


def _get_question_gen_port() -> QuestionGenPort:
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.8,
        timeout=settings.LLM_TIMEOUT_SECONDS,  
        max_retries=2,                         
    )
    prompt_provider = QuestionGenPromptProvider(version="v1")
    return LLMQuestionGenAdapter(llm=llm, prompt_provider=prompt_provider)


def _get_callback_port() -> CallbackPort:
    return WebhookCallbackAdapter(sender=WebhookSender())

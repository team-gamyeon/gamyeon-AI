import logging
from app.core.config import settings
from app.question.application.port.callback_port import CallbackPort
from app.question.application.port.pdf_extract_port import PdfExtractPort
from app.question.application.port.question_gen_port import QuestionGenPort
from app.question.application.port.s3_download_port import S3DownloadPort
from app.question.application.port.structuring_port import StructuringPort
from app.question.schema.request import QuestionGenerateRequest
from app.question.schema.response import QuestionCallbackPayload
from app.question.exception import (
    S3DownloadError,
    PdfExtractError,
    LLMStructuringError,
    LLMGenerationError,
)

logger = logging.getLogger(__name__)


class QuestionService:

    def __init__(
        self,
        s3_download_port: S3DownloadPort,
        pdf_extract_port: PdfExtractPort,
        structuring_port: StructuringPort,
        question_gen_port: QuestionGenPort,
        callback_port: CallbackPort,
    ) -> None:
        self._s3 = s3_download_port
        self._pdf = pdf_extract_port
        self._struct = structuring_port
        self._qgen = question_gen_port
        self._callback = callback_port

    async def run(self, request: QuestionGenerateRequest) -> None:
        payload: QuestionCallbackPayload

        try:
            # 1. 파일 키 추출
            resume_key = request.get_file_key("RESUME")
            if not resume_key:
                raise ValueError("RESUME file not found in request.files")

            portfolio_key = request.get_file_key("PORTFOLIO")
            self_intro_key = request.get_file_key("SELF_INTRODUCTION")

            # 2. S3 다운로드 (이력서 필수, 나머지는 선택)
            resume_bytes = await self._s3.download(resume_key)
            portfolio_bytes = (
                await self._s3.download(portfolio_key) if portfolio_key else None
            )
            self_intro_bytes = (
                await self._s3.download(self_intro_key) if self_intro_key else None
            )

            # 3. PDF 텍스트 추출
            resume_text = await self._pdf.extract(resume_bytes)
            portfolio_text = (
                await self._pdf.extract(portfolio_bytes) if portfolio_bytes else None
            )
            self_intro_text = (
                await self._pdf.extract(self_intro_bytes) if self_intro_bytes else None
            )

            # 4. LLM 구조화
            interview = await self._struct.structure(
                resume_text=resume_text,
                job_role=None,
                portfolio_text=portfolio_text,
                self_intro_text=self_intro_text,
            )

            # 5. 질문 생성
            questions = await self._qgen.generate(interview)
            if not questions:
                raise LLMGenerationError("LLM이 질문을 생성하지 못했습니다. (빈 배열 반환)")

            # 6. 성공 페이로드
            payload = QuestionCallbackPayload(
                intvId=request.intvId,
                status="SUCCESS",
                questions=questions,
                errorMessage=None,
            )
            logger.info(f"질문 생성 성공 intvId={request.intvId}")

        except S3DownloadError as e:
            logger.error(f"질문 생성 실패 intvId={request.intvId}: {e}", exc_info=True)
            payload = QuestionCallbackPayload(
                intvId=request.intvId,
                status="FAILED",
                questions=[],
                errorMessage=f"[S3_DOWNLOAD_ERROR] {e}",
            )

        except PdfExtractError as e:
            logger.error(f"질문 생성 실패 intvId={request.intvId}: {e}", exc_info=True)
            payload = QuestionCallbackPayload(
                intvId=request.intvId,
                status="FAILED",
                questions=[],
                errorMessage=f"[PDF_EXTRACT_ERROR] {e}",
            )

        except LLMStructuringError as e:
            logger.error(f"질문 생성 실패 intvId={request.intvId}: {e}", exc_info=True)
            payload = QuestionCallbackPayload(
                intvId=request.intvId,
                status="FAILED",
                questions=[],
                errorMessage=f"[LLM_STRUCTURING_ERROR] {e}",
            )

        except LLMGenerationError as e:
            logger.error(f"질문 생성 실패 intvId={request.intvId}: {e}", exc_info=True)
            payload = QuestionCallbackPayload(
                intvId=request.intvId,
                status="FAILED",
                questions=[],
                errorMessage=f"[LLM_GENERATION_ERROR] {e}",
            )

        except Exception as e:
            logger.error(f"질문 생성 실패 intvId={request.intvId}: {e}", exc_info=True)
            payload = QuestionCallbackPayload(
                intvId=request.intvId,
                status="FAILED",
                questions=[],
                errorMessage=f"[UNKNOWN_ERROR] {e}",
            )

        finally:
            try:
                await self._callback.send(
                    url=settings.QUESTION_SPRING_WEBHOOK_URL,
                    payload=payload,
                )
            except Exception as callback_e:
                logger.error(
                    f"콜백 전송 실패 intvId={request.intvId}: {callback_e}",
                    exc_info=True,
                )
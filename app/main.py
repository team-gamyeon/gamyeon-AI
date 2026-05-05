import logging
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging_config import setup_logging
from app.core.schema import ApiResponse
from app.feedback.infrastructure.di import get_feedback_service
from app.feedback.infrastructure.event_listener import register_feedback_listeners
from app.feedback.router import router as feedback_router
from app.media.interface.router import router as media_router
from app.question.router import router as question_router
from app.report.router import router as report_router

load_dotenv()
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    feedback_service = get_feedback_service()
    register_feedback_listeners(feedback_service)
    print("피드백 이벤트 리스너 등록 완료")

    yield


app = FastAPI(
    title="Interview AI Server",
    description="AI Interview Simulator - AI Features",
    version="0.1.0",
    lifespan=lifespan,
)


# ── 헬스체크 ─────────────────────────────────────────────────────
@app.get("/health")
def health_check():
    return {"status": "ok", "message": "AI server is running"}


# ── 전역 예외 핸들러 ─────────────────────────────────────────────
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = [
        {"field": " -> ".join(str(loc) for loc in e["loc"]), "message": e["msg"]}
        for e in exc.errors()
    ]
    logger.warning(
        "422 validation error url=%s errors=%s",
        request.url.path, errors,
    )
    return JSONResponse(
        status_code=422,
        content=ApiResponse(
            success=False,
            code="CMMN-V001",
            message="입력값 유효성 검사에 실패했습니다.",
            data=errors,
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content=ApiResponse(
            success=False,
            code="CMMN-I001",
            message="서버 내부 오류가 발생했습니다.",
            data=None,
        ).model_dump(),
    )


# ── 라우터 등록 ──────────────────────────────────────────────────
app.include_router(feedback_router)
app.include_router(question_router)
app.include_router(report_router)
app.include_router(media_router)

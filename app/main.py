import asyncio
import logging
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.config import settings
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

INTERNAL_PATH_PREFIX = "/internal/"
INTERNAL_API_KEY_HEADER = "X-Internal-API-Key"

@asynccontextmanager
async def lifespan(app: FastAPI):
    feedback_service = get_feedback_service()
    register_feedback_listeners(feedback_service)
    logger.info("feedback_event_listeners_registered")

    yield  # 서버 실행 중

    # graceful shutdown — 진행 중인 BackgroundTasks 완료 대기.
    # BackgroundTasks는 인메모리이므로 프로세스가 즉시 종료되면 콜백이 유실된다.
    pending_tasks = [
        t for t in asyncio.all_tasks()
        if not t.done() and t is not asyncio.current_task()
    ]
    if pending_tasks:
        logger.info(
            "graceful_shutdown_wait pending_tasks=%d timeout=30s",
            len(pending_tasks),
        )
        done, still_pending = await asyncio.wait(pending_tasks, timeout=30)
        if still_pending:
            logger.warning(
                "graceful_shutdown_timeout tasks_not_completed=%d",
                len(still_pending),
            )


app = FastAPI(
    title="Interview AI Server",
    description="AI Interview Simulator - AI Features",
    version="0.1.0",
    lifespan=lifespan,
)

# ── 내부 API 인증 미들웨어 ────────────────────────────────────────
@app.middleware("http")
async def internal_api_key_middleware(request: Request, call_next):
    if request.url.path.startswith(INTERNAL_PATH_PREFIX):
        key = request.headers.get(INTERNAL_API_KEY_HEADER)
        if key != settings.INTERNAL_API_KEY:
            logger.warning(
                "internal_api_key_rejected path=%s",
                request.url.path,
            )
            return JSONResponse(
                status_code=401,
                content=ApiResponse(
                    success=False,
                    code="CMMN-U001",
                    message="유효하지 않은 내부 API 키입니다.",
                    data=None,
                ).model_dump(),
            )
    return await call_next(request)

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
        "validation_error url=%s errors=%s",
        request.url.path,
        errors,
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
    # BackgroundTasks 내부 예외는 이 핸들러에 도달하지 않는다.
    # 라우터 레벨에서 발생한 예상치 못한 예외만 여기서 처리된다.
    logger.error(
        "unhandled_exception url=%s error=%s",
        request.url.path,
        str(exc),
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content=ApiResponse(
            success=False,
            code="CMMN-I001",
            message="서버 내부 오류가 발생했습니다.",
            data=None,
        ).model_dump(),
    )


# -- 라우터 등록 --------------------------------------------------------------
app.include_router(question_router)
app.include_router(feedback_router)
app.include_router(report_router)
app.include_router(media_router)
import asyncio
import json
import logging

from app.core.config import settings
from app.report.application.port.callback_port import CallbackPort
from app.report.application.port.report_generator_port import ReportGeneratorPort
from app.report.domain.report_model import ReportResult
from app.report.schema.request import FeedbackStatus, ReportGenerateRequest
from app.report.schema.response import ReportCallbackPayload

logger = logging.getLogger(__name__)


class ReportService:

    def __init__(
        self,
        adapter: ReportGeneratorPort,
        callback_port: CallbackPort,
    ):
        self.adapter = adapter
        self.callback_port = callback_port

    def execute(self, request: ReportGenerateRequest) -> ReportResult:
        # SUCCEED 항목만 필터링
        completed = [f for f in request.feedbacks if f.status == FeedbackStatus.SUCCEED]
        success_count = len(completed)

        # 성공 개수 검증 — 2개 이하면 리포트 생성 불가
        if success_count <= 2:
            raise ValueError(
                f"리포트 생성 불가: 성공한 피드백이 {success_count}개입니다."
            )

        return self.adapter.generate(
            feedbacks=completed,
            intv_id=request.intv_id,
        )

    async def execute_and_callback(self, request: ReportGenerateRequest) -> None:
        """
        리포트 생성 후 Spring 서버에 콜백 전송.

        콜백 URL 우선순위:
          1순위 - request.callback (Spring이 동적으로 전달)
          2순위 - settings.REPORT_SPRING_WEBHOOK_URL (환경변수 fallback)

        실패 보장:
          리포트 생성 실패 시에도 FAILED 페이로드로 콜백이 반드시 전송됩니다.
          콜백 전송 자체가 실패해도 예외가 상위로 전파되지 않도록 처리합니다.
          BackgroundTasks 내부에서 예외가 올라오면 무음 처리되므로
          모든 예외는 이 메서드 안에서 캐치해야 합니다.
        """

        # 콜백 URL 결정 — 빈 문자열도 falsy이므로 or 조건이 올바르게 동작
        callback_url = request.callback or settings.REPORT_SPRING_WEBHOOK_URL

        # URL이 없으면 콜백 전송 자체가 불가능 — 조기 종료 후 로그 기록
        if not callback_url:
            logger.critical(
                "callback_url_missing intv_id=%s — 콜백 URL 미설정으로 전송 불가",
                request.intv_id,
            )
            return

        # 기본 페이로드를 FAILED로 초기화
        # 이후 로직에서 예외 발생 시에도 이 값이 콜백으로 전송됩니다
        payload_obj = ReportCallbackPayload.failed(
            intv_id=request.intv_id,
            user_id=request.user_id,
            error_message="알 수 없는 시스템 에러가 발생했습니다.",
        )

        try:
            # execute()는 동기 함수이므로 이벤트 루프 블로킹 방지를 위해
            # 별도 스레드에서 실행합니다.
            # report feature는 순수 계산이라 처리 시간이 짧지만,
            # 동시 요청이 많을 경우 이벤트 루프 점유를 방지하는 안전장치입니다.
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self.execute, request)

            payload_obj = ReportCallbackPayload.from_result(
                intv_id=request.intv_id,
                user_id=request.user_id,
                result=result,
            )

            logger.info(
                "report_generate_success intv_id=%s answered_count=%s",
                request.intv_id,
                result.answered_count,
            )

            # 개발 환경 디버깅용 — 운영 배포 전 제거 권장
            final_json = payload_obj.model_dump(mode="json", by_alias=True)
            logger.debug(
                "report_payload intv_id=%s payload=%s",
                request.intv_id,
                json.dumps(final_json, ensure_ascii=False),
            )

        except Exception as e:
            # 리포트 생성 실패 — FAILED 페이로드로 교체
            # str(e)를 그대로 Spring에 전달하면 내부 스택 정보가 노출될 수 있으므로
            # ValueError(비즈니스 예외)와 그 외를 구분하여 메시지를 제어합니다
            if isinstance(e, ValueError):
                # 성공 피드백 부족 등 예측 가능한 비즈니스 예외는 메시지 그대로 전달
                error_message = str(e)
            else:
                # 예측 불가능한 시스템 예외는 내부 메시지를 외부에 노출하지 않음
                error_message = "리포트 생성 중 내부 오류가 발생했습니다."

            logger.error(
                "report_generate_failed intv_id=%s error=%s",
                request.intv_id,
                str(e),  # 로그에는 실제 오류를 기록
                exc_info=True,
            )

            payload_obj = ReportCallbackPayload.failed(
                intv_id=request.intv_id,
                user_id=request.user_id,
                error_message=error_message,
            )

        # try/except 밖 — 성공/실패 모두 콜백이 반드시 실행됩니다
        try:
            logger.info(
                "callback_send_start intv_id=%s url=%s",
                request.intv_id,
                callback_url,
            )
            await self.callback_port.send(
                url=callback_url,
                payload=payload_obj,
            )
        except Exception as e:
            # WebhookSender 내부에서 tenacity 재시도 후에도 실패한 경우
            # DLQ 로그는 WebhookSender에서 이미 기록되었으므로
            # 여기서는 critical 레벨로 추가 기록만 합니다
            logger.critical(
                "callback_send_failed intv_id=%s url=%s error=%s",
                request.intv_id,
                callback_url,
                str(e),
                exc_info=True,
            )
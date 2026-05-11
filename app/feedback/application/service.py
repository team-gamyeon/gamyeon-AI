import logging

from pydantic import ValidationError

from app.core.config import settings
from app.feedback.application.port.callback_port import FeedbackCallbackPort
from app.feedback.application.port.feedback_port import FeedbackPort
from app.feedback.domain.feedback_model import QuestionFeedback
from app.feedback.schema.request import FeedbackEventRequest, FeedbackRequest
from app.feedback.schema.response import FeedbackResponse

logger = logging.getLogger(__name__)


class FeedbackService:

    def __init__(
        self, feedback_port: FeedbackPort, callback: FeedbackCallbackPort
    ) -> None:
        self._port = feedback_port
        self._callback = callback

    async def media_completed(self, payload: dict) -> None:
        """이벤트 버스(blinker)로부터 dict 데이터를 받아 처리 시작"""
        try:
            event_request = FeedbackEventRequest.model_validate(payload)
            logger.info(
                "media_completed 이벤트 수신 interview_id=%s question_id=%s",
                event_request.intv_id,
                event_request.question_id,
            )
            await self.run(event_request)

        except ValidationError as e:
            # Pydantic 파싱 실패 → Spring에 FAILED 전달 (IN_PROGRESS 영구 대기 방지)
            intv_id = payload.get("intvId", 0)
            question_id = payload.get("questionId", 0)
            logger.error(
                "이벤트 페이로드 파싱 실패 interview_id=%s question_id=%s error=%s",
                intv_id, question_id, e,
            )
            await self._notify_parse_failure(intv_id, question_id)

        except Exception as e:
            logger.error("media_completed 처리 중 예외 발생 error=%s", e)

    async def run(self, event: FeedbackEventRequest) -> None:
        try:
            request = self._to_request(event)
            result: QuestionFeedback = await self._port.generate_feedback(request)
            payload = self._to_response(event, result)
        except Exception as e:
            logger.error(
                "피드백 생성 중 예외 발생 interview_id=%s question_id=%s error=%s",
                event.intv_id, event.question_id, e,
            )
            payload = self._build_error_response(event, str(e))

        await self._callback.send(
            url=settings.FEEDBACK_SPRING_WEBHOOK_URL,
            payload=payload,
        )

    # ── FeedbackEventRequest → FeedbackRequest ───────────────────
    @staticmethod
    def _to_request(event: FeedbackEventRequest) -> FeedbackRequest:
        return FeedbackRequest(
            intv_question_id=event.question_id,
            question_content=event.question_content,
            corrected_transcript=event.transcript.corrected_transcript,
            degraded=event.degraded,
            reliability_score=event.reliability.score,
            gaze_score=event.gaze.gaze_score,
            time_score=event.time.time_score,
            answer_duration_ms=event.time.answer_duration_ms,
            keyword_candidates=event.keywords.candidates,
        )

    # ── QuestionFeedback → FeedbackResponse ─────────────────────
    @staticmethod
    def _to_response(
        event: FeedbackEventRequest, domain: QuestionFeedback
    ) -> FeedbackResponse:
        return FeedbackResponse(
            intv_id=event.intv_id,
            intv_question_id=domain.intv_question_id,
            status=(
                domain.status.value
                if hasattr(domain.status, "value")
                else str(domain.status)
            ),
            # ✅ or 0 → is not None 패턴으로 교체 (0이 유효한 점수값이므로)
            logic_score=domain.logic_score if domain.logic_score is not None else 0,
            answer_composition_score=(
                domain.answer_composition_score
                if domain.answer_composition_score is not None
                else 0
            ),
            characteristic=domain.characteristic or "평가 내용 없음",
            answer_summary=domain.answer_summary or "요약 없음",
            strength=domain.strength or "내용 없음",
            improvement=domain.improvement or "내용 없음",
            # ✅ 뱃지 최대 2개 후처리 (LLM이 초과 반환 시 방어)
            feedback_badges=(domain.feedback_badges[:2] if domain.feedback_badges else ["평가 완료"]),
            gaze_score=domain.gaze_score,
            time_score=domain.time_score,
            answer_duration_ms=domain.answer_duration_ms,
            keyword_count=domain.keyword_count,
            reliability=domain.reliability_score,
        )

    # ── 파싱 실패 시 Spring 알림 ─────────────────────────────────
    async def _notify_parse_failure(self, intv_id: int, question_id: int) -> None:
        """Pydantic 파싱 실패 시 Spring이 IN_PROGRESS로 대기하지 않도록 FAILED 전송"""
        payload = FeedbackResponse(
            intv_id=intv_id,
            intv_question_id=question_id,
            status="FAILED",
            logic_score=0,
            answer_composition_score=0,
            reliability=0,
            characteristic="입력 데이터 오류로 평가할 수 없습니다.",
            answer_summary=None,
            strength=None,
            improvement=None,
            feedback_badges=["평가 실패"],
            gaze_score=0,
            time_score=0,
            answer_duration_ms=0,
            keyword_count=0,
        )
        try:
            await self._callback.send(
                url=settings.FEEDBACK_SPRING_WEBHOOK_URL,
                payload=payload,
            )
        except Exception as e:
            logger.error("파싱 실패 알림 Webhook 전송 실패 error=%s", e)

    # ── run() 예외 시 에러 응답 생성 ─────────────────────────────
    @staticmethod
    def _build_error_response(event: FeedbackEventRequest, error_msg: str) -> FeedbackResponse:
        return FeedbackResponse(
            intv_id=event.intv_id,
            intv_question_id=event.question_id,
            status="FAILED",
            logic_score=0,
            answer_composition_score=0,
            reliability=0,
            characteristic="일시적 오류로 평가를 생성하지 못했습니다.",
            answer_summary=None,
            strength=None,
            improvement=None,
            feedback_badges=["평가 실패"],
            gaze_score=event.gaze.gaze_score,
            time_score=event.time.time_score,
            answer_duration_ms=event.time.answer_duration_ms,
            keyword_count=len(event.keywords.candidates),
        )
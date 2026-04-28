import pytest
from unittest.mock import AsyncMock, MagicMock

from app.report.application.service import ReportService
from app.report.application.port.callback_port import CallbackPort
from app.report.infrastructure.static_score_adapter import StaticScoreAdapter
from app.report.schema.request import FeedbackItem, FeedbackStatus, ReportGenerateRequest


# CallbackPort Mock — 단위 테스트에서 실제 HTTP 전송 없이 주입
class MockCallbackPort(CallbackPort):
    async def send(self, url: str, payload) -> None:
        pass


service = ReportService(
    adapter=StaticScoreAdapter(),
    callback_port=MockCallbackPort(),
)


# ── 요청 객체 생성 헬퍼 ────────────────────────────────────────


def make_request(feedbacks: list[FeedbackItem]) -> ReportGenerateRequest:
    return ReportGenerateRequest(
        intv_id=5,
        user_id=3,
        callback="http://localhost:9000/callback",
        feedbacks=feedbacks,
    )


def make_feedback(question_set_id: int, status=FeedbackStatus.SUCCEED, **kwargs) -> FeedbackItem:
    defaults = {
        "question_set_id": question_set_id,
        "index": 1,
        "question_content": "질문 내용입니다.",
        "status": status,
        "reliability": 90,
        "logic_score": 80,
        "answer_composition_score": 75,
        "answer_summary": "요약 내용",
        "characteristic": "특징",
        "strength": "강점",
        "improvement": "개선점",
        "feedback_badges": ["badge1"],
        "gaze_score": 80,
        "time_score": 90,
        "keyword_count": 2,
        "answer_duration_ms": 52000,
    }
    defaults.update(kwargs)
    return FeedbackItem(**defaults)


# ── 성공 개수 검증 ─────────────────────────────────────────────


class TestSuccessCountValidation:
    def test_raises_when_success_count_is_2(self):
        feedbacks = [make_feedback(i) for i in range(1, 3)]
        with pytest.raises(ValueError, match="리포트 생성 불가"):
            service.execute(make_request(feedbacks))

    def test_raises_when_all_failed(self):
        feedbacks = [make_feedback(i, status=FeedbackStatus.FAILED) for i in range(1, 5)]
        with pytest.raises(ValueError):
            service.execute(make_request(feedbacks))

    def test_passes_when_success_count_is_3(self):
        feedbacks = [make_feedback(i) for i in range(1, 4)]
        result = service.execute(make_request(feedbacks))
        assert result.answered_count == 3


# ── FAILED 항목 제외 검증 ──────────────────────────────────────


class TestFailedExclusion:
    def test_failed_items_excluded_from_score(self):
        feedbacks = [
            make_feedback(101, logic_score=100, answer_composition_score=100),
            make_feedback(102, logic_score=100, answer_composition_score=100),
            make_feedback(103, logic_score=100, answer_composition_score=100),
            make_feedback(104, status=FeedbackStatus.FAILED, logic_score=0, answer_composition_score=0),
        ]
        result = service.execute(make_request(feedbacks))
        assert result.competency_scores.logic == 100
        assert result.answered_count == 3

    def test_failed_items_excluded_from_question_summaries(self):
        feedbacks = [
            make_feedback(101),
            make_feedback(102),
            make_feedback(103),
            make_feedback(104, status=FeedbackStatus.FAILED),
        ]
        result = service.execute(make_request(feedbacks))
        # QuestionSummary.intv_question_id 기준으로 FAILED 항목 제외 확인
        ids = [q.intv_question_id for q in result.question_summaries]
        assert 104 not in ids


# ── ReportResult 조립 검증 ─────────────────────────────────────


class TestReportResultAssembly:
    def _make_standard_request(self):
        # 6개 SUCCEED — report_accuracy "높음" 조건 충족
        feedbacks = [make_feedback(i) for i in range(1, 7)]
        return make_request(feedbacks)

    def test_report_accuracy_is_high(self):
        result = service.execute(self._make_standard_request())
        assert result.report_accuracy == "높음"

    def test_total_score_is_average_of_5(self):
        result = service.execute(self._make_standard_request())
        cs = result.competency_scores
        expected = round(
            (cs.logic + cs.answer_composition + cs.gaze + cs.time_management + cs.keyword) / 5
        )
        assert result.total_score == expected


# ── execute_and_callback 검증 ──────────────────────────────────


class TestExecuteAndCallback:
    """
    execute_and_callback은 async 메서드이므로 pytest-asyncio가 필요합니다.
    pyproject.toml 또는 pytest.ini에 asyncio_mode = "auto" 설정을 권장합니다.
    """

    @pytest.mark.asyncio
    async def test_callback_sent_on_success(self):
        # send 호출 여부와 전달된 payload의 status를 검증
        mock_port = AsyncMock(spec=CallbackPort)
        svc = ReportService(adapter=StaticScoreAdapter(), callback_port=mock_port)

        feedbacks = [make_feedback(i) for i in range(1, 4)]
        request = make_request(feedbacks)
        await svc.execute_and_callback(request)

        mock_port.send.assert_called_once()
        _, kwargs = mock_port.send.call_args
        assert kwargs["payload"].status == "SUCCEED"

    @pytest.mark.asyncio
    async def test_callback_sent_on_failure(self):
        # 성공 피드백 2개 — ValueError 발생 후에도 FAILED 콜백이 전송되어야 함
        mock_port = AsyncMock(spec=CallbackPort)
        svc = ReportService(adapter=StaticScoreAdapter(), callback_port=mock_port)

        feedbacks = [make_feedback(i) for i in range(1, 3)]
        request = make_request(feedbacks)
        await svc.execute_and_callback(request)

        mock_port.send.assert_called_once()
        _, kwargs = mock_port.send.call_args
        assert kwargs["payload"].status == "FAILED"

    @pytest.mark.asyncio
    async def test_callback_not_sent_when_url_missing(self):
        # callback URL이 없으면 send가 호출되지 않아야 함
        mock_port = AsyncMock(spec=CallbackPort)
        svc = ReportService(adapter=StaticScoreAdapter(), callback_port=mock_port)

        request = ReportGenerateRequest(
            intv_id=5,
            user_id=3,
            callback=None,
            feedbacks=[make_feedback(i) for i in range(1, 4)],
        )

        # settings.REPORT_SPRING_WEBHOOK_URL도 None인 환경을 가정
        # 실제 환경에서는 monkeypatch로 settings를 오버라이드하세요
        await svc.execute_and_callback(request)
        mock_port.send.assert_not_called()
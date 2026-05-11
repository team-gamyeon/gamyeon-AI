import pytest

from app.feedback.application.service import FeedbackService
from app.feedback.domain.feedback_model import FeedbackStatus, QuestionFeedback
from app.feedback.schema.request import FeedbackEventRequest, TranscriptInfo


def make_event(**kwargs) -> FeedbackEventRequest:
    defaults = {
        "intv_id": 1,
        "question_id": 10,
        "question_content": "질문 내용입니다.",
        "status": "DONE",
        "degraded": False,
        "transcript": TranscriptInfo(corrected_transcript="충분한 답변 내용입니다."),
    }
    defaults.update(kwargs)
    return FeedbackEventRequest(**defaults)


def make_domain(**kwargs) -> QuestionFeedback:
    defaults = {
        "intv_question_id": 10,
        "status": FeedbackStatus.SUCCEED,
        "logic_score": 80,
        "answer_composition_score": 75,
        "characteristic": "답변 특징",
        "answer_summary": "요약 내용",
        "strength": "강점",
        "improvement": "개선점",
        "feedback_badges": ["badge1", "badge2"],
        "gaze_score": 80,
        "time_score": 90,
        "answer_duration_ms": 52000,
        "keyword_count": 2,
        "reliability_score": 90,
    }
    defaults.update(kwargs)
    return QuestionFeedback(**defaults)


# ── 점수 None → 0 변환 정책 ────────────────────────────────────────


class TestToResponseScoreNullHandling:

    def test_logic_score_none_becomes_zero(self):
        response = FeedbackService._to_response(make_event(), make_domain(logic_score=None))
        assert response.logic_score == 0

    def test_logic_score_zero_preserved(self):
        # 0은 유효한 점수값 — None이 아니므로 그대로 유지 (or 0 패턴과의 차이)
        response = FeedbackService._to_response(make_event(), make_domain(logic_score=0))
        assert response.logic_score == 0

    def test_answer_composition_score_none_becomes_zero(self):
        response = FeedbackService._to_response(
            make_event(), make_domain(answer_composition_score=None)
        )
        assert response.answer_composition_score == 0

    def test_answer_composition_score_zero_preserved(self):
        response = FeedbackService._to_response(
            make_event(), make_domain(answer_composition_score=0)
        )
        assert response.answer_composition_score == 0


# ── 빈 텍스트 fallback 정책 ──────────────────────────────────────


class TestToResponseFallbackText:

    def test_characteristic_none_uses_fallback(self):
        response = FeedbackService._to_response(make_event(), make_domain(characteristic=None))
        assert response.characteristic == "평가 내용 없음"

    def test_characteristic_empty_string_uses_fallback(self):
        response = FeedbackService._to_response(make_event(), make_domain(characteristic=""))
        assert response.characteristic == "평가 내용 없음"

    def test_answer_summary_none_uses_fallback(self):
        response = FeedbackService._to_response(make_event(), make_domain(answer_summary=None))
        assert response.answer_summary == "요약 없음"

    def test_answer_summary_empty_string_uses_fallback(self):
        response = FeedbackService._to_response(make_event(), make_domain(answer_summary=""))
        assert response.answer_summary == "요약 없음"

    def test_strength_none_uses_fallback(self):
        response = FeedbackService._to_response(make_event(), make_domain(strength=None))
        assert response.strength == "내용 없음"

    def test_improvement_none_uses_fallback(self):
        response = FeedbackService._to_response(make_event(), make_domain(improvement=None))
        assert response.improvement == "내용 없음"


# ── feedback_badges 슬라이싱 정책 ────────────────────────────────


class TestToResponseBadges:

    def test_badges_over_two_sliced_to_two(self):
        # LLM이 3개 이상 반환해도 앞 2개만 사용
        response = FeedbackService._to_response(
            make_event(), make_domain(feedback_badges=["a", "b", "c"])
        )
        assert response.feedback_badges == ["a", "b"]

    def test_badges_four_sliced_to_two(self):
        response = FeedbackService._to_response(
            make_event(), make_domain(feedback_badges=["a", "b", "c", "d"])
        )
        assert response.feedback_badges == ["a", "b"]

    def test_badges_exactly_two_not_changed(self):
        response = FeedbackService._to_response(
            make_event(), make_domain(feedback_badges=["a", "b"])
        )
        assert response.feedback_badges == ["a", "b"]

    def test_badges_one_kept(self):
        response = FeedbackService._to_response(
            make_event(), make_domain(feedback_badges=["a"])
        )
        assert response.feedback_badges == ["a"]

    def test_badges_empty_uses_default(self):
        response = FeedbackService._to_response(
            make_event(), make_domain(feedback_badges=[])
        )
        assert response.feedback_badges == ["평가 완료"]

import pytest
from app.report.infrastructure.static_score_adapter import StaticScoreAdapter
from app.report.schema.request import FeedbackItem, FeedbackStatus

adapter = StaticScoreAdapter()


def make_feedback(**kwargs) -> FeedbackItem:
    defaults = {
        # 현재 FeedbackItem 필드명 기준으로 수정
        "question_set_id": 101,
        "index": 1,
        "question_content": "본인의 강점을 말해주세요",
        "status": FeedbackStatus.SUCCEED,
        "reliability": 90,
        "logic_score": 80,
        "answer_composition_score": 75,
        "answer_summary": "summary",
        "characteristic": "characteristic",
        "strength": "strength",
        "improvement": "improvement",
        "feedback_badges": ["badge1"],
        "gaze_score": 80,
        "time_score": 90,
        "keyword_count": 2,
        "answer_duration_ms": 52000,
    }
    defaults.update(kwargs)
    return FeedbackItem(**defaults)


# ── calc_time_management ───────────────────────────────────
# time_management는 answer_duration_ms 구간 변환이 아니라
# time_score 평균으로 산정합니다. (정책 문서 5번 항목 참고)


class TestCalcTimeManagement:

    def test_single_feedback(self):
        feedbacks = [make_feedback(time_score=90)]
        assert adapter.calc_time_management(feedbacks) == 90

    def test_average_of_multiple(self):
        feedbacks = [
            make_feedback(time_score=80),
            make_feedback(time_score=90),
            make_feedback(time_score=100),
        ]
        assert adapter.calc_time_management(feedbacks) == 90

    def test_rounds_correctly(self):
        # (70 + 71) / 2 = 70.5 → round() 결과 검증
        feedbacks = [
            make_feedback(time_score=70),
            make_feedback(time_score=71),
        ]
        assert adapter.calc_time_management(feedbacks) == round(70.5)

    def test_includes_zero_in_average(self):
        # time_score=0도 단순 평균에 포함 — 제외 로직 없음
        feedbacks = [
            make_feedback(time_score=80),
            make_feedback(time_score=90),
            make_feedback(time_score=0),
        ]
        # (80 + 90 + 0) / 3 = 56.67 → 57
        assert adapter.calc_time_management(feedbacks) == 57

    def test_all_zero_returns_zero(self):
        # 모든 time_score가 0이면 평균도 0
        feedbacks = [make_feedback(time_score=0)] * 3
        assert adapter.calc_time_management(feedbacks) == 0


# ── calc_keyword ───────────────────────────────────────────


class TestCalcKeyword:

    def test_zero(self):
        feedbacks = [make_feedback(keyword_count=0)] * 3
        assert adapter.calc_keyword(feedbacks) == 10

    def test_one(self):
        # 평균 1 → < 2 구간 → 50점
        feedbacks = [make_feedback(keyword_count=1)] * 3
        assert adapter.calc_keyword(feedbacks) == 50

    def test_two(self):
        # 평균 2 → < 4 구간 → 70점
        feedbacks = [make_feedback(keyword_count=2)] * 3
        assert adapter.calc_keyword(feedbacks) == 70

    def test_three(self):
        # 평균 3 → < 4 구간 → 70점
        feedbacks = [make_feedback(keyword_count=3)] * 3
        assert adapter.calc_keyword(feedbacks) == 70

    def test_four_to_five_range(self):
        # 평균 4 → < 6 구간 → 85점
        feedbacks = [make_feedback(keyword_count=4)] * 3
        assert adapter.calc_keyword(feedbacks) == 85

    def test_six_or_more(self):
        # 평균 6 이상 → 최상위 구간 → 95점
        feedbacks = [make_feedback(keyword_count=6)] * 3
        assert adapter.calc_keyword(feedbacks) == 95

    def test_mixed_average_boundary(self):
        # 평균이 정확히 2.0인 경우 → < 4 구간 → 70점
        feedbacks = [
            make_feedback(keyword_count=1),
            make_feedback(keyword_count=3),
        ]
        # 평균 = 2.0 → < 4 구간 → 70점
        assert adapter.calc_keyword(feedbacks) == 70


# ── calc_accuracy ──────────────────────────────────────────


class TestCalcAccuracy:

    def test_high(self):
        assert adapter.calc_accuracy(6, 70.0) == "높음"

    def test_medium(self):
        assert adapter.calc_accuracy(5, 70.0) == "중간"

    def test_low_4(self):
        assert adapter.calc_accuracy(4, 70.0) == "낮음"

    def test_low_3(self):
        assert adapter.calc_accuracy(3, 70.0) == "낮음"

    def test_downgrade_high_to_medium(self):
        # avg_score <= 40이면 1단계 결과를 한 단계 하향
        assert adapter.calc_accuracy(6, 40.0) == "중간"

    def test_downgrade_medium_to_low(self):
        assert adapter.calc_accuracy(5, 40.0) == "낮음"

    def test_downgrade_low_stays_low(self):
        # 낮음은 더 이상 하향되지 않음
        assert adapter.calc_accuracy(4, 40.0) == "낮음"

    def test_boundary_avg_score_41_no_downgrade(self):
        # 41.0은 보정 기준(40 이하)에 해당하지 않으므로 하향 없음
        assert adapter.calc_accuracy(6, 41.0) == "높음"

    def test_boundary_avg_score_40_triggers_downgrade(self):
        # 정확히 40.0은 보정 대상
        assert adapter.calc_accuracy(6, 40.0) == "중간"


# ── extract_strengths / weaknesses ────────────────────────


class TestExtractStrengthsWeaknesses:

    def _make_feedbacks(self):
        # logic_score + answer_composition_score 평균 기준으로 정렬됨
        # 점수: 90, 70, 50, 30, 10 순서로 내림차순
        return [
            make_feedback(
                question_set_id=i,
                index=i,
                logic_score=s,
                answer_composition_score=s,
                strength=f"strength_{i}",
                improvement=f"improvement_{i}",
            )
            for i, s in enumerate([90, 70, 50, 30, 10], start=1)
        ]

    def test_strengths_top3_by_score(self):
        # 점수 높은 순 상위 3개의 strength
        result = adapter.extract_strengths(self._make_feedbacks())
        assert result == ["strength_1", "strength_2", "strength_3"]

    def test_weaknesses_bottom3_by_score(self):
        # 점수 낮은 순 하위 3개의 improvement
        result = adapter.extract_weaknesses(self._make_feedbacks())
        assert result == ["improvement_5", "improvement_4", "improvement_3"]

    def test_strengths_count_is_exactly_3(self):
        result = adapter.extract_strengths(self._make_feedbacks())
        assert len(result) == 3

    def test_weaknesses_count_is_exactly_3(self):
        result = adapter.extract_weaknesses(self._make_feedbacks())
        assert len(result) == 3
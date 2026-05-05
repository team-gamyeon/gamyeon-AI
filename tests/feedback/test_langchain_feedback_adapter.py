import asyncio

import pytest
from unittest.mock import MagicMock, patch

from app.feedback.infrastructure.langchain_feedback_adapter import LangchainFeedbackAdapter
from app.feedback.schema.request import FeedbackRequest


@pytest.fixture
def adapter():
    # LangChain 체인 구성을 모킹하여 LLM 호출 없이 인스턴스 생성
    with (
        patch("app.feedback.infrastructure.langchain_feedback_adapter.ChatPromptTemplate"),
        patch("app.feedback.infrastructure.langchain_feedback_adapter.PydanticOutputParser"),
    ):
        return LangchainFeedbackAdapter(
            llm=MagicMock(),
            prompt_provider=MagicMock(),
            semaphore=asyncio.Semaphore(3),
        )


def make_request(**kwargs) -> FeedbackRequest:
    defaults = {
        "intv_question_id": 1,
        "question_content": "질문 내용",
        "corrected_transcript": "충분한 길이의 답변 내용입니다.",
        "reliability_score": 90,
    }
    defaults.update(kwargs)
    return FeedbackRequest(**defaults)


# ── transcript 길이 경계값 (MIN = 10) ────────────────────────────


class TestShouldSkipTranscript:

    def test_9_chars_skips(self, adapter):
        request = make_request(corrected_transcript="123456789")  # 9자
        assert adapter._should_skip(request) is True

    def test_10_chars_not_skipped(self, adapter):
        # 10자는 조건(< 10) 미충족 → 차단되지 않음
        request = make_request(corrected_transcript="1234567890")  # 10자
        assert adapter._should_skip(request) is False

    def test_11_chars_not_skipped(self, adapter):
        request = make_request(corrected_transcript="12345678901")  # 11자
        assert adapter._should_skip(request) is False

    def test_empty_string_skips(self, adapter):
        request = make_request(corrected_transcript="")
        assert adapter._should_skip(request) is True

    def test_whitespace_only_skips(self, adapter):
        # strip() 후 0자 → 차단
        request = make_request(corrected_transcript="          ")
        assert adapter._should_skip(request) is True

    def test_whitespace_padded_10_chars_not_skipped(self, adapter):
        # 앞뒤 공백 제거 후 10자 이상이면 차단 안 됨
        request = make_request(corrected_transcript="  1234567890  ")
        assert adapter._should_skip(request) is False


# ── reliability_score 경계값 (MIN = 40) ──────────────────────────


class TestShouldSkipReliability:

    def test_39_skips(self, adapter):
        request = make_request(reliability_score=39)
        assert adapter._should_skip(request) is True

    def test_40_not_skipped(self, adapter):
        # 40은 조건(< 40) 미충족 → 차단되지 않음
        request = make_request(reliability_score=40)
        assert adapter._should_skip(request) is False

    def test_41_not_skipped(self, adapter):
        request = make_request(reliability_score=41)
        assert adapter._should_skip(request) is False

    def test_zero_skips(self, adapter):
        request = make_request(reliability_score=0)
        assert adapter._should_skip(request) is True


# ── 복합 조건 (OR) ────────────────────────────────────────────────


class TestShouldSkipCombined:

    def test_short_transcript_overrides_high_reliability(self, adapter):
        # transcript < 10자이면 reliability와 무관하게 차단
        request = make_request(corrected_transcript="짧음", reliability_score=100)
        assert adapter._should_skip(request) is True

    def test_sufficient_transcript_low_reliability_skips(self, adapter):
        # reliability < 40이면 transcript와 무관하게 차단
        request = make_request(corrected_transcript="충분한 답변 내용입니다.", reliability_score=39)
        assert adapter._should_skip(request) is True

    def test_both_sufficient_not_skipped(self, adapter):
        # transcript 10자 이상 AND reliability 40 이상 → 차단 안 됨
        request = make_request(corrected_transcript="1234567890", reliability_score=40)
        assert adapter._should_skip(request) is False

import asyncio
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from app.feedback.application.port.feedback_port import FeedbackPort
from app.feedback.domain.feedback_model import FeedbackStatus, QuestionFeedback
from app.feedback.infrastructure.prompt_provider import FeedbackPromptProvider
from app.feedback.schema.request import FeedbackRequest


# ── Structured Output 스키마 ─────────────────────────────────────
class FeedbackOutput(BaseModel):
    logic_score: int = Field(description="논리성 점수 (0~100)")
    answer_composition_score: int = Field(description="답변구성력 점수 (0~100)")
    characteristic: str = Field(description="답변 전반적 특징 (공백 포함 80자 이내)")
    answer_summary: str = Field(description="답변 내용 요약 (1~2문장)")
    strength: str = Field(description="잘한 점 (한 문장, 구체적 근거 포함)")
    improvement: str = Field(description="개선점 (한 문장, 구체적 방향 포함)")
    feedback_badges: list[str] = Field(description="답변 특징 키워드 뱃지 (1~2개)")


# ── Adapter ─────────────────────────────────────────────────────

class LangchainFeedbackAdapter(FeedbackPort):

    MIN_TRANSCRIPT_LENGTH = 10
    MIN_RELIABILITY_SCORE = 40

    def __init__(
        self,
        llm: ChatOpenAI,
        prompt_provider: FeedbackPromptProvider,
        semaphore: asyncio.Semaphore,          # di.py에서 주입
    ) -> None:
        self._semaphore = semaphore
        self._parser = PydanticOutputParser(pydantic_object=FeedbackOutput)
        self._prompt = ChatPromptTemplate.from_messages([
            ("system", prompt_provider.system_prompt),
            ("human", prompt_provider.human_prompt),
        ]).partial(format_instructions=self._parser.get_format_instructions())
        self._chain = self._prompt | llm | self._parser

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_fixed(1),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )

    # ── 외부 진입점 ──────────────────────────────────────────────
    async def generate_feedback(self, request: FeedbackRequest) -> QuestionFeedback:
        media_scores = self._extract_media_scores(request)

        if self._should_skip(request):
            return QuestionFeedback.skipped(request.intv_question_id)

        try:
            output: FeedbackOutput = await self._invoke_with_retry(request)
            return self._to_domain(output, request, media_scores)

        except Exception:
            return QuestionFeedback.failed(
                intv_question_id=request.intv_question_id,
                **media_scores,
            )

    # ── 사전 차단 ────────────────────────────────────────────────
    def _should_skip(self, request: FeedbackRequest) -> bool:
        return (
            # request.degraded or
            len(request.corrected_transcript.strip()) < self.MIN_TRANSCRIPT_LENGTH
            or request.reliability_score < self.MIN_RELIABILITY_SCORE
        )

    # ── LLM 호출 (재시도 1회) ────────────────────────────────────
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_fixed(1),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )

    async def _invoke_with_retry(self, request: FeedbackRequest) -> FeedbackOutput:
        # 세마포어로 동시 호출 수를 제한하여 OpenAI TPM 한도 초과를 방지한다.
        async with self._semaphore:
            return await self._chain.ainvoke({
                "question_content": request.question_content,
                "corrected_transcript": request.corrected_transcript,
            })

    # ── media 수치 추출 ──────────────────────────────────────────
    @staticmethod
    def _extract_media_scores(request: FeedbackRequest) -> dict:
        return {
            "reliability_score": request.reliability_score,
            "gaze_score": request.gaze_score,
            "time_score": request.time_score,
            "answer_duration_ms": request.answer_duration_ms,
            "keyword_count": len(request.keyword_candidates),
        }

    # ── 도메인 변환 ──────────────────────────────────────────────
    @staticmethod
    def _to_domain(
        output: FeedbackOutput,
        request: FeedbackRequest,
        media_scores: dict,
    ) -> QuestionFeedback:
        return QuestionFeedback(
            intv_question_id=request.intv_question_id,
            status=FeedbackStatus.SUCCEED,
            logic_score=output.logic_score,
            answer_composition_score=output.answer_composition_score,
            characteristic=output.characteristic,
            answer_summary=output.answer_summary,
            strength=output.strength,
            improvement=output.improvement,
            feedback_badges=output.feedback_badges,
            **media_scores,
        )

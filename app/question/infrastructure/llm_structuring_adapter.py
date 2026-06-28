from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.question.application.port.structuring_port import StructuringPort
from app.question.domain.interview_input import InterviewInput
from app.question.infrastructure.structuring_prompt_provider import StructuringPromptProvider
from app.question.exception import LLMStructuringError


class LLMStructuringAdapter(StructuringPort):

    def __init__(self, llm: ChatOpenAI, prompt_provider: StructuringPromptProvider) -> None:
        prompt = ChatPromptTemplate.from_messages([
            ("system", prompt_provider.system_prompt),
            ("human", prompt_provider.human_prompt),
        ])
        self._chain = prompt | llm.with_structured_output(InterviewInput)

    async def structure(
        self,
        resume_text: str,
        job_role: str | None = None,
        portfolio_text: str | None = None,
        self_intro_text: str | None = None,
    ) -> InterviewInput:
        try:
            return await self._chain.ainvoke({
                "resume_text":        resume_text,
                "job_role":           job_role or "",
                "portfolio_section":  f"[포트폴리오]\n{portfolio_text}\n\n" if portfolio_text else "",
                "self_intro_section": f"[자기소개서]\n{self_intro_text}\n\n" if self_intro_text else "",
            })
        except Exception as e:
            raise LLMStructuringError(f"이력서 구조화 중 오류가 발생했습니다: {e}") from e
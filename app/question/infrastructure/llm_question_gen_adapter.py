from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.question.application.port.question_gen_port import QuestionGenPort
from app.question.domain.interview_input import InterviewInput
from app.question.infrastructure.question_gen_prompt_provider import QuestionGenPromptProvider
from app.question.exception import LLMGenerationError



class LLMQuestionGenAdapter(QuestionGenPort):

    def __init__(self, llm: ChatOpenAI, prompt_provider: QuestionGenPromptProvider) -> None:
        prompt = ChatPromptTemplate.from_messages([
            ("system", prompt_provider.system_prompt),
            ("human", prompt_provider.human_prompt),
        ])
        self._chain = prompt | llm | StrOutputParser()

    async def generate(self, interview_input: InterviewInput) -> list[str]:
        try:
            result = await self._chain.ainvoke(self._build_variables(interview_input))
            questions = [q.strip() for q in result.split("\n") if q.strip()]
            return questions[:4]
        except Exception as e:
            raise LLMGenerationError(f"질문 생성 중 오류가 발생했습니다: {e}") from e

    @staticmethod
    def _build_variables(i: InterviewInput) -> dict:
        return {
            "job_role":                   i.job_role,
            "core_competencies_section":  f"핵심 역량: {', '.join(i.core_competencies)}\n\n" if i.core_competencies else "",
            "career_summary_section":     f"경력 요약: {i.career_summary}\n\n" if i.career_summary else "",
            "work_experiences_section":   f"주요 경력:\n" + "\n".join(i.work_experiences) + "\n\n" if i.work_experiences else "",
            "projects_section":           f"프로젝트:\n" + "\n".join(i.projects) + "\n\n" if i.projects else "",
            "portfolio_section":          f"포트폴리오 요약: {i.portfolio_summary}\n\n" if i.portfolio_summary else "",
            "self_intro_section":         f"자기소개서 요약: {i.self_introduction_summary}\n\n" if i.self_introduction_summary else "",
        }
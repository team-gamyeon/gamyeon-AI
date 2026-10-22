from pydantic import BaseModel

class InterviewInput(BaseModel):
    name: str                                    # 필수
    job_role: str | None = None                                  # 1차 mvp 없음
    core_competencies: list[str] = []            # 직군 무관 핵심 역량 목록
    career_summary: str | None = None            # 경력 한줄 요약
    work_experiences: list[str] = []             # 주요 경력 목록
    projects: list[str] = []                     # 프로젝트/작업물 요약 목록
    portfolio_summary: str | None = None         # 포트폴리오 요약
    cover_letter_summary: str | None = None # 자기소개서 요약

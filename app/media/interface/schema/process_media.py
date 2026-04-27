from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

class ProcessMediaRequest(BaseModel):
    """
    POST /internal/media/process 요청 스키마

    Spring Boot -> Agent Server 파이프라인 처리 요청.

    복합 유일키 - interview_id + question_id:

    media_path:
    - S3 다운로드 -> 포맷 검증 + ffprobe duration 추출 (answer_duration_ms 대체) -> ffmpeg WAV 추출

    tech_stack[MVP2]:
    - LLM CoT 교정 Few-shot 도메인 분류 힌트
    - Whisper initial_prompt 구성
    - 빈 배열 허용 → 일반 IT 용어 기준 교정 진행

    interview_type:
    - 면접 유형 분류 키
    - "default" | "tech" | "personality" | "executive"
    """
    model_config = ConfigDict(populate_by_name=True)

    interview_id:    int       = Field(..., alias="intvId",        description="면접 세션 ID")
    question_id:     int       = Field(..., alias="questionSetId", description="질문 ID")
    s3_key:          str       = Field(..., alias="mediaFileKey",  description="S3 영상 키 (webm/mp4)")
    question_content: str      = Field(..., alias="questionContent", description="질문 내용")
    tech_stack:      list[str] = Field(default_factory=list)
    interview_type:  str       = Field(default="default")
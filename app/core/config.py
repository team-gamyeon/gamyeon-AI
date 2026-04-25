from pydantic_settings import BaseSettings, SettingsConfigDict


# 기본값을 할당하여, .env 파일이 없어도 일단 에러 없이 객체가 생성
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    S3_BASE_URL: str = "https://s3.ap-northeast-2.amazonaws.com/your-bucket-name"

    # ── AWS / S3 ──────────────────────────────────────────────────
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "ap-northeast-2"
    S3_BUCKET: str = ""  # 영상 저장 버킷 이름

    # ── Whisper STT ───────────────────────────────────────────────
    WHISPER_DEVICE: str = "cpu"  # "cpu" | "cuda"
    WHISPER_COMPUTE_TYPE: str = "int8"  # "int8" | "float16" | "float32"

    # ── OpenAI (LLM 교정) ─────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    GPT_MINI_MODEL: str = "gpt-4o-mini"
    LLM_TIMEOUT_SECONDS: float = 15.0

    # ── 점수 정책 ─────────────────────────────────────────────────
    SCORING_LIMIT_MS: int = 60_000
    SCORING_QUESTION_SUCCESS_RATE_WEIGHT: float = 50.0
    SCORING_SEGMENT_COVERAGE_WEIGHT: float = 30.0
    SCORING_AVG_WORD_CONFIDENCE_WEIGHT: float = 20.0

    # ── Spring Boot 웹훅 ──────────────────────────────────────────
    SPRING_WEBHOOK_URL: str = (
        "http://spring-server:8080/internal/v1/answers/stt/callback"
    )

    FEEDBACK_SPRING_WEBHOOK_URL: str = (
        "http://spring-server:8080/internal/v1/feedbacks/callback"
    )

    REPORT_SPRING_WEBHOOK_URL: str = (
        "http://spring-server:8080/internal/v1/reports/callback"
    )

    QUESTION_SPRING_WEBHOOK_URL: str = (
        "http://spring-server:8080/internal/v1/questions/callback"
    )



settings = Settings()

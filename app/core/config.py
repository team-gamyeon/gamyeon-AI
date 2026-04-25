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

    # ── Claude (LLM 교정) ─────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    GPT_MINI_MODEL: str = "gpt-4o-mini"
    LLM_TIMEOUT_SECONDS: float = 15.0

    # ── Consul (점수 정책) ────────────────────────────────────────
    CONSUL_URL: str = "http://consul:8500"
    CONSUL_TOKEN: str = ""

    # ── Whisper STT ───────────────────────────────────────────────
    WHISPER_DEVICE: str = "cuda"  # "cpu" | "cuda"
    WHISPER_COMPUTE_TYPE: str = "int8"  # "int8" | "float16" | "float32"

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

    # feedback LLM 설정
    FEEDBACK_LLM_MODEL: str = "gpt-4o-mini"
    FEEDBACK_LLM_TIMEOUT_SEC: int = 20
    FEEDBACK_LLM_CONCURRENCY: int = 3
    RELIABILITY_THRESHOLD: int = 50
    FEEDBACK_SPRING_WEBHOOK_URL: str = "http://localhost:8080/dummy"

    OPENAI_API_KEY: str = ""



settings = Settings()

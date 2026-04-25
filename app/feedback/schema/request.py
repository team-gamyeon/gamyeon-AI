from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel


class KeywordCandidate(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    term: str
    count: int
    category: str


class TranscriptInfo(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    raw_transcript: str = ""
    phonetic_transcript: str = ""
    corrected_transcript: str = ""
    corrections: list = []
    word_timestamps: list = []


class KeywordsInfo(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    candidates: list[KeywordCandidate] = []


class GazeInfo(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    gaze_score: int = 0

    @field_validator("gaze_score", mode="before")
    @classmethod
    def normalize_none(cls, v: int | None) -> int:
        return 0 if v is None else v


class TimeInfo(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    time_score: int = 0
    answer_duration_ms: int = 0

    @field_validator("time_score", "answer_duration_ms", mode="before")
    @classmethod
    def normalize_none(cls, v: int | None) -> int:
        return 0 if v is None else v


class ReliabilityInfo(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    score: int = 0

    @field_validator("score", mode="before")
    @classmethod
    def normalize_none(cls, v: int | None) -> int:
        return 0 if v is None else v


class FeedbackEventRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    intv_id: int
    question_id: int
    question_content: str
    status: str
    degraded: bool
    transcript: TranscriptInfo
    keywords: KeywordsInfo = KeywordsInfo()
    gaze: GazeInfo = GazeInfo()
    time: TimeInfo = TimeInfo()
    reliability: ReliabilityInfo = ReliabilityInfo()


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    intv_question_id: int
    question_content: str
    corrected_transcript: str
    degraded: bool = False
    reliability_score: int = Field(default=0, ge=0, le=100)
    gaze_score: int = Field(default=0, ge=0, le=100)
    time_score: int = Field(default=0, ge=0, le=100)
    answer_duration_ms: int = Field(default=0, ge=0)
    keyword_candidates: list[KeywordCandidate] = Field(default_factory=list)
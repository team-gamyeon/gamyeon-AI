from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class FileEntry(BaseModel):
    fileType: Literal["RESUME", "PORTFOLIO", "COVER_LETTER"]
    fileKey: str


class QuestionGenerateRequest(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )
    intvId: int
    files: list[FileEntry]

    def get_file_key(self, file_type: str) -> str | None:
        for f in self.files:
            if f.fileType == file_type:
                return f.fileKey
        return None

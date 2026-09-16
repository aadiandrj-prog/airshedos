import os

from pydantic import BaseModel, Field


class CitizenSettings(BaseModel):
    project: str = ""
    location: str = "global"
    model: str = "gemini-3.1-flash-lite"
    timeout_seconds: float = Field(default=30, ge=1, le=60)

    @classmethod
    def from_env(cls):
        return cls(
            project=os.getenv("GOOGLE_CLOUD_PROJECT", "").strip(),
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "").strip() or "global",
            model=os.getenv("GEMINI_MODEL", "").strip() or "gemini-3.1-flash-lite",
            timeout_seconds=os.getenv("GEMINI_TIMEOUT_SECONDS", "30"),
        )

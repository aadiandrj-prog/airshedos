from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.persistence.contracts import ReportSubmission, StrictModel


class ResidentSubmission(ReportSubmission):
    reported_place: str = Field(min_length=1, max_length=200)

    @field_validator("reported_place")
    @classmethod
    def useful_place(cls, value):
        if not value.strip():
            raise ValueError("Reported place is required")
        return value


class ResidentReceipt(StrictModel):
    report_id: UUID
    receipt_id: UUID
    accepted_at: datetime
    status: Literal["RECEIVED"] = "RECEIVED"
    processing: Literal["PENDING"] = "PENDING"
    replayed: bool = False


class SupplementSubmission(StrictModel):
    body: str = Field(min_length=1, max_length=2000)
    media_id: UUID | None = None

    @field_validator("body")
    @classmethod
    def useful_text(cls, value):
        if not value.strip():
            raise ValueError("Supplementary information is required")
        return value


class SupplementReceipt(StrictModel):
    id: UUID
    report_id: UUID
    request_id: UUID
    accepted_at: datetime
    replayed: bool = False

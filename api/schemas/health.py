from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(description="Current application status.")
    service: str = Field(description="API service identifier.")

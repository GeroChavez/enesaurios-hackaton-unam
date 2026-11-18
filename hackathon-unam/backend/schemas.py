from typing import Optional

from pydantic import BaseModel, Field


class NovaRequest(BaseModel):
    receiver_id: Optional[str] = Field(default=None, max_length=32, pattern=r"^[A-Za-z0-9_.\-]+$")
    question: Optional[str] = Field(default=None, max_length=500)

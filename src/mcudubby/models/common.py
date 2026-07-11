from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    status: str = "ok"
    summary: str
    key_data: dict[str, Any] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)
    suggested_next_steps: list[str] = Field(default_factory=list)

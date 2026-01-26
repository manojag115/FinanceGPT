"""
Schemas for FinanceGPT documentation.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FinanceGPTDocsChunkRead(BaseModel):
    """Schema for a FinanceGPT docs chunk."""

    id: int
    content: str

    model_config = ConfigDict(from_attributes=True)


class FinanceGPTDocsDocumentRead(BaseModel):
    """Schema for a FinanceGPT docs document (without chunks)."""

    id: int
    title: str
    source: str
    content: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class FinanceGPTDocsDocumentWithChunksRead(BaseModel):
    """Schema for a FinanceGPT docs document with its chunks."""

    id: int
    title: str
    source: str
    content: str
    chunks: list[FinanceGPTDocsChunkRead]

    model_config = ConfigDict(from_attributes=True)

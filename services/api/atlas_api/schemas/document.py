"""Schemas relacionados a documentos."""

from datetime import datetime

from pydantic import BaseModel


class DocumentBase(BaseModel):
    title: str
    body: str
    tags: list[str] = []


class DocumentOut(DocumentBase):
    id: str
    version: int
    created_at: datetime
    updated_at: datetime

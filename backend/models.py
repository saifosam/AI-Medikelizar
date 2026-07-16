"""
AI-Medikelizar — Pydantic Models
==================================
Request and response schemas for the API.
"""

from pydantic import BaseModel
from typing import Optional


class QueryRequest(BaseModel):
    """Incoming user query."""
    query: str


class SourceModel(BaseModel):
    """A single source / citation returned with the answer."""
    id: int
    title: str
    authors: str
    journal: str
    date: str
    volume: str = ""
    doi: str = ""
    pmid: str = ""
    url: str = ""
    abstract: str = ""
    publisher: str = ""
    relevance: float = 0.0


class QueryResponse(BaseModel):
    """Full response returned to the frontend."""
    answer: str
    sources: list[SourceModel]
    confidence: str  # "high" | "moderate" | "limited"
    provider: str
    model: str


class HealthResponse(BaseModel):
    """Health-check endpoint response."""
    status: str
    provider: str
    model: str
    version: str = "1.0.0"

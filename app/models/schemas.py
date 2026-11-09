from typing import List, Optional

from pydantic import BaseModel, Field


class RagSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=8, ge=1, le=50)


class RagSearchResult(BaseModel):
    content: str
    page: int
    chapter: Optional[str] = None
    section: Optional[str] = None
    title: Optional[str] = None
    score: float


class RagSearchResponse(BaseModel):
    results: List[RagSearchResult]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    top_k: int = Field(default=8, ge=1, le=50)
    filenames: Optional[List[str]] = None


class ChatSource(BaseModel):
    page: int
    section: Optional[str] = None
    title: Optional[str] = None
    excerpt: Optional[str] = None
    value: Optional[str] = None
    unit: Optional[str] = None
    filename: Optional[str] = None
    book: Optional[str] = None
    code: Optional[str] = None
    book_id: Optional[str] = None


class ChatBook(BaseModel):
    book_id: Optional[str] = None
    filename: Optional[str] = None
    code: Optional[str] = None
    title: Optional[str] = None
    label: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    sources: List[ChatSource]
    books: List[ChatBook] = Field(default_factory=list)
    primary_value: Optional[str] = None
    primary_unit: Optional[str] = None
    headline: Optional[str] = None
    # Routing info (added in rcos-norm-ai): useful in Postman and for the app.
    intent: Optional[str] = None
    input_script: Optional[str] = None
    reply_script: Optional[str] = None
    normalized_message: Optional[str] = None
    answer_cyrillic: Optional[str] = None

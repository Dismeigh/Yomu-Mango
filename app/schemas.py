from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class MangaBase(BaseModel):
    title: str
    alt_title: Optional[str] = None
    description: Optional[str] = None
    status: str = "ongoing"
    content_rating: str = "safe"
    type: str = "manga"
    cover_image_url: Optional[str] = None


class MangaOut(MangaBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class ChapterBase(BaseModel):
    number: float
    title: Optional[str] = None
    language: str = "en"
    volume: Optional[int] = None
    external_url: str
    source_name: Optional[str] = None


class ChapterOut(ChapterBase):
    id: int
    manga_id: int
    published_at: datetime

    class Config:
        orm_mode = True


class MangaWithChapters(MangaOut):
    chapters: List[ChapterOut] = []

from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Boolean,
    ForeignKey,
    Float,
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class Manga(Base):
    __tablename__ = "manga"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, index=True)
    alt_title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String(50), default="ongoing")  # ongoing/completed/hiatus
    content_rating = Column(String(50), default="safe")
    type = Column(String(50), default="manga")  # manga/manhwa/webtoon
    cover_image_url = Column(String(512), nullable=True)  # for YOUR OWN images
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    chapters = relationship("Chapter", back_populates="manga")


class Chapter(Base):
    __tablename__ = "chapter"

    id = Column(Integer, primary_key=True, index=True)
    manga_id = Column(Integer, ForeignKey("manga.id"), index=True, nullable=False)
    number = Column(Float, nullable=False)  # 1, 1.5, etc.
    title = Column(String(255), nullable=True)
    language = Column(String(10), default="en")
    volume = Column(Integer, nullable=True)
    external_url = Column(String(512), nullable=False)  # link to external reader
    source_name = Column(String(100), nullable=True)  # optional display
    published_at = Column(DateTime, default=datetime.utcnow)

    manga = relationship("Manga", back_populates="chapters")


class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    role = Column(String(20), default="user")  # user/admin
    created_at = Column(DateTime, default=datetime.utcnow)

    lists = relationship("CustomList", back_populates="user", cascade="all, delete-orphan")


class UserLibrary(Base):
    __tablename__ = "user_library"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), index=True)
    manga_id = Column(Integer, ForeignKey("manga.id"), index=True)
    status = Column(String(50), default="reading")  # reading/completed/dropped/plan_to_read
    last_read_chapter_id = Column(Integer, ForeignKey("chapter.id"), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CustomList(Base):
    __tablename__ = "custom_list"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), index=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="lists")
    items = relationship(
        "CustomListItem",
        back_populates="custom_list",
        cascade="all, delete-orphan",
    )


class CustomListItem(Base):
    __tablename__ = "custom_list_item"

    id = Column(Integer, primary_key=True, index=True)
    list_id = Column(Integer, ForeignKey("custom_list.id"), index=True, nullable=False)
    manga_id = Column(Integer, ForeignKey("manga.id"), index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    custom_list = relationship("CustomList", back_populates="items")
    manga = relationship("Manga")

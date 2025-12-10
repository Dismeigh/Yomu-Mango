from typing import Optional, List

from fastapi import FastAPI, Depends, Request, HTTPException, Query, Form
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .database import engine
from .models import Base, Manga, Chapter
from .deps import get_db
from . import schemas

# Create tables on startup (simple dev approach)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Manga Index")

# Static files (CSS, your own images, etc.)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Jinja2 templates
templates = Jinja2Templates(directory="templates")


# -----------------------------
# HTML PAGES (PUBLIC)
# -----------------------------

@app.get("/", tags=["pages"])
def home(
    request: Request,
    q: Optional[str] = Query(default=None, description="Search by title"),
    db: Session = Depends(get_db),
):
    query = db.query(Manga)
    if q:
        like = f"%{q}%"
        query = query.filter(Manga.title.ilike(like))
    manga_list: List[Manga] = query.order_by(Manga.title).limit(100).all()

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "manga_list": manga_list,
            "q": q or "",
        },
    )


@app.get("/manga/{manga_id}", tags=["pages"])
def manga_detail(manga_id: int, request: Request, db: Session = Depends(get_db)):
    manga = db.query(Manga).filter(Manga.id == manga_id).first()
    if not manga:
        raise HTTPException(status_code=404, detail="Manga not found")

    chapters = sorted(manga.chapters, key=lambda c: c.number)

    return templates.TemplateResponse(
        "manga_detail.html",
        {
            "request": request,
            "manga": manga,
            "chapters": chapters,
        },
    )


# -----------------------------
# ADMIN PAGES (NO AUTH YET)
# -----------------------------

@app.get("/admin", tags=["admin"])
def admin_home(request: Request, db: Session = Depends(get_db)):
    manga_list = db.query(Manga).order_by(Manga.title).all()
    return templates.TemplateResponse(
        "admin_index.html",
        {
            "request": request,
            "manga_list": manga_list,
        },
    )


# --- Add Manga ---

@app.get("/admin/manga/new", tags=["admin"])
def admin_new_manga_form(request: Request):
    return templates.TemplateResponse(
        "admin_manga_new.html",
        {
            "request": request,
        },
    )


@app.post("/admin/manga/new", tags=["admin"])
def admin_create_manga(
    request: Request,
    title: str = Form(...),
    alt_title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    status: str = Form("ongoing"),
    content_rating: str = Form("safe"),
    type: str = Form("manga"),
    cover_image_url: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    manga = Manga(
        title=title,
        alt_title=alt_title,
        description=description,
        status=status,
        content_rating=content_rating,
        type=type,
        cover_image_url=cover_image_url,
    )
    db.add(manga)
    db.commit()
    db.refresh(manga)

    # Redirect to the new manga detail page
    return RedirectResponse(url=f"/manga/{manga.id}", status_code=303)


# --- Add Chapter ---

@app.get("/admin/chapters/new", tags=["admin"])
def admin_new_chapter_form(request: Request, db: Session = Depends(get_db)):
    manga_list = db.query(Manga).order_by(Manga.title).all()
    return templates.TemplateResponse(
        "admin_chapter_new.html",
        {
            "request": request,
            "manga_list": manga_list,
        },
    )


@app.post("/admin/chapters/new", tags=["admin"])
def admin_create_chapter(
    request: Request,
    manga_id: int = Form(...),
    number: float = Form(...),
    title: Optional[str] = Form(None),
    language: str = Form("en"),
    volume: Optional[int] = Form(None),
    external_url: str = Form(...),
    source_name: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    # Ensure manga exists
    manga = db.query(Manga).filter(Manga.id == manga_id).first()
    if not manga:
        raise HTTPException(status_code=404, detail="Manga not found for chapter")

    chapter = Chapter(
        manga_id=manga_id,
        number=number,
        title=title,
        language=language,
        volume=volume,
        external_url=external_url,
        source_name=source_name,
    )
    db.add(chapter)
    db.commit()
    db.refresh(chapter)

    # Redirect back to the manga detail page
    return RedirectResponse(url=f"/manga/{manga_id}", status_code=303)


# -----------------------------
# JSON API
# -----------------------------

@app.get("/api/manga", response_model=List[schemas.MangaOut], tags=["api"])
def api_list_manga(
    q: Optional[str] = Query(default=None, description="Search by title"),
    db: Session = Depends(get_db),
):
    query = db.query(Manga)
    if q:
        like = f"%{q}%"
        query = query.filter(Manga.title.ilike(like))
    return query.order_by(Manga.title).limit(100).all()


@app.get(
    "/api/manga/{manga_id}",
    response_model=schemas.MangaWithChapters,
    tags=["api"],
)
def api_get_manga(manga_id: int, db: Session = Depends(get_db)):
    manga = db.query(Manga).filter(Manga.id == manga_id).first()
    if not manga:
        raise HTTPException(status_code=404, detail="Manga not found")
    _ = manga.chapters
    return manga


@app.get("/api/chapters/{chapter_id}", response_model=schemas.ChapterOut, tags=["api"])
def api_get_chapter(chapter_id: int, db: Session = Depends(get_db)):
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return chapter


@app.get("/api/chapters/{chapter_id}/read", tags=["api"])
def api_redirect_to_reader(chapter_id: int, db: Session = Depends(get_db)):
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    # Redirect to the external reader URL
    return RedirectResponse(url=chapter.external_url)

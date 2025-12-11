from typing import Optional, List

from fastapi import (
    FastAPI,
    Depends,
    Request,
    HTTPException,
    Query,
    Form,
)
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_

from starlette.middleware.sessions import SessionMiddleware

from .database import engine
from .models import (
    Base,
    Manga,
    Chapter,
    User,
    CustomList,
    CustomListItem,
)
from .deps import get_db
from . import schemas

from passlib.context import CryptContext

# -----------------------------
# Setup
# -----------------------------

# Create tables on startup (dev-friendly)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Manga Index")

# Session middleware for login sessions
# IMPORTANT: change this secret key in a real project
app.add_middleware(SessionMiddleware, secret_key="CHANGE_ME_SUPER_SECRET")

# Static files (CSS, your own images, etc.)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# -----------------------------
# Auth helpers
# -----------------------------

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    user = db.query(User).filter(User.id == user_id).first()
    return user


def require_admin(user: Optional[User]) -> None:
    if not user or user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")


# -----------------------------
# HTML PAGES (PUBLIC)
# -----------------------------

@app.get("/", tags=["pages"])
def home(
    request: Request,
    q: Optional[str] = Query(default=None, description="Search by title"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
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
            "user": current_user,
        },
    )


@app.get("/manga/{manga_id}", tags=["pages"])
def manga_detail(
    manga_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    manga = db.query(Manga).filter(Manga.id == manga_id).first()
    if not manga:
        raise HTTPException(status_code=404, detail="Manga not found")

    chapters = sorted(manga.chapters, key=lambda c: c.number)

    user_lists: List[CustomList] = []
    if current_user:
        user_lists = (
            db.query(CustomList)
            .filter(CustomList.user_id == current_user.id)
            .order_by(CustomList.name)
            .all()
        )

    return templates.TemplateResponse(
        "manga_detail.html",
        {
            "request": request,
            "manga": manga,
            "chapters": chapters,
            "user": current_user,
            "user_lists": user_lists,
        },
    )


# -----------------------------
# AUTH PAGES
# -----------------------------

@app.get("/auth/register", tags=["auth"])
def register_form(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
):
    if current_user:
        # already logged in
        return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse(
        "auth_register.html",
        {"request": request, "user": current_user, "error": None},
    )


@app.post("/auth/register", tags=["auth"])
def register_submit(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    if current_user:
        return RedirectResponse(url="/", status_code=303)

    # Check if username or email already exists
    existing = (
        db.query(User)
        .filter(or_(User.username == username, User.email == email))
        .first()
    )
    if existing:
        return templates.TemplateResponse(
            "auth_register.html",
            {
                "request": request,
                "user": current_user,
                "error": "Username or email already in use.",
            },
        )

    hashed = get_password_hash(password)
    user = User(
        username=username,
        email=email,
        password_hash=hashed,
        role="user",  # always normal user
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Log them in immediately
    request.session["user_id"] = user.id

    return RedirectResponse(url="/", status_code=303)


@app.get("/auth/login", tags=["auth"])
def login_form(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
):
    if current_user:
        return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse(
        "auth_login.html",
        {"request": request, "user": current_user, "error": None},
    )


@app.post("/auth/login", tags=["auth"])
def login_submit(
    request: Request,
    identifier: str = Form(...),  # username or email
    password: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    if current_user:
        return RedirectResponse(url="/", status_code=303)

    user = (
        db.query(User)
        .filter(or_(User.username == identifier, User.email == identifier))
        .first()
    )
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "auth_login.html",
            {
                "request": request,
                "user": None,
                "error": "Invalid username/email or password.",
            },
        )

    request.session["user_id"] = user.id
    return RedirectResponse(url="/", status_code=303)


@app.get("/auth/logout", tags=["auth"])
def logout(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
):
    if "user_id" in request.session:
        request.session.pop("user_id")
    return RedirectResponse(url="/", status_code=303)


# -----------------------------
# CUSTOM LISTS
# -----------------------------

@app.get("/my/lists", tags=["lists"])
def my_lists(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=303)

    lists = (
        db.query(CustomList)
        .filter(CustomList.user_id == current_user.id)
        .order_by(CustomList.name)
        .all()
    )

    return templates.TemplateResponse(
        "my_lists.html",
        {
            "request": request,
            "user": current_user,
            "lists": lists,
        },
    )


@app.get("/lists/new", tags=["lists"])
def new_list_form(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
):
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=303)

    return templates.TemplateResponse(
        "list_new.html",
        {
            "request": request,
            "user": current_user,
            "error": None,
        },
    )


@app.post("/lists/new", tags=["lists"])
def new_list_submit(
    request: Request,
    name: str = Form(...),
    description: Optional[str] = Form(None),
    is_public: Optional[bool] = Form(False),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=303)

    is_public_flag = bool(is_public)

    custom_list = CustomList(
        user_id=current_user.id,
        name=name,
        description=description,
        is_public=is_public_flag,
    )
    db.add(custom_list)
    db.commit()
    db.refresh(custom_list)

    return RedirectResponse(url="/my/lists", status_code=303)


@app.get("/lists/{list_id}", tags=["lists"])
def list_detail(
    list_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    custom_list = db.query(CustomList).filter(CustomList.id == list_id).first()
    if not custom_list:
        raise HTTPException(status_code=404, detail="List not found")

    # Only show private lists to their owner
    if not custom_list.is_public:
        if not current_user or custom_list.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not allowed to view this list")

    return templates.TemplateResponse(
        "list_detail.html",
        {
            "request": request,
            "user": current_user,
            "custom_list": custom_list,
        },
    )


@app.post("/lists/add", tags=["lists"])
def add_to_list(
    request: Request,
    manga_id: int = Form(...),
    list_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=303)

    custom_list = (
        db.query(CustomList)
        .filter(CustomList.id == list_id, CustomList.user_id == current_user.id)
        .first()
    )
    if not custom_list:
        raise HTTPException(status_code=404, detail="List not found")

    manga = db.query(Manga).filter(Manga.id == manga_id).first()
    if not manga:
        raise HTTPException(status_code=404, detail="Manga not found")

    # Avoid duplicates
    existing = (
        db.query(CustomListItem)
        .filter(
            CustomListItem.list_id == custom_list.id,
            CustomListItem.manga_id == manga.id,
        )
        .first()
    )
    if not existing:
        item = CustomListItem(list_id=custom_list.id, manga_id=manga.id)
        db.add(item)
        db.commit()

    return RedirectResponse(url=f"/manga/{manga_id}", status_code=303)


@app.post("/lists/remove", tags=["lists"])
def remove_from_list(
    request: Request,
    item_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=303)

    item = (
        db.query(CustomListItem)
        .join(CustomList, CustomListItem.list_id == CustomList.id)
        .filter(
            CustomListItem.id == item_id,
            CustomList.user_id == current_user.id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item not found or not yours")

    list_id = item.list_id
    db.delete(item)
    db.commit()

    return RedirectResponse(url=f"/lists/{list_id}", status_code=303)


@app.post("/lists/{list_id}/delete", tags=["lists"])
def delete_list(
    list_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=303)

    custom_list = (
        db.query(CustomList)
        .filter(CustomList.id == list_id, CustomList.user_id == current_user.id)
        .first()
    )

    if not custom_list:
        raise HTTPException(status_code=404, detail="List not found or not yours")

    db.delete(custom_list)  # cascade deletes items too
    db.commit()

    return RedirectResponse(url="/my/lists", status_code=303)


# -----------------------------
# ADMIN PAGES (ADMIN ONLY)
# -----------------------------

@app.get("/admin", tags=["admin"])
def admin_home(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    require_admin(current_user)

    manga_list = db.query(Manga).order_by(Manga.title).all()
    return templates.TemplateResponse(
        "admin_index.html",
        {
            "request": request,
            "manga_list": manga_list,
            "user": current_user,
        },
    )


@app.get("/admin/users", tags=["admin"])
def admin_users(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    require_admin(current_user)

    users = db.query(User).order_by(User.created_at).all()
    return templates.TemplateResponse(
        "admin_users.html",
        {
            "request": request,
            "user": current_user,
            "users": users,
        },
    )


@app.post("/admin/users/{user_id}/role", tags=["admin"])
def admin_update_user_role(
    user_id: int,
    request: Request,
    role: str = Form(...),  # "user" or "admin"
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    require_admin(current_user)

    # Ensure only valid roles
    if role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="Invalid role")

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    # Optional safety: don't let an admin demote themselves
    if target.id == current_user.id and role != "admin":
        raise HTTPException(status_code=400, detail="You cannot demote yourself")

    target.role = role
    db.commit()

    return RedirectResponse(url="/admin/users", status_code=303)


@app.get("/admin/manga/new", tags=["admin"])
def admin_new_manga_form(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
):
    require_admin(current_user)

    return templates.TemplateResponse(
        "admin_manga_new.html",
        {
            "request": request,
            "user": current_user,
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
    current_user: Optional[User] = Depends(get_current_user),
):
    require_admin(current_user)

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

    return RedirectResponse(url=f"/manga/{manga.id}", status_code=303)


@app.get("/admin/chapters/new", tags=["admin"])
def admin_new_chapter_form(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    require_admin(current_user)

    manga_list = db.query(Manga).order_by(Manga.title).all()
    return templates.TemplateResponse(
        "admin_chapter_new.html",
        {
            "request": request,
            "manga_list": manga_list,
            "user": current_user,
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
    current_user: Optional[User] = Depends(get_current_user),
):
    require_admin(current_user)

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
    return RedirectResponse(url=chapter.external_url)

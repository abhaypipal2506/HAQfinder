"""FastAPI application for HAQfinder."""

from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import re
import secrets
import sqlite3
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import engine, store
from app.store import ALLOWED_STATUSES

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
SESSION_COOKIE = "haqfinder_session"
SESSION_DAYS = 14


@asynccontextmanager
async def lifespan(_app: FastAPI):
    store.init_db()
    yield


app = FastAPI(title="HAQfinder", lifespan=lifespan)


# ---------- Pydantic models ----------

class MatchRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=2000)
    state: Optional[str] = None
    district: Optional[str] = None
    age: Optional[int] = None
    annual_income: Optional[int] = None
    occupation: Optional[str] = None
    education: Optional[str] = None
    category: Optional[str] = None
    is_rural: Optional[bool] = None
    has_disability: Optional[bool] = None
    gender: Optional[str] = None
    family_situation: Optional[str] = None
    family_occupations: Optional[dict[str, str]] = None
    bpl: Optional[bool] = None
    special_answers: Optional[dict[str, bool]] = None


class RegistrationRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=10, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=1, max_length=128)


class ProfileUpdate(BaseModel):
    age: Optional[int] = Field(None, ge=0, le=120)
    state: Optional[str] = Field(None, max_length=100)
    district: Optional[str] = Field(None, max_length=100)
    occupation: Optional[str] = Field(None, max_length=100)
    annual_income: Optional[int] = Field(None, ge=0)
    category: Optional[str] = Field(None, max_length=50)
    education: Optional[str] = Field(None, max_length=100)
    gender: Optional[str] = Field(None, max_length=50)
    has_disability: Optional[bool] = None
    is_rural: Optional[bool] = None
    family_situation: Optional[str] = Field(None, max_length=1000)
    family_occupations: Optional[dict[str, str]] = None
    bpl: Optional[bool] = None
    special_answers: Optional[dict[str, bool]] = None


class DocumentCheck(BaseModel):
    name: str = Field(..., min_length=1, max_length=300)
    checked: bool = False


class ApplicationCreate(BaseModel):
    scheme_id: str
    status: str = "Not started"
    notes: str = ""
    deadline: Optional[str] = None


class ApplicationUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    deadline: Optional[str] = None
    documents: Optional[list[DocumentCheck]] = None


# ---------- helpers ----------

def _validate_status(status: Optional[str]) -> None:
    if status is not None and status not in ALLOWED_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status {status!r}; must be one of {list(ALLOWED_STATUSES)}",
        )


def _validate_deadline(deadline: Optional[str]) -> None:
    if deadline is None:
        return
    try:
        date.fromisoformat(deadline)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid deadline {deadline!r}; expected YYYY-MM-DD",
        )


def _find_scheme(scheme_id: str) -> Optional[dict]:
    for scheme in engine.SCHEMES:
        if scheme.get("id") == scheme_id:
            return scheme
    return None


def _request_user(request: Request) -> Optional[dict]:
    token = request.cookies.get(SESSION_COOKIE)
    return store.get_session_user(token) if token else None


def _require_user(request: Request) -> dict:
    user = _request_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Please log in to use this feature.")
    return user


def _start_session(response: Response, user: dict, request: Request) -> None:
    token = secrets.token_urlsafe(32)
    store.create_session(
        user["id"],
        token,
        datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS),
    )
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=request.url.scheme == "https"
        or request.headers.get("x-forwarded-proto") == "https",
        samesite="strict",
        path="/",
    )


def _validate_email(email: str) -> str:
    normalized = email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
        raise HTTPException(status_code=422, detail="Enter a valid email address.")
    return normalized


# ---------- health ----------

@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


# ---------- authentication and profile ----------

@app.post("/api/auth/register", status_code=201)
def register(body: RegistrationRequest, request: Request, response: Response) -> dict:
    email = _validate_email(body.email)
    try:
        user = store.create_user(email, body.full_name, store.hash_password(body.password))
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    _start_session(response, user, request)
    return {"user": user}


@app.post("/api/auth/login")
def login(body: LoginRequest, request: Request, response: Response) -> dict:
    email = _validate_email(body.email)
    account = store.get_user_by_email(email)
    if account is None or not store.verify_password(body.password, account["password_hash"]):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    user = {key: account[key] for key in ("id", "email", "full_name", "created_at")}
    _start_session(response, user, request)
    return {"user": user}


@app.post("/api/auth/logout", status_code=204)
def logout(request: Request, response: Response) -> Response:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        store.delete_session(token)
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="strict")
    response.status_code = 204
    return response


@app.get("/api/auth/me")
def current_account(request: Request) -> dict:
    user = _request_user(request)
    return {
        "user": user,
        "profile": store.get_profile(user["id"]) if user else {},
    }


@app.put("/api/profile")
def update_profile(body: ProfileUpdate, request: Request) -> dict:
    user = _require_user(request)
    profile = store.save_profile(user["id"], body.model_dump(exclude_unset=True))
    return {"profile": profile}


@app.get("/api/profile")
def get_profile(request: Request) -> dict:
    user = _require_user(request)
    return {"profile": store.get_profile(user["id"])}


# ---------- matching ----------

@app.post("/api/match")
def match(body: MatchRequest, request: Request) -> dict:
    overrides = body.model_dump(exclude={"description"}, exclude_none=True)
    saved_profile = {}
    user = _request_user(request)
    if user:
        saved_profile = store.get_profile(user["id"])
    profile = engine.merge_profile(engine.parse_description(body.description), saved_profile)
    profile = engine.merge_profile(profile, overrides)
    results = engine.match_schemes(profile)
    questions = engine.missing_questions(results)
    for result in results:
        result["scheme"] = _find_scheme(result.get("scheme_id"))
    return {"profile": profile, "results": results, "questions": questions}


# ---------- schemes ----------

@app.get("/api/schemes")
def list_schemes(
    q: Optional[str] = None,
    category: Optional[str] = None,
    state: Optional[str] = None,
    page: Optional[int] = Query(None, ge=1),
    page_size: Optional[int] = Query(None, ge=1, le=100),
) -> list[dict] | dict:
    items = list(engine.SCHEMES)
    if q and q.strip():
        query = q.strip().casefold()
        items = [
            scheme for scheme in items
            if query in " ".join(
                str(value)
                for value in (
                    scheme.get("name", ""),
                    scheme.get("description", ""),
                    scheme.get("category", ""),
                    scheme.get("categories", []),
                    scheme.get("department", ""),
                    scheme.get("state", ""),
                    scheme.get("benefits", []),
                )
            ).casefold()
        ]
    if category and category.casefold() != "all":
        items = [
            scheme for scheme in items
            if category.casefold() in {
                str(value).casefold()
                for value in [scheme.get("category"), *(scheme.get("categories") or [])]
            }
        ]
    if state:
        if state.casefold() == "central":
            items = [scheme for scheme in items if not scheme.get("state")]
        else:
            items = [
                scheme for scheme in items
                if str(scheme.get("state") or "").casefold() == state.casefold()
            ]
    if page is None and page_size is None and not q and not category and not state:
        return items
    current_page = page or 1
    size = page_size or 12
    start = (current_page - 1) * size
    return {
        "items": items[start:start + size],
        "total": len(items),
        "page": current_page,
        "page_size": size,
        "pages": (len(items) + size - 1) // size,
    }


@app.get("/api/categories")
def list_categories() -> list[str]:
    categories = {
        str(value)
        for scheme in engine.SCHEMES
        for value in [scheme.get("category", "other"), *(scheme.get("categories") or [])]
    }
    return sorted(categories)


@app.get("/api/schemes/{scheme_id}")
def get_scheme(scheme_id: str) -> dict:
    scheme = _find_scheme(scheme_id)
    if scheme is None:
        raise HTTPException(status_code=404, detail=f"Scheme {scheme_id!r} not found")
    return scheme


@app.post("/api/schemes/reload")
def reload_schemes() -> dict:
    engine.reload_schemes()
    return {"count": len(engine.SCHEMES)}


# ---------- applications ----------

@app.post("/api/applications", status_code=201)
def create_application(body: ApplicationCreate, request: Request) -> dict:
    scheme = _find_scheme(body.scheme_id)
    if scheme is None:
        raise HTTPException(status_code=404, detail=f"Scheme {body.scheme_id!r} not found")
    _validate_status(body.status)
    _validate_deadline(body.deadline)
    return store.create_application(
        scheme_id=body.scheme_id,
        scheme_name=scheme.get("name"),
        status=body.status,
        notes=body.notes,
        deadline=body.deadline,
        user_id=(user["id"] if (user := _request_user(request)) else None),
        required_documents=scheme.get("required_documents", []),
    )


@app.get("/api/applications")
def list_applications(request: Request) -> list[dict]:
    user = _request_user(request)
    return store.list_applications(user["id"] if user else None)


@app.patch("/api/applications/{app_id}")
def update_application(app_id: int, body: ApplicationUpdate, request: Request) -> dict:
    user = _request_user(request)
    user_id = user["id"] if user else None
    if store.get_application(app_id, user_id) is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id} not found")
    _validate_status(body.status)
    _validate_deadline(body.deadline)
    fields = body.model_dump(exclude_unset=True)
    if "documents" in fields and fields["documents"] is not None:
        fields["documents"] = [document.model_dump() for document in body.documents or []]
    row = store.update_application(app_id, user_id=user_id, **fields)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id} not found")
    return row


@app.delete("/api/applications/{app_id}", status_code=204)
def delete_application(app_id: int, request: Request) -> Response:
    user = _request_user(request)
    if not store.delete_application(app_id, user["id"] if user else None):
        raise HTTPException(status_code=404, detail=f"Application {app_id} not found")
    return Response(status_code=204)


@app.get("/api/reminders")
def reminders(request: Request) -> list[dict]:
    user = _request_user(request)
    rows = store.reminders(date.today(), user["id"] if user else None)
    if user:
        cutoff = date.today() + timedelta(days=store.REMINDER_WINDOW_DAYS)
        tracked_ids = {
            application["scheme_id"]
            for application in store.list_applications(user["id"])
        }
        reminded_ids = {row["scheme_id"] for row in rows}
        for bookmark in store.list_bookmarks(user["id"]):
            scheme = _find_scheme(bookmark["scheme_id"])
            deadline = (scheme or {}).get("deadline")
            if not deadline or bookmark["scheme_id"] in tracked_ids | reminded_ids:
                continue
            try:
                due = date.fromisoformat(deadline)
            except ValueError:
                continue
            if due <= cutoff:
                rows.append({
                    "scheme_id": bookmark["scheme_id"],
                    "scheme_name": (scheme or {}).get("name"),
                    "deadline": deadline,
                    "status": "Saved scheme",
                })
    return sorted(rows, key=lambda row: (row["deadline"], row["scheme_id"]))


@app.get("/api/bookmarks")
def list_bookmarks(request: Request) -> list[dict]:
    user = _require_user(request)
    return store.list_bookmarks(user["id"])


@app.put("/api/bookmarks/{scheme_id}", status_code=201)
def add_bookmark(scheme_id: str, request: Request) -> dict:
    if _find_scheme(scheme_id) is None:
        raise HTTPException(status_code=404, detail=f"Scheme {scheme_id!r} not found")
    user = _require_user(request)
    store.add_bookmark(user["id"], scheme_id)
    return {"scheme_id": scheme_id, "saved": True}


@app.delete("/api/bookmarks/{scheme_id}", status_code=204)
def delete_bookmark(scheme_id: str, request: Request) -> Response:
    user = _require_user(request)
    if not store.remove_bookmark(user["id"], scheme_id):
        raise HTTPException(status_code=404, detail="Saved scheme not found.")
    return Response(status_code=204)


# ---------- static (must be mounted last) ----------

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static_files")
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

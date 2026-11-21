"""FastAPI application for HAQfinder."""

from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import engine, store
from app.store import ALLOWED_STATUSES

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    store.init_db()
    yield


app = FastAPI(title="HAQfinder", lifespan=lifespan)


# ---------- Pydantic models ----------

class MatchRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=2000)
    state: Optional[str] = None
    age: Optional[int] = None
    annual_income: Optional[int] = None
    occupation: Optional[str] = None
    category: Optional[str] = None
    is_rural: Optional[bool] = None
    has_disability: Optional[bool] = None
    gender: Optional[str] = None


class ApplicationCreate(BaseModel):
    scheme_id: str
    status: str = "Not started"
    notes: str = ""
    deadline: Optional[str] = None


class ApplicationUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    deadline: Optional[str] = None


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


# ---------- health ----------

@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


# ---------- matching ----------

@app.post("/api/match")
def match(body: MatchRequest) -> dict:
    overrides = body.model_dump(exclude={"description"}, exclude_none=True)
    profile = engine.merge_profile(engine.parse_description(body.description), overrides)
    results = engine.match_schemes(profile)
    questions = engine.missing_questions(results)
    for result in results:
        result["scheme"] = _find_scheme(result.get("scheme_id"))
    return {"profile": profile, "results": results, "questions": questions}


# ---------- schemes ----------

@app.get("/api/schemes")
def list_schemes() -> list[dict]:
    return list(engine.SCHEMES)


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
def create_application(body: ApplicationCreate) -> dict:
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
    )


@app.get("/api/applications")
def list_applications() -> list[dict]:
    return store.list_applications()


@app.patch("/api/applications/{app_id}")
def update_application(app_id: int, body: ApplicationUpdate) -> dict:
    if store.get_application(app_id) is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id} not found")
    _validate_status(body.status)
    _validate_deadline(body.deadline)
    fields = body.model_dump(exclude_unset=True)
    row = store.update_application(app_id, **fields)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id} not found")
    return row


@app.delete("/api/applications/{app_id}", status_code=204)
def delete_application(app_id: int) -> Response:
    if not store.delete_application(app_id):
        raise HTTPException(status_code=404, detail=f"Application {app_id} not found")
    return Response(status_code=204)


@app.get("/api/reminders")
def reminders() -> list[dict]:
    return store.reminders(date.today())


# ---------- static (must be mounted last) ----------

app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

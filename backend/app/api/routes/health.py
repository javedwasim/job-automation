from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Basic liveness check — does not touch the database."""
    return {"status": "ok"}


@router.get("/health/db")
def health_db(db: Session = Depends(get_db)) -> dict:
    """Verifies the MySQL connection is reachable (Phase 0 verification gate)."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "reachable"}

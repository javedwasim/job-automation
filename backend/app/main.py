from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import gmail, health, jobs
from app.config.settings import get_settings

settings = get_settings()

app = FastAPI(
    title="Job Alert Extraction & CSV Export System",
    description=(
        "Monitors Gmail job-alert emails, extracts and classifies job postings, "
        "deduplicates them, and exports matches to CSV. Does not scrape job sites "
        "or automate applications."
    ),
    version="0.1.0",
    debug=settings.debug,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(gmail.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")


@app.get("/")
def root() -> dict:
    return {"service": settings.app_name, "status": "running"}

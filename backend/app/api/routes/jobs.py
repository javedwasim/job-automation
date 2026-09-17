from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.repositories.job_repository import JobRepository
from app.schemas.jobs import JobOut, JobsPageOut

router = APIRouter(prefix="/jobs", tags=["jobs"])

_MAX_PAGE_SIZE = 100


@router.get("", response_model=JobsPageOut)
def list_jobs(
    page: int = Query(default=1, ge=1, description="1-based page number"),
    page_size: int = Query(default=20, ge=1, le=_MAX_PAGE_SIZE, description="Rows per page"),
    db: Session = Depends(get_db),
) -> JobsPageOut:
    """Returns one page of extracted jobs (any classification status), most
    recently received first — the dashboard is the pipeline's full output."""
    jobs, total = JobRepository(db).list_paginated(page=page, page_size=page_size)
    return JobsPageOut(
        items=[
            JobOut(
                id=job.id,
                title=job.title,
                company=job.company,
                location=job.location,
                source=job.platform.slug if job.platform else None,
                job_url=job.job_url,
                application_url=job.application_url,
                categories=[c.name for c in job.categories],
                job_posted_at=job.job_posted_at,
                received_at=job.received_at,
                status=job.status.value,
                remote_type=job.remote_type,
                salary=job.salary,
                employment_type=job.employment_type,
            )
            for job in jobs
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )

"""
OfferI Backend API Server
FastAPI server for study abroad recommendation system
"""
import os
import uuid
import json
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from redis import Redis
from sqlalchemy.orm import Session
from loguru import logger

from .models import (
    UserBackground,
    JobSubmitResponse,
    JobStatusResponse,
    ErrorResponse
)
from .routes.payment import router as payment_router
from database import get_db, Payment, PaymentStatus, init_db

# Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

# Redis client
redis_client = Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    decode_responses=True
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    logger.info("Starting OfferI Backend API...")
    logger.info(f"Redis: {REDIS_HOST}:{REDIS_PORT}")

    # Test Redis connection
    try:
        redis_client.ping()
        logger.success("✓ Redis connection established")
    except Exception as e:
        logger.error(f"✗ Redis connection failed: {e}")
        raise

    # Initialize database
    try:
        init_db()
        logger.success("✓ Database initialized")
    except Exception as e:
        logger.warning(f"⚠ Database initialization skipped: {e}")

    yield

    # Shutdown
    logger.info("Shutting down OfferI Backend API...")


# Initialize FastAPI app
app = FastAPI(
    title="OfferI Backend API",
    description="Study Abroad Recommendation System - Backend API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for web frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js dev
        "http://localhost:3001",
        "https://offeri.com",     # Production web
        "https://www.offeri.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include payment routes
app.include_router(payment_router)


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """API health check"""
    return {
        "service": "OfferI Backend API",
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    try:
        # Check Redis
        redis_client.ping()
        redis_status = "healthy"
    except Exception as e:
        redis_status = f"unhealthy: {str(e)}"

    # Check job queue length
    queue_length = redis_client.llen("job_queue")

    # Count jobs by status
    pending_jobs = len([k for k in redis_client.keys("job:*") if redis_client.hget(k, "status") == "pending"])
    processing_jobs = len([k for k in redis_client.keys("job:*") if redis_client.hget(k, "status") == "processing"])
    completed_jobs = len([k for k in redis_client.keys("job:*") if redis_client.hget(k, "status") == "completed"])

    return {
        "status": "healthy",
        "redis": redis_status,
        "queue": {
            "length": queue_length,
            "pending": pending_jobs,
            "processing": processing_jobs,
            "completed": completed_jobs
        },
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/submit")
async def submit_background(
    user_background: UserBackground,
    payment_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Submit user background for study abroad recommendation

    User fills unstructured form with their background:
    - School, GPA, major (flexible format)
    - Projects, papers, internships (free text)
    - Career goal, target countries, budget

    Returns job_id for tracking progress

    Requires valid payment_id from Stripe checkout ($6)
    """
    try:
        # Extract user_id from background (set by frontend with Clerk)
        user_id = user_background.dict().get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=400,
                detail="User authentication required"
            )

        # Verify payment exists and is valid
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            raise HTTPException(
                status_code=402,
                detail="Payment not found. Please complete payment first."
            )

        # Check payment belongs to this user
        if payment.user_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="Payment does not belong to this user"
            )

        # Check payment is valid (PAID or PENDING_RETRY for retry after failure)
        if payment.status not in [PaymentStatus.PAID, PaymentStatus.PENDING_RETRY]:
            raise HTTPException(
                status_code=402,
                detail=f"Payment already {payment.status}. Please make a new payment."
            )

        # Generate unique job ID
        job_id = str(uuid.uuid4())

        # Mark payment as being used for this job
        payment.job_id = job_id
        payment.status = PaymentStatus.PAID  # Reset to PAID if was PENDING_RETRY
        payment.updated_at = datetime.utcnow()
        db.commit()

        logger.info(f"New job submitted: {job_id} (user: {user_id}, payment: {payment_id})")
        logger.debug(f"User background: {user_background.dict()}")

        # Store job in Redis
        job_data = {
            "status": "pending",
            "progress": "排队中...",
            "user_background": json.dumps(user_background.dict(), ensure_ascii=False),
            "user_id": user_id,
            "payment_id": payment_id,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

        redis_client.hset(f"job:{job_id}", mapping=job_data)

        # Add to job queue
        redis_client.lpush("job_queue", job_id)

        # Set TTL: 24 hours
        redis_client.expire(f"job:{job_id}", 86400)

        logger.success(f"Job {job_id} queued successfully")

        return JobSubmitResponse(
            job_id=job_id,
            status="queued",
            message="您的请求已提交，我们正在为您生成专业留学规划报告",
            estimated_time="10-15分钟"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting job: {e}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit job: {str(e)}"
        )


@app.get("/api/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    Check job status

    Frontend polls this endpoint every 5 seconds
    Returns: pending → processing → completed → failed
    """
    try:
        # Check if job exists
        if not redis_client.exists(f"job:{job_id}"):
            raise HTTPException(
                status_code=404,
                detail=f"Job {job_id} not found"
            )

        # Get job data
        job_data = redis_client.hgetall(f"job:{job_id}")

        return JobStatusResponse(
            job_id=job_id,
            status=job_data.get("status", "unknown"),
            progress=job_data.get("progress"),
            created_at=job_data.get("created_at"),
            updated_at=job_data.get("updated_at")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get job status: {str(e)}"
        )


@app.get("/api/results/{job_id}/preview", response_class=HTMLResponse)
async def preview_report(job_id: str):
    """
    Preview report as HTML in browser

    Returns beautiful styled HTML for instant viewing
    """
    try:
        # Check if job completed
        if not redis_client.exists(f"job:{job_id}"):
            raise HTTPException(status_code=404, detail="Job not found")

        status = redis_client.hget(f"job:{job_id}", "status")
        if status != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Report not ready yet. Current status: {status}"
            )

        # Get HTML report
        html_content = redis_client.hget(f"job:{job_id}", "html")
        if not html_content:
            raise HTTPException(status_code=404, detail="HTML report not found")

        return HTMLResponse(content=html_content)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting preview: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get preview: {str(e)}"
        )


@app.get("/api/results/{job_id}/download")
async def download_report(job_id: str):
    """
    Download PDF report

    Returns PDF file for download/printing
    """
    try:
        # Check if job completed
        if not redis_client.exists(f"job:{job_id}"):
            raise HTTPException(status_code=404, detail="Job not found")

        status = redis_client.hget(f"job:{job_id}", "status")
        if status != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Report not ready yet. Current status: {status}"
            )

        # Get PDF path
        pdf_path = redis_client.hget(f"job:{job_id}", "pdf_path")
        if not pdf_path or not os.path.exists(pdf_path):
            raise HTTPException(status_code=404, detail="PDF report not found")

        # Get user's school name for filename
        user_bg_json = redis_client.hget(f"job:{job_id}", "user_background")
        user_bg = json.loads(user_bg_json)
        school = user_bg.get("school", "Unknown")

        filename = f"OfferI_留学规划报告_{school}_{job_id[:8]}.pdf"

        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=filename
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading report: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download report: {str(e)}"
        )


@app.get("/api/results/{job_id}/markdown")
async def get_markdown(job_id: str):
    """
    Get raw markdown report (for debugging/developers)
    """
    try:
        if not redis_client.exists(f"job:{job_id}"):
            raise HTTPException(status_code=404, detail="Job not found")

        status = redis_client.hget(f"job:{job_id}", "status")
        if status != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Report not ready yet. Current status: {status}"
            )

        markdown_content = redis_client.hget(f"job:{job_id}", "markdown")
        if not markdown_content:
            raise HTTPException(status_code=404, detail="Markdown report not found")

        return {
            "job_id": job_id,
            "markdown": markdown_content
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting markdown: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get markdown: {str(e)}"
        )


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "detail": str(exc.detail) if hasattr(exc, 'detail') else "Resource not found"
        }
    )


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": "An unexpected error occurred. Please try again later."
        }
    )


# ============================================================================
# Development/Debug Endpoints
# ============================================================================

@app.get("/debug/jobs")
async def list_all_jobs():
    """List all jobs (debug endpoint)"""
    job_keys = redis_client.keys("job:*")
    jobs = []

    for key in job_keys:
        job_data = redis_client.hgetall(key)
        job_id = key.split(":")[-1]
        jobs.append({
            "job_id": job_id,
            "status": job_data.get("status"),
            "progress": job_data.get("progress"),
            "created_at": job_data.get("created_at")
        })

    return {"total": len(jobs), "jobs": jobs}


@app.delete("/debug/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a job (debug endpoint)"""
    if not redis_client.exists(f"job:{job_id}"):
        raise HTTPException(status_code=404, detail="Job not found")

    redis_client.delete(f"job:{job_id}")
    return {"message": f"Job {job_id} deleted"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

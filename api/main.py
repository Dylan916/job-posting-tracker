"""FastAPI main application entrypoint."""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routes.health import router as health_router
from api.routes.postings import router as postings_router
from api.routes.skills import router as skills_router
from api.routes.stats import router as stats_router
from db.connection import close_pool, get_pool


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown events."""
    # Initialize connection pool on startup
    get_pool()
    yield
    # Close pool on shutdown
    close_pool()


app = FastAPI(
    title="InternPulse — Real-Time Internship & Job Tracker API",
    description="REST API for querying tech internships, filtering by recruiting seasons (Summer 2027), and analyzing hiring trends.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware for web dashboard access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API v1 routes
app.include_router(health_router, prefix="/api/v1")
app.include_router(postings_router, prefix="/api/v1")
app.include_router(skills_router, prefix="/api/v1")
app.include_router(stats_router, prefix="/api/v1")

# Mount Web Dashboard static directory at root '/'
web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")
if os.path.exists(web_dir):
    app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)

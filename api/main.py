"""FastAPI main application entrypoint."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from api.routes.health import router as health_router
from api.routes.postings import router as postings_router
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
    title="Real-Time Internship & Job Posting Tracker API",
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
app.include_router(stats_router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    """Redirect root path to interactive OpenAPI documentation."""
    return RedirectResponse(url="/docs")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)

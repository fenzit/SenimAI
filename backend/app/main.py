import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes.analysis import router as analysis_router
from app.core.config import settings

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("senimai")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.PROJECT_NAME}")
    logger.info(f"Mock Mode: {settings.MOCK_MODE}")
    logger.info(f"Search Provider: {settings.SEARCH_PROVIDER}")
    yield
    logger.info(f"Shutting down {settings.PROJECT_NAME}")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Evidence-based Fact Checking and Trust Verification API for AI generated responses.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Setup CORS for Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(analysis_router, prefix=settings.API_V1_STR, tags=["Analysis"])


@app.get("/", summary="Root endpoint")
async def root():
    return {
        "service": settings.PROJECT_NAME,
        "version": "1.0.0",
        "docs": "/docs",
        "api_v1": f"{settings.API_V1_STR}/analyze",
        "health": f"{settings.API_V1_STR}/health",
        "mock_mode": settings.MOCK_MODE,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

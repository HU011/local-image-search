"""FastAPI entry point for the local image search service."""

import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.api.routes import router
from app.core.config import PROJECT_ROOT, get_settings
from app.core.queue import task_queue
from app.services.embedding import embedding_service
from app.services.error_store import error_store
from app.services.vector_db import vector_db
from app.services.worker import ingest_worker


log_dir = PROJECT_ROOT / "logs"
web_dir = PROJECT_ROOT / "web"
log_dir.mkdir(parents=True, exist_ok=True)

logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
)
logger.add(
    log_dir / "app.log",
    rotation="10 MB",
    retention="7 days",
    level="DEBUG",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and shut down service resources."""
    settings = get_settings()

    logger.info("=" * 50)
    logger.info("Starting local image search service...")
    logger.info("=" * 50)

    (PROJECT_ROOT / "data").mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Connecting task queue...")
    await task_queue.connect()

    logger.info("Connecting vector database...")
    vector_db.connect()

    if not vector_db.collection_exists():
        logger.info("Vector collection does not exist; creating it...")
        vector_db.init_collection()

    logger.info("Initializing error store...")
    await error_store.init()

    logger.info("Loading embedding model...")
    embedding_service.load_model()

    logger.info("Starting ingest worker...")
    await ingest_worker.start()

    logger.info("=" * 50)
    logger.info("Service started")
    logger.info(f"API: http://{settings.host}:{settings.port}")
    logger.info(f"Docs: http://{settings.host}:{settings.port}/docs")
    logger.info("=" * 50)

    yield

    logger.info("Stopping service...")

    await ingest_worker.stop()
    await task_queue.disconnect()
    vector_db.disconnect()
    embedding_service.unload_model()

    logger.info("Service stopped")


app = FastAPI(
    title="Local Image Search API",
    description="Local GPU-accelerated image embedding and vector search service.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

if web_dir.is_dir():
    app.mount("/web", StaticFiles(directory=web_dir, html=True), name="web")


@app.get("/", include_in_schema=False)
async def web_index():
    """Open the local web workbench."""
    if web_dir.is_dir():
        return RedirectResponse(url="/web/")
    return {"name": get_settings().instance_name}


@app.get("/health", tags=["health"])
async def health_check():
    """Return basic service health."""
    return {
        "status": "healthy",
        "instance": get_settings().instance_name,
        "model_loaded": embedding_service.is_loaded,
        "db_connected": vector_db.collection_exists(),
    }


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )

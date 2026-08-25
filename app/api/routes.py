"""API routes for image ingest, search, stats, and error records."""

import time

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from app.api.schemas import (
    BatchIngestRequest,
    BatchIngestResponse,
    BatchSearchRequest,
    BatchSearchResponse,
    BatchSearchResultItem,
    DatabaseInitRequest,
    DatabaseInitResponse,
    DeleteResponse,
    ErrorListResponse,
    ImageIdCheckRequest,
    ImageIdCheckResponse,
    ImageIngestRequest,
    ImageIngestResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
    StatsResponse,
)
from app.core.queue import IngestTask, task_queue
from app.services.embedding import embedding_service
from app.services.error_store import error_store
from app.services.vector_db import vector_db
from app.services.worker import ingest_worker
from app.utils.image import decode_base64_image


router = APIRouter()


@router.post("/images/ingest", response_model=ImageIngestResponse, tags=["ingest"])
async def ingest_image(request: ImageIngestRequest):
    """Queue one image for embedding and vector upsert."""
    task = IngestTask(id=request.id, base64=request.base64, url=request.url)
    position = await task_queue.put(task)

    return ImageIngestResponse(
        status="queued",
        id=request.id,
        queue_position=position,
    )


@router.post("/images/ingest/batch", response_model=BatchIngestResponse, tags=["ingest"])
async def ingest_images_batch(request: BatchIngestRequest):
    """Queue multiple images for embedding and vector upsert."""
    tasks = [
        IngestTask(id=image.id, base64=image.base64, url=image.url)
        for image in request.images
    ]

    start_position = await task_queue.size() + 1
    await task_queue.put_batch(tasks)

    return BatchIngestResponse(
        queued_count=len(tasks),
        queue_position_start=start_position,
    )


@router.post("/images/missing", response_model=ImageIdCheckResponse, tags=["ingest"])
async def get_missing_image_ids(request: ImageIdCheckRequest):
    """Return which image ids are already indexed and which are missing."""
    clean_ids = []
    seen = set()
    for value in request.ids:
        image_id = str(value or "").strip()
        if image_id and image_id not in seen:
            clean_ids.append(image_id)
            seen.add(image_id)

    existing = vector_db.existing_payload_ids(clean_ids)
    return ImageIdCheckResponse(
        existing_ids=[image_id for image_id in clean_ids if image_id in existing],
        missing_ids=[image_id for image_id in clean_ids if image_id not in existing],
    )


@router.post("/search", response_model=SearchResponse, tags=["search"])
async def search_image(request: SearchRequest):
    """Search for visually similar indexed images."""
    start_time = time.time()

    try:
        image = decode_base64_image(request.base64)
        embedding = embedding_service.get_embedding(image)
        results = vector_db.search(
            query_vector=embedding,
            top_k=request.top_k,
            threshold=request.threshold,
        )
        query_time = (time.time() - start_time) * 1000

        return SearchResponse(
            query_time_ms=round(query_time, 2),
            results=[SearchResult(**result) for result in results],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Image search failed")
        raise HTTPException(status_code=500, detail=f"Image search failed: {exc}") from exc


@router.post("/search/batch", response_model=BatchSearchResponse, tags=["search"])
async def search_images_batch(request: BatchSearchRequest):
    """Search with multiple query images in one request."""
    total_start = time.time()
    images = []

    for index, item in enumerate(request.images):
        try:
            images.append(decode_base64_image(item.base64))
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Image decode failed at index {index}: {exc}",
            ) from exc

    embeddings = embedding_service.get_embeddings_batch(images)
    results = []

    for index, (item, embedding) in enumerate(zip(request.images, embeddings)):
        query_start = time.time()
        search_results = vector_db.search(
            query_vector=embedding,
            top_k=item.top_k,
            threshold=item.threshold,
        )
        query_time = (time.time() - query_start) * 1000

        results.append(
            BatchSearchResultItem(
                index=index,
                query_time_ms=round(query_time, 2),
                matches=[SearchResult(**result) for result in search_results],
            )
        )

    total_time = (time.time() - total_start) * 1000
    return BatchSearchResponse(
        total_query_time_ms=round(total_time, 2),
        results=results,
    )


@router.get("/stats", response_model=StatsResponse, tags=["stats"])
async def get_stats():
    """Return service and vector index statistics."""
    total_images = vector_db.count()
    queue_pending = await task_queue.size()
    failed_count = await error_store.count()

    if total_images == 0 and queue_pending == 0:
        index_status = "empty"
    elif queue_pending > 0 or ingest_worker.stats.processing_count > 0:
        index_status = "building"
    else:
        index_status = "ready"

    last_updated = None
    if ingest_worker.stats.last_batch_time:
        last_updated = ingest_worker.stats.last_batch_time.isoformat()

    return StatsResponse(
        total_images=total_images,
        queue_pending=queue_pending,
        queue_processing=ingest_worker.stats.processing_count,
        failed_count=failed_count,
        index_status=index_status,
        last_updated=last_updated,
    )


@router.post("/database/init", response_model=DatabaseInitResponse, tags=["database"])
async def init_database(request: DatabaseInitRequest = DatabaseInitRequest()):
    """Create or recreate the configured vector collection."""
    try:
        result = vector_db.init_collection(recreate=request.recreate)
        return DatabaseInitResponse(**result)
    except Exception as exc:
        logger.exception("Database initialization failed")
        raise HTTPException(status_code=500, detail=f"Initialization failed: {exc}") from exc


@router.get("/errors", response_model=ErrorListResponse, tags=["errors"])
async def get_errors(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=50, ge=1, le=200, description="Page size"),
):
    """Return paginated failed ingest records."""
    result = await error_store.get_errors(page=page, page_size=page_size)
    return ErrorListResponse(**result)


@router.delete("/errors", response_model=DeleteResponse, tags=["errors"])
async def clear_errors():
    """Clear all failed ingest records."""
    count = await error_store.clear_errors()
    return DeleteResponse(
        success=True,
        deleted_count=count,
        message=f"Cleared {count} error records",
    )


@router.delete("/errors/{error_id}", response_model=DeleteResponse, tags=["errors"])
async def delete_error(error_id: str):
    """Delete one failed ingest record."""
    success = await error_store.delete_error(error_id)
    if success:
        return DeleteResponse(
            success=True,
            deleted_count=1,
            message="Deleted",
        )

    raise HTTPException(status_code=404, detail="Error record not found")

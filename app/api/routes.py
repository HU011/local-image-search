"""API routes for image ingest, search, stats, and error records."""

import asyncio
import base64
import hashlib
import mimetypes
import re
import time
from pathlib import PurePosixPath
from urllib import request as url_request
from urllib.parse import unquote, urlparse

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
    UrlIngestError,
    UrlIngestRequest,
    UrlIngestResponse,
)
from app.core.queue import IngestTask, task_queue
from app.services.embedding import embedding_service
from app.services.error_store import error_store
from app.services.vector_db import vector_db
from app.services.worker import ingest_worker
from app.utils.image import decode_base64_image


router = APIRouter()
MAX_EXTERNAL_IMAGE_BYTES = 20 * 1024 * 1024


def _sanitize_id_part(value: str) -> str:
    clean_value = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")
    return clean_value[:100]


def _image_id_from_url(url: str, id_prefix: str, index: int) -> str:
    parsed = urlparse(url)
    filename = PurePosixPath(unquote(parsed.path)).name
    stem = re.sub(r"\.[^.]+$", "", filename) if filename else ""
    base = _sanitize_id_part(stem) or f"url-{index + 1}"
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    prefix = _sanitize_id_part(id_prefix)
    if prefix:
        return f"{prefix}-{base}-{digest}"
    return f"{base}-{digest}"


def _fetch_external_image_as_data_uri(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http and https image URLs are supported")

    request = url_request.Request(
        url,
        headers={"User-Agent": "LocalImageSearch/1.0"},
        method="GET",
    )
    with url_request.urlopen(request, timeout=30) as response:
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        data = response.read(MAX_EXTERNAL_IMAGE_BYTES + 1)

    if len(data) > MAX_EXTERNAL_IMAGE_BYTES:
        raise ValueError("Image is larger than 20 MB")

    guessed_type = mimetypes.guess_type(urlparse(url).path)[0]
    mime_type = content_type or guessed_type or "image/jpeg"
    if content_type and not content_type.startswith("image/"):
        raise ValueError(f"URL returned non-image content type: {content_type}")

    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


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


@router.post("/images/ingest/urls", response_model=UrlIngestResponse, tags=["ingest"])
async def ingest_image_urls(request: UrlIngestRequest):
    """Fetch external image URLs server-side and queue them for indexing."""
    clean_urls = []
    seen = set()
    for url in request.urls:
        clean_url = str(url or "").strip()
        if clean_url and clean_url not in seen:
            clean_urls.append(clean_url)
            seen.add(clean_url)

    candidates = [
        (url, _image_id_from_url(url, request.id_prefix, index))
        for index, url in enumerate(clean_urls)
    ]
    skipped_count = 0
    if request.skip_existing and candidates:
        existing = vector_db.existing_payload_ids([image_id for _, image_id in candidates])
        skipped_count = len(existing)
        candidates = [
            (url, image_id)
            for url, image_id in candidates
            if image_id not in existing
        ]

    tasks = []
    errors = []
    for url, image_id in candidates:
        try:
            base64_image = await asyncio.to_thread(_fetch_external_image_as_data_uri, url)
            tasks.append(IngestTask(id=image_id, base64=base64_image, url=url))
        except Exception as exc:
            errors.append(UrlIngestError(url=url, error_message=str(exc)))

    queue_position_start = await task_queue.size() + 1 if tasks else 0
    if tasks:
        await task_queue.put_batch(tasks)

    return UrlIngestResponse(
        queued_count=len(tasks),
        skipped_count=skipped_count,
        failed_count=len(errors),
        queue_position_start=queue_position_start,
        errors=errors,
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

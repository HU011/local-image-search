"""Pydantic schemas for the image search API."""

from typing import Optional

from pydantic import BaseModel, Field


class ImageIngestRequest(BaseModel):
    """Single image ingest request."""

    id: str = Field(..., description="Unique image id")
    base64: str = Field(..., description="Base64-encoded image content")
    url: str = Field(..., description="Original URL, local path, or source reference")


class ImageIngestResponse(BaseModel):
    """Single image ingest response."""

    status: str = Field(..., description="Task status: queued, processing, completed, or failed")
    id: str = Field(..., description="Image id")
    queue_position: int = Field(..., description="Queue position")


class BatchIngestRequest(BaseModel):
    """Batch image ingest request."""

    images: list[ImageIngestRequest] = Field(..., description="Images to ingest")


class BatchIngestResponse(BaseModel):
    """Batch image ingest response."""

    queued_count: int = Field(..., description="Number of queued images")
    queue_position_start: int = Field(..., description="Starting queue position")


class ImageIdCheckRequest(BaseModel):
    """Request for checking which image ids already exist in the vector index."""

    ids: list[str] = Field(..., description="Image ids to check")


class ImageIdCheckResponse(BaseModel):
    """Response for existing and missing image ids."""

    existing_ids: list[str] = Field(default_factory=list, description="Image ids already indexed")
    missing_ids: list[str] = Field(default_factory=list, description="Image ids not found in the index")


class SearchRequest(BaseModel):
    """Single image search request."""

    base64: str = Field(..., description="Base64-encoded query image")
    top_k: int = Field(default=10, ge=1, le=100, description="Number of results to return")
    threshold: Optional[float] = Field(default=None, ge=0, le=1, description="Optional similarity threshold")


class SearchResult(BaseModel):
    """Single search result item."""

    id: str = Field(..., description="Matched image id")
    url: str = Field(..., description="Stored image URL, local path, or source reference")
    score: float = Field(..., description="Similarity score")
    rank: int = Field(..., description="Result rank")


class SearchResponse(BaseModel):
    """Single image search response."""

    query_time_ms: float = Field(..., description="Query time in milliseconds")
    results: list[SearchResult] = Field(..., description="Search results")


class BatchSearchItem(BaseModel):
    """Single query item in a batch search request."""

    base64: str = Field(..., description="Base64-encoded query image")
    top_k: int = Field(default=10, ge=1, le=100, description="Number of results to return")
    threshold: Optional[float] = Field(default=None, ge=0, le=1, description="Optional similarity threshold")


class BatchSearchRequest(BaseModel):
    """Batch image search request."""

    images: list[BatchSearchItem] = Field(..., description="Query images")


class BatchSearchResultItem(BaseModel):
    """Single result item in a batch search response."""

    index: int = Field(..., description="Input query index")
    query_time_ms: float = Field(..., description="Query time in milliseconds")
    matches: list[SearchResult] = Field(..., description="Matched images")


class BatchSearchResponse(BaseModel):
    """Batch image search response."""

    total_query_time_ms: float = Field(..., description="Total query time in milliseconds")
    results: list[BatchSearchResultItem] = Field(..., description="Batch results")


class StatsResponse(BaseModel):
    """Service and index statistics."""

    total_images: int = Field(..., description="Total indexed images")
    queue_pending: int = Field(..., description="Pending queue size")
    queue_processing: int = Field(..., description="Number of images currently processing")
    failed_count: int = Field(..., description="Failed ingest record count")
    index_status: str = Field(..., description="Index status: ready, building, or empty")
    last_updated: Optional[str] = Field(None, description="Last completed batch timestamp")


class DatabaseInitRequest(BaseModel):
    """Vector collection initialization request."""

    recreate: bool = Field(default=False, description="Recreate the vector collection")


class DatabaseInitResponse(BaseModel):
    """Vector collection initialization response."""

    status: str = Field(..., description="Status: created, already_exists, or recreated")
    collection_name: str = Field(..., description="Vector collection name")
    message: str = Field(..., description="Human-readable message")


class ErrorItem(BaseModel):
    """Failed ingest record."""

    id: str
    url: str
    error_message: str
    created_at: str


class ErrorListResponse(BaseModel):
    """Paginated failed ingest records."""

    total: int
    page: int
    page_size: int
    errors: list[ErrorItem]


class DeleteResponse(BaseModel):
    """Delete operation response."""

    success: bool
    deleted_count: int = 0
    message: str = ""

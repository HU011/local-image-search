"""Qdrant vector database service."""

from pathlib import Path
from typing import Optional
from uuid import NAMESPACE_URL, uuid5

import numpy as np
from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.http import models

from app.core.config import get_settings


class VectorDBService:
    """Manage Qdrant connections, collections, upserts, and vector search."""

    def __init__(self):
        self.settings = get_settings()
        self._client: Optional[QdrantClient] = None

    def connect(self):
        """Connect to the configured Qdrant instance."""
        if self._client:
            return

        if self.settings.qdrant_url:
            self._client = QdrantClient(
                url=self.settings.qdrant_url,
                grpc_port=self.settings.qdrant_grpc_port,
                prefer_grpc=self.settings.qdrant_prefer_grpc,
                timeout=120,
            )
            self._client.get_collections()
            logger.info(f"Connected to Qdrant Server: {self.settings.qdrant_url}")
            return

        Path(self.settings.qdrant_path).mkdir(parents=True, exist_ok=True)
        self._client = QdrantClient(path=self.settings.qdrant_path)
        logger.warning(f"Using embedded Qdrant local storage: {self.settings.qdrant_path}")

    def disconnect(self):
        """Close the active Qdrant client."""
        if self._client:
            self._client.close()
            self._client = None

    def init_collection(self, recreate: bool = False) -> dict:
        """Create the configured vector collection if needed."""
        if not self._client:
            self.connect()

        collection_name = self.settings.qdrant_collection
        collections = self._client.get_collections().collections
        exists = any(collection.name == collection_name for collection in collections)

        if exists:
            if recreate:
                self._client.delete_collection(collection_name)
                logger.info(f"Deleted collection: {collection_name}")
            else:
                logger.info(f"Collection already exists: {collection_name}")
                return {
                    "status": "already_exists",
                    "collection_name": collection_name,
                    "message": "Collection already exists",
                }

        self._client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=self.settings.vector_dimension,
                distance=models.Distance.COSINE,
            ),
        )

        self._client.create_payload_index(
            collection_name=collection_name,
            field_name="id",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )

        status = "recreated" if (exists and recreate) else "created"
        logger.info(f"Collection {status}: {collection_name}")
        return {
            "status": status,
            "collection_name": collection_name,
            "message": f"Collection {status}",
        }

    def upsert_vectors(
        self,
        ids: list[str],
        vectors: np.ndarray,
        urls: list[str],
    ) -> int:
        """Upsert image vectors into the configured collection."""
        if not self._client:
            self.connect()

        if not ids:
            return 0

        points = []
        for image_id, vector, url in zip(ids, vectors, urls):
            point_id = str(uuid5(NAMESPACE_URL, image_id))
            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=vector.tolist(),
                    payload={
                        "id": image_id,
                        "url": url,
                        "instance": self.settings.instance_name,
                    },
                )
            )

        self._client.upsert(
            collection_name=self.settings.qdrant_collection,
            points=points,
        )
        return len(points)

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 10,
        threshold: Optional[float] = None,
    ) -> list[dict]:
        """Search for nearest vectors in the configured collection."""
        if not self._client:
            self.connect()

        results = self._client.query_points(
            collection_name=self.settings.qdrant_collection,
            query=query_vector.tolist(),
            limit=top_k,
            score_threshold=threshold,
            with_payload=True,
        )

        return [
            {
                "id": hit.payload.get("id"),
                "url": hit.payload.get("url"),
                "score": hit.score,
                "rank": index + 1,
            }
            for index, hit in enumerate(results.points)
        ]

    def search_batch(
        self,
        query_vectors: np.ndarray,
        top_k: int = 10,
        threshold: Optional[float] = None,
    ) -> list[list[dict]]:
        """Search for nearest vectors for multiple query vectors."""
        if not self._client:
            self.connect()

        requests = [
            models.QueryRequest(
                query=vector.tolist(),
                limit=top_k,
                score_threshold=threshold,
                with_payload=True,
            )
            for vector in query_vectors
        ]

        batch_results = self._client.query_batch_points(
            collection_name=self.settings.qdrant_collection,
            requests=requests,
        )

        all_results = []
        for result in batch_results:
            all_results.append(
                [
                    {
                        "id": hit.payload.get("id"),
                        "url": hit.payload.get("url"),
                        "score": hit.score,
                        "rank": index + 1,
                    }
                    for index, hit in enumerate(result.points)
                ]
            )

        return all_results

    def count(self) -> int:
        """Return the vector count for the configured collection."""
        if not self._client:
            self.connect()

        try:
            info = self._client.get_collection(self.settings.qdrant_collection)
            return info.points_count
        except Exception:
            return 0

    def existing_payload_ids(self, ids: list[str]) -> set[str]:
        """Return image ids that already exist in the collection."""
        if not self._client:
            self.connect()

        clean_ids = [str(item or "").strip() for item in ids if str(item or "").strip()]
        if not clean_ids:
            return set()

        point_ids = [str(uuid5(NAMESPACE_URL, item)) for item in clean_ids]
        points = self._client.retrieve(
            collection_name=self.settings.qdrant_collection,
            ids=point_ids,
            with_payload=True,
            with_vectors=False,
        )

        existing = set()
        for point in points:
            payload = point.payload or {}
            image_id = str(payload.get("id") or "").strip()
            if image_id:
                existing.add(image_id)
        return existing

    def collection_exists(self) -> bool:
        """Return whether the configured collection exists."""
        if not self._client:
            self.connect()

        try:
            collections = self._client.get_collections().collections
            return any(collection.name == self.settings.qdrant_collection for collection in collections)
        except Exception:
            return False


vector_db = VectorDBService()

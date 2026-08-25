"""SigLIP2 image embedding service."""

from typing import Optional

import numpy as np
import torch
from loguru import logger
from PIL import Image
from transformers import AutoModel, AutoProcessor

from app.core.config import get_settings


class EmbeddingService:
    """Load the image model and produce normalized image embeddings."""

    def __init__(self):
        self.settings = get_settings()
        self.model: Optional[AutoModel] = None
        self.processor: Optional[AutoProcessor] = None
        self._loaded = False

    def load_model(self):
        """Load the configured model onto CUDA when available."""
        if self._loaded:
            return

        logger.info(f"Loading model: {self.settings.model_name}")

        try:
            self.processor = AutoProcessor.from_pretrained(
                self.settings.model_name,
                trust_remote_code=True,
                local_files_only=self.settings.model_local_files_only,
            )
            self.model = AutoModel.from_pretrained(
                self.settings.model_name,
                trust_remote_code=True,
                local_files_only=self.settings.model_local_files_only,
            )

            if self.settings.device == "cuda" and torch.cuda.is_available():
                self.model = self.model.to("cuda")
                logger.info(f"Model loaded on GPU: {torch.cuda.get_device_name(0)}")
            else:
                self.model = self.model.to("cpu")
                logger.info("Model loaded on CPU")

            self.model.eval()
            self._loaded = True
            logger.info(f"Model ready, vector dimension={self.settings.vector_dimension}")

        except Exception as exc:
            logger.error(f"Model load failed: {exc}")
            raise

    def unload_model(self):
        """Unload the model and release CUDA cache when available."""
        if self.model:
            del self.model
            self.model = None
        if self.processor:
            del self.processor
            self.processor = None

        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        self._loaded = False
        logger.info("Model unloaded")

    @torch.no_grad()
    def get_embedding(self, image: Image.Image) -> np.ndarray:
        """Return one normalized embedding vector for a PIL image."""
        if not self._loaded:
            self.load_model()

        inputs = self.processor(images=image, return_tensors="pt")
        device = next(self.model.parameters()).device
        inputs = {key: value.to(device) for key, value in inputs.items()}

        outputs = self.model.get_image_features(**inputs)
        embedding = outputs[0].cpu().numpy()
        return embedding / np.linalg.norm(embedding)

    @torch.no_grad()
    def get_embeddings_batch(self, images: list[Image.Image]) -> np.ndarray:
        """Return normalized embedding vectors for multiple PIL images."""
        if not self._loaded:
            self.load_model()

        if not images:
            return np.array([])

        inputs = self.processor(images=images, return_tensors="pt", padding=True)
        device = next(self.model.parameters()).device
        inputs = {key: value.to(device) for key, value in inputs.items()}

        outputs = self.model.get_image_features(**inputs)
        embeddings = outputs.cpu().numpy()
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        return embeddings / norms

    @property
    def is_loaded(self) -> bool:
        """Return whether the model has been loaded."""
        return self._loaded

    @property
    def device(self) -> str:
        """Return the active model device."""
        if self._loaded and self.model:
            return str(next(self.model.parameters()).device)
        return "not_loaded"


embedding_service = EmbeddingService()

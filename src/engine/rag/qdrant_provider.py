import os
from typing import Optional
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

import time

_QDRANT_INSTANCES: dict[str, QdrantClient] = {}
_EMBEDDING_MODELS: dict[tuple[str, str], SentenceTransformer] = {}


def get_shared_qdrant_client(
    path: str = "qdrant_data",
    max_retries: int = 5,
    retry_delay: float = 0.5
) -> QdrantClient:
    """Returns a singleton QdrantClient per directory path to prevent portalocker file lock conflicts."""
    abs_path = os.path.abspath(path)
    if abs_path not in _QDRANT_INSTANCES:
        for attempt in range(max_retries):
            try:
                _QDRANT_INSTANCES[abs_path] = QdrantClient(path=path)
                break
            except RuntimeError as e:
                if "already accessed" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    raise
    return _QDRANT_INSTANCES[abs_path]


def close_shared_qdrant_client(path: str = "qdrant_data") -> None:
    """Closes and removes the shared QdrantClient for the given directory path."""
    abs_path = os.path.abspath(path)
    client = _QDRANT_INSTANCES.pop(abs_path, None)
    if client is not None:
        try:
            client.close()
        except Exception:
            pass


def _cleanup_all_qdrant_clients():
    for client in list(_QDRANT_INSTANCES.values()):
        try:
            client.close()
        except Exception:
            pass
    _QDRANT_INSTANCES.clear()


import atexit
atexit.register(_cleanup_all_qdrant_clients)



def get_shared_embedding_model(
    model_name: str = "Qwen/Qwen3-Embedding-0.6B",
    device: str = "cuda"
) -> SentenceTransformer:
    """Caches the embedding model in memory so it is only loaded once across components."""
    key = (model_name, device)
    if key not in _EMBEDDING_MODELS:
        _EMBEDDING_MODELS[key] = SentenceTransformer(model_name, device=device)
    return _EMBEDDING_MODELS[key]

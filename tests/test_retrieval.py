import os

os.environ.setdefault("EMBEDDING_PROVIDER", "mock")
os.environ.setdefault("EMBEDDING_DIMENSION", "8")

from app.services.embedding_service import MockEmbeddingProvider
from app.config import Settings


def test_mock_embedding_dimension():
    settings = Settings(embedding_dimension=8, embedding_provider="mock")
    provider = MockEmbeddingProvider(settings)
    vectors = provider.embed_texts(["test"])
    assert len(vectors) == 1
    assert len(vectors[0]) == 8

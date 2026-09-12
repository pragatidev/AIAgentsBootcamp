"""Deterministic 768-dim embedder for pytest. Not a live model."""

from __future__ import annotations


class FakeEmbedder:
    dims = 768

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)

    def __call__(self, texts: list[str]) -> list[list[float]]:
        return self.embed_documents(texts)

    def _vec(self, text: str) -> list[float]:
        vec = [0.0] * self.dims
        for tok in (text or "").lower().split():
            h = 0
            for ch in tok:
                h = (h * 31 + ord(ch)) % self.dims
            vec[h] += 1.0
        n = sum(x * x for x in vec) ** 0.5
        if n:
            vec = [x / n for x in vec]
        return vec

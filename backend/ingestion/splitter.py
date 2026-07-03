"""Simple, deterministic text splitting for document ingestion.

Chunking is a shared, tenant-agnostic pipeline part (multi-tenant-design.md):
the same strategy runs for every tenant, so it must stay generic rather than
NLP-aware. A fixed-size character window with overlap is intentionally simple
and dependency-free while still giving retrieval reasonably fine-grained,
context-preserving snippets.
"""

# Chosen to keep each chunk comfortably within typical embedding model input
# limits while still giving retrieval fine-grained snippets. Character count is
# used (not tokens) to avoid pulling in a tokenizer dependency for this step.
DEFAULT_CHUNK_SIZE = 500
# ~10% overlap so a sentence split across a chunk boundary is not lost entirely
# from either neighboring chunk's context.
DEFAULT_CHUNK_OVERLAP = 50


def split_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Split ``text`` into fixed-size, overlapping chunks.

    The input is stripped of leading/trailing whitespace first; an empty (or
    whitespace-only) input yields an empty list rather than a single blank
    chunk, so callers can treat "no chunks" as "nothing to ingest".
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and smaller than chunk_size")

    normalized = text.strip()
    if not normalized:
        return []

    chunks: list[str] = []
    step = chunk_size - overlap
    length = len(normalized)
    start = 0
    while start < length:
        end = min(start + chunk_size, length)
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == length:
            break
        start += step
    return chunks

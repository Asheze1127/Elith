"""Boundary-design guarantees, checked at metadata / file-string level.

No live DB is required: we inspect Base.metadata and the migration source so
the tenant-scoping and pgvector guarantees are enforced in CI regardless of DB
availability.
"""

from pathlib import Path

import app.models  # noqa: F401  # register all tables on Base.metadata
from app.core.db import Base
from app.models.chunk import EMBEDDING_DIM

# Business tables that must be directly tenant-scopable via a tenant_id column.
DIRECT_TENANT_TABLES = {
    "tenant_config",
    "workspace",
    "document",
    "chunk",
    "answer",
    "feedback",
}

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations" / "versions"


def _table(name: str):
    return Base.metadata.tables[name]


def test_all_expected_tables_exist() -> None:
    expected = {
        "tenant",
        "tenant_config",
        "workspace",
        "document",
        "chunk",
        "answer",
        "citation",
        "feedback",
    }
    assert expected <= set(Base.metadata.tables.keys())


def test_business_tables_have_tenant_id_column() -> None:
    for name in DIRECT_TENANT_TABLES:
        columns = _table(name).columns
        assert "tenant_id" in columns, f"{name} must carry tenant_id for scoping"


def test_tenant_id_is_a_foreign_key_to_tenant() -> None:
    for name in DIRECT_TENANT_TABLES:
        col = _table(name).columns["tenant_id"]
        targets = {fk.column.table.name for fk in col.foreign_keys}
        assert "tenant" in targets, f"{name}.tenant_id must reference tenant.id"


def test_tenant_config_is_one_per_tenant() -> None:
    # The tenant boundary requires exactly one config row per tenant.
    col = _table("tenant_config").columns["tenant_id"]
    assert col.unique is True


def test_citation_is_scopable_via_answer() -> None:
    # Citation deliberately has no direct tenant_id; its boundary is answer_id
    # (permission-design.md §3). It must be reachable to answer, which is
    # tenant-scoped.
    citation = _table("citation")
    assert "tenant_id" not in citation.columns
    answer_fk_targets = {
        fk.column.table.name for fk in citation.columns["answer_id"].foreign_keys
    }
    assert "answer" in answer_fk_targets
    assert "tenant_id" in _table("answer").columns


def test_chunk_embedding_dimension_is_768() -> None:
    # Gemini text-embedding-004 dimension; must not drift from the model.
    assert EMBEDDING_DIM == 768
    embedding = _table("chunk").columns["embedding"]
    # pgvector's Vector type exposes its dimension as .dim.
    assert getattr(embedding.type, "dim", None) == 768


def _initial_migration_source() -> str:
    files = [
        p
        for p in MIGRATIONS_DIR.glob("*.py")
        if not p.name.startswith("__")
    ]
    assert files, "expected at least one migration file"
    # The initial migration is the one with down_revision = None.
    for path in files:
        text = path.read_text(encoding="utf-8")
        if "down_revision: Union[str, Sequence[str], None] = None" in text:
            return text
    raise AssertionError("no initial migration (down_revision=None) found")


def test_initial_migration_enables_pgvector() -> None:
    source = _initial_migration_source()
    assert "CREATE EXTENSION" in source
    assert "vector" in source


def test_initial_migration_creates_vector_column_with_dim_768() -> None:
    source = _initial_migration_source()
    assert "VECTOR(dim=768)" in source

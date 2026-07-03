"""Seed local A-company sample tenant, config, and FAQ document."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.models.document import Document
from app.models.tenant import Tenant
from app.models.tenant_config import TenantConfig
from ingestion.pipeline import ingest_document

BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = BASE_DIR / "sample_data" / "shinonome_config.json"
FAQ_PATH = BASE_DIR / "sample_data" / "shinonome_faq.txt"
SAMPLE_DOCUMENT_TITLE = "東雲ビジネスサポート ご利用ガイド"


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    faq_content = FAQ_PATH.read_text(encoding="utf-8")

    session = get_sessionmaker()()
    try:
        tenant = session.scalar(select(Tenant).where(Tenant.display_name == config["display_name"]))
        if tenant is None:
            tenant = Tenant(display_name=config["display_name"])
            session.add(tenant)
            session.commit()
            session.refresh(tenant)

        tenant_config = session.scalar(
            select(TenantConfig).where(TenantConfig.tenant_id == tenant.id)
        )
        if tenant_config is None:
            tenant_config = TenantConfig(tenant_id=tenant.id, config=config)
            session.add(tenant_config)
        else:
            tenant_config.config = config
        session.commit()

        existing_document = session.scalar(
            select(Document).where(
                Document.tenant_id == tenant.id,
                Document.title == SAMPLE_DOCUMENT_TITLE,
            )
        )
        if existing_document is None:
            ingest_document(
                session,
                tenant_id=tenant.id,
                title=SAMPLE_DOCUMENT_TITLE,
                content=faq_content,
                source_uri="sample_data/shinonome_faq.txt",
                source_updated_at=datetime(2026, 1, 2, tzinfo=UTC),
            )

        print(f"Seeded Shinonome tenant_id={tenant.id}")
    finally:
        session.close()


if __name__ == "__main__":
    main()

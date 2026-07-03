"""Shared RAG pipeline package (directory.md): retrieve / pipeline / prompt / steps.

``retrieve`` (#8), the ``pipeline`` orchestrator and ``prompt`` layer (#9) now
exist. The named pipeline steps themselves (stale_warning / contradiction_check
/ ground_check / cite, under ``app.rag.steps``) are still separate, later
issues (#10/#11/#18/#19) -- #9 only builds the registry mechanism they will
register into. This package stays a flat catalog of common parts, never a
per-tenant fork (multi-tenant-design.md).
"""

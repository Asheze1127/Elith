"""Shared RAG pipeline package (directory.md): retrieve / prompt / steps.

Only ``retrieve`` exists so far (#8); the orchestrator, prompt layer, and
named pipeline steps (stale_warning / contradiction_check / ground_check /
cite) are separate, later issues (#9-#12) and are added here incrementally --
this package stays a flat catalog of common parts, never a per-tenant fork
(multi-tenant-design.md).
"""

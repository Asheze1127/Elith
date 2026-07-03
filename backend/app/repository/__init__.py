"""Data access layer: all reads/writes here are scoped by tenant_id.

Keeps DB querying out of the API/ingestion layers so tenant-scoping is
enforced in one place (permission-design.md §3, directory.md).
"""

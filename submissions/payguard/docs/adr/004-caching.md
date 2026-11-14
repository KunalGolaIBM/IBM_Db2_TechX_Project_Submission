# ADR 004: Cache inputs and intelligence, never authorization

Status: accepted.

Use bounded LRU caches with short TTLs for query embeddings, scam playbooks and entity
lookups. Return copies to avoid callers mutating cached evidence. Invalidate entity
entries after reports and upserts; generation tokens prevent stale in-flight refills.
Never cache reports, velocity, final verdicts or payment authorization.

Process-local caching needs no extra service and keeps the offline demonstration simple.
Its trade-off is brief staleness for writes from another process and duplicate cache
misses. At multiple instances, use Redis plus shared invalidation rather than extending
TTLs. Provider identity is part of the embedding cache key; vector spaces must not mix.

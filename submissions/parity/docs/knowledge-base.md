# Knowledge base

## What it does

The knowledge base stores known database differences and verified fixes. Agents search it before they translate or fix. Verified fixes come back as hints. Unverified guesses never come back.

## Embeddings

`src/parity/kb/embeddings.py` holds a deterministic hashing embedder. It makes 384 dim vectors with no model download and no network. The interface matches a sentence transformer embedder, so a neural model can replace it later without changing callers.

## Store

`src/parity/kb/store.py` holds two stores:

- `InMemoryKb` for tests and local runs.
- `Db2Kb` for production. It uses the `known_difference` table with a `VECTOR(384, FLOAT32)` column and `VECTOR_DISTANCE` with COSINE.

Workflow:

1. A fix is verified by execution.
2. It is added as a candidate.
3. A human approves or rejects it.
4. Search returns verified entries only, closest first.

Verified entries cannot be rejected. Unknown titles raise a clear error.

## Search with categories

Hashing embeddings are weak for SQL meaning. Search also accepts a `category` filter. An entry matches when the category word appears in its category field, its source pattern, or its title. The Db2 store fetches three times the limit and then filters, so filtered results still come back full. Use a category such as `aggregate`, `string`, or `limit` when you know the family of the difference.

## Reuse metric

Every store counts searches and hits with `stats()`. The hit rate is the share of searches that found a verified entry. That rate is the reuse metric: fixes found through search instead of from scratch.

## Honest limit

Hashing embeddings are weaker than neural embeddings for SQL meaning. The category filter helps, and the verified only rule is the main defense against bad entries.

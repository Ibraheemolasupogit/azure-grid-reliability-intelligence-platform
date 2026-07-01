# Indexing And Retrieval

The assistant extracts Markdown, JSON, CSV, YAML, and explicitly approved JSONL
content, chunks it deterministically, and builds a local lexical index.

Retrieval uses transparent term scoring with metadata boosts for query category,
component, entity, metric, and reason-code overlap. It uses deterministic
tie-breaking and does not use embeddings or vector databases.

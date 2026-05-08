# EPIC-21 — Light Material Context Search v1

**Status:** Done (2026-05-08)
**PRD references:** §5.1, §9, §13, §25.2
**Depends on:** EPIC-20

## Goal

Add lightweight local retrieval over uploaded lesson materials so lesson plans
and generated exercises can use relevant context without full RAG
infrastructure.

## In scope

- Add `MaterialChunk` or equivalent linked to `SourceMaterial`.
- Split parsed lesson text into bounded chunks with index, text, tags, and
  timestamps.
- Implement local keyword or SQLite search.
- Provide 2-5 relevant chunks to the Learning Engine and AI Exercise Generator
  when available.
- Fall back safely when no chunks exist.

## Out of scope

- LangChain.
- External vector databases.
- Required embeddings or remote retrieval services.

## Acceptance criteria

- Source material can be split and indexed into chunks.
- Chunks can be searched by topic/text/tags with a bounded limit.
- `/today` works with or without chunks.
- Material context can influence at least one prompt when relevant chunks are
  available.

## Verification plan

- Unit tests for splitting, storage, search, context building, and empty
  fallback.
- Live smoke: back up the DB, index the provided lesson material, search for a
  topic, run `/today`, verify context influence, and check logs.

## Notes from implementation

- Added `MaterialChunk` as an additive table linked to `SourceMaterial`.
- New source materials are indexed automatically into bounded local chunks.
- Added local keyword search and context-building helpers without embeddings,
  LangChain, or an external vector database.
- Lesson-mode Learning Engine sessions attach bounded material context to
  metadata and prepend the input step with a short source snippet.
- AI exercise generation payloads can receive the same bounded material
  context.

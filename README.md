# atlas-graph ✅ (Completed: 2026-02-22)

Graph Engine for **PipelineAtlas** — the core normalized CI/CD graph model.

## Purpose

Receives parsed nodes and edges from `atlas-parser`, builds a normalized CI/CD dependency graph, and persists it. Also includes the Documentation Intelligence module for detecting, classifying, and scoring documentation coverage.

## Features

- Graph construction from parsed nodes/edges
- Recursion detection and safe traversal
- Persistence to PostgreSQL
- Export to JSON, GraphML, DOT
- Documentation intelligence (detection, coverage scoring, drift detection)

## Dependencies

- `atlas-sdk` (shared models)
- `psycopg[binary]` (PostgreSQL)
- `redis` (Redis Streams)

## Related Services

Receives from ← `atlas-parser`, `atlas-log-analyzer` (via Redis Streams)
Queried by → `atlas-rule-engine`, `atlas-ai`, `atlas-report`

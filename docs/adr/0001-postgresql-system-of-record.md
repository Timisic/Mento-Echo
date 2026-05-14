# PostgreSQL is the system of record

Status: accepted

Mentor Echo will use PostgreSQL as the single source of truth for participant codes, experiment sessions, assignments, questionnaire responses, scores, dialogue messages, behavior events, audit logs, and export records. The MVP needs recoverable sessions, locked group assignments, immutable questionnaire submissions, reliable admin status views, and reproducible exports; direct CSV/JSONL storage or SQLite would make those guarantees more fragile as the experiment grows.

## Considered Options

- PostgreSQL as primary database.
- SQLite for simpler deployment.
- Direct CSV/JSONL files for fastest prototyping.

## Consequences

Exports are generated views from PostgreSQL, not primary storage. Local development and deployment must include a PostgreSQL instance, but data integrity and operational recovery are simpler.

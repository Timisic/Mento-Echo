# Mentor Echo Documentation Index

This directory contains the Markdown source of truth for the MVP experiment platform.

## Canonical MVP docs

- [MVP specification](./mvp-spec.md) — product scope, flow, backend rules, admin requirements, and acceptance criteria.
- [MVP PRD](./prd/mvp-experiment-platform.md) — GitHub-published product requirements document for implementation planning.
- [Codex goals](./goal/README.md) — execution prompts grouped into practical Codex goal runs.
- [Questionnaire implementation spec](./questionnaire-spec.md) — how the Word questionnaire is interpreted for the MVP.
- [Questionnaire implementation map](./questionnaire-implementation-map.md) — AFK-ready item keys, scales, dimensions, scoring rules, and HITL source-issue resolutions.
- [Data export spec](./data-export-spec.md) — ZIP contents, required files, and analysis dataset shape.
- [Interview decisions](./mvp-interview-decisions.md) — the 15 resolved planning questions from the grill-with-docs session.
- [Domain context](../CONTEXT.md) — glossary and domain relationships.

## Source documents converted from Word

- [研究1-AI对话平台.md](./研究1-AI对话平台.md) — Markdown conversion of `研究1-AI对话平台.docx`.
- [汇总问卷.md](./汇总问卷.md) — Markdown conversion of `汇总问卷.docx`.
- [AI对话实验平台说明.md](./source/AI对话实验平台说明.md) — existing one-page platform note.

## Decisions

Architectural decisions are recorded under [docs/adr](./adr/):

- [0001-postgresql-system-of-record.md](./adr/0001-postgresql-system-of-record.md)
- [0002-react-fastapi-separated-stack.md](./adr/0002-react-fastapi-separated-stack.md)
- [0003-hybrid-assignment-locking.md](./adr/0003-hybrid-assignment-locking.md)
- [0004-versioned-questionnaire-configuration.md](./adr/0004-versioned-questionnaire-configuration.md)
- [0005-sensitive-raw-chat-export-boundary.md](./adr/0005-sensitive-raw-chat-export-boundary.md)

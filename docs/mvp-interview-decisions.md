# MVP Interview Decisions

This file records the resolved answers from the grill-with-docs planning session. These decisions should be treated as the current MVP requirements unless superseded by a later ADR or spec update.

| # | Topic | Decision |
|---:|---|---|
| 1 | MVP scope | Build the full experimental loop: unified entry → participant code → pre-survey → group assignment → AI dialogue → post-survey → logs/export. |
| 2 | Participant identity | Researchers may import participant codes. The platform stores participant codes only, not names; an internal session ID may be generated. |
| 3 | Group assignment | Imported participant rows may include a pre-assigned group. If absent, the platform randomizes on first entry and locks the result. |
| 4 | AI provider | MVP enables one current SOTA model through an API key using an OpenAI-compatible interface; implementation keeps a replaceable provider boundary. |
| 5 | Dialogue completion | Dialogue may end only after at least 6 participant turns and at least 10 minutes. Participant instructions should state this rule. |
| 6 | Resume behavior | A participant can re-enter with the same participant code and resume the same experiment session. |
| 7 | Questionnaire management | Questionnaire definitions are structured configuration, not editable in the MVP admin UI, and must carry a version. |
| 8 | Questionnaire edits | Submitted questionnaires are locked. Only the administrator can reset a stage, and resets must be audited. |
| 9 | Admin permissions | MVP has one researcher administrator account for imports, progress monitoring, resets, exclusions, and exports. |
| 10 | Export format | Export a ZIP with structured files and include an additional complete analysis CSV with participant code plus questionnaire scores. |
| 11 | Progress status | Admin dashboard uses a status machine plus key metrics, but does not need separate “pre-survey in progress” or “post-survey in progress” states. |
| 12 | Behavior logs | Record key experiment events plus technical diagnostics; do not build high-granularity frontend analytics. |
| 13 | Storage | PostgreSQL is the single source of truth. Export files are generated views, not primary storage. |
| 14 | Technology stack | Frontend: React. Backend: FastAPI. Database: PostgreSQL. UI can be upgraded later independently. |
| 15 | Privacy/export | Platform stores no names. Database stores full raw data. Routine analysis export emphasizes scores/status; complete raw chat is exported as a clearly marked sensitive file. |

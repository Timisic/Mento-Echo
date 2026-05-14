# Use React frontend and FastAPI backend

Status: accepted

The MVP will use a separated React frontend, FastAPI backend, and PostgreSQL database. The UI is intentionally simple for MVP, but the frontend is expected to be upgraded later; separating React from FastAPI keeps backend experiment logic stable while allowing later UI iteration.

## Considered Options

- Next.js full-stack implementation.
- React frontend plus FastAPI backend.
- FastAPI with server-rendered templates.

## Consequences

The project has a clearer API boundary and a more replaceable UI, at the cost of slightly more setup than a single full-stack application.

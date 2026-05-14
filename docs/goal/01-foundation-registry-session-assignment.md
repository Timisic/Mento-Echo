# Goal 01: Foundation, Participant Registry, Session, and Assignment

## GitHub issues

Implement and satisfy:

- https://github.com/Timisic/Mento-Echo/issues/2
- https://github.com/Timisic/Mento-Echo/issues/3
- https://github.com/Timisic/Mento-Echo/issues/4
- https://github.com/Timisic/Mento-Echo/issues/5

## Target result

Create the first working vertical platform: React frontend, FastAPI backend, PostgreSQL database, admin import, participant code entry, recoverable Experiment Session, admin status foundation, and locked imported/randomized Group Assignment.

## Read first

- `CONTEXT.md`
- `docs/prd/mvp-experiment-platform.md`
- `docs/mvp-spec.md`
- `docs/adr/0001-postgresql-system-of-record.md`
- `docs/adr/0002-react-fastapi-separated-stack.md`
- `docs/adr/0003-hybrid-assignment-locking.md`
- GitHub Issues #2, #3, #4, #5

## Scope

Build the end-to-end tracer path through all layers:

1. React app can call FastAPI.
2. FastAPI can reach PostgreSQL.
3. Admin can sign in using the MVP single-admin model.
4. Admin can import participant codes with optional `assigned_group`.
5. Participant can enter with a known code.
6. Backend creates/resumes exactly one active Experiment Session per Participant Code.
7. Backend enforces the canonical session status machine foundation.
8. Imported assignments are honored; blank assignments randomize once and lock.
9. Admin can see participant/session/assignment status.
10. Import, code entry, resume, and assignment events have basic audit/behavior records.

## Constraints

- Store participant codes only; do not store participant names.
- PostgreSQL is the system of record.
- Keep UI simple; prioritize correctness and observability.
- Do not implement questionnaire rendering or AI calls in this goal except placeholders needed for status flow.

## Validation evidence

Run and report:

- Backend tests for health/database connectivity.
- Frontend smoke/API integration test if test harness exists.
- Participant import tests, including duplicate participant code handling.
- Experiment Session state/resume tests.
- Group Assignment locking/no re-randomization tests.
- Manual or automated demo path: admin import → participant code entry → session visible in admin → assignment locked.

## Stop condition

Stop when Issues #2-#5 acceptance criteria are satisfied or when a real blocker is documented with exact failing command/output.

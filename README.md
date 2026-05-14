# Mentor Echo MVP Platform

Mentor Echo is a React + FastAPI + PostgreSQL experiment platform for an AI dialogue study about university students' identity formation.

## Local setup

1. Start PostgreSQL:

   ```bash
   docker compose up -d db
   ```

2. Install backend dependencies and run the initial migration:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install -e 'backend[dev]'
   cd backend
   DATABASE_URL=postgresql+pg8000://mentor_echo:mentor_echo@localhost:5432/mentor_echo alembic upgrade head
   cd ..
   ```

3. Start the FastAPI backend:

   ```bash
   source .venv/bin/activate
   uvicorn app.main:app --app-dir backend --reload
   ```

4. Install and start the React frontend:

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

The frontend defaults to `http://localhost:5173` and calls the backend at `http://localhost:8000`.

## Verification commands

With PostgreSQL running:

```bash
source .venv/bin/activate
pytest backend
cd frontend && npm test -- --run
```

For the full researcher pilot gate, use the command sequence in
[`docs/pilot-readiness-check.md`](docs/pilot-readiness-check.md).

## Configuration

Copy `.env.example` to `.env` for local overrides. The MVP uses a single researcher administrator account controlled by `ADMIN_USERNAME`, `ADMIN_PASSWORD`, and `ADMIN_TOKEN`. Do not commit real credentials, participant names, or provider API keys.

## Implemented foundation slice

- FastAPI health endpoints verify app and PostgreSQL connectivity.
- React renders backend/database health from a real API call.
- Researcher administrator can sign in and import participant codes with optional `assigned_group` (`experiment` or `control`).
- Participant entry accepts known participant codes, rejects unknown codes neutrally, creates/resumes one recoverable Experiment Session, and logs behavior events.
- Group Assignment honors imported assignments, randomizes blank assignments once, records `assignment_source`, and locks the result.
- Admin status API exposes participant code, session status, group, assignment source, timestamps, resume count, and last seen time.
- Versioned pre/post questionnaires render from `mentor_echo_questionnaire_v2026_05_14_hitl_map`, lock on submission, store raw response metadata, and compute derived scores plus attention-check status.
- AI Dialogue starts only after pre-survey submission and locked assignment, selects the experiment/control prompt, stores participant and assistant messages with provider/model/prompt metadata, and enforces 10 participant turns plus 15 elapsed minutes before post-survey access.
- Researcher admin operations include pilot dashboard fields, audited pre-survey reset, audited exclusion, and export ZIP generation with a separated sensitive raw chat JSONL plus routine `analysis_dataset.csv`.

# Local pilot-readiness check

Use this sequence before a researcher pilot. It validates the PostgreSQL-backed
admin dashboard, reset/exclusion controls, behavior events, audit logs, export
ZIP, privacy boundary, and end-to-end participant flow.

## 1. Start PostgreSQL and apply migrations

```bash
docker compose up -d db

source .venv/bin/activate
cd backend
DATABASE_URL=postgresql+pg8000://mentor_echo:mentor_echo@localhost:5432/mentor_echo \
  alembic upgrade head
cd ..
```

## 2. Run backend regression evidence

Run with the mock AI provider unless you intentionally want paid/live model calls.

```bash
source .venv/bin/activate
AI_PROVIDER_NAME=mock \
AI_MODEL_NAME=mock-mentor-echo \
pytest backend
```

The Goal 03 coverage lives in:

```bash
source .venv/bin/activate
AI_PROVIDER_NAME=mock \
AI_MODEL_NAME=mock-mentor-echo \
pytest backend/tests/test_admin_export_pilot_readiness.py
```

This targeted suite covers:

- dashboard fields for participant code, group, assignment source, status,
  survey completion, turn count, elapsed dialogue minutes, eligibility,
  completion, exclusion, resume count, and last seen;
- reset and exclusion controls with required audit reasons;
- behavior events for entry, survey submission, assignment, dialogue, messages,
  eligibility, completion, export, reset, and exclusion;
- audit logs for import, reset, exclusion, and export;
- export ZIP structure and manifest;
- privacy boundaries: no participant names, no frontend provider secrets, no full
  IP export, and no raw chat in `analysis_dataset.csv`;
- end-to-end flow: import → entry → pre-survey → assignment → chat →
  eligibility → post-survey → dashboard → export.

## 3. Run frontend checks

```bash
cd frontend
npm test -- --run
npm run build
cd ..
```

## 4. Optional live model smoke check

Only run this after `.env` contains the intended provider settings and you accept
that it may call a paid external API.

```bash
source .venv/bin/activate
AI_MAX_TOKENS=16 AI_TEMPERATURE=0 PYTHONPATH=backend python - <<'PY'
from app.ai_provider import OpenAICompatibleProvider
from app.config import get_settings

s = get_settings()
result = OpenAICompatibleProvider(s).generate(
    system_prompt="你是一个健康检查助手。只按用户要求输出，不要额外解释。",
    messages=[{"role": "user", "content": "请只回复：OK"}],
)
print({"provider": result.provider_name, "model": result.model_name, "response": result.content})
PY
```

Never print or commit `AI_API_KEY`, `ADMIN_PASSWORD`, `ADMIN_TOKEN`, exported raw
chat, or researcher-held name-to-code rosters.

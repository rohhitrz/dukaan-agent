# Dukaan Agent

Customer support agent for a fake Indian online store. A learning project for
tracing, evals and guardrails - see `PLAN.md` for the phases and `LOG.md` for what
each phase actually changed.

## Run it

```bash
cp .env.example .env     # then paste your OpenAI key into it
uv sync
uv run uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 and try *"can I return order 1042?"*.

The DB is created from `data/seed.sql` on first run. Delete `data/dukaan.db` to
start over (useful after the agent has issued test refunds).

Set `LOG_LEVEL=DEBUG` in `.env` for the noisier version of the loop.

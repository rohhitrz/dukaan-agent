# Dukaan Agent

A small customer support agent for a fake Indian online store, built to learn
**tracing → evals → guardrails** hands-on, measuring before vs after at every step.

The point isn't the agent. The point is being able to explain, from my own traces and
eval scores, what each observability feature actually changed and why.

> **Status:** Phase 1 complete (tracing with self-hosted Langfuse). See [`LOG.md`](LOG.md)
> for what each phase changed and [`PLAN.md`](PLAN.md) for where it's going.

## Why it's built this way

- **No agent framework.** The tool-calling loop in [`app/agent.py`](app/agent.py) is
  ~130 lines written by hand against the OpenAI SDK. When a span shows up in a trace
  later, it's code I wrote - nothing is hidden behind a framework abstraction.
- **BM25, not embeddings,** for policy search. Retrieval isn't the subject here, but
  grounding still needs a source.
- **No guardrails in the baseline.** `issue_refund` will write any amount for any
  order if the model asks it to. That's deliberate: it's the "before" that Phase 4
  gets measured against.
- **Spans are hand-written too.** No auto-instrumentation wrapper around the OpenAI
  client - each span in [`app/agent.py`](app/agent.py) is a `with` block, so the
  trace tree and the control flow are the same thing.

## The agent

Four tools, defined in [`app/tools.py`](app/tools.py):

| Tool | What it does |
| ---- | ------------ |
| `get_order(order_id)` | Status, items, amount, dates, existing refunds |
| `search_policy(query)` | Top BM25 chunks from six policy docs |
| `issue_refund(order_id, amount, reason)` | Writes a refund row |
| `escalate_to_human(summary)` | Logs a ticket |

Conversation history is kept in memory per `session_id`. The UI renders every LLM
call (latency, tokens, finish reason) and every tool call (args, full result) inline
under the reply, plus a link to the full trace.

## Tracing

Every user turn is one Langfuse trace, with a span per LLM call, per tool call and
for the BM25 retrieval:

```
chat-turn                      agent        4.31s
  |- llm step=0                generation   1.52s  $0.000071
  |- tool get_order            tool         0.00s
  |- llm step=1                generation   1.19s  $0.000090
  |- tool search_policy        tool         0.00s
  |    +- policy_search bm25   retriever    0.00s
  +- llm step=2                generation   1.57s  $0.000150
```

Traces sharing a `session_id` are grouped into one session, so a whole conversation
reads as a single thing with its own token and cost totals. Cost is computed by
Langfuse from its own pricing table.

## Run it

```bash
cp .env.example .env     # add your OpenAI key
uv sync

docker compose up -d     # Langfuse; ~2 min on first boot
uv run uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000> and try *"can I return order 1042?"*, then follow the
**trace** link under the reply.

Langfuse is at <http://localhost:3100> (`dev@dukaan.local` / `dukaan-local-dev` -
local throwaway credentials, created on first boot by the `LANGFUSE_INIT_*` block in
[`docker-compose.yml`](docker-compose.yml)). Ports are shifted off the Langfuse
defaults so a second Langfuse on `:3000` can keep running alongside it.

`docker compose down` stops it; add `-v` to wipe the traces too. The app runs fine
with the stack down - without the keys, tracing turns itself off and every span
becomes a no-op.

The SQLite DB is built from [`data/seed.sql`](data/seed.sql) on first run - 20 orders
seeded to cover the interesting cases (already refunded, still processing, outside the
return window, COD, above the escalation threshold). Delete `data/dukaan.db` to reset
after the agent has issued test refunds.

### Config

| Variable | Notes |
| -------- | ----- |
| `OPENAI_API_KEY` | required |
| `OPENAI_MODEL` | default `gpt-6-luna` |
| `OPENAI_REASONING_EFFORT` | must be `none` for reasoning models - they reject function tools in `/v1/chat/completions` otherwise. Leave blank to send nothing. |
| `MAX_TOOL_ITERATIONS` | loop safety net, default 6 |
| `LOG_LEVEL` | `DEBUG` for the full loop |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | from `docker-compose.yml`. Blank disables tracing. |
| `LANGFUSE_HOST` | default `http://localhost:3100` |
| `LANGFUSE_ENVIRONMENT` / `LANGFUSE_RELEASE` | Langfuse filters by the first, groups by the second - one project can hold every phase |
| `PRICE_PER_1M_INPUT` / `PRICE_PER_1M_OUTPUT` | USD. Only needed when Langfuse doesn't know the model's price; it knows `gpt-6-luna`, so these stay 0 |

## Phases

| | Phase | State |
| - | ----- | ----- |
| 0 | Baseline agent, no observability | done |
| 1 | Tracing with self-hosted Langfuse | done |
| 2 | Failure hunt via `CHAOS_MODE` injection | next |
| 3 | Offline evals - hand-written dataset, code + LLM-judge scorers | |
| 4 | Guardrails (input / tool-level / output), re-run the same evals | |
| 5 | Online signals - 👍/👎 → scores, judge on live traces | |
| 6 | Change one thing, see if evals catch the regression | |

## Layout

```
app/
  main.py          FastAPI app + routes
  agent.py         the tool-calling loop
  tools.py         four tools + their JSON schemas
  policy_search.py BM25 over the policy docs
  tracing.py       Langfuse client + span helpers
  db.py            SQLite
data/
  seed.sql         20 orders
  policies/        six policy docs
static/index.html  chat UI, shows the loop inline
docker-compose.yml self-hosted Langfuse
evals/             Phase 3
```

## Stack

Python 3.12+ · FastAPI · OpenAI SDK · SQLite · `rank_bm25` · Langfuse (self-hosted) · uv · vanilla JS

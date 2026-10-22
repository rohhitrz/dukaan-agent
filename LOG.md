# Log

## Phase 0 - Baseline agent (no observability)

**Date:** 2026-10-23

### What changed

Built the whole thing from an empty folder:

- `app/main.py` - FastAPI, `POST /chat`, `POST /reset`, `GET /health`, serves the UI at `/`
- `app/agent.py` - the tool-calling loop by hand (OpenAI Chat Completions), in-memory history per `session_id`, capped at `MAX_TOOL_ITERATIONS=6`
- `app/tools.py` - `get_order`, `search_policy`, `issue_refund`, `escalate_to_human`, plus the JSON schemas the model sees
- `app/policy_search.py` - BM25 over the 6 policy files
- `app/db.py` + `data/seed.sql` - SQLite, 20 orders, 23 line items, `refunds` and `tickets` tables
- `static/index.html` - one page, shows each LLM call and tool call inline under the reply
- Model: `gpt-6-luna` (set in `.env`, one line to swap)

**Gotcha that cost a first run:** `gpt-6-luna` is a reasoning model, and
`/v1/chat/completions` rejects function tools whenever a reasoning effort is in
play - even the model's own default, which we never set. Fix was to send
`reasoning_effort="none"` explicitly (`OPENAI_REASONING_EFFORT` in `.env`; left
blank, nothing is sent). The other way out is the Responses API, which is the
Phase 0 design decision we'd be reversing. Worth knowing that "none" means the
model isn't reasoning before it picks tools - if tool selection looks sloppy in
Phase 3, this knob is a suspect.

Deliberately **no** guardrails: `issue_refund` will write any amount for any order id if the model asks. That is the baseline Phase 4 gets measured against.

Seeded cases worth knowing about:

| Order | Why it's there |
| ----- | -------------- |
| 1042 | delivered shoes - 14 day window, the clean refund path |
| 1044 | `processing` - should be cancelled, not refunded |
| 1049 | already refunded once - policy says escalate |
| 1050 | COD + shipped - refund needs human handling |
| 1054 | Rs 12,499 - above the damaged-item escalation threshold |
| 1058 | delivered 3 Sep - far outside the return window |

### Before vs after

No before. This is the baseline.

Observability right now = `logging.info` lines in the terminal and the trace list the UI renders. Each `/chat` response carries `trace` (every LLM call with latency + tokens, every tool call with args and result), `latency_ms` and `steps`.

### The "debug one wrong answer using only logs" check

_(to fill in after using it - that's the point of the exercise)_

- Wrong answer I hit:
- What I had to do to find the cause:
- What the logs could not tell me:

### First real conversation (3 turns, one session)

| Turn | Tools called | Steps | Latency |
| ---- | ------------ | ----- | ------- |
| "where is my order 1043" | `get_order`, `search_policy` | 3 | 11.9s |
| "can I return it when it arrives?" | `search_policy` | 2 | 3.0s |
| "actually just cancel it" | `search_policy`, `get_order` | 3 | 7.6s |

Memory held: turn 2 and 3 never repeated the order id, and the agent kept calling
Meera by name. Turn 3 correctly refused to cancel a `shipped` order and offered
refuse-delivery instead. Token count grew 615 -> 2,304 across three turns, because
every tool result stays in the history forever.

### One surprising thing

BM25 is more literal than it feels. "can I return shoes after 10 days" ranks `cancellations.md` **above** `returns_window.md`, because "return" appears in the cancellations text too and nothing in the query matches the word "window". Keyword search has no idea that "10 days" is the thing that matters. Worth remembering when Phase 3 shows ungrounded answers - the retrieval may be the culprit, not the model.

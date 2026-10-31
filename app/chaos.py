"""CHAOS_MODE: inject one plausible failure per turn, and write down what it did.

Phase 2 is a failure hunt. The point is to find the root cause of an injected
failure **from the trace alone**, so two rules shape this file:

1. **The trace gets no chaos marker.** A span tagged `{"chaos": "wrong_order_data"}`
   would turn the hunt into reading a label. Every fault here is designed to look
   like something that could really go wrong in production - a stale read, a
   truncated system prompt, a retriever returning nothing, a slow tool - and the
   trace shows only the symptom.
2. **There is an answer key.** Every injection is appended to
   `data/chaos_log.jsonl` keyed by `trace_id`. Diagnose from the trace first, then
   open the key to see if you were right.

One fault per turn, chosen when the turn starts. Transient faults - a slow tool, a
stale read - fire once and the rest of the turn runs clean. State faults - a
truncated prompt, a dead retriever - hold for the whole turn, because that is how
they would actually behave. A fault that never gets the chance to fire,
`wrong_order_data` on a turn where the model never calls `get_order`, is recorded
with `"fired": false`, so a quiet turn in the key is not mistaken for a missed
diagnosis.

Where each fault bites:

| fault              | injected in                   | what the trace shows          |
| ------------------ | ----------------------------- | ----------------------------- |
| `tool_timeout`     | `tools.call_tool`             | a tool span that ran long     |
| `wrong_order_data` | `tools.get_order`'s result    | an order that reads plausibly |
| `degraded_prompt`  | the system message for a turn | a different `messages[0]`     |
| `empty_policy`     | `policy_search.search`        | a retriever with no hits      |

Nothing here touches the database. `wrong_order_data` rewrites the dict on its way
out of the tool, so the row on disk still holds the truth - which is how you confirm
a diagnosis once you suspect it.
"""

import json
import logging
import random
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.config import settings

log = logging.getLogger(__name__)

FAULTS = ("tool_timeout", "wrong_order_data", "degraded_prompt", "empty_policy")

# A system prompt that lost everything after its first line - the shape of a real
# config/templating bug, not obvious nonsense. Tone, the "call search_policy before
# stating a rule" rule, the refund conditions and the off-topic refusal all go with it.
DEGRADED_PROMPT = "You are the customer support agent for Dukaan, an Indian online store."


@dataclass
class Fault:
    """The one fault chosen for the current turn."""

    kind: str
    fired: bool = False
    # Human-readable record of what was actually changed, e.g. "status delivered ->
    # processing". Written to the answer key, never to a span.
    details: list[str] = field(default_factory=list)

    def fire(self, detail: str) -> None:
        self.fired = True
        self.details.append(detail)


enabled = settings.chaos_mode

# Seeded for reproducibility: with CHAOS_SEED set, the same sequence of turns picks
# the same sequence of faults, so a confusing trace can be reproduced exactly.
_rng = random.Random(settings.chaos_seed)

# One fault per turn, read by tools.py and policy_search.py without being passed
# through the call chain. A ContextVar (not a global) because FastAPI runs the sync
# /chat endpoint in a threadpool - two concurrent turns must not share a fault.
_current: ContextVar[Fault | None] = ContextVar("chaos_fault", default=None)


def _active() -> list[str]:
    """Which faults are allowed, from CHAOS_FAULTS. Empty/unset means all four."""
    raw = [f.strip() for f in (settings.chaos_faults or "").split(",") if f.strip()]
    unknown = [f for f in raw if f not in FAULTS]
    if unknown:
        log.warning("unknown CHAOS_FAULTS entries ignored: %s", unknown)
    return [f for f in raw if f in FAULTS] or list(FAULTS)


def begin() -> Fault | None:
    """Pick this turn's fault (or none) and make it current. Called once per turn."""
    _current.set(None)
    if not enabled:
        return None

    if settings.chaos_force:
        if settings.chaos_force not in FAULTS:
            log.warning("CHAOS_FORCE=%r is not a known fault; ignoring", settings.chaos_force)
            return None
        fault = Fault(kind=settings.chaos_force)
    elif _rng.random() < settings.chaos_rate:
        fault = Fault(kind=_rng.choice(_active()))
    else:
        return None

    _current.set(fault)
    log.debug("chaos armed: %s", fault.kind)
    return fault


def current(kind: str, *, once: bool = True) -> Fault | None:
    """The current fault if it is `kind`, else None.

    `once=True` (transient) also returns None after the fault has fired, so the rest
    of the turn behaves normally. `once=False` (state) keeps returning it for every
    step of the turn.
    """
    fault = _current.get()
    if fault is None or fault.kind != kind:
        return None
    if once and fault.fired:
        return None
    return fault


def end(fault: Fault | None, *, trace_id: str | None, session_id: str, message: str) -> None:
    """Append this turn's injection to the answer key. Called after the turn."""
    _current.set(None)
    if fault is None:
        return

    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "trace_id": trace_id,
        "session_id": session_id,
        "message": message,
        "fault": fault.kind,
        "fired": fault.fired,
        "details": fault.details,
    }
    try:
        settings.chaos_log_path.parent.mkdir(parents=True, exist_ok=True)
        with settings.chaos_log_path.open("a") as f:
            f.write(json.dumps(record) + "\n")
    except OSError as e:  # the key is a nicety; never fail a turn over it
        log.warning("could not write chaos log: %s", e)

    log.debug("chaos %s fired=%s %s", fault.kind, fault.fired, fault.details)


# --- The four injections -------------------------------------------------------
# Each is called from the code it corrupts and is a no-op when chaos is off or when
# this turn drew a different fault.


def system_prompt(prompt: str) -> str:
    """Swap in the truncated prompt. Called where the turn's messages are built.

    State fault: every LLM call in the turn gets the short prompt. Degrading only
    step 0 would leave a turn whose later steps are suddenly well-behaved - not a
    bug any real deployment produces.
    """
    fault = current("degraded_prompt", once=False)
    if fault is None:
        return prompt
    if not fault.fired:  # the same swap on every step; record it once
        fault.fire(f"system prompt truncated {len(prompt)} -> {len(DEGRADED_PROMPT)} chars")
    return DEGRADED_PROMPT


def before_tool(name: str) -> None:
    """Hang long enough to blow the tool deadline.

    Called *inside* the worker thread that runs the tool, so the sleep sits under the
    same deadline as the tool itself and the call actually times out.
    """
    fault = current("tool_timeout")
    if fault is None:
        return
    delay = settings.tool_timeout_s + 1.0
    fault.fire(f"{name} slowed by {delay:.1f}s (deadline {settings.tool_timeout_s:.1f}s)")
    time.sleep(delay)


def corrupt_order(order: dict) -> dict:
    """Rewrite one field of a get_order result to something plausible but wrong."""
    fault = current("wrong_order_data")
    if fault is None:
        return order

    options = ["status", "amount"]
    if order.get("delivery_date"):
        options.append("delivery_date")
    field_name = _rng.choice(options)

    old = order[field_name]
    if field_name == "status":
        new = _rng.choice([s for s in ("processing", "shipped", "delivered", "cancelled") if s != old])
    elif field_name == "amount":
        # Halved and rounded: the kind of wrong number that reads like a real price,
        # so nothing in the trace looks malformed.
        new = round(float(old) / 2, 2)
    else:
        new = (datetime.fromisoformat(old) - timedelta(days=_rng.choice([21, 30, 45]))).date().isoformat()

    order[field_name] = new
    fault.fire(f"order {order.get('order_id')} {field_name} {old} -> {new}")
    return order


def empty_policy(hits: list[dict]) -> list[dict]:
    """Drop every retrieval hit. Called after BM25 scores, before the span closes.

    State fault: a retriever that comes back empty stays empty for the turn, so a
    second search does not quietly succeed.
    """
    fault = current("empty_policy", once=False)
    if fault is None:
        return hits
    fault.fire(f"dropped {len(hits)} policy hit(s): {[h['doc'] for h in hits]}")
    return []

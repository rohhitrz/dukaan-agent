"""Langfuse wiring. One trace per user turn, nested spans inside it.

Langfuse is an open-source LLM observability server: you send it spans, it shows
you a tree per request with latency, tokens, cost and the exact input/output of
every step. Self-hosted here via docker-compose.yml.

Under the hood the Python SDK (v5) is OpenTelemetry. Two consequences worth
knowing:

- Nesting is implicit. `start_as_current_observation` makes the new span the
  "current" one for the duration of the `with` block, so anything started inside
  that block - even several files away, like the BM25 span inside
  policy_search.search - becomes its child automatically. Nothing is threaded
  through by hand.
- Export is asynchronous and batched on a background thread, so a span costs
  microseconds in the request path, and the data shows up in the UI a moment
  later. `flush()`/`shutdown()` force it out.

Observation types matter only for display: Langfuse renders `generation` with
token/cost columns, and colours `tool`/`retriever` differently in the tree.

If the Langfuse keys are missing, the client is built with tracing_enabled=False
and every span becomes a no-op, so the app still runs exactly as it did in
Phase 0. Nothing in agent.py needs an `if tracing_on:` branch.
"""

import logging

from langfuse import Langfuse

from app.config import settings

log = logging.getLogger(__name__)

enabled = bool(settings.langfuse_public_key and settings.langfuse_secret_key)

client = Langfuse(
    public_key=settings.langfuse_public_key or "pk-disabled",
    secret_key=settings.langfuse_secret_key or "sk-disabled",
    host=settings.langfuse_host,
    tracing_enabled=enabled,
    # Tags every trace so later phases can be filtered apart in one project.
    environment=settings.langfuse_environment,
    release=settings.langfuse_release,
)

if not enabled:
    log.warning("LANGFUSE_* keys not set - tracing disabled, spans are no-ops")


def check() -> None:
    """Log whether the server accepted our keys. Called once at startup."""
    if not enabled:
        return
    try:
        ok = client.auth_check()
    except Exception as e:  # server down; must not stop the app booting
        log.warning("langfuse unreachable at %s (%s)", settings.langfuse_host, e)
        return
    log.info("langfuse %s at %s", "connected" if ok else "AUTH FAILED", settings.langfuse_host)


def cost_details(prompt_tokens: int | None, completion_tokens: int | None) -> dict | None:
    """Cost in USD for one LLM call, or None to let Langfuse work it out.

    Langfuse computes cost itself from (model, usage) when it recognises the model
    name. It does not recognise every model, so if a per-token price is configured
    we send the cost explicitly instead of leaving the column empty.
    """
    if not (settings.price_per_1m_input or settings.price_per_1m_output):
        return None
    return {
        "input": (prompt_tokens or 0) / 1_000_000 * settings.price_per_1m_input,
        "output": (completion_tokens or 0) / 1_000_000 * settings.price_per_1m_output,
    }


def trace_url(trace_id: str) -> str | None:
    """Deep link to one trace, so the UI can offer "open in Langfuse"."""
    if not enabled:
        return None
    try:
        return client.get_trace_url(trace_id=trace_id)
    except Exception:
        return None


def shutdown() -> None:
    """Flush pending spans and stop the exporter thread. Called on app shutdown."""
    if enabled:
        client.shutdown()

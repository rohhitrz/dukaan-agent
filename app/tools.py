"""The four tools the agent can call, plus their JSON schemas for the OpenAI API.

Each tool is a plain Python function returning a JSON-serialisable dict. Errors are
returned as {"error": ...} rather than raised, so a bad order id gives the model
something to recover from instead of blowing up the request.

Phase 0 deliberately has *no* guardrails here: issue_refund will do whatever it is
told as long as the SQL is valid. That is the baseline Phase 4 gets compared against.
"""

import logging

from app import db

log = logging.getLogger(__name__)


def get_order(order_id: int) -> dict:
    """Look up one order with its line items."""
    with db.connect() as conn:
        order = conn.execute(
            "SELECT * FROM orders WHERE order_id = ?", (order_id,)
        ).fetchone()
        if order is None:
            return {"error": f"No order found with id {order_id}"}

        items = conn.execute(
            "SELECT item_name, quantity, price FROM order_items WHERE order_id = ?",
            (order_id,),
        ).fetchall()
        refunds = conn.execute(
            "SELECT amount, reason, created_at FROM refunds WHERE order_id = ?",
            (order_id,),
        ).fetchall()

    return {
        "order_id": order["order_id"],
        "customer_name": order["customer_name"],
        "status": order["status"],
        "amount": order["amount"],
        "payment_method": order["payment_method"],
        "order_date": order["order_date"],
        "delivery_date": order["delivery_date"],
        "items": [dict(i) for i in items],
        "existing_refunds": [dict(r) for r in refunds],
    }


def search_policy(query: str) -> dict:
    """Top policy chunks for a query."""
    from app import policy_search

    hits = policy_search.search(query)
    if not hits:
        return {"query": query, "results": [], "note": "No policy matched this query."}
    return {"query": query, "results": hits}


def issue_refund(order_id: int, amount: float, reason: str) -> dict:
    """Write a refund row. No policy checks in Phase 0 - that is the point."""
    with db.connect() as conn:
        order = conn.execute(
            "SELECT order_id, amount FROM orders WHERE order_id = ?", (order_id,)
        ).fetchone()
        if order is None:
            return {"error": f"No order found with id {order_id}"}

        cur = conn.execute(
            "INSERT INTO refunds (order_id, amount, reason) VALUES (?, ?, ?)",
            (order_id, amount, reason),
        )
        refund_id = cur.lastrowid

    log.info("REFUND issued: order=%s amount=%s reason=%r", order_id, amount, reason)
    return {
        "refund_id": refund_id,
        "order_id": order_id,
        "amount": amount,
        "status": "issued",
        "note": "Refund will reflect in 5-7 business days.",
    }


def escalate_to_human(summary: str, session_id: str | None = None) -> dict:
    """Log a ticket for a human agent."""
    with db.connect() as conn:
        cur = conn.execute(
            "INSERT INTO tickets (session_id, summary) VALUES (?, ?)",
            (session_id, summary),
        )
        ticket_id = cur.lastrowid

    log.info("ESCALATED: ticket=%s summary=%r", ticket_id, summary)
    return {
        "ticket_id": ticket_id,
        "status": "open",
        "note": "A human agent will reply within 24 hours.",
    }


# --- Schemas sent to the model -------------------------------------------------
# The model only knows what these descriptions say, so the wording here is part of
# the prompt. Phase 6 changes one of these on purpose to see if evals catch it.

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_order",
            "description": "Look up an order by its numeric id. Returns status, items, amount, dates, payment method and any refunds already issued.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "integer", "description": "The order id, e.g. 1042"}
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_policy",
            "description": "Search Dukaan's written policies (refunds, returns window, shipping, cancellations, damaged items, payment issues). Use this before stating any rule to the customer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What you want to know, e.g. 'return window for shoes'"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "issue_refund",
            "description": "Issue a refund for an order. Only call this after checking the order and the refund policy.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "integer"},
                    "amount": {"type": "number", "description": "Amount in rupees"},
                    "reason": {"type": "string", "description": "Short reason for the refund"},
                },
                "required": ["order_id", "amount", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_to_human",
            "description": "Hand the conversation to a human agent. Use when policy requires approval, when the customer is asking for something you cannot do, or when you are unsure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Short summary of the issue for the human agent"}
                },
                "required": ["summary"],
            },
        },
    },
]

REGISTRY = {
    "get_order": get_order,
    "search_policy": search_policy,
    "issue_refund": issue_refund,
    "escalate_to_human": escalate_to_human,
}


def call_tool(name: str, args: dict, session_id: str | None = None) -> dict:
    """Dispatch a tool call by name. Unknown names and bad args come back as errors."""
    fn = REGISTRY.get(name)
    if fn is None:
        return {"error": f"Unknown tool {name!r}"}

    if name == "escalate_to_human":
        args = {**args, "session_id": session_id}

    try:
        return fn(**args)
    except TypeError as e:
        return {"error": f"Bad arguments for {name}: {e}"}
    except Exception as e:  # keep the loop alive; the model can read the error
        log.exception("tool %s failed", name)
        return {"error": f"{type(e).__name__}: {e}"}

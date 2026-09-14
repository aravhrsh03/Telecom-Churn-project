"""
Phase 8, Lab AI2 -- turn the existing API/service-layer functions into tools
Claude can call.

Each tool description is written like a briefing to a new analyst: when to
reach for it, and what it returns. execute_tool() is the single dispatch
point -- it validates arguments against the tool's own JSON Schema
(security/guard.py, CL2's checklist item 2) before calling straight into
churn_service.py / ml/predict.py. No business logic is duplicated here.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import churn_service  # noqa: E402
from config import ASSISTANT_MAX_LIST_ITEMS  # noqa: E402
from ml.predict import predict_churn  # noqa: E402
from security import ToolArgumentError, validate_tool_args  # noqa: E402
from tables3 import SessionLocal  # noqa: E402

TOOLS = [
    {
        "name": "get_customer_profile",
        "description": (
            "Look up one customer's full profile by customer ID -- demographics, "
            "which services they're subscribed to, contract type, billing amounts, "
            "and whether they've already churned. Use this when the user asks about "
            "a specific, named customer (e.g. 'what plan does 7590-VHVEG have', "
            "'is customer 3668-QPYBK still with us'). Returns 404-equivalent (null) "
            "if the ID doesn't exist -- report that honestly, never invent a profile."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "e.g. '7590-VHVEG'"},
            },
            "required": ["customer_id"],
        },
    },
    {
        "name": "get_churn_summary",
        "description": (
            "Get company-wide churn KPIs: total customers, total churned, overall "
            "churn rate, and churn rate broken down by contract type and by internet "
            "service type. Use this for ANY question about overall trends, rates, or "
            "cross-segment comparisons -- never estimate or recall these numbers from "
            "general knowledge, always call this tool."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_high_risk_customers",
        "description": (
            "Get the rule-based list of customers flagged high-risk (month-to-month "
            "contract, under 12 months tenure, above-average monthly charges), each "
            "with a plain-English risk_reason. Use this when asked for customers to "
            "prioritize for retention outreach. Always pass a modest `limit` -- never "
            "ask for or report more than a small number of individual customers."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": ASSISTANT_MAX_LIST_ITEMS, "default": 10},
                "min_tenure": {"type": "integer", "minimum": 0},
                "max_tenure": {"type": "integer", "minimum": 0},
            },
            "required": [],
        },
    },
    {
        "name": "predict_churn",
        "description": (
            "Predict churn risk. Pass customer_id for an EXACT prediction using that "
            "customer's real data -- prefer this whenever a real customer is being "
            "discussed. For a hypothetical 'what if a customer looked like X' question "
            "with no real customer, instead pass tenure, monthly_charges, contract_type "
            "and service_count. The response's `assumptions` field lists anything that "
            "had to be defaulted in hypothetical mode -- you must surface those "
            "assumptions to the user, never present a hypothetical result as exact."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "tenure": {"type": "number", "minimum": 0, "maximum": 100},
                "monthly_charges": {"type": "number", "exclusiveMinimum": 0},
                "contract_type": {"type": "string", "enum": ["Month-to-month", "One year", "Two year"]},
                "service_count": {"type": "integer", "minimum": 0, "maximum": 6},
            },
            "required": [],
        },
    },
]

_TOOLS_BY_NAME = {t["name"]: t for t in TOOLS}


def execute_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Single dispatch point for every tool call. Validates arguments,
    never raises out to the caller -- any failure (bad args, unknown
    customer, a genuine exception) comes back as {"error": "..."} so the
    request loop can hand it back to Claude instead of crashing."""
    tool = _TOOLS_BY_NAME.get(name)
    if tool is None:
        return {"error": f"Unknown tool '{name}'"}

    try:
        validate_tool_args(tool["input_schema"], args, name)
    except ToolArgumentError as e:
        return {"error": str(e)}

    db = SessionLocal()
    try:
        if name == "get_customer_profile":
            profile = churn_service.get_customer_profile(db, args["customer_id"])
            return profile if profile is not None else {"error": f"No customer found with ID {args['customer_id']}"}

        if name == "get_churn_summary":
            return churn_service.get_churn_summary(db)

        if name == "get_high_risk_customers":
            limit = min(args.get("limit", 10), ASSISTANT_MAX_LIST_ITEMS)
            result = churn_service.get_high_risk_customers(
                db, limit=limit, min_tenure=args.get("min_tenure"), max_tenure=args.get("max_tenure")
            )
            return {"count": len(result), "items": result}

        if name == "predict_churn":
            return predict_churn(
                customer_id=args.get("customer_id"),
                tenure=args.get("tenure"),
                monthly_charges=args.get("monthly_charges"),
                contract_type=args.get("contract_type"),
                service_count=args.get("service_count"),
            )

        return {"error": f"Tool '{name}' has a schema but no dispatch implementation"}

    except Exception as e:  # noqa: BLE001 -- a tool must never crash the assistant loop
        return {"error": f"Tool '{name}' raised an error: {e}"}
    finally:
        db.close()

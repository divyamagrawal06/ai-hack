"""Explicit fictional demo configuration; never infer jurisdiction from timezone."""
import os

POLICY_VERSION = "demo-policy-0.3"
DEFAULT_LOCAL_MODEL = "qwen3:4b-instruct"


def local_model():
    return os.environ.get("CLINIC_LOCAL_MODEL", DEFAULT_LOCAL_MODEL)


QUESTIONS = [
    {"id": "CHECK-01", "text": "Severe trouble breathing now"},
    {"id": "CHECK-02", "text": "Severe chest discomfort now"},
    {"id": "CHECK-03", "text": "Sudden trouble speaking or new one-sided weakness"},
    {"id": "CHECK-04", "text": "Uncontrolled heavy bleeding now"},
    {"id": "CHECK-05", "text": "Possible overdose or poisoning now"},
    {"id": "CHECK-06", "text": "Immediate danger of self-harm"},
]


def public_config():
    jev = bool(os.environ.get("TYPESAFE_API_KEY") or os.environ.get("JEV_API_KEY"))
    llm = bool(os.environ.get("CLINIC_LLM_API_KEY") and os.environ.get("CLINIC_LLM_MODEL"))
    return {
        "policy_version": POLICY_VERSION,
        "synthetic_only": True,
        "default_variant": "local_ai",
        "emergency_questions": QUESTIONS,
        "variants": [
            {"id": "local_ai", "label": "Local AI · " + local_model(), "available": True, "reason": "Reads your invented request using a model on this computer. No API key needed."},
            {"id": "no_ai", "label": "Structured intake • no AI", "available": True, "reason": "Staff interpret the narrative."},
            {"id": "replay", "label": "Replay • authored synthetic assessment", "available": True, "reason": "Exact saved fixture, never a live inference."},
            {"id": "jev_direct", "label": "Jev • direct decision with defer", "available": jev, "reason": "Requires a TypeSafe API key in environment settings."},
            {"id": "jev_decomposed", "label": "Jev • focused assessments", "available": jev, "reason": "Requires a TypeSafe API key in environment settings."},
            {"id": "llm", "label": "LLM • structured assessments", "available": llm, "reason": "Requires CLINIC_LLM_API_KEY and CLINIC_LLM_MODEL."},
        ],
        "coverage": {
            "mode": "simulated", "clinic_timezone": "UTC",
            "open": os.environ.get("CLINIC_DEMO_OPEN", "1") == "1",
            "reviewer_available": os.environ.get("CLINIC_DEMO_REVIEWER_AVAILABLE", "1") == "1",
            "description": "Fictional staffing simulation; no real notifications or care service.",
            "alternate_contact": None,
        },
        "jurisdiction": {"configured": False, "emergency_text": "Contact your local emergency services now. Do not wait for this form or a clinic reply."},
        "demo_credentials": {
            "reviewer": {"username": "reviewer", "password": "demo-reviewer"},
            "supervisor": {"username": "supervisor", "password": "demo-supervisor"},
        },
    }

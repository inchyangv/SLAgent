"""LLM policy helpers for SLA judgement and mandate/price negotiation.

This module is intentionally fail-open: if Gemini is unavailable or returns
malformed output, gateway falls back to deterministic rule-based behavior.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from seller.gemini_client import GeminiClient, GeminiError

logger = logging.getLogger("sla-gateway.llm-policy")


def _enabled(flag: str, default: str = "false") -> bool:
    return os.getenv(flag, default).lower() in ("1", "true", "yes", "on")


def _extract_json_obj(raw: str) -> dict[str, Any]:
    text = raw.strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    if "```" in text:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            obj = json.loads(text[start : end + 1])
            if isinstance(obj, dict):
                return obj

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        obj = json.loads(text[start : end + 1])
        if isinstance(obj, dict):
            return obj

    raise ValueError("No JSON object found in LLM output")


def _clamp_int(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def _has_gemini_key() -> bool:
    return bool(os.getenv("GEMINI_API_KEY", ""))


async def evaluate_sla_with_gemini(
    *,
    mandate: dict[str, Any],
    seller_response: dict[str, Any],
    success: bool,
    schema_validation_pass: bool,
    latency_ms: int,
    mode: str = "",
    scenario_tag: str = "",
) -> dict[str, Any] | None:
    """Ask Gemini to evaluate SLA quality and suggest payout.

    Returns a normalized decision object or None when disabled/failed.
    """
    if not _enabled("LLM_POLICY_ENABLED", "false") or not _has_gemini_key():
        return None

    max_price = int(mandate.get("max_price", "0") or 0)
    base_pay = int(mandate.get("base_pay", "0") or 0)

    scenario = (scenario_tag or "").strip().lower()
    prompt = f"""\
You are an SLA adjudicator for autonomous AI-to-AI payments.
Given the request result, decide whether SLA passed and suggest payout.

Input:
- scenario_profile: "{scenario or 'auto'}"  # expected one of happy / slow / breaches / auto
- call_mode: "{mode or 'unknown'}"
- max_price: {max_price}
- base_pay: {base_pay}
- success: {str(success).lower()}
- schema_validation_pass: {str(schema_validation_pass).lower()}
- latency_ms: {latency_ms}
- mandate_bonus_rules: {json.dumps(mandate.get("bonus_rules", {}), ensure_ascii=True)}
- seller_response: {json.dumps(seller_response, ensure_ascii=True)}

Output ONLY JSON:
{{
  "sla_pass": true|false,
  "recommended_payout": <integer between 0 and max_price>,
  "reason": "<short reason>",
  "breach_reasons": ["BREACH_*", ...],
  "confidence": <number between 0 and 1>
}}
"""
    try:
        client = GeminiClient()
        raw = await client.generate(prompt, json_mode=True)
        obj = _extract_json_obj(raw)
    except (GeminiError, ValueError, json.JSONDecodeError) as e:
        logger.warning("LLM SLA evaluation failed, falling back to rules: %s", e)
        return None

    sla_pass = bool(obj.get("sla_pass", schema_validation_pass and success))
    payout_raw = obj.get("recommended_payout")
    payout = None
    if isinstance(payout_raw, (int, float)):
        payout = _clamp_int(int(payout_raw), 0, max_price)

    confidence_raw = obj.get("confidence", 0.0)
    confidence = float(confidence_raw) if isinstance(confidence_raw, (int, float)) else 0.0
    confidence = max(0.0, min(1.0, confidence))

    breach_reasons = obj.get("breach_reasons", [])
    if not isinstance(breach_reasons, list):
        breach_reasons = []
    breach_reasons = [str(x) for x in breach_reasons[:5]]

    # Scenario guardrails for deterministic demo behavior:
    # - happy: bias full payout when basic checks pass
    # - slow: enforce degraded but non-zero payout when basic checks pass
    # - breaches: enforce hard fail + zero payout
    if scenario == "breaches":
        sla_pass = False
        payout = 0
        if "BREACH_SCENARIO_BREACHES" not in breach_reasons:
            breach_reasons.append("BREACH_SCENARIO_BREACHES")
    elif scenario == "happy" and success and schema_validation_pass:
        sla_pass = True
        payout = max_price if payout is None else _clamp_int(max(payout, max_price), 0, max_price)
    elif scenario == "slow" and success and schema_validation_pass:
        floor = max(0, min(base_pay, max_price))
        ceil = max(floor, max_price - 1)
        if payout is None:
            payout = ceil
        payout = _clamp_int(payout, floor, ceil)

    return {
        "mode": "llm",
        "model": os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        "sla_pass": sla_pass,
        "recommended_payout": payout,
        "reason": str(obj.get("reason", ""))[:240],
        "breach_reasons": breach_reasons,
        "confidence": confidence,
    }


async def suggest_mandate_with_gemini(
    *,
    mandate: dict[str, Any],
    seller_capabilities: dict[str, Any] | None = None,
    scenario_tag: str = "",
) -> dict[str, Any] | None:
    """Ask Gemini for SLA/price negotiation suggestions.

    Returns normalized suggested terms or None when disabled/failed.
    """
    if not _enabled("LLM_NEGOTIATION_ENABLED", "false") or not _has_gemini_key():
        return None

    max_price = int(mandate.get("max_price", "0") or 0)
    base_pay = int(mandate.get("base_pay", "0") or 0)
    tiers = mandate.get("bonus_rules", {}).get("tiers", [])

    scenario = (scenario_tag or "").strip().lower()
    prompt = f"""\
You are negotiating SLA terms between buyer and seller agent.
Suggest practical pricing terms that preserve buyer safety.

Input:
- scenario_profile: "{scenario or 'auto'}"  # expected one of happy / slow / breaches / auto
- mandate: {json.dumps(mandate, ensure_ascii=True)}
- seller_capabilities: {json.dumps(seller_capabilities or {{}}, ensure_ascii=True)}

Output ONLY JSON:
{{
  "summary": "<short negotiation summary>",
  "accepted": true|false,
  "counter_terms": {{
    "max_price": <integer>,
    "base_pay": <integer>,
    "tiers": [{{"lte_ms": <int>, "payout": <int>}}]
  }}
}}
"""
    try:
        client = GeminiClient()
        raw = await client.generate(prompt, json_mode=True)
        obj = _extract_json_obj(raw)
    except (GeminiError, ValueError, json.JSONDecodeError) as e:
        logger.warning("LLM mandate negotiation failed: %s", e)
        return None

    counter = obj.get("counter_terms", {})
    if not isinstance(counter, dict):
        counter = {}

    suggested_max = int(counter.get("max_price", max_price) or max_price)
    suggested_base = int(counter.get("base_pay", base_pay) or base_pay)
    suggested_max = max(0, suggested_max)
    suggested_base = _clamp_int(suggested_base, 0, suggested_max if suggested_max > 0 else suggested_base)

    # Scenario-specific negotiation posture.
    if scenario == "breaches":
        # Tighten terms: lower base pay and stricter timeout-oriented tiers.
        suggested_base = _clamp_int(int(suggested_base * 0.6), 0, suggested_max)
    elif scenario == "slow":
        # Keep base pay but avoid full payout as default.
        suggested_base = _clamp_int(int(max(suggested_base, int(0.7 * suggested_max))), 0, suggested_max)
    elif scenario == "happy":
        # Favor full value collaboration posture.
        suggested_base = _clamp_int(int(max(suggested_base, suggested_max)), 0, suggested_max)

    norm_tiers: list[dict[str, str]] = []
    for t in counter.get("tiers", tiers):
        if not isinstance(t, dict):
            continue
        try:
            lte_ms = int(t.get("lte_ms"))
            payout = _clamp_int(int(t.get("payout")), 0, suggested_max)
            norm_tiers.append({"lte_ms": lte_ms, "payout": str(payout)})
        except Exception:
            continue

    # Ensure deterministic order and at least one tier.
    norm_tiers = sorted(norm_tiers, key=lambda x: x["lte_ms"])
    if not norm_tiers:
        norm_tiers = [{"lte_ms": 999999999, "payout": str(suggested_base)}]

    if scenario == "happy":
        norm_tiers = [
            {"lte_ms": 2000, "payout": str(suggested_max)},
            {"lte_ms": 5000, "payout": str(max(suggested_base, int(0.9 * suggested_max)))},
            {"lte_ms": 999999999, "payout": str(max(suggested_base, int(0.8 * suggested_max)))},
        ]
    elif scenario == "slow":
        norm_tiers = [
            {"lte_ms": 2000, "payout": str(max(suggested_base, int(0.9 * suggested_max)))},
            {"lte_ms": 5000, "payout": str(max(suggested_base, int(0.8 * suggested_max)))},
            {"lte_ms": 999999999, "payout": str(max(suggested_base, int(0.7 * suggested_max)))},
        ]
    elif scenario == "breaches":
        norm_tiers = [
            {"lte_ms": 2000, "payout": str(max(0, int(0.7 * suggested_max)))},
            {"lte_ms": 5000, "payout": str(max(0, int(0.5 * suggested_max)))},
            {"lte_ms": 999999999, "payout": str(max(0, int(0.3 * suggested_max)))},
        ]

    return {
        "mode": "llm",
        "model": os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        "accepted": bool(obj.get("accepted", True)),
        "summary": str(obj.get("summary", ""))[:240],
        "suggested_terms": {
            "max_price": str(suggested_max),
            "base_pay": str(suggested_base),
            "bonus_rules": {
                "type": "latency_tiers",
                "tiers": norm_tiers,
            },
        },
    }

import pytest

from gateway.app.llm_policy import evaluate_sla_with_gemini


@pytest.mark.asyncio
async def test_slow_scenario_forces_pass_degraded(monkeypatch):
    monkeypatch.setenv("LLM_POLICY_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    captured = {"prompt": ""}

    async def _fake_generate(self, prompt: str, json_mode: bool = True):  # noqa: ARG001
        captured["prompt"] = prompt
        # Intentionally contradictory response; guardrail must normalize it.
        return (
            '{"sla_pass": false, "recommended_payout": 100000, '
            '"reason": "too slow", "breach_reasons": [], "confidence": 0.7}'
        )

    monkeypatch.setattr("gateway.app.llm_policy.GeminiClient.generate", _fake_generate)

    decision = await evaluate_sla_with_gemini(
        mandate={
            "max_price": "100000",
            "base_pay": "60000",
            "bonus_rules": {"type": "latency_tiers", "tiers": []},
        },
        seller_response={"invoice_id": "INV-1"},
        success=True,
        schema_validation_pass=True,
        latency_ms=4200,
        mode="slow",
        scenario_tag="slow",
    )

    assert decision is not None
    assert "Scenario policy (MUST FOLLOW)" in captured["prompt"]
    assert decision["sla_pass"] is True
    assert int(decision["recommended_payout"]) < 100000
    assert int(decision["recommended_payout"]) >= 60000


@pytest.mark.asyncio
async def test_breaches_scenario_forces_fail_zero(monkeypatch):
    monkeypatch.setenv("LLM_POLICY_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    async def _fake_generate(self, prompt: str, json_mode: bool = True):  # noqa: ARG001
        return (
            '{"sla_pass": true, "recommended_payout": 90000, '
            '"reason": "looks okay", "breach_reasons": [], "confidence": 0.9}'
        )

    monkeypatch.setattr("gateway.app.llm_policy.GeminiClient.generate", _fake_generate)

    decision = await evaluate_sla_with_gemini(
        mandate={"max_price": "100000", "base_pay": "60000"},
        seller_response={"invoice_id": "INV-2"},
        success=True,
        schema_validation_pass=True,
        latency_ms=1000,
        mode="invalid",
        scenario_tag="breaches",
    )

    assert decision is not None
    assert decision["sla_pass"] is False
    assert int(decision["recommended_payout"]) == 0
    assert "BREACH_SCENARIO_BREACHES" in decision["breach_reasons"]

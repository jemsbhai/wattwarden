"""Tests for TomlCpuMeter against the installed pollard 1.5.1 protocol."""

import pytest
from pollard.governor import charge_to_decimal
from pollard.meters import MeterPrecheckRefusal

from wattwarden.meter import TomlCpuMeter
from wattwarden.toml_model import NEOVERSE_N1, QWEN25_1_5B, estimate_energy


def _payload(model="qwen2.5-1.5b-instruct-q4_0", **extra):
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are terse."},
            {"role": "user", "content": "Say hello to the Ampere A1."},
        ],
    }
    payload.update(extra)
    return payload


def _result(input_tokens=120, output_tokens=40, style="normalized"):
    if style == "openai":
        usage = {"prompt_tokens": input_tokens, "completion_tokens": output_tokens}
    else:
        usage = {"input_tokens": input_tokens, "output_tokens": output_tokens}
    return {"usage": usage}


def test_meter_speaks_the_pollard_protocol():
    meter = TomlCpuMeter()
    assert meter.name == "joules"
    assert callable(meter.charge)
    assert callable(meter.precheck_estimate)
    assert meter.precheck_is_estimate is True


def test_charge_ignores_non_model_calls():
    meter = TomlCpuMeter()
    assert meter.charge("tool_call", _payload(), _result(), {}) == 0.0


def test_charge_matches_the_toml_model_exactly():
    meter = TomlCpuMeter()
    charged = meter.charge("model_call", _payload(), _result(120, 40), {})
    expected = estimate_energy(
        QWEN25_1_5B, NEOVERSE_N1, "Q4_0", 120, 40
    ).total_j
    assert charged == pytest.approx(expected)
    assert meter.last_estimate is not None
    assert meter.last_estimate.label == "predicted"


def test_charge_accepts_raw_openai_usage_keys():
    meter = TomlCpuMeter()
    normalized = meter.charge("model_call", _payload(), _result(120, 40), {})
    raw = meter.charge("model_call", _payload(), _result(120, 40, "openai"), {})
    assert raw == pytest.approx(normalized)


def test_quant_is_parsed_from_the_model_name():
    meter = TomlCpuMeter()
    q4 = meter.charge("model_call", _payload("qwen2.5-1.5b-instruct-q4_0"), _result(), {})
    q8 = meter.charge("model_call", _payload("qwen2.5-1.5b-instruct-q8_0"), _result(), {})
    assert q8 > q4


def test_duration_in_meta_adds_static_energy():
    meter = TomlCpuMeter()
    base = meter.charge("model_call", _payload(), _result(), {})
    with_static = meter.charge("model_call", _payload(), _result(), {"duration_s": 2.0})
    assert with_static - base == pytest.approx(NEOVERSE_N1.p_static_w * 2.0)


def test_unknown_model_charges_zero_with_one_warning():
    meter = TomlCpuMeter()
    with pytest.warns(UserWarning, match="no ModelSpec"):
        charged = meter.charge("model_call", _payload("mystery-9b"), _result(), {})
    assert charged == 0.0
    # Second occurrence is silent (warn once).
    assert meter.charge("model_call", _payload("mystery-9b"), _result(), {}) == 0.0


def test_missing_usage_charges_zero_with_one_warning():
    meter = TomlCpuMeter()
    with pytest.warns(UserWarning, match="usage"):
        assert meter.charge("model_call", _payload(), {"no": "usage"}, {}) == 0.0


def test_precheck_returns_none_for_tool_calls():
    assert TomlCpuMeter().precheck_estimate("tool_call", _payload()) is None


def test_precheck_estimates_positive_joules_before_dispatch():
    meter = TomlCpuMeter()
    estimate = meter.precheck_estimate("model_call", _payload())
    assert estimate is not None and estimate > 0.0
    assert meter.last_precheck is not None
    assert meter.last_precheck.label == "predicted"


def test_precheck_respects_max_tokens_reservation():
    meter = TomlCpuMeter()
    small = meter.precheck_estimate("model_call", _payload(max_tokens=64))
    large = meter.precheck_estimate("model_call", _payload(max_tokens=512))
    assert large > small


def test_precheck_uses_a_supplied_estimator():
    class FixedEstimator:
        def estimate_input_tokens(self, payload):
            return 1000

    meter = TomlCpuMeter(estimator=FixedEstimator(), reserved_output_tokens=100)
    estimate = meter.precheck_estimate("model_call", _payload())
    expected = estimate_energy(QWEN25_1_5B, NEOVERSE_N1, "Q4_0", 1000, 100).total_j
    assert estimate == pytest.approx(expected)


def test_precheck_falls_back_to_heuristic_when_estimator_declines():
    class DecliningEstimator:
        def estimate_input_tokens(self, payload):
            return None

    meter = TomlCpuMeter(estimator=DecliningEstimator())
    estimate = meter.precheck_estimate("model_call", _payload())
    assert estimate is not None and estimate > 0.0


def test_strict_mode_raises_auditable_refusal_for_unknown_models():
    meter = TomlCpuMeter(strict_unknown_models=True)
    with pytest.raises(MeterPrecheckRefusal) as excinfo:
        meter.precheck_estimate("model_call", _payload("mystery-9b"))
    refusal = excinfo.value
    assert refusal.reason == "unknown_model_architecture"
    assert refusal.audit_meta is not None
    assert "known_architectures" in refusal.audit_meta
    assert refusal.audit_meta["model"] == "mystery-9b"


def test_non_strict_mode_returns_none_for_unknown_models():
    meter = TomlCpuMeter(strict_unknown_models=False)
    assert meter.precheck_estimate("model_call", _payload("mystery-9b")) is None


def test_charges_convert_cleanly_to_pollard_decimals():
    meter = TomlCpuMeter()
    charged = meter.charge("model_call", _payload(), _result(), {})
    assert charge_to_decimal(charged) > 0

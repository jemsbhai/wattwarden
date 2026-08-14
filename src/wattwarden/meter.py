"""TomlCpuMeter: a pollard meter that prices Arm CPU inference in joules.

This is the adapter between the pure TOML model (toml_model.py) and
pollard's meter protocol (pollard 1.5.1). Three capabilities:

1. charge(): after a model call settles, convert its token usage into
   predicted joules for the configured Arm CPU profile.
2. precheck_estimate(): before dispatch, estimate the joules the call
   would spend, so a Budget(extra={"joules": ...}) can refuse it first.
   The NVML meter cannot do this; a model-based meter can.
3. strict mode: raise MeterPrecheckRefusal for unknown architectures,
   recording an auditable refusal instead of silently passing.

Honesty contract: every figure this meter emits is a prediction from the
TOML operation model. It never claims measurement. Unknown models are
charged zero with a warning, never guessed.
"""

from __future__ import annotations

import math
import warnings
from collections.abc import Mapping, Sequence
from typing import Any

from pollard.meters import MeterPrecheckRefusal, usage_from_openai

from .toml_model import (
    PROFILES,
    ArmCpuProfile,
    ModelSpec,
    TomlEstimate,
    estimate_energy,
    resolve_spec,
)

_QUANT_TOKENS = ("Q4_K_M", "Q8_0", "Q4_0", "F16")


class TomlCpuMeter:
    """Predictive energy meter for Arm CPU LLM inference.

    name is "joules" so budgets share one energy dimension with pollard's
    NVML meter; only the provenance differs (predicted vs measured), and
    the provenance is visible in last_estimate.label.
    """

    name = "joules"

    def __init__(
        self,
        profile: ArmCpuProfile | str = "neoverse-n1",
        *,
        default_spec: ModelSpec | None = None,
        default_quant: str = "Q4_0",
        estimator: Any | None = None,
        reserved_output_tokens: int = 256,
        chars_per_token: float = 4.0,
        strict_unknown_models: bool = False,
    ) -> None:
        if isinstance(profile, str):
            try:
                profile = PROFILES[profile]
            except KeyError as exc:
                known = ", ".join(sorted(PROFILES))
                raise KeyError(f"unknown profile {profile!r}; known: {known}") from exc
        if isinstance(reserved_output_tokens, bool) or reserved_output_tokens < 0:
            raise ValueError("reserved_output_tokens must be a non-negative int")
        if chars_per_token <= 0:
            raise ValueError("chars_per_token must be positive")
        self.profile = profile
        self.default_spec = default_spec
        self.default_quant = default_quant
        self.reserved_output_tokens = reserved_output_tokens
        self.chars_per_token = float(chars_per_token)
        self.strict_unknown_models = strict_unknown_models
        self.precheck_is_estimate = True
        self.last_estimate: TomlEstimate | None = None
        self.last_precheck: TomlEstimate | None = None
        self._estimator = estimator
        self._warned_missing_usage = False
        self._warned_unknown_model = False

    # -- pollard meter protocol -------------------------------------------

    def charge(
        self,
        node_kind: str,
        payload: dict[str, Any],
        result: Any,
        meta: dict[str, Any],
    ) -> float:
        if node_kind != "model_call" or not isinstance(result, dict):
            return 0.0
        usage = usage_from_openai(result)
        input_tokens = usage["input_tokens"]
        output_tokens = usage["output_tokens"]
        if input_tokens == 0 and output_tokens == 0:
            if not isinstance(result.get("usage"), dict):
                self._warn_once_missing_usage()
            return 0.0
        spec = self._resolve_spec(payload)
        if spec is None:
            self._warn_once_unknown_model(payload.get("model"))
            return 0.0
        duration = meta.get("duration_s")
        duration_s = (
            float(duration)
            if isinstance(duration, int | float) and not isinstance(duration, bool)
            else None
        )
        estimate = estimate_energy(
            spec,
            self.profile,
            self._resolve_quant(payload),
            input_tokens,
            output_tokens,
            duration_s=duration_s,
        )
        self.last_estimate = estimate
        return float(estimate.total_j)

    def precheck_estimate(
        self, node_kind: str, payload: dict[str, Any]
    ) -> float | None:
        if node_kind != "model_call":
            return None
        spec = self._resolve_spec(payload)
        if spec is None:
            if self.strict_unknown_models:
                model = payload.get("model")
                raise MeterPrecheckRefusal(
                    "unknown_model_architecture",
                    "TomlCpuMeter cannot estimate energy for an architecture "
                    "it has no ModelSpec for; refusing under strict mode",
                    audit_meta={
                        "model": model if isinstance(model, str) else None,
                        "known_architectures": sorted(_known_spec_names()),
                    },
                )
            return None
        input_tokens = self._estimate_input_tokens(payload)
        output_reserve = self._output_reserve(payload)
        estimate = estimate_energy(
            spec,
            self.profile,
            self._resolve_quant(payload),
            input_tokens,
            output_reserve,
        )
        self.last_precheck = estimate
        return float(estimate.total_j)

    # -- internals ---------------------------------------------------------

    def _resolve_spec(self, payload: dict[str, Any]) -> ModelSpec | None:
        model = payload.get("model")
        if isinstance(model, str):
            try:
                return resolve_spec(model)
            except KeyError:
                pass
        return self.default_spec

    def _resolve_quant(self, payload: dict[str, Any]) -> str:
        model = payload.get("model")
        if isinstance(model, str):
            normalized = model.upper().replace("-", "_")
            for token in _QUANT_TOKENS:
                if token in normalized:
                    return token
        return self.default_quant

    def _estimate_input_tokens(self, payload: dict[str, Any]) -> int:
        if self._estimator is not None:
            estimated = self._estimator.estimate_input_tokens(payload)
            if estimated is not None:
                if (
                    isinstance(estimated, bool)
                    or not isinstance(estimated, int)
                    or estimated < 0
                ):
                    raise ValueError(
                        "token estimator must return a non-negative int or None"
                    )
                return estimated
        chars = _count_textual_chars(payload)
        tokens = math.ceil(chars / self.chars_per_token)
        messages = payload.get("messages")
        if isinstance(messages, list):
            tokens += 3 * len(messages)
        return tokens

    def _output_reserve(self, payload: dict[str, Any]) -> int:
        max_tokens = payload.get("max_tokens")
        if (
            isinstance(max_tokens, int)
            and not isinstance(max_tokens, bool)
            and max_tokens > 0
        ):
            return max_tokens
        return self.reserved_output_tokens

    def _warn_once_missing_usage(self) -> None:
        if self._warned_missing_usage:
            return
        self._warned_missing_usage = True
        warnings.warn(
            "wattwarden TomlCpuMeter saw no compatible usage payload; charging 0",
            stacklevel=2,
        )

    def _warn_once_unknown_model(self, model: Any) -> None:
        if self._warned_unknown_model:
            return
        self._warned_unknown_model = True
        warnings.warn(
            f"wattwarden TomlCpuMeter has no ModelSpec for {model!r}; charging 0 "
            "rather than guessing",
            stacklevel=2,
        )


def _known_spec_names() -> Sequence[str]:
    from .toml_model import MODEL_SPECS

    return tuple(MODEL_SPECS)


def _count_textual_chars(value: Any, *, key: str | None = None) -> int:
    """Count characters in textual leaves, skipping the model identifier.

    Mirrors the traversal shape of pollard's OpenAITokenEstimator so the
    heuristic and the tiktoken-backed path see the same leaves.
    """
    if isinstance(value, str):
        return 0 if key == "model" else len(value)
    if isinstance(value, Mapping):
        return sum(
            _count_textual_chars(item, key=str(item_key))
            for item_key, item in value.items()
        )
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray | str):
        return sum(_count_textual_chars(item) for item in value)
    return 0

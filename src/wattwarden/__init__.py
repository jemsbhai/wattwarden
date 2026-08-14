"""wattwarden: energy-governed AI agents on Arm CPUs.

A pollard-compatible energy meter implementing the TOML operation-level
energy model for Arm CPU inference, a configuration sweep driver, and an
SLO-aware configuration advisor.
"""

from .meter import TomlCpuMeter
from .toml_model import (
    MODEL_SPECS,
    PROFILES,
    ArmCpuProfile,
    ModelSpec,
    TomlEstimate,
    estimate_energy,
    resolve_spec,
)

__version__ = "0.0.1"

__all__ = [
    "ArmCpuProfile",
    "MODEL_SPECS",
    "ModelSpec",
    "PROFILES",
    "TomlCpuMeter",
    "TomlEstimate",
    "__version__",
    "estimate_energy",
    "resolve_spec",
]

# =============================================================================
# params.py — Load params.yaml into one frozen object, and hash it.
#
# WHY ONE PARAMETER FILE
#   Every number the study chooses (windows, thresholds, date ranges) lives in
#   params.yaml at the repository root (ADR 0001 §1). Code never hard-codes
#   them. A stage writes params_hash into its manifest, so two runs with
#   different parameters can never be mixed up.
#
# THE HASH
#   params_hash = SHA-256 of the canonical JSON form of the parsed file: keys
#   sorted, no spaces. Comments and key order in the YAML do not change it;
#   a changed value does.
# =============================================================================

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATH = ROOT / "params.yaml"


def _freeze(value: Any) -> Any:
    """Make nested dicts and lists read-only (a frozen dataclass alone is not)."""
    if isinstance(value, dict):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    return value


def canonical_json(raw: Mapping) -> str:
    """The text that params_hash is computed from: sorted keys, no spaces."""
    return json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


@dataclass(frozen=True)
class Params:
    """The parsed params.yaml. Read a section with params["windows"]["baseline"]."""

    raw: Mapping
    params_hash: str

    def __getitem__(self, key: str) -> Any:
        return self.raw[key]

    def day(self, section: str, key: str) -> date:
        """A date-valued parameter, e.g. params.day("timing", "lookup_from")."""
        return date.fromisoformat(self.raw[section][key])

    def date_range(self, section: str, key: str) -> tuple[date, date]:
        """A [from, to] pair of dates, both ends inclusive."""
        lo, hi = self.raw[section][key]
        return date.fromisoformat(lo), date.fromisoformat(hi)


def load(path: Path | None = None) -> Params:
    """Read params.yaml (or `path`) and return the frozen Params with its hash."""
    path = DEFAULT_PATH if path is None else path
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must hold a mapping at the top level")
    digest = hashlib.sha256(canonical_json(raw).encode("utf-8")).hexdigest()
    return Params(raw=_freeze(raw), params_hash=digest)

"""The node manifest: everything about a cell that is declared rather than learned.

Brief reference: section 8. Cell budget: KNP-8 section 2.3. Autonomy: KNP-7 section 2.

Loading a manifest is the first thing every command does, so its errors have to be good:
a bad manifest names the key that is wrong, not the line number of a YAML parser.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, ValidationError

from kourob.types import Tier

__milestone__ = "M1"

MANIFEST_FILE = "kourob.yaml"


class Identity(BaseModel):
    did: str = ""
    name: str
    set: str = "default"


class Exclusion(BaseModel):
    """Something people will wrongly bring here, and where it should go (KNP-1 section 2)."""

    pattern: str
    refer_to: str | None = None


class Scope(BaseModel):
    summary: str
    schemas: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    excludes: list[Exclusion] = Field(default_factory=list)
    max_hops: int = 4


class PortConfig(BaseModel):
    enabled: bool = False
    model_config = {"extra": "allow"}


class TierConfig(BaseModel):
    enabled: bool = False
    confidence_bar: float = 0.0
    model: str | None = None


class Pricing(BaseModel):
    base_cost: dict[Tier, float]
    capacity_window: int = 1000
    window: str = "1h"
    max_surge: float = 3.0
    quality_multiplier: float = 1.0
    free_allowance: int = 100
    q_floor: float = 0.8


class CellBudget(BaseModel):
    """The size ceiling. Exceeding it does not raise it (KNP-8 section 2.3)."""

    max_context_tokens: int = 15_000
    max_source_files: int = 40
    max_source_lines: int = 4_000
    max_schemas: int = 3
    max_tiers: int = 4
    max_hot_storage_mb: int = 500
    max_tools: int = 8
    on_exceed: Literal["propose_division", "halt", "warn"] = "propose_division"


class Autonomy(BaseModel):
    """What this cell may change about itself without asking (KNP-7 section 2).

    `level` is set by the operator's tooling from the ledger, never by the node itself:
    a node cannot promote itself.
    """

    level: Literal["A0", "A1", "A2", "A3", "A4"] = "A0"
    graduation_window: int = 4
    settle_floor: float = 0.2
    rollback_window: str = "30d"
    evolution_budget: float = 1.0
    bootstrap_grant: float = 10.0
    bootstrap_window: str = "90d"


class SplitPolicy(BaseModel):
    split_threshold: float = 0.5
    split_window: str = "14d"
    merge_window: str = "30d"
    min_cluster_share: float = 0.2
    auto_approve: bool = False


class BridgePolicy(BaseModel):
    enabled: bool = True
    bridge_limit: int = 3


class PrunePolicy(BaseModel):
    """Nothing here can collect an event, a receipt, or an outcome (KNP-9 section 4)."""

    prune_floor: float = 0.05
    prune_window: str = "30d"
    rule_window: str = "60d"
    page_window: str = "90d"
    shed_window: str = "90d"
    decay_per_window: float = 0.9
    hebbian_alpha: float = 0.3
    hebbian_beta: float = 0.5


class StoreConfig(BaseModel):
    backend: str = "parquet_duckdb"
    partition_by: str = "month"


class Manifest(BaseModel):
    """One cell, fully declared."""

    kourob: str = "0.1"
    identity: Identity
    scope: Scope
    ports: dict[str, PortConfig] = Field(default_factory=dict)
    tiers: dict[str, TierConfig] = Field(default_factory=dict)
    pricing: Pricing
    cell: CellBudget = Field(default_factory=CellBudget)
    autonomy: Autonomy = Field(default_factory=Autonomy)
    split: SplitPolicy = Field(default_factory=SplitPolicy)
    bridge: BridgePolicy = Field(default_factory=BridgePolicy)
    prune: PrunePolicy = Field(default_factory=PrunePolicy)
    retention: dict[str, str] = Field(default_factory=dict)
    store: StoreConfig = Field(default_factory=StoreConfig)
    loops: dict[str, Any] = Field(default_factory=dict)

    def tier_enabled(self, tier: Tier) -> bool:
        cfg = self.tiers.get(tier.value.lower())
        return bool(cfg and cfg.enabled)

    def confidence_bar(self, tier: Tier) -> float:
        cfg = self.tiers.get(tier.value.lower())
        return cfg.confidence_bar if cfg else 0.0


class ManifestError(ValueError):
    """A manifest that cannot be trusted. Names the key, not the parser."""


def load(node_dir: Path | str) -> Manifest:
    path = Path(node_dir) / MANIFEST_FILE
    if not path.exists():
        raise ManifestError(f"no manifest at {path}. Is this a node? Try `kourob init`.")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ManifestError(f"{path} is not valid YAML: {exc}") from exc
    try:
        return Manifest.model_validate(raw)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()
        )
        raise ManifestError(f"{path}: {problems}") from exc


def save(node_dir: Path | str, manifest: Manifest) -> Path:
    path = Path(node_dir) / MANIFEST_FILE
    path.write_text(
        yaml.safe_dump(
            manifest.model_dump(mode="json", exclude_none=False), sort_keys=False, width=100
        ),
        encoding="utf-8",
    )
    return path


__all__ = ["MANIFEST_FILE", "Manifest", "ManifestError", "load", "save"]

"""Load ODCS data contracts and validate payloads against them.

Brief reference: section 9 (Schemas).

This is a deliberately small reader over the subset of ODCS v3 the gate needs: required,
logical type, enum, range, and pattern. Full contract tooling — breaking-change detection,
exports, `datacontract changelog` — comes with `datacontract-cli` in its own task (kb-4m5).
Shipping the small reader first means the gate can be built and measured now, and it is
replaceable because nothing outside this module knows the file format.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

__milestone__ = "M1"

#: ODCS logical types mapped to what Python accepts for them. `bool` is checked before
#: `int` everywhere because bool is an int in Python and silently passing True as a count
#: is exactly the kind of thing a gate exists to catch.
_TYPE_CHECKS: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "date": (str,),
    "object": (dict,),
    "array": (list,),
}


@dataclass(frozen=True)
class ContractField:
    name: str
    logical_type: str = "string"
    required: bool = False
    enum: tuple[str, ...] | None = None
    minimum: float | None = None
    maximum: float | None = None
    pattern: str | None = None
    description: str = ""


@dataclass(frozen=True)
class Violation:
    """One reason a payload failed. `step` is the gate step that owns it."""

    step: str
    field: str
    detail: str

    def __str__(self) -> str:
        return f"{self.step}: {self.field} {self.detail}"


@dataclass(frozen=True)
class Contract:
    id: str
    version: str
    name: str = ""
    description: str = ""
    fields: tuple[ContractField, ...] = ()
    key_fields: tuple[str, ...] = ()
    quality: tuple[str, ...] = ()
    outcome_window: str | None = None
    settles_against: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def field_by_name(self, name: str) -> ContractField | None:
        return next((f for f in self.fields if f.name == name), None)

    def validate(self, payload: dict[str, Any]) -> list[Violation]:
        """Every violation, not just the first: a push with three problems has three."""
        problems: list[Violation] = []
        for spec in self.fields:
            if spec.name not in payload or payload[spec.name] is None:
                if spec.required:
                    problems.append(
                        Violation("validate.missing_required", spec.name, "is required")
                    )
                continue
            problems.extend(self._check(spec, payload[spec.name]))
        return problems

    @staticmethod
    def _check(spec: ContractField, value: Any) -> list[Violation]:
        problems: list[Violation] = []
        expected = _TYPE_CHECKS.get(spec.logical_type, (object,))
        if isinstance(value, bool) and bool not in expected:
            return [
                Violation(
                    "validate.wrong_type", spec.name, f"is a boolean, want {spec.logical_type}"
                )
            ]
        if not isinstance(value, expected):
            return [
                Violation(
                    "validate.wrong_type",
                    spec.name,
                    f"is {type(value).__name__}, want {spec.logical_type}",
                )
            ]
        if spec.enum is not None and value not in spec.enum:
            problems.append(
                Violation("validate.enum", spec.name, f"{value!r} not in {list(spec.enum)}")
            )
        if spec.minimum is not None and isinstance(value, int | float) and value < spec.minimum:
            problems.append(Violation("validate.range", spec.name, f"{value} < {spec.minimum}"))
        if spec.maximum is not None and isinstance(value, int | float) and value > spec.maximum:
            problems.append(Violation("validate.range", spec.name, f"{value} > {spec.maximum}"))
        if (
            spec.pattern is not None
            and isinstance(value, str)
            and not re.match(spec.pattern, value)
        ):
            problems.append(
                Violation("validate.pattern", spec.name, f"{value!r} does not match {spec.pattern}")
            )
        return problems


def parse(raw: dict[str, Any]) -> Contract:
    """Build a Contract from a parsed ODCS document."""
    schema_blocks = raw.get("schema") or []
    fields: list[ContractField] = []
    for block in schema_blocks:
        for prop in block.get("properties", []) or []:
            enum = prop.get("enum")
            fields.append(
                ContractField(
                    name=prop["name"],
                    logical_type=prop.get("logicalType", "string"),
                    required=bool(prop.get("required", False)),
                    enum=tuple(enum) if enum else None,
                    minimum=prop.get("minimum"),
                    maximum=prop.get("maximum"),
                    pattern=prop.get("pattern"),
                    description=prop.get("description", ""),
                )
            )
    kourob = raw.get("kourob") or {}
    return Contract(
        id=raw["id"],
        version=str(raw.get("version", "1.0.0")),
        name=raw.get("name", ""),
        description=raw.get("description", ""),
        fields=tuple(fields),
        key_fields=tuple(kourob.get("key_fields", ())),
        quality=tuple(rule.get("rule", "") for rule in raw.get("quality", []) or []),
        outcome_window=kourob.get("outcome_window"),
        settles_against=kourob.get("settles_against"),
        extras=kourob,
    )


def load(path: Path | str) -> Contract:
    return parse(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def load_dir(schemas_dir: Path | str) -> dict[str, Contract]:
    """Every contract a node owns, by id. `kourob schema list` prints this."""
    return {c.id: c for c in (load(p) for p in sorted(Path(schemas_dir).glob("*.odcs.yaml")))}


__all__ = ["Contract", "ContractField", "Violation", "load", "load_dir", "parse"]

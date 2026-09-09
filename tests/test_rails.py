"""The rails from AGENTS.md section 4, enforced as tests so they run locally and in CI.

These are cheap, boring, and the reason the project can let agents write most of the code.
Each one exists because breaking it silently would be expensive to discover later.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "kourob"

#: Inference SDKs. A model call must go through runner/, so these may only be imported in
#: runner/adapters/. Training libraries (torch, transformers, peft) are not on this list:
#: they run offline in loops/distill/, they do not serve requests.
VENDOR_SDKS = (
    "anthropic",
    "openai",
    "cohere",
    "mistralai",
    "litellm",
    "ollama",
    "google.generativeai",
    "google.genai",
)


def _py_files() -> list[Path]:
    return sorted(SRC.rglob("*.py"))


def _is_stub(path: Path) -> bool:
    return "Status: stub." in path.read_text(encoding="utf-8")


def _rel(path: Path) -> str:
    return path.relative_to(SRC).as_posix()


@pytest.mark.parametrize("zone", ["data/silver", "data/gold"])
def test_only_gate_touches_the_written_zones(zone: str) -> None:
    """Nothing writes data/silver or data/gold except gate.py.

    Enforced as "nothing else even names the path", which is stricter and easier to see.
    Code that needs those rows reads them through the Store interface by logical table.
    """
    offenders = [
        _rel(p)
        for p in _py_files()
        if zone in p.read_text(encoding="utf-8") and p.name != "gate.py"
    ]
    assert not offenders, f"{zone} named outside gate.py: {offenders}"


def test_training_code_reaches_gold_only_through_evals() -> None:
    """Training code never references data/gold paths except through evals/."""
    training_dirs = ("loops/distill", "trainer", "tiers/t1_student.py")
    offenders = [
        _rel(p)
        for p in _py_files()
        if any(_rel(p).startswith(d) for d in training_dirs)
        and re.search(r"data/gold|gold/", p.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"training code reaching gold directly: {offenders}"


@pytest.mark.parametrize("sdk", VENDOR_SDKS)
def test_vendor_sdks_are_imported_only_in_runner_adapters(sdk: str) -> None:
    """Every model call goes through runner/ so it is logged with tier, tokens, and cost."""
    pattern = re.compile(rf"^\s*(?:import|from)\s+{re.escape(sdk)}\b", re.MULTILINE)
    offenders = [
        _rel(p)
        for p in _py_files()
        if not _rel(p).startswith("runner/adapters/")
        and pattern.search(p.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"{sdk} imported outside runner/adapters/: {offenders}"


def test_storage_internals_stay_inside_the_store_package() -> None:
    """ADR-0001: no caller opens a parquet path or a DuckDB connection directly."""
    pattern = re.compile(r"^\s*(?:import|from)\s+(?:duckdb|pyarrow)\b", re.MULTILINE)
    offenders = [
        _rel(p)
        for p in _py_files()
        if not _rel(p).startswith("store/") and pattern.search(p.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"store internals leaked: {offenders}"


def test_ports_are_thin() -> None:
    """A file in ports/ over 300 lines is a smell (AGENTS.md section 4)."""
    fat = {
        _rel(p): len(p.read_text(encoding="utf-8").splitlines())
        for p in (SRC / "ports").glob("*.py")
        if len(p.read_text(encoding="utf-8").splitlines()) > 300
    }
    assert not fat, f"ports over 300 lines: {fat}"


def test_implemented_ports_return_the_answer_envelope() -> None:
    """Every port handler returns {data, rendered, citations, receipt_id}.

    Checked as "the module uses the Answer type", which is where that shape is defined
    once. Stubs are exempt until they are implemented.
    """
    offenders = [
        _rel(p)
        for p in (SRC / "ports").glob("*.py")
        if p.name != "__init__.py"
        and not _is_stub(p)
        and "Answer" not in p.read_text(encoding="utf-8")
    ]
    assert not offenders, f"ports not returning the Answer envelope: {offenders}"


def test_every_module_declares_its_milestone() -> None:
    """Every module says which milestone owns it, so `--help` and the tree stay honest."""
    offenders = [
        _rel(p)
        for p in _py_files()
        if p.name != "__init__.py" and "__milestone__" not in p.read_text(encoding="utf-8")
    ]
    # kourob/__init__.py carries the version, not a milestone.
    assert not offenders, f"missing __milestone__: {offenders}"

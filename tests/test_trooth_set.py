"""A set of Trooth-fed nodes, connected, with the outputs a Trooth provider gets.

Brief reference: section 3.2 (referral, bridge), section 7 (sets), section 12 M3 and M5.
KNP-1 sections 4 and 5, KNP-4 section 2. Three data nodes and a desk that holds nothing:
the desk bridges once, hands back the route, and refers after that. Each node then
publishes the two documents Trooth's provider page describes - a catalog entry and a
six-dimension scorecard - and they validate against Trooth's own schemas (vendored under
`examples/trooth-set/fixtures/trooth-schemas/`).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import jsonschema
import pytest
import yaml
from typer.testing import CliRunner

from kourob import node as node_mod
from kourob import serve
from kourob.cli import app
from kourob.ledger.verify import trace
from kourob.publish import catalog_entry, provider_scorecard, publish_trooth
from kourob.routes import RouteTable
from kourob.types import ScopeResult, Tier

REPO = Path(__file__).resolve().parents[1]
EXAMPLE = REPO / "examples" / "trooth-set"
SCHEMAS = EXAMPLE / "fixtures" / "trooth-schemas"

pytestmark = pytest.mark.m3


def _build_module():
    spec = importlib.util.spec_from_file_location("trooth_set_build", EXAMPLE / "build.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module  # dataclasses resolve annotations through sys.modules
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def cells(tmp_path_factory: pytest.TempPathFactory) -> dict[str, node_mod.Node]:
    root = tmp_path_factory.mktemp("set") / "cells"
    return _build_module().build(root, bridge_limit=1)


def _schema(name: str) -> dict:
    return json.loads((SCHEMAS / f"{name}.v0.1.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ the fixtures


def test_the_envelopes_are_valid_trooth_envelopes_signed_locally() -> None:
    schema = _schema("envelope")
    files = sorted((EXAMPLE / "fixtures" / "envelopes").glob("*.json"))
    assert len(files) == 4
    for path in files:
        envelope = json.loads(path.read_text(encoding="utf-8"))
        jsonschema.validate(envelope, schema)
        assert envelope["signature"]["key_id"] == "kourob-local", (
            "an envelope not signed by Trooth must say so"
        )


# ------------------------------------------------------------------ the set


def test_every_node_holds_its_sources(cells: dict[str, node_mod.Node]) -> None:
    assert set(cells) == {"weather-node", "seismic-node", "economy-node", "trooth-desk"}
    assert cells["weather-node"].store.stats("silver")["rows"] == 4  # 2 envelopes + 2 cards
    assert cells["seismic-node"].store.stats("silver")["rows"] == 2
    assert cells["economy-node"].store.stats("silver")["rows"] == 3  # 1 envelope + 2 cards
    assert cells["trooth-desk"].store.stats("silver")["rows"] == 0


def test_the_desk_knows_three_neighbours_and_nothing_else(cells) -> None:
    desk = cells["trooth-desk"]
    routes = RouteTable(desk.store, desk.manifest.prune).all()
    assert {r.name for r in routes} == {"weather-node", "seismic-node", "economy-node"}
    assert all(r.source == "connect" for r in routes)


def test_the_desk_bridges_an_earthquake_question_and_the_chain_crosses_two_nodes(cells) -> None:
    desk, seismic = cells["trooth-desk"], cells["seismic-node"]
    answer = serve.answer(desk, "largest earthquake in the last hour", caller="user:test")
    assert answer.scope_result is ScopeResult.BRIDGE, answer.rendered
    assert answer.tier_used is Tier.T0, "the neighbour answered from a rule"
    assert "M" in answer.rendered and "usgs" in answer.rendered
    assert answer.citations, "a bridged answer still cites the events behind it"
    assert answer.route_hints and answer.route_hints[0].node == seismic.did

    chain = trace(desk.dir, answer.receipt_id)
    assert set(chain.nodes) >= {desk.did, seismic.did}
    assert len(chain.receipts) == 2, "one receipt on the desk, one on the node it bridged to"
    assert any(r.get("upstream") for r in chain.receipts), "the desk's receipt names upstream"


def test_the_second_call_is_referred_not_bridged(cells) -> None:
    desk, economy = cells["trooth-desk"], cells["economy-node"]
    first = serve.answer(desk, "what is the latest cpi", caller="user:once")
    second = serve.answer(desk, "what is the latest cpi", caller="user:once")
    assert first.scope_result is ScopeResult.BRIDGE
    assert second.scope_result is ScopeResult.REFERRAL
    assert second.route_hints[0].node == economy.did
    assert second.citations == []


def test_a_direct_question_to_a_data_node_names_its_source(cells) -> None:
    weather = cells["weather-node"]
    answer = serve.answer(weather, "open-meteo observation at KJFK", caller="user:test")
    assert answer.scope_result is ScopeResult.IN_SCOPE, answer.rendered
    assert answer.rendered.startswith("open-meteo at KJFK")
    other = serve.answer(weather, "nws observation at KJFK", caller="user:test")
    assert other.rendered.startswith("nws at KJFK")
    assert other.citations != answer.citations, "two sources, two events, two citations"


# ------------------------------------------------------------------ provider outputs


def test_each_node_publishes_a_valid_trooth_catalog_entry_and_scorecard(cells) -> None:
    catalog, scorecard = _schema("catalog"), _schema("scorecard")
    for name, node in cells.items():
        entry = catalog_entry(node)
        jsonschema.validate(entry, catalog)
        assert entry["id"] == name
        card = provider_scorecard(node)
        jsonschema.validate(card, scorecard)
        assert card["source_id"] == name


def test_the_scorecard_measures_what_the_node_recorded(cells) -> None:
    seismic = cells["seismic-node"]
    card = provider_scorecard(seismic)
    dims = card["dimensions"]
    assert card["scoring_window"]["snapshot_count"] >= 1, "the bridged question reached it"
    assert dims["freshness_lag"]["sample_count"] >= 1
    assert dims["freshness_lag"]["p95_seconds"] > 0, "answer time minus the cited event's time"
    assert dims["completeness_by_segment"]["overall_pct"] == 100.0
    assert dims["completeness_by_segment"]["segments"] == {"T0": 100.0}
    assert dims["internal_consistency"]["contradictions_count"] == 0
    entry = catalog_entry(seismic)
    assert entry["declared_lineage"]["upstream_sources"] == ["usgs-earthquake"]
    assert entry["license"]["spdx"] == "public-domain"
    assert any(f["name"] == "observation.v1.content_hash" for f in entry["fields"])


def test_publish_trooth_writes_both_documents(cells, tmp_path: Path) -> None:
    desk = cells["trooth-desk"]
    written = publish_trooth(desk, tmp_path / "out")
    assert yaml.safe_load(written["catalog"].read_text(encoding="utf-8"))["id"] == "trooth-desk"
    assert json.loads(written["scorecard"].read_text(encoding="utf-8"))["schema_version"] == "0.1"

    result = CliRunner().invoke(app, ["publish", "--trooth", "--node", str(desk.dir)])
    assert result.exit_code == 0, result.output
    assert (desk.dir / "out" / "trooth" / "catalog.yaml").exists()
    assert "trooth-desk:" in result.output


# ------------------------------------------------------------------ the tap


def test_the_set_dashboard_renders_against_the_built_set(cells) -> None:
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    root = cells["trooth-desk"].dir.parent
    at = AppTest.from_file(str(EXAMPLE / "dashboard.py"), default_timeout=120)
    at.run()
    at.sidebar.text_input[0].set_value(str(root))
    at.run()
    assert not at.exception, at.exception
    assert at.title[0].value == "trooth-set"
    assert len(at.tabs) == 4, "one provider tab per node"

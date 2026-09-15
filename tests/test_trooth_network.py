"""A network of seven Trooth-fed nodes, two hops deep, advertising what it uses.

Brief reference: section 3.2 (referral, bridge), section 7 (sets). KNP-1 sections 4 and 5.
One node per Trooth feed, a weather desk over two of them, a front desk over all, so a
weather question from the front crosses three nodes and three receipts. Each source node
holds its Modafied emblem - the independent benchmark's attestation, verified against
Modafied's manifest, failing closed when it cannot be - and the network generates a credits
page that shows every feed and every UI output it uses, emblems embedded the way Modafied
prescribes.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from kourob import node as node_mod
from kourob import serve
from kourob.cli import app
from kourob.credits import credits_markdown, held
from kourob.ledger.verify import trace
from kourob.ports import modafied
from kourob.types import ScopeResult, Tier

REPO = Path(__file__).resolve().parents[1]
EXAMPLE = REPO / "examples" / "trooth-network"
MODAFIED = EXAMPLE / "fixtures" / "modafied"

pytestmark = pytest.mark.m3


def _build_module():
    spec = importlib.util.spec_from_file_location("trooth_network_build", EXAMPLE / "build.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def network(tmp_path_factory: pytest.TempPathFactory) -> dict[str, node_mod.Node]:
    root = tmp_path_factory.mktemp("net") / "cells"
    nodes, refused = _build_module().build(root)
    assert refused == [], refused
    return nodes


def _attestation(source_id: str) -> dict:
    return json.loads((MODAFIED / f"{source_id}.json").read_text(encoding="utf-8"))


def _manifest() -> dict:
    return json.loads((MODAFIED / "manifest.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ the Modafied in-port


def test_an_attestation_verifies_against_the_manifest_and_becomes_an_emblem() -> None:
    (line,) = modafied.attestation_to_events(_attestation("nws"), _manifest())
    push = json.loads(line)
    assert push["schema_ref"] == "emblem.v1"
    assert push["source_id"] == "nws"
    assert push["grade"] in "ABCDE"
    assert push["trace_id"] == _attestation("nws")["trace_id"]
    assert push["emblem_full"].endswith("/v1/emblems/nws.svg")
    assert "not an endorsement" in push["notice"], "the notice travels with the emblem"
    assert set(push["dimensions"]) == set(modafied.DIMENSIONS)
    assert push["scorecard_sha256"] == modafied.manifest_sha(_manifest(), "nws")


def test_an_attestation_whose_hash_is_not_in_the_manifest_is_refused() -> None:
    """Modafied's emblems page: a consumer that cannot verify the hash should fail closed."""
    tampered = _attestation("nws")
    tampered["evidence"]["scorecard_sha256"] = "0" * 64
    with pytest.raises(modafied.UnverifiedError, match="not the manifest"):
        modafied.attestation_to_events(tampered, _manifest())
    unlisted = _attestation("nws")
    unlisted["source_id"] = "nobody"
    with pytest.raises(modafied.UnverifiedError, match="lists no"):
        modafied.attestation_to_events(unlisted, _manifest())


def test_the_fixture_tree_yields_five_verified_emblems() -> None:
    pushes, refused = modafied.verified_tree(MODAFIED)
    assert refused == []
    assert sorted(json.loads(p)["source_id"] for p in pushes) == [
        "bls",
        "fred",
        "nws",
        "open-meteo",
        "usgs-earthquake",
    ]


# ------------------------------------------------------------------ the network


def test_seven_nodes_and_what_each_holds(network: dict[str, node_mod.Node]) -> None:
    assert set(network) == {
        "nws-node",
        "open-meteo-node",
        "usgs-node",
        "bls-node",
        "fred-node",
        "weather-desk",
        "trooth-desk",
    }
    for name in ("nws-node", "open-meteo-node", "usgs-node", "bls-node"):
        assert network[name].store.stats("silver")["rows"] == 3  # envelope + card + emblem
    assert network["fred-node"].store.stats("silver")["rows"] == 2  # no envelope: needs a key
    assert network["weather-desk"].store.stats("silver")["rows"] == 0
    assert network["trooth-desk"].store.stats("silver")["rows"] == 0


def test_a_weather_question_from_the_front_crosses_three_nodes(network) -> None:
    front, desk, nws = network["trooth-desk"], network["weather-desk"], network["nws-node"]
    answer = serve.answer(front, "nws observation at KJFK", caller="user:test")
    assert answer.scope_result is ScopeResult.BRIDGE, answer.rendered
    assert answer.tier_used is Tier.T0
    assert answer.rendered.startswith("nws at KJFK")
    assert answer.citations
    chain = trace(front.dir, answer.receipt_id)
    assert {front.did, desk.did, nws.did} <= set(chain.nodes)
    assert len(chain.receipts) == 3, "front, weather desk, nws node: three receipts"


def test_the_front_answers_a_modafied_grade_question_by_bridging(network) -> None:
    front = network["trooth-desk"]
    answer = serve.answer(front, "modafied grade of usgs-earthquake", caller="user:grade")
    assert answer.scope_result is ScopeResult.BRIDGE, answer.rendered
    assert answer.tier_used is Tier.T0
    assert answer.rendered.startswith("Modafied grade ")
    assert "not an endorsement" in answer.rendered, "the emblem is never shown without its notice"
    assert "/v1/emblems/usgs-earthquake.svg" in answer.rendered
    cited = network["usgs-node"].store.get("silver", answer.citations[0])
    assert cited is not None and cited["schema_ref"] == "emblem.v1"


def test_the_second_call_to_the_same_neighbour_is_referred(network) -> None:
    front, usgs = network["trooth-desk"], network["usgs-node"]
    first = serve.answer(front, "largest earthquake in the last hour", caller="user:once")
    second = serve.answer(front, "how many earthquakes in the last hour", caller="user:once")
    assert first.scope_result is ScopeResult.BRIDGE
    assert second.scope_result is ScopeResult.REFERRAL
    assert second.route_hints[0].node == usgs.did


# ------------------------------------------------------------------ credits


def test_credits_advertise_every_feed_and_every_ui_output(network) -> None:
    text = credits_markdown(network.values(), attribution=_build_module().attribution())
    for feed in ("nws", "open-meteo", "usgs-earthquake", "bls"):
        assert f"**{feed}**" in text
    assert "Weather data by Open-Meteo.com" in text, "the catalog's attribution text is used"
    assert "CC-BY-4.0" in text
    assert text.count("trooth-site/scorecards/") >= 5, "one Trooth scorecard page per card held"
    assert text.count("/v1/emblems/") == 5, "one Modafied emblem per source, embedded"
    assert "[![Modafied benchmark" in text, "embedded the way Modafied's emblems page says"
    assert "not an endorsement" in text
    root = network["trooth-desk"].dir.parent
    assert (root / "credits.md").exists(), "build writes it next to the cells"


def test_held_reports_the_emblem_with_its_links(network) -> None:
    (emblem,) = held(network["nws-node"])["emblems"]
    assert emblem["page_url"].endswith("/scorecards/nws")
    assert emblem["full"].endswith("/nws.svg") and emblem["compact"].endswith("/nws-compact.svg")
    assert emblem["alt"].startswith("Modafied benchmark")


def test_publish_credits_writes_the_page(network) -> None:
    nws = network["nws-node"]
    result = CliRunner().invoke(app, ["publish", "--credits", "--node", str(nws.dir)])
    assert result.exit_code == 0, result.output
    page = (nws.dir / "out" / "credits.md").read_text(encoding="utf-8")
    assert "/v1/emblems/nws.svg" in page


# ------------------------------------------------------------------ the tap


def test_the_network_dashboard_renders_against_the_built_network(network) -> None:
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    root = network["trooth-desk"].dir.parent
    at = AppTest.from_file(str(EXAMPLE / "dashboard.py"), default_timeout=120)
    at.run()
    at.sidebar.text_input[0].set_value(str(root))
    at.run()
    assert not at.exception, at.exception
    assert at.title[0].value == "trooth-network"
    assert len(at.subheader) >= 5, "one credits block per source node"

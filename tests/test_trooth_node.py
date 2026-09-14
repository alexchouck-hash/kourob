"""The first cross-project cell: a node fed by Trooth, with a human tap.

Brief reference: section 3 (in-ports), section 7 (integrations). Trooth is the single data
connector and provenance pipe (github.com/alexchouck-hash/trooth); its envelopes and
scorecards are the first external data a KouroB node holds. The example is built from
scratch here the way `tests/test_dogfood.py` builds the repo's own node, so
`examples/trooth-node` cannot rot without this file saying so.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from kourob import node as node_mod
from kourob import serve
from kourob.cli import app
from kourob.ports.trooth import (
    document_to_events,
    envelope_to_events,
    scorecard_to_events,
    tree_to_events,
)
from kourob.types import Tier

REPO = Path(__file__).resolve().parents[1]
EXAMPLE = REPO / "examples" / "trooth-node"
FIXTURES = EXAMPLE / "fixtures"

pytestmark = pytest.mark.m3


def _build_module():
    spec = importlib.util.spec_from_file_location("trooth_node_build", EXAMPLE / "build.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def cell(tmp_path_factory: pytest.TempPathFactory) -> Path:
    target = tmp_path_factory.mktemp("trooth") / "trooth-node"
    _node, report = _build_module().build(target)
    assert report.accepted == 6, f"one envelope and five scorecards: {report.reasons}"
    assert report.rejected == 0
    return target


# ------------------------------------------------------------------ the in-port


def test_an_envelope_becomes_one_observation_with_its_provenance() -> None:
    envelope = json.loads((FIXTURES / "envelopes" / "nws-kjfk-2026-09-10.json").read_text())
    (line,) = envelope_to_events(envelope)
    push = json.loads(line)
    assert push["schema_ref"] == "observation.v1"
    assert push["source_id"] == "nws"
    assert push["data"]["temperature_c"] == 21.1
    assert push["ts"] == "2026-09-10T18:51:00Z", "the fact happened when the station said"
    assert push["freshness_lag_s"] == 412
    assert push["content_hash"].startswith("sha256:")
    assert push["signature_key_id"] == "2026-09"
    assert push["considered_and_rejected"][0]["id"] == "open-meteo"


def test_untrusted_text_is_not_readmitted() -> None:
    """Trooth quarantined it; the node does not undo that by holding it in silver."""
    envelope = json.loads((FIXTURES / "envelopes" / "nws-kjfk-2026-09-10.json").read_text())
    (line,) = envelope_to_events(envelope)
    assert "Fair and Breezy" not in line
    assert json.loads(line)["untrusted_text_dropped"] == 1


def test_a_scorecard_flattens_to_the_numbers_a_rule_asks_for() -> None:
    card = json.loads((FIXTURES / "scorecards" / "nws.json").read_text())
    (line,) = scorecard_to_events(card)
    push = json.loads(line)
    assert push["schema_ref"] == "scorecard.v1"
    assert push["source_id"] == "nws"
    assert push["freshness_p95_s"] == pytest.approx(1261.3)
    assert push["accuracy_metric"] == "temperature_mae_deg_c"
    assert push["ts"] == card["generated_at"]


def test_a_scorecard_without_accuracy_omits_it_rather_than_writing_null() -> None:
    card = json.loads((FIXTURES / "scorecards" / "usgs-earthquake.json").read_text())
    push = json.loads(scorecard_to_events(card)[0])
    assert "accuracy_score" not in push


def test_the_manifest_is_not_a_fact() -> None:
    manifest = json.loads((FIXTURES / "scorecards" / "manifest.json").read_text())
    assert document_to_events(manifest) == []


def test_the_fixture_tree_yields_one_envelope_and_five_scorecards() -> None:
    pushes = [json.loads(p) for p in tree_to_events(FIXTURES)]
    kinds = sorted(p["schema_ref"] for p in pushes)
    assert kinds == ["observation.v1"] + ["scorecard.v1"] * 5


# ------------------------------------------------------------------ the node


def test_the_node_answers_the_latest_observation_at_t0_with_a_citation(cell: Path) -> None:
    node = node_mod.open_node(cell)
    answer = serve.answer(node, "latest observation at KJFK")
    assert answer.scope_result.value == "in_scope", answer.rendered
    assert answer.tier_used is Tier.T0
    assert answer.determinism == "derived"
    assert "21.1" in answer.rendered
    assert "api.weather.gov" in answer.rendered, "the source URL rides on the answer"
    assert len(answer.citations) == 1
    cited = node.store.get("silver", answer.citations[0])
    assert cited is not None
    assert cited["payload"]["content_hash"].startswith("sha256:")


def test_the_node_answers_a_scorecard_question_at_t0(cell: Path) -> None:
    node = node_mod.open_node(cell)
    answer = serve.answer(node, "how fresh is open-meteo")
    assert answer.scope_result.value == "in_scope", answer.rendered
    assert answer.tier_used is Tier.T0
    assert "Open-Meteo" in answer.rendered
    assert "p95" in answer.rendered


def test_a_second_push_of_the_same_snapshot_is_deduplicated(cell: Path) -> None:
    node = node_mod.open_node(cell)
    before = node.store.stats("silver")["rows"]
    report = node.gate.ingest_lines(tree_to_events(FIXTURES / "envelopes"), source="again")
    assert report.accepted == 0
    assert node.store.stats("silver")["rows"] == before


def test_the_cell_fits_its_ceiling(cell: Path) -> None:
    """Every doctor check passes except `outcomes`: nothing settles an observation yet.

    A Trooth revision (same source timestamp, different content hash) is the natural
    correction for an observation answer, and that comparator is not built (`kb-mpc`).
    The check is honest and stays red until it is.
    """
    node = node_mod.open_node(cell)
    failing = {check: detail for check, ok, detail in node.health() if not ok}
    assert set(failing) <= {"outcomes"}, failing


# ------------------------------------------------------------------ the CLI


def test_ingest_from_trooth_takes_a_directory(tmp_path: Path) -> None:
    target = tmp_path / "cell"
    _build_module().build(target)
    result = CliRunner().invoke(
        app, ["ingest", str(FIXTURES / "scorecards"), "--from-trooth", "--node", str(target)]
    )
    assert result.exit_code == 0, result.output
    assert "accepted 0" in result.output, "already held: the gate dedupes, the port does not"


# ------------------------------------------------------------------ the tap


def test_the_dashboard_renders_against_the_built_node(cell: Path) -> None:
    """Streamlit's own test harness runs the script headless; any exception fails it."""
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(EXAMPLE / "dashboard.py"), default_timeout=120)
    at.run()  # the first run draws the sidebar; then point it at the built cell
    at.sidebar.text_input[0].set_value(str(cell))
    at.run()
    assert not at.exception, at.exception
    assert at.title[0].value == "trooth-node"
    labels = [m.label for m in at.metric]
    assert "Chain" in labels
    chain = next(m for m in at.metric if m.label == "Chain")
    assert chain.value == "ok"

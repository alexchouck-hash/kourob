"""Rule mining: the candidate, the binding search, and the exact-replay gate.

Brief reference: KNP-5 section 3.3, ADR-0008.
"""

from __future__ import annotations

import re

import pytest

from kourob.loops.distill.mine import Candidate, _match_pattern, subject_of
from kourob.loops.evolve import MIN_COVERAGE, ClusterStats

pytestmark = pytest.mark.m5


def _candidate(**kw) -> Candidate:
    base = {
        "rule_id": "mined-note-topic",
        "schema_ref": "note.v1",
        "bind_field": "topic",
        "render_field": "body",
        "match": r"what is (?P<subject>.+)",
        "sql": "SELECT id FROM silver",
        "render": "{body}",
    }
    base.update(kw)
    return Candidate(**base)


# ------------------------------------------------------------------------------- the gate


def test_exact_on_every_covered_request_is_required() -> None:
    """99% right is not a function (ADR-0008 option A, rejected)."""
    perfect = _candidate(replayed=100, covered=100, exact=100)
    assert perfect.replay_exact_match == 1.0 and perfect.promotable

    nearly = _candidate(replayed=100, covered=100, exact=99, misses=["rcpt_x"])
    assert nearly.replay_exact_match == 0.99
    assert not nearly.promotable


def test_partial_coverage_is_allowed_down_to_the_floor() -> None:
    """A rule may decline requests. It may not get them wrong."""
    declines_some = _candidate(replayed=100, covered=96, exact=96)
    assert declines_some.coverage == 0.96 and declines_some.promotable

    declines_too_many = _candidate(replayed=100, covered=90, exact=90)
    assert declines_too_many.coverage < MIN_COVERAGE
    assert not declines_too_many.promotable


def test_nothing_replayed_is_not_promotable() -> None:
    assert not _candidate().promotable
    assert _candidate().replay_exact_match == 0.0


def test_the_rule_yaml_is_the_same_artefact_a_hand_written_rule_is() -> None:
    """A mined rule and a hand-written one run down the same T0 path."""
    import yaml

    from kourob.tiers.t0_rules import Rule

    candidate = _candidate(replayed=10, covered=10, exact=10)
    loaded = yaml.safe_load(candidate.as_yaml())
    rule = Rule.from_dict(loaded)

    assert rule.id == "mined-note-topic"
    assert rule.settles_schema == "note.v1" and rule.settles_key == ("topic",)
    assert loaded["mined"]["coverage"] == 1.0
    assert "ADR-0008" in loaded["description"]


# --------------------------------------------------------------------------- the subject


@pytest.mark.parametrize(
    ("question", "subject"),
    [
        ("what is a bridge", "bridge"),
        ("What is the Cell?", "cell"),
        ("tell me about pruning", "pruning"),
        ("explain the settle key", "settle key"),
        ("what is topic-12", "topic-12"),
    ],
)
def test_subject_drops_the_frame_and_keeps_the_rest(question: str, subject: str) -> None:
    assert subject_of(question) == subject


def test_the_match_pattern_is_built_from_the_dominant_frame() -> None:
    """One frame per rule: `re` forbids a group name twice, and `Rule` has one pattern.

    Questions in the minority frame go uncovered, and the replay gate counts that against
    coverage rather than papering over it."""
    rows = [{"shape": "what is *"}, {"shape": "tell me about *"}, {"shape": "what is *"}]
    pattern = re.compile(_match_pattern(rows), re.IGNORECASE)

    assert pattern.search("what is a bridge").group("subject") == "bridge"
    assert pattern.search("What is the settle key?").group("subject") == "settle key"
    assert pattern.search("tell me about pruning") is None, "the minority frame is uncovered"
    assert pattern.search("who wins wimbledon") is None, "a frame never seen does not bind"


def test_a_second_subject_in_a_frame_is_matched_but_not_bound() -> None:
    pattern = re.compile(_match_pattern([{"shape": "compare * with *"}]), re.IGNORECASE)
    match = pattern.search("compare bridges with referrals")
    assert match is not None
    assert match.group("subject") == "bridges"
    assert match.groupdict() == {"subject": "bridges"}


def test_numbers_in_a_frame_become_a_number_class() -> None:
    pattern = re.compile(_match_pattern([{"shape": "* # of *"}]), re.IGNORECASE)
    assert pattern.search("shot 3 of p001")
    assert not pattern.search("shot three of p001")


# ----------------------------------------------------------------------- the mining gate


def test_a_cluster_that_is_not_a_function_is_not_mined(tmp_path) -> None:
    from kourob import node as node_mod
    from kourob.loops.distill.mine import mine_rule

    node = node_mod.init(tmp_path / "c", scope="x")
    unstable = ClusterStats(key="k", volume=10, settle_rate=1.0, answer_entropy=1.5)
    assert mine_rule(node.store, unstable, {}) is None

    unsettled = ClusterStats(key="k", volume=10, settle_rate=0.0, answer_entropy=1.0)
    assert mine_rule(node.store, unsettled, {}) is None, "unverifiable work is not mined"

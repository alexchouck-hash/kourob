"""M5 acceptance: the cost curve. This is the claim the whole project rests on.

Brief section 12, M5 and GOAL.md: replaying 30 days of synthetic traffic on tennis-node,
cost per request on day 30 is at most one fifth of day 1, and the T0+T1 share is at least
80 percent.

If this eval does not pass, a node is just an expensive way to call a frontier model.

Imports of not-yet-existing modules live inside the test bodies on purpose: a module-level
import would fail collection instead of producing an honest xfail.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.m5, pytest.mark.eval]

M5 = "M5 not implemented"

COST_RATIO_TARGET = 5.0  # day 1 cost / day 30 cost
CHEAP_TIER_SHARE_TARGET = 0.80
STUDENT_ACCURACY_GAP = 0.02  # student within 2 points of the teacher


@pytest.mark.xfail(reason=M5)
def test_cost_per_request_falls_fivefold_over_thirty_days(tmp_path) -> None:
    from kourob.testing import replay_synthetic_traffic, tennis_node_fixture

    node = tennis_node_fixture(tmp_path)
    days = replay_synthetic_traffic(node, days=30, requests_per_day=200, evolve_weekly=True)

    day1, day30 = days[0], days[-1]

    ratio = day1.cost_per_request / day30.cost_per_request
    assert ratio >= COST_RATIO_TARGET, (
        f"cost fell only {ratio:.2f}x (day 1 {day1.cost_per_request:.5f}, "
        f"day 30 {day30.cost_per_request:.5f})"
    )


@pytest.mark.xfail(reason=M5)
def test_cheap_tiers_serve_most_traffic_by_day_thirty(tmp_path) -> None:
    from kourob.testing import replay_synthetic_traffic, tennis_node_fixture

    node = tennis_node_fixture(tmp_path)
    days = replay_synthetic_traffic(node, days=30, requests_per_day=200, evolve_weekly=True)

    share = days[-1].tier_share["T0"] + days[-1].tier_share["T1"]
    assert share >= CHEAP_TIER_SHARE_TARGET, f"T0+T1 share {share:.2f}"


@pytest.mark.xfail(reason=M5)
def test_student_tracks_the_teacher_on_the_scope_classifier(tmp_path) -> None:
    """Brief section 12, M5: within 2 points of the teacher on gold."""
    from kourob.loops.distill.calibrate import compare_to_teacher
    from kourob.testing import tennis_node_fixture

    node = tennis_node_fixture(tmp_path)
    scores = compare_to_teacher(node, task="scope_classifier")

    gap = scores.teacher_accuracy - scores.student_accuracy
    assert gap <= STUDENT_ACCURACY_GAP, (
        f"student {scores.student_accuracy:.3f} vs teacher {scores.teacher_accuracy:.3f}"
    )


@pytest.mark.xfail(reason=M5)
def test_a_node_without_gold_cannot_enable_t1(tmp_path) -> None:
    """Brief section 15: distilled tiers copying teacher mistakes. Enforced, not advised."""
    from kourob.testing import tennis_node_fixture
    from kourob.tiers.t1_student import T1Student

    node = tennis_node_fixture(tmp_path, with_gold=False)

    with pytest.raises(ValueError, match="gold"):
        T1Student.enable(node)


@pytest.mark.xfail(reason=M5)
def test_reference_ui_renders_an_answer_with_no_node_specific_code(tmp_path) -> None:
    """Brief section 12, M5: the UI is a thin client over the REST port."""
    from kourob.testing import reference_ui_render, tennis_node_fixture

    node = tennis_node_fixture(tmp_path)
    html, sources = reference_ui_render(node, "how many backhand winners did A hit")

    assert "receipt" in html.lower()
    assert not any("tennis" in s.lower() for s in sources), (
        "the reference UI must not contain node-specific code"
    )

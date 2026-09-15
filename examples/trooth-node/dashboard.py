"""A human tap on the Trooth-fed node, in Streamlit.

    uv sync --extra ui
    uv run streamlit run examples/trooth-node/dashboard.py -- examples/trooth-node/cell

KNP-6 says a UI is just another caller. This one reads the node through its public
surface - `open_node` and the Store API, never a Parquet path - and asks questions through
`serve.answer`, so every question it puts to the node leaves a receipt like any other
caller's. Nothing here knows the node's insides; point it at a different cell and it
shows that cell instead.

Four panels: what the node holds (observations with their provenance, scorecards), how it
is serving (tier share and cost per request by day), whether its chain verifies, and a
box to ask it something.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

from kourob import node as node_mod
from kourob import serve

DEFAULT_CELL = Path(__file__).resolve().parent / "cell"


def _cell_from_argv() -> Path:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    return Path(args[0]) if args else DEFAULT_CELL


def _frame(node, sql: str) -> pd.DataFrame:
    return node.store.query(sql).to_pandas()


st.set_page_config(page_title="trooth-node", page_icon="⚡", layout="wide")

cell = Path(st.sidebar.text_input("Cell", value=str(_cell_from_argv())))
if not (cell / "kourob.yaml").exists():
    st.error(f"{cell} is not a node. Build one: `uv run python examples/trooth-node/build.py`")
    st.stop()
node = node_mod.open_node(cell)
st.sidebar.caption(node.did)
if st.sidebar.button("Refresh"):
    st.rerun()

st.title(node.manifest.identity.name)
st.caption(node.manifest.scope.summary)

# ------------------------------------------------------------------ health tiles
counts = {t: node.store.stats(t)["rows"] for t in ("silver", "quarantine", "requests", "receipts")}
verify = node.ledger.verify()
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Events held", counts["silver"])
c2.metric("Quarantined", counts["quarantine"])
c3.metric("Requests", counts["requests"])
c4.metric("Receipts", counts["receipts"])
c5.metric("Chain", "ok" if verify.ok else "BROKEN")
if not verify.ok:
    st.error(str(verify))

# ------------------------------------------------------------------ observations
st.header("Observations")
observations = _frame(
    node,
    """
    SELECT
      id,
      json_extract_string(payload, '$.source_id')        AS source,
      json_extract_string(payload, '$.data.location')    AS location,
      json_extract(payload, '$.data')                    AS data,
      json_extract_string(payload, '$.source_timestamp') AS source_time,
      json_extract_string(payload, '$.fetched_at')       AS fetched_at,
      CAST(json_extract(payload, '$.freshness_lag_s') AS DOUBLE) AS lag_s,
      json_extract_string(payload, '$.license')          AS license,
      json_extract_string(payload, '$.content_hash')     AS content_hash,
      json_extract_string(payload, '$.signature_key_id') AS key_id,
      json_extract_string(payload, '$.source_url')       AS url
    FROM silver
    WHERE schema_ref = 'observation.v1'
    ORDER BY ts DESC
    """,
)
if observations.empty:
    st.info("No envelopes yet. `kourob ingest <envelopes> --from-trooth --node <cell>`.")
else:
    st.dataframe(observations, use_container_width=True, hide_index=True)
    st.bar_chart(observations.set_index("id")["lag_s"], y_label="freshness lag (s)")

# ------------------------------------------------------------------ scorecards
st.header("Scorecards")
cards = _frame(
    node,
    """
    SELECT
      json_extract_string(payload, '$.source_id')    AS source,
      json_extract_string(payload, '$.source_name')  AS name,
      json_extract_string(payload, '$.generated_at') AS generated_at,
      CAST(json_extract(payload, '$.freshness_p50_s') AS DOUBLE)  AS fresh_p50_s,
      CAST(json_extract(payload, '$.freshness_p95_s') AS DOUBLE)  AS fresh_p95_s,
      CAST(json_extract(payload, '$.completeness_pct') AS DOUBLE) AS complete_pct,
      CAST(json_extract(payload, '$.consistency_pct') AS DOUBLE)  AS consistent_pct,
      CAST(json_extract(payload, '$.schema_changes') AS INTEGER)  AS schema_changes,
      json_extract_string(payload, '$.accuracy_metric')           AS accuracy_metric,
      CAST(json_extract(payload, '$.accuracy_score') AS DOUBLE)   AS accuracy,
      id
    FROM silver
    WHERE schema_ref = 'scorecard.v1'
    ORDER BY ts DESC
    """,
)
if cards.empty:
    st.info("No scorecards yet. `kourob ingest <trooth site url> --from-trooth --node <cell>`.")
else:
    latest = cards.drop_duplicates("source", keep="first")
    st.dataframe(latest, use_container_width=True, hide_index=True)
    left, right = st.columns(2)
    left.bar_chart(latest.set_index("source")["fresh_p95_s"], y_label="freshness lag p95 (s)")
    right.bar_chart(latest.set_index("source")["complete_pct"], y_label="completeness (%)")

# ------------------------------------------------------------------ serving
st.header("Serving")
requests = _frame(
    node,
    """
    SELECT
      CAST(ts AS DATE)                    AS day,
      COALESCE(tier_used, 'refused')      AS tier,
      count(*)                            AS n,
      avg(COALESCE(cost_credits, 0))      AS cost_per_request,
      avg(COALESCE(price_credits, 0))     AS price_per_request
    FROM requests
    GROUP BY 1, 2
    ORDER BY 1, 2
    """,
)
if requests.empty:
    st.info("Nothing served yet. Ask something below.")
else:
    by_tier = requests.pivot_table(index="day", columns="tier", values="n", fill_value=0)
    share = by_tier.div(by_tier.sum(axis=1), axis=0)
    cheap = share.get("T0", 0) + share.get("T1", 0)
    last = requests.groupby("day").apply(
        lambda d: (d["cost_per_request"] * d["n"]).sum() / d["n"].sum()
    )
    m1, m2, m3 = st.columns(3)
    m1.metric("T0+T1 share, latest day", f"{float(pd.Series(cheap).iloc[-1]):.0%}")
    m2.metric("Cost per request, latest day", f"{float(last.iloc[-1]):.6f}")
    m3.metric("Days served", len(by_tier))
    left, right = st.columns(2)
    left.bar_chart(by_tier, y_label="requests by tier")
    right.line_chart(last.rename("cost per request"), y_label="credits")

# ------------------------------------------------------------------ receipts
st.header("Receipts")
receipts = _frame(
    node,
    """
    SELECT id, ts, kind, tier_used, determinism, scope_result, price_credits, citations
    FROM receipts
    ORDER BY seq DESC
    LIMIT 25
    """,
)
st.dataframe(receipts, use_container_width=True, hide_index=True)

# ------------------------------------------------------------------ ask
st.header("Ask")
st.caption(
    "Goes through `serve.answer` like any caller: T0 rules only, unless a runner is configured."
)
question = st.text_input("Question", value="latest observation at KJFK")
if st.button("Ask") and question.strip():
    answer = serve.answer(node, question.strip(), caller="user:dashboard")
    if answer.scope_result.value == "in_scope":
        st.success(answer.rendered)
    else:
        st.warning(answer.rendered)
    st.code(
        f"tier {answer.tier_used or '-'} ({answer.determinism or 'n/a'})\n"
        f"citations {', '.join(answer.citations) or 'none'}\n"
        f"receipt {answer.receipt_id}"
    )

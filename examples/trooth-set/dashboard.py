"""The set dashboard: four nodes, their routes, a bridged answer, and what Trooth would show.

    uv sync --extra ui
    uv run streamlit run examples/trooth-set/dashboard.py -- examples/trooth-set/cells

Reads every cell under the root through `open_node` and the Store API, never a Parquet
path. Asks the desk through `serve.answer` like any caller, then walks the receipt with
`kourob trace` across the nodes it passed through, so "metered along the whole chain" is a
table on screen rather than a sentence in GOAL.md.

The last panel is the two documents a Trooth provider gets - a catalog listing and a
six-dimension scorecard - computed for each node by `kourob publish --trooth`, next to the
node's own meter report. A node and a public source are then comparable on one page.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

from kourob import node as node_mod
from kourob import serve
from kourob.ledger import meter
from kourob.ledger.verify import trace
from kourob.publish import catalog_entry, provider_scorecard
from kourob.routes import RouteTable

DEFAULT_ROOT = Path(__file__).resolve().parent / "cells"
DESK = "trooth-desk"


def _root_from_argv() -> Path:
    args = [a for a in sys.argv[1:] if not a.startswith("-") and Path(a).is_dir()]
    return Path(args[0]) if args else DEFAULT_ROOT


def _cells(root: Path) -> dict[str, node_mod.Node]:
    found = {}
    for path in sorted(root.iterdir()) if root.exists() else []:
        if (path / "kourob.yaml").exists():
            node = node_mod.open_node(path)
            found[node.manifest.identity.name] = node
    return found


st.set_page_config(page_title="trooth-set", page_icon="🕸️", layout="wide")
root = Path(st.sidebar.text_input("Set root", value=str(_root_from_argv())))
cells = _cells(root)
if not cells:
    st.error(f"No cells under {root}. Build the set: `uv run python examples/trooth-set/build.py`")
    st.stop()
by_did = {n.did: name for name, n in cells.items()}
st.sidebar.write({name: n.did[:24] + "…" for name, n in cells.items()})
if st.sidebar.button("Refresh"):
    st.rerun()

st.title("trooth-set")
st.caption("Three nodes fed by Trooth sources, one desk that refers to them. Ask the desk.")

# --------------------------------------------------------------------------- the graph
st.header("The set")
dot = ["digraph set {", "  rankdir=LR;", '  node [shape=box, style="rounded"];']
for name, node in cells.items():
    held = node.store.stats("silver")["rows"]
    dot.append(f'  "{name}" [label="{name}\\n{held} events"];')
    for route in RouteTable(node.store, node.manifest.prune).all():
        other = by_did.get(route.node, route.name or route.node[:16])
        label = f"{route.source} s={route.strength:.2f} ok={route.successes}"
        dot.append(f'  "{name}" -> "{other}" [label="{label}"];')
dot.append("}")
st.graphviz_chart("\n".join(dot))

# ------------------------------------------------------------------------ ask the desk
st.header("Ask the desk")
desk = cells.get(DESK) or next(iter(cells.values()))
st.caption(
    f"Goes to **{desk.manifest.identity.name}** through `serve.answer`. It holds nothing; it "
    "bridges once per neighbour, hands back the route, then refers."
)
question = st.text_input("Question", value="largest earthquake in the last hour")
if st.button("Ask") and question.strip():
    answer = serve.answer(desk, question.strip(), caller="user:dashboard")
    kind = answer.scope_result.value
    (st.success if kind in ("in_scope", "bridge") else st.warning)(
        f"**{kind}** — {answer.rendered}"
    )
    if answer.route_hints:
        hint = answer.route_hints[0]
        st.info(f"Route handed back: {by_did.get(hint.node, hint.name)} — {hint.scope}")
    chain = trace(desk.dir, answer.receipt_id)
    rows = [
        {
            "node": by_did.get(r.get("node"), str(r.get("node"))[:20]),
            "receipt": r.get("id"),
            "tier": r.get("tier_used"),
            "scope": r.get("scope_result"),
            "price": float(r.get("price_credits") or 0.0),
            "cost": float(r.get("cost_credits") or 0.0),
            "citations": ",".join(r.get("citations") or []),
        }
        for r in chain.receipts
    ]
    if rows:
        frame = pd.DataFrame(rows)
        st.subheader("The chain")
        st.dataframe(frame, use_container_width=True, hide_index=True)
        c1, c2, c3 = st.columns(3)
        c1.metric("Nodes on the path", len(chain.nodes))
        c2.metric("Price along the chain", f"{frame['price'].sum():.6f}")
        c3.metric("Cost along the chain", f"{frame['cost'].sum():.6f}")
    with st.expander("kourob trace"):
        st.code(chain.render())

# --------------------------------------------------------------- provider outputs
st.header("What Trooth would show for each node")
st.caption(
    "The two documents a provider gets on trooth-site/providers: a catalog listing and a "
    "six-dimension scorecard, computed from each node's own records by `kourob publish --trooth`."
)
tabs = st.tabs(list(cells))
for tab, node in zip(tabs, cells.values(), strict=True):
    with tab:
        card = provider_scorecard(node)
        dims = card["dimensions"]
        m = st.columns(6)
        m[0].metric("Requests", card["scoring_window"]["snapshot_count"])
        m[1].metric("Freshness p95 (s)", dims["freshness_lag"]["p95_seconds"])
        m[2].metric("Complete %", dims["completeness_by_segment"]["overall_pct"])
        m[3].metric("Consistent %", dims["internal_consistency"]["consistent_snapshots_pct"])
        m[4].metric("Revisions %", dims["revision_behavior"]["revision_rate_pct"])
        m[5].metric("Schema changes", dims["schema_stability"]["schema_changes_count"])
        left, right = st.columns(2)
        with left:
            st.subheader("Catalog entry")
            st.code(yaml.safe_dump(catalog_entry(node), sort_keys=False), language="yaml")
        with right:
            st.subheader("Scorecard")
            st.json(card, expanded=False)
            st.subheader("Meter")
            st.code(meter.report(node.dir, "all").render())

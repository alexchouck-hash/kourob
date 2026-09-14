"""The network dashboard: seven nodes, a two-hop answer, and the feeds and emblems it shows.

    uv sync --extra ui
    uv run streamlit run examples/trooth-network/dashboard.py -- examples/trooth-network/cells

Reads every cell under the root through `open_node` and the Store API. Asks the front desk
through `serve.answer`, then walks the receipt with `kourob trace` across the nodes it
crossed. The credits panel is the network advertising what it uses: each feed with its
Trooth scorecard, and each source's Modafied emblem - Modafied's own SVG, linked to its
scorecard page, with the notice under it - exactly as Modafied's emblems page prescribes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

from kourob import node as node_mod
from kourob import serve
from kourob.credits import MODAFIED_SITE, TROOTH_SITE, credits_markdown, held
from kourob.ledger.verify import trace
from kourob.routes import RouteTable

DEFAULT_ROOT = Path(__file__).resolve().parent / "cells"
FRONT = "trooth-desk"


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


st.set_page_config(page_title="trooth-network", page_icon="🕸️", layout="wide")
root = Path(st.sidebar.text_input("Network root", value=str(_root_from_argv())))
cells = _cells(root)
if not cells:
    st.error(f"No cells under {root}. Build: `uv run python examples/trooth-network/build.py`")
    st.stop()
by_did = {n.did: name for name, n in cells.items()}
st.sidebar.write({name: n.did[:20] + "…" for name, n in cells.items()})
st.sidebar.markdown(
    f"Data via [Trooth]({TROOTH_SITE}/) · benchmarks by [Modafied]({MODAFIED_SITE}/)"
)
if st.sidebar.button("Refresh"):
    st.rerun()

st.title("trooth-network")
st.caption(
    "Five nodes, one per Trooth feed; a weather desk over two of them; a front desk over all."
)

# --------------------------------------------------------------------------- the graph
st.header("The network")
dot = ["digraph net {", "  rankdir=LR;", '  node [shape=box, style="rounded"];']
for name, node in cells.items():
    emblem = next(iter(held(node)["emblems"]), None)
    grade = f"\\nModafied {emblem['grade']}" if emblem else ""
    dot.append(f'  "{name}" [label="{name}\\n{node.store.stats("silver")["rows"]} events{grade}"];')
    for route in RouteTable(node.store, node.manifest.prune).all():
        other = by_did.get(route.node, route.name or route.node[:16])
        dot.append(f'  "{name}" -> "{other}" [label="{route.source} s={route.strength:.2f}"];')
dot.append("}")
st.graphviz_chart("\n".join(dot))

# ------------------------------------------------------------------------ ask the front
st.header("Ask the front desk")
front = cells.get(FRONT) or next(iter(cells.values()))
question = st.text_input("Question", value="nws observation at KJFK")
if st.button("Ask") and question.strip():
    answer = serve.answer(front, question.strip(), caller="user:dashboard")
    kind = answer.scope_result.value
    (st.success if kind in ("in_scope", "bridge") else st.warning)(
        f"**{kind}** — {answer.rendered}"
    )
    if answer.route_hints:
        hint = answer.route_hints[0]
        st.info(f"Route handed back: {by_did.get(hint.node, hint.name)} — {hint.scope}")
    chain = trace(front.dir, answer.receipt_id)
    rows = [
        {
            "node": by_did.get(r.get("node"), str(r.get("node"))[:20]),
            "receipt": r.get("id"),
            "tier": r.get("tier_used"),
            "scope": r.get("scope_result"),
            "price": float(r.get("price_credits") or 0.0),
            "cost": float(r.get("cost_credits") or 0.0),
        }
        for r in chain.receipts
    ]
    if rows:
        frame = pd.DataFrame(rows)
        st.dataframe(frame, use_container_width=True, hide_index=True)
        c1, c2, c3 = st.columns(3)
        c1.metric("Nodes on the path", len(chain.nodes))
        c2.metric("Price along the chain", f"{frame['price'].sum():.6f}")
        c3.metric("Cost along the chain", f"{frame['cost'].sum():.6f}")
    with st.expander("kourob trace"):
        st.code(chain.render())

# ------------------------------------------------------------------- feeds and emblems
st.header("What this network uses")
st.caption(
    "Every feed, with its Trooth scorecard, and every source's Modafied emblem. The emblems "
    "are Modafied's own files, verified against its manifest before a node held them."
)
for name, node in cells.items():
    h = held(node)
    if not (h["sources"] or h["scorecards"] or h["emblems"]):
        continue
    with st.container(border=True):
        left, right = st.columns([2, 1])
        with left:
            st.subheader(name)
            for s in h["sources"]:
                st.markdown(
                    f"**{s['source_id']}** — [source]({s['url']}) · {s['license']} · "
                    f"observed {s['source_timestamp']} · `{s['content_hash'][:23]}…`"
                )
            for c in h["scorecards"]:
                st.markdown(
                    f"[Trooth scorecard: {c['source_name']}]({c['page_url']}) — "
                    f"freshness p95 {c['freshness_p95_s']}s, completeness {c['completeness_pct']}%"
                )
        with right:
            for e in h["emblems"]:
                st.image(e["full"], caption=e["alt"])
                st.markdown(f"[Modafied scorecard]({e['page_url']}) · trace `{e['trace_id']}`")
notice = next(
    (e["notice"] for n in cells.values() for e in held(n)["emblems"] if e.get("notice")), ""
)
if notice:
    st.caption(notice)

with st.expander("credits.md, as generated"):
    st.markdown(credits_markdown(cells.values(), title="trooth-network credits"))

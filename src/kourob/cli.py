"""The kourob CLI.

Brief reference: sections 11 and 12.

Every command listed here is named in the brief. Commands that are not yet implemented
exit 2 with the milestone that will implement them, so ``kourob --help`` is an honest map
of the project rather than a promise.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from kourob import __version__

__milestone__ = "M0"

app = typer.Typer(
    name="kourob",
    help="Metered, provenance-tracked, self-specializing nodes that agents attach to.",
    no_args_is_help=True,
    add_completion=False,
)


def _todo(command: str, milestone: str, brief: str) -> None:
    """Exit with the milestone that implements `command`."""
    typer.secho(
        f"kourob {command}: not implemented yet (milestone {milestone}).",
        fg=typer.colors.YELLOW,
        err=True,
    )
    typer.secho(f"  brief: docs/brief/07-kourob-development.md {brief}", err=True)
    typer.secho(f"  tasks: bd list --milestone {milestone}", err=True)
    raise typer.Exit(2)


# --------------------------------------------------------------------------- node lifecycle


@app.command()
def init(
    name: Annotated[str, typer.Argument(help="Directory to create the node in.")],
    scope: Annotated[str, typer.Option(help="One-line description of what the node answers.")] = "",
) -> None:
    """Lay down a new node from the template: manifest, schemas, data zones, ledger, keys."""
    _todo("init", "M1", "section 8")


@app.command()
def ingest(
    path: Annotated[Path, typer.Argument(help="File or directory of events to push.")],
    node: Annotated[Path, typer.Option(help="Node directory.")] = Path("."),
) -> None:
    """Push data through the gate into silver, or into quarantine with a reason."""
    _todo("ingest", "M1", "section 3.1 step 3")


@app.command()
def query(
    question: Annotated[str, typer.Argument(help="What to ask the node.")],
    node: Annotated[Path, typer.Option(help="Node directory.")] = Path("."),
) -> None:
    """Ask the node a question through the tier cascade. Prints data, rendered, citations."""
    _todo("query", "M1", "section 3.1 step 4")


@app.command()
def serve(
    mcp: Annotated[bool, typer.Option("--mcp", help="Serve the MCP port.")] = False,
    a2a: Annotated[bool, typer.Option("--a2a", help="Serve the A2A port.")] = False,
    rest: Annotated[bool, typer.Option("--rest", help="Serve the REST port.")] = False,
    node: Annotated[Path, typer.Option(help="Node directory.")] = Path("."),
) -> None:
    """Serve a node on one or more ports."""
    _todo("serve", "M1", "sections 7 and 9")


@app.command()
def attach(
    target: Annotated[str, typer.Argument(help="claude-code | codex | cursor | <node-url>")],
    node: Annotated[Path, typer.Option(help="Node directory.")] = Path("."),
) -> None:
    """Attach an agent to this node, or attach this node to another node."""
    _todo("attach", "M2", "section 12, M2 and M3")


@app.command()
def pack(
    task: Annotated[str, typer.Argument(help="Beads task id to build a context pack for.")],
    node: Annotated[Path, typer.Option(help="Node directory.")] = Path("."),
) -> None:
    """Build a context pack for an attached agent. Target: under 15k tokens."""
    _todo("pack", "M2", "section 12, M2")


@app.command()
def trace(
    receipt_id: Annotated[str, typer.Argument(help="Receipt id to trace, e.g. rcpt_01J...")],
    node: Annotated[Path, typer.Option(help="Node directory.")] = Path("."),
) -> None:
    """Render the full provenance chain behind an answer: nodes, receipts, events, sources."""
    _todo("trace", "M1", "section 4.3")


@app.command()
def publish(
    node: Annotated[Path, typer.Option(help="Node directory.")] = Path("."),
) -> None:
    """Publish a node to its set registry: agent card, scope, price, Merkle root."""
    _todo("publish", "M5", "sections 7 and 12, M5")


@app.command()
def doctor(
    node: Annotated[Path, typer.Option(help="Node directory.")] = Path("."),
) -> None:
    """Check a node: manifest valid, keys present, store readable, ledger verifies."""
    _todo("doctor", "M1", "section 8")


@app.command()
def version() -> None:
    """Print the kourob version."""
    typer.echo(__version__)


# ------------------------------------------------------------------------------ model calls


@app.command()
def run(
    prompt: Annotated[str, typer.Argument(help="Prompt or path to a prompt file.")],
    adapter: Annotated[
        str, typer.Option(help="claude_code|codex|openai|anthropic|gemini|local")
    ] = "local",
) -> None:
    """Make a model call through the vendor-neutral runner. Logged to logs/calls.parquet."""
    _todo("run", "M1", "section 9, Runner")


@app.command()
def train(
    node: Annotated[Path, typer.Argument(help="Node to build or improve.")],
    brief: Annotated[Path, typer.Option(help="Trainer brief file.")] = Path("brief.md"),
) -> None:
    """Launch a trainer session: a frontier model that builds a node but never serves it."""
    _todo("train", "M5", "section 6.2")


# ---------------------------------------------------------------------------------- groups

ledger_app = typer.Typer(help="Receipts: verify the chain, export, publish Merkle roots.")
meter_app = typer.Typer(help="Credits: balances, cost, price, margin.")
schema_app = typer.Typer(help="ODCS data contracts: list, generate, diff.")
routes_app = typer.Typer(help="The route table: what this node knows about other nodes.")
tools_app = typer.Typer(help="The tool registry of a node.")
keys_app = typer.Typer(help="Node identity: ed25519 keypairs and did:key ids.")
loop_app = typer.Typer(help="Scheduled loops: ingest, compile, lint, evolve, prune, reflect.")
distill_app = typer.Typer(help="Train and calibrate the T1 student.")
scope_app = typer.Typer(help="Scope declaration and classification.")

app.add_typer(ledger_app, name="ledger")
app.add_typer(meter_app, name="meter")
app.add_typer(schema_app, name="schema")
app.add_typer(routes_app, name="routes")
app.add_typer(tools_app, name="tools")
app.add_typer(keys_app, name="keys")
app.add_typer(loop_app, name="loop")
app.add_typer(distill_app, name="distill")
app.add_typer(scope_app, name="scope")


@ledger_app.command("verify")
def ledger_verify(node: Annotated[Path, typer.Option()] = Path(".")) -> None:
    """Walk the hash chain and check every signature. Non-zero exit on any break."""
    _todo("ledger verify", "M1", "section 4.2")


@ledger_app.command("export")
def ledger_export(node: Annotated[Path, typer.Option()] = Path(".")) -> None:
    """Export receipts as JSONL, and the provenance graph as W3C PROV."""
    _todo("ledger export", "M1", "sections 4.2 and 4.3")


@ledger_app.command("root")
def ledger_root(node: Annotated[Path, typer.Option()] = Path(".")) -> None:
    """Compute and publish the Merkle root of this ledger to the set registry."""
    _todo("ledger root", "M4", "section 4.2, ADR-0003")


@meter_app.command("report")
def meter_report(
    period: Annotated[str, typer.Option(help="e.g. 30d, 2026-09")] = "30d",
    node: Annotated[Path, typer.Option()] = Path("."),
) -> None:
    """Revenue, cost, margin, and top callers for a period."""
    _todo("meter report", "M4", "section 4.4")


@meter_app.command("price")
def meter_price(node: Annotated[Path, typer.Option()] = Path(".")) -> None:
    """Show the current price and demand factor, as callers see it in the agent card."""
    _todo("meter price", "M4", "section 5.1, ADR-0004")


@schema_app.command("list")
def schema_list(node: Annotated[Path, typer.Option()] = Path(".")) -> None:
    """List the ODCS contracts this node declares."""
    _todo("schema list", "M1", "section 9, Schemas")


@schema_app.command("gen")
def schema_gen(node: Annotated[Path, typer.Option()] = Path(".")) -> None:
    """Generate pydantic models from the contracts into .kourob/gen/."""
    _todo("schema gen", "M1", "section 9, Schemas")


@schema_app.command("diff")
def schema_diff(node: Annotated[Path, typer.Option()] = Path(".")) -> None:
    """Detect breaking changes against the published version (datacontract changelog)."""
    _todo("schema diff", "M1", "section 13.3")


@routes_app.command("list")
def routes_list(node: Annotated[Path, typer.Option()] = Path(".")) -> None:
    """Show the route table: scope pattern, node, price, latency, last success."""
    _todo("routes list", "M3", "section 7")


@routes_app.command("add")
def routes_add(
    node_id: Annotated[str, typer.Argument(help="did:key or URL of the node to route to.")],
    scope: Annotated[str, typer.Option(help="Scope pattern this node answers.")] = "",
    node: Annotated[Path, typer.Option()] = Path("."),
) -> None:
    """Add a route by hand. Normally routes are learned from referrals and bridges."""
    _todo("routes add", "M3", "sections 3.2 and 7")


@tools_app.command("list")
def tools_list(node: Annotated[Path, typer.Option()] = Path(".")) -> None:
    """List the tools this node exposes, with scope, dry_run, and review_required flags."""
    _todo("tools list", "M2", "section 8")


@keys_app.command("init")
def keys_init(node: Annotated[Path, typer.Option()] = Path(".")) -> None:
    """Generate this node's ed25519 keypair and did:key id into .kourob/ (gitignored)."""
    _todo("keys init", "M1", "section 9, identity and signing")


@keys_app.command("show")
def keys_show(node: Annotated[Path, typer.Option()] = Path(".")) -> None:
    """Print this node's did:key. Never prints the private key."""
    _todo("keys show", "M1", "section 9, identity and signing")


@loop_app.command("run")
def loop_run(
    name: Annotated[str, typer.Argument(help="ingest|compile|lint|evolve|prune|reflect")],
    node: Annotated[Path, typer.Option()] = Path("."),
    budget: Annotated[float, typer.Option(help="Credit budget for this run.")] = 1.0,
) -> None:
    """Run one loop once. Each loop outputs a PR or an event, nothing else."""
    _todo("loop run", "M2", "section 6.1")


@loop_app.command("list")
def loop_list(node: Annotated[Path, typer.Option()] = Path(".")) -> None:
    """List loops, their triggers, their budgets, and when each last ran."""
    _todo("loop list", "M2", "section 6.1")


@distill_app.command("train")
def distill_train(node: Annotated[Path, typer.Option()] = Path(".")) -> None:
    """Train the T1 student from the call log. Refuses if the node has no gold set."""
    _todo("distill train", "M5", "sections 6.1 and 15")


@distill_app.command("calibrate")
def distill_calibrate(node: Annotated[Path, typer.Option()] = Path(".")) -> None:
    """Calibrate cascade thresholds against gold, per class."""
    _todo("distill calibrate", "M5", "section 15")


@scope_app.command("show")
def scope_show(node: Annotated[Path, typer.Option()] = Path(".")) -> None:
    """Print what this node claims to answer."""
    _todo("scope show", "M3", "section 2, Scope")


@scope_app.command("check")
def scope_check(
    question: Annotated[str, typer.Argument(help="Request to classify.")],
    node: Annotated[Path, typer.Option()] = Path("."),
) -> None:
    """Classify a request: in_scope, referral, or reject."""
    _todo("scope check", "M3", "section 3.1 step 2")


def main() -> None:
    """Console-script entry point (`kourob`)."""
    app()


if __name__ == "__main__":
    main()

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


def _fail(message: str) -> None:
    typer.secho(message, fg=typer.colors.RED, err=True)
    raise typer.Exit(1)


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
    from kourob import node as node_mod

    try:
        created = node_mod.init(name, scope=scope)
    except FileExistsError as exc:
        _fail(str(exc))
        return
    typer.secho(
        f"created cell {created.manifest.identity.name} at {created.dir}", fg=typer.colors.GREEN
    )
    typer.echo(f"  identity  {created.did}")
    typer.echo(f"  scope     {created.manifest.scope.summary}")
    typer.echo(
        f"  autonomy  {created.manifest.autonomy.level} (observe: every change is a proposal)"
    )
    typer.echo("")
    typer.echo("Next: write GOAL.md, add a contract to schemas/, then `kourob ingest`.")


@app.command()
def ingest(
    path: Annotated[Path, typer.Argument(help="File or directory of events to push.")],
    node: Annotated[Path, typer.Option(help="Node directory.")] = Path("."),
    from_markdown: Annotated[
        bool,
        typer.Option("--from-markdown", help="Treat PATH as markdown: one note per paragraph."),
    ] = False,
) -> None:
    """Push data through the gate into silver, or into quarantine with a reason."""
    from kourob.node import open_node

    cell = open_node(node)
    if not cell.contracts:
        _fail(f"{node} declares no contracts. Add one to schemas/ before ingesting.")
    if from_markdown:
        from kourob.ports.files import markdown_to_notes, markdown_tree_to_notes

        lines = markdown_tree_to_notes(path) if path.is_dir() else markdown_to_notes(path)
        report = cell.gate.ingest_lines(lines, source=str(path))
    else:
        report = cell.gate.ingest_file(path)
    typer.secho(f"accepted {report.accepted}", fg=typer.colors.GREEN, nl=False)
    typer.echo("   ", nl=False)
    typer.secho(f"quarantined {report.rejected}", fg=typer.colors.YELLOW)
    for step, count in sorted(report.reasons.items(), key=lambda kv: -kv[1]):
        typer.echo(f"  {count:>4}  {step}")


@app.command()
def query(
    question: Annotated[str, typer.Argument(help="What to ask the node.")],
    node: Annotated[Path, typer.Option(help="Node directory.")] = Path("."),
) -> None:
    """Ask the node a question through the tier cascade. Prints data, rendered, citations."""
    from kourob import serve
    from kourob.node import open_node

    result = serve.answer(open_node(node), question)
    typer.echo(result.rendered)
    typer.echo("")
    typer.echo(f"  tier        {result.tier_used or '-'} ({result.determinism or 'n/a'})")
    typer.echo(f"  citations   {', '.join(result.citations) or 'none'}")
    typer.echo(f"  receipt     {result.receipt_id}")
    if result.scope_result.value != "in_scope":
        raise typer.Exit(3)


@app.command()
def serve(
    mcp: Annotated[bool, typer.Option("--mcp", help="Serve the MCP port.")] = False,
    a2a: Annotated[bool, typer.Option("--a2a", help="Serve the A2A port.")] = False,
    rest: Annotated[bool, typer.Option("--rest", help="Serve the REST port.")] = False,
    node: Annotated[Path, typer.Option(help="Node directory.")] = Path("."),
) -> None:
    """Serve a node on one or more ports. Only MCP over stdio exists today."""
    if a2a or rest:
        _todo("serve --a2a / --rest", "M3", "sections 7 and 9")
    if not mcp:
        _fail("nothing to serve: pass --mcp")
    try:
        from kourob.ports.mcp_server import serve_stdio
    except ImportError:
        _fail("the MCP SDK is not installed: `uv sync --extra mcp` (or pip install 'kourob[mcp]')")
        return
    serve_stdio(node)


@app.command()
def attach(
    target: Annotated[str, typer.Argument(help="claude-code | codex | cursor | <node-url>")],
    node: Annotated[Path, typer.Option(help="Node directory.")] = Path("."),
) -> None:
    """Attach an agent to this node by writing its MCP client config. Attaching to another
    node is `kourob connect`."""
    import json as _json

    from kourob.node import open_node

    if target.startswith(("http://", "https://")) or Path(target).exists():
        _fail("to reach another node use `kourob connect <path>`; `attach` is for agents")
    cell = open_node(node)
    name = f"kourob-{cell.manifest.identity.name}"
    entry = {
        "command": "kourob",
        "args": ["serve", "--mcp", "--node", str(Path(node).resolve())],
    }
    if target in ("claude-code", "cursor"):
        path = Path(node) / ".mcp.json"
        config: dict = {}
        if path.exists():
            config = _json.loads(path.read_text(encoding="utf-8") or "{}")
        config.setdefault("mcpServers", {})[name] = entry
        path.write_text(_json.dumps(config, indent=2) + "\n", encoding="utf-8")
        typer.secho(f"wrote {path}", fg=typer.colors.GREEN)
        typer.echo(f"  {target} picks it up from the project root; the server is `{name}`.")
        return
    if target == "codex":
        typer.echo(f"add to ~/.codex/config.toml:\n\n[mcp_servers.{name}]")
        typer.echo(f'command = "{entry["command"]}"')
        typer.echo(f"args = {_json.dumps(entry['args'])}")
        return
    _fail(f"unknown agent {target!r}; know claude-code, cursor, codex")


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
    from kourob.ledger.verify import trace as trace_chain

    chain = trace_chain(node, receipt_id)
    if not chain.receipts:
        _fail(f"no receipt {receipt_id} in this ledger")
    typer.echo(chain.render())


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
    from kourob.node import open_node

    failures = 0
    for name, ok, detail in open_node(node).health():
        mark = "ok  " if ok else "FAIL"
        colour = typer.colors.GREEN if ok else typer.colors.RED
        typer.secho(f"[{mark}] ", fg=colour, nl=False)
        typer.echo(f"{name:<9} {detail}")
        failures += not ok
    if failures:
        raise typer.Exit(1)


@app.command()
def tend(
    node: Annotated[Path, typer.Option(help="Cell directory.")] = Path("."),
    budget: Annotated[float, typer.Option(help="Credits this cycle may spend.")] = 1.0,
    autonomy_max: Annotated[str, typer.Option(help="Cap the autonomy level: A0..A4.")] = "A0",
    dry_run: Annotated[bool, typer.Option(help="Decide and report, apply nothing.")] = False,
) -> None:
    """Run one self-development cycle: ingest, evolve, decide, apply within autonomy, report."""
    from kourob.loops.tend import TendError, render, tend

    try:
        report = tend(node, budget=budget, autonomy_max=autonomy_max, dry_run=dry_run)
    except TendError as exc:
        _fail(str(exc))
        return
    typer.echo(render(report))
    if report.halted:
        raise typer.Exit(4)


@app.command()
def rollback(
    change: Annotated[str, typer.Argument(help="Change event id, e.g. evt_01J...")],
    node: Annotated[Path, typer.Option(help="Cell directory.")] = Path("."),
) -> None:
    """Apply the recorded inverse of an auto-applied change."""
    from kourob.loops.tend import TendError
    from kourob.loops.tend import rollback as roll

    try:
        event_id = roll(node, change)
    except TendError as exc:
        _fail(str(exc))
        return
    typer.secho(f"rolled back {change} -> {event_id}", fg=typer.colors.GREEN)


@app.command()
def connect(
    target: Annotated[
        str, typer.Argument(help="Path to a cell on disk (URLs come with the A2A port).")
    ],
    node: Annotated[Path, typer.Option(help="Cell directory.")] = Path("."),
) -> None:
    """Make a neighbour of another cell. One command, one route row, never an import."""
    from kourob.node import connect as connect_cell
    from kourob.node import open_node

    if target.startswith(("http://", "https://")):
        _fail("HTTP neighbours arrive with the A2A port (kb-imt). Connect a path for now.")
    try:
        route = connect_cell(open_node(node), target)
    except (FileNotFoundError, ValueError) as exc:
        _fail(str(exc))
        return
    typer.secho(f"connected {route.name} ({route.node[:28]}...)", fg=typer.colors.GREEN)
    typer.echo(f"  scope    {route.summary}")
    typer.echo(f"  schemas  {', '.join(route.schemas) or 'none declared'}")


@app.command()
def disconnect(
    did: Annotated[str, typer.Argument(help="did:key of the neighbour to forget.")],
    node: Annotated[Path, typer.Option(help="Cell directory.")] = Path("."),
) -> None:
    """Drop a route. Receipts either side wrote stay verifiable forever."""
    from kourob.routes import RouteTable

    table = RouteTable.load(node)
    route = table.get(did)
    if route is None:
        _fail(f"no route to {did}")
        return
    route.strength = 0.0
    table.save(route)
    typer.echo(f"forgot {route.name or did}")


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
cell_app = typer.Typer(help="The cell as a unit of work: size budget, seams, division.")
outcome_app = typer.Typer(help="Outcomes: whether what this node said held up.")

app.add_typer(ledger_app, name="ledger")
app.add_typer(meter_app, name="meter")
app.add_typer(schema_app, name="schema")
app.add_typer(routes_app, name="routes")
app.add_typer(tools_app, name="tools")
app.add_typer(keys_app, name="keys")
app.add_typer(loop_app, name="loop")
app.add_typer(distill_app, name="distill")
app.add_typer(scope_app, name="scope")
app.add_typer(cell_app, name="cell")
app.add_typer(outcome_app, name="outcome")


@ledger_app.command("verify")
def ledger_verify(node: Annotated[Path, typer.Option()] = Path(".")) -> None:
    """Walk the hash chain and check every signature. Non-zero exit on any break."""
    from kourob.ledger.verify import verify as verify_ledger

    report = verify_ledger(node)
    colour = typer.colors.GREEN if report.ok else typer.colors.RED
    typer.secho(str(report), fg=colour)
    if not report.ok:
        raise typer.Exit(1)


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
    from kourob.ledger.meter import report as meter_report_for

    typer.echo(meter_report_for(node, period).render())


@meter_app.command("price")
def meter_price(node: Annotated[Path, typer.Option()] = Path(".")) -> None:
    """Show the current price and demand factor, as callers see it in the agent card."""
    from kourob.ledger.pricing import Pricer
    from kourob.node import open_node
    from kourob.types import Tier

    cell = open_node(node)
    pricer = Pricer(cell)
    typer.echo(
        f"demand factor {pricer.demand():.2f}  ({pricer.requests_in_window()} requests in "
        f"{cell.manifest.pricing.window}, capacity {cell.manifest.pricing.capacity_window})"
    )
    typer.echo(f"quality       {pricer.quality():.2f}  (earned from settled outcomes)")
    typer.echo(f"ceiling       {pricer.ceiling():.6f}  credits, the dearest enabled tier")
    for tier in Tier:
        if cell.manifest.tier_enabled(tier):
            typer.echo(f"  {tier.value}  {pricer.price(tier):.6f}")


@schema_app.command("list")
def schema_list(node: Annotated[Path, typer.Option()] = Path(".")) -> None:
    """List the ODCS contracts this node declares."""
    from kourob.node import open_node

    contracts = open_node(node).contracts
    if not contracts:
        typer.secho("no contracts. Add one to schemas/*.odcs.yaml", fg=typer.colors.YELLOW)
        return
    for contract in contracts.values():
        required = sum(1 for f in contract.fields if f.required)
        typer.echo(
            f"{contract.id:<20} v{contract.version:<8} "
            f"{len(contract.fields)} fields ({required} required)  {contract.name}"
        )


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
    """Show the route table: neighbour, scope, strength, observed price and latency."""
    from kourob.routes import RouteTable

    routes = RouteTable.load(node).all()
    if not routes:
        typer.secho("no routes. Try `kourob connect <path-to-cell>`.", fg=typer.colors.YELLOW)
        return
    for route in routes:
        price = "-" if route.observed_price is None else f"{route.observed_price:.5f}"
        latency = "-" if route.observed_latency_ms is None else f"{route.observed_latency_ms:.0f}ms"
        typer.echo(
            f"{route.name or '?':<16} {route.node[:24]}...  strength {route.strength:.2f}  "
            f"price {price:<9} latency {latency:<8} {route.successes}/{route.failures} "
            f"{route.source}  {route.summary[:40]}"
        )


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
    from kourob import identity

    try:
        typer.echo(identity.generate(node))
    except FileExistsError as exc:
        _fail(str(exc))


@keys_app.command("show")
def keys_show(node: Annotated[Path, typer.Option()] = Path(".")) -> None:
    """Print this node's did:key. Never prints the private key."""
    from kourob import identity

    try:
        typer.echo(identity.load_did(node))
    except FileNotFoundError as exc:
        _fail(str(exc))


@loop_app.command("run")
def loop_run(
    name: Annotated[str, typer.Argument(help="ingest|compile|lint|evolve|prune|reflect")],
    node: Annotated[Path, typer.Option()] = Path("."),
    budget: Annotated[float, typer.Option(help="Credit budget for this run.")] = 1.0,
) -> None:
    """Run one loop once. Each loop outputs a PR or an event, nothing else."""
    if name == "compile":
        from kourob.loops.compile import run as run_compile

        typer.echo(str(run_compile(node)))
        return
    if name == "lint":
        from kourob.loops.lint import lint_node
        from kourob.node import open_node

        lint_report = lint_node(open_node(node))
        for flag in lint_report.flags:
            typer.echo(f"  {flag}")
        colour = typer.colors.GREEN if lint_report.ok else typer.colors.RED
        typer.secho(str(lint_report), fg=colour)
        if not lint_report.ok:
            raise typer.Exit(1)
        return
    if name != "evolve":
        _todo(f"loop run {name}", "M2", "section 6.1")
        return

    from kourob.loops.evolve import evolve, render

    report = evolve(node)
    typer.echo(render(report))
    if not report.constraints_held():
        typer.secho(
            "constraints broken: cost may fall only if verifiability and "
            "quality did not (KNP-5 section 1)",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)


@loop_app.command("list")
def loop_list(node: Annotated[Path, typer.Option()] = Path(".")) -> None:
    """List loops, their triggers, their budgets, and when each last ran."""
    from kourob.loops.evolve import past_reports
    from kourob.manifest import load as load_manifest

    manifest = load_manifest(node)
    runs = {"evolve": len(past_reports(node))}
    for loop_name, config in manifest.loops.items():
        trigger = (config or {}).get("trigger", "-")
        budget = (config or {}).get("budget_credits", "-")
        status = "implemented" if loop_name == "evolve" else "stub (M2)"
        typer.echo(
            f"{loop_name:<9} {trigger:<10} budget {budget!s:<6} "
            f"runs {runs.get(loop_name, 0):<4} {status}"
        )


@distill_app.command("train")
def distill_train(node: Annotated[Path, typer.Option()] = Path(".")) -> None:
    """Train the T1 student from settled answers and switch it on. Refuses without gold."""
    from kourob.node import open_node
    from kourob.tiers.t1_student import T1Student, load_student

    try:
        path = T1Student.enable(open_node(node))
    except ValueError as exc:
        _fail(str(exc))
        return
    student = load_student(node)
    assert student is not None
    typer.secho(
        f"trained {student.version}: {student.trained_on} settled examples", fg=typer.colors.GREEN
    )
    typer.echo(f"  model  {path}")
    typer.echo(f"  bar    {student.bar:.2f}  (calibrated on gold, per class)")


@distill_app.command("calibrate")
def distill_calibrate(node: Annotated[Path, typer.Option()] = Path(".")) -> None:
    """Score the student against gold, per class, and set its confidence bar."""
    from kourob.loops.distill.calibrate import calibrate_bar, compare_to_teacher
    from kourob.node import open_node

    cell = open_node(node)
    try:
        scores = compare_to_teacher(cell)
    except ValueError as exc:
        _fail(str(exc))
        return
    bar = calibrate_bar(cell)
    typer.echo(
        f"gold {scores.n}  teacher {scores.teacher_accuracy:.3f}  student "
        f"{scores.student_accuracy:.3f}  gap {scores.gap:+.3f}  bar {bar:.2f}"
    )
    for label, row in sorted(scores.per_class.items()):
        typer.echo(
            f"  {label:<24} n={int(row['n']):<4} teacher {row['teacher_accuracy']:.2f}  "
            f"student {row['student_accuracy']:.2f}"
        )
    if scores.gap > 0.02:
        typer.secho(
            f"student is {scores.gap:.3f} behind the teacher (weakest: {scores.weakest_class}); "
            "KNP-5 section 3.2 allows 0.02",
            fg=typer.colors.YELLOW,
        )


@distill_app.command("gold")
def distill_gold(
    path: Annotated[Path, typer.Argument(help="JSONL of {question, label} rows.")],
    task: Annotated[str, typer.Option(help="Which task these label.")] = "scope_classifier",
    node: Annotated[Path, typer.Option()] = Path("."),
) -> None:
    """Push labelled examples into gold. Through the gate, like everything else."""
    from kourob.node import open_node

    cell = open_node(node)
    report = cell.gate.ingest_gold(path.read_text(encoding="utf-8").splitlines(), task=task)
    typer.secho(
        f"gold: accepted {report.accepted}, rejected {report.rejected}", fg=typer.colors.GREEN
    )
    for step, count in sorted(report.reasons.items()):
        typer.echo(f"  {count:>4}  {step}")


@scope_app.command("show")
def scope_show(node: Annotated[Path, typer.Option()] = Path(".")) -> None:
    """Print what this node claims to answer, and what it declares out of scope."""
    from kourob.node import open_node

    scope = open_node(node).manifest.scope
    typer.echo(scope.summary)
    typer.echo(f"  schemas   {', '.join(scope.schemas) or 'none'}")
    typer.echo(f"  max hops  {scope.max_hops}")
    for exclusion in scope.excludes:
        typer.echo(f"  excludes  {exclusion.pattern!r} -> {exclusion.refer_to or 'nobody known'}")


@scope_app.command("check")
def scope_check(
    question: Annotated[str, typer.Argument(help="Request to classify.")],
    node: Annotated[Path, typer.Option()] = Path("."),
) -> None:
    """Classify a request: in_scope, referral, or reject. Runs no tier."""
    from kourob import scope as scope_mod
    from kourob.node import open_node
    from kourob.routes import RouteTable

    cell = open_node(node)
    decision = scope_mod.check(
        cell.manifest,
        RouteTable(cell.store, cell.manifest.prune),
        question,
        own_did=cell.did,
        hops=[],
    )
    typer.echo(f"{decision.result.value}  decided by {decision.decided_by}")
    if decision.reason:
        typer.echo(f"  reason   {decision.reason.value}")
    for hint in decision.hints:
        typer.echo(f"  route    {hint.name or hint.node}  {hint.scope[:50]}")


@cell_app.command("size")
def cell_size(node: Annotated[Path, typer.Option()] = Path(".")) -> None:
    """Measure this cell against its declared ceiling. Non-zero exit when over budget."""
    from kourob.node import cell_size, open_node

    report = cell_size(open_node(node))
    for name, (value, limit) in report["measured"].items():
        over = value > limit
        colour = typer.colors.RED if over else typer.colors.GREEN
        typer.secho(f"{'OVER' if over else '  ok'}  ", fg=colour, nl=False)
        typer.echo(f"{name:<16} {value} / {limit}")
    if report["over"]:
        typer.secho(
            f"over budget: {', '.join(report['over'])}. "
            "A cell does not grow past its ceiling: shed or divide.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)


@cell_app.command("seams")
def cell_seams(node: Annotated[Path, typer.Option()] = Path(".")) -> None:
    """Find where this cell could divide: the minimum cut over schema and tool co-occurrence."""
    _todo("cell seams", "M4", "docs/protocols/knp-8-cells.md section 3.1")


@cell_app.command("divide")
def cell_divide(
    seam: Annotated[str, typer.Argument(help="Seam id from `kourob cell seams`.")],
    node: Annotated[Path, typer.Option()] = Path("."),
) -> None:
    """Propose a division along a seam: child manifest, narrowed parent, referral rule."""
    _todo("cell divide", "M4", "docs/protocols/knp-8-cells.md section 3")


@outcome_app.command("submit")
def outcome_submit(
    receipt_id: Annotated[str, typer.Argument(help="The receipt being judged.")],
    verdict: Annotated[
        str, typer.Option(help="accepted|corrected|rejected|superseded")
    ] = "accepted",
    evidence: Annotated[
        list[str] | None, typer.Option(help="Event id(s) that say what was true.")
    ] = None,
    by: Annotated[str, typer.Option(help="did:key or user:<id> reporting it.")] = "",
    note: Annotated[str, typer.Option(help="One line of context.")] = "",
    node: Annotated[Path, typer.Option()] = Path("."),
) -> None:
    """Record whether an answer held up. Never edits the receipt it judges."""
    from kourob.ledger.outcome import OutcomeSource, Verdict
    from kourob.ledger.outcomes import OutcomeError, submit
    from kourob.node import open_node

    cell = open_node(node)
    try:
        outcome = submit(
            cell.ledger,
            receipt_id,
            verdict=Verdict(verdict),
            source=OutcomeSource.HUMAN if by.startswith("user:") else OutcomeSource.CALLER,
            evidence=list(evidence),
            by=by or None,
            note=note or None,
        )
    except (OutcomeError, ValueError) as exc:
        _fail(str(exc))
        return
    typer.secho(
        f"{outcome.id}  {outcome.verdict.value} by {outcome.source.value}", fg=typer.colors.GREEN
    )


@outcome_app.command("list")
def outcome_list(
    receipt_id: Annotated[str, typer.Option(help="Only outcomes about this receipt.")] = "",
    node: Annotated[Path, typer.Option()] = Path("."),
) -> None:
    """Show what has been said about this node's answers."""
    from kourob.ledger.outcomes import outcomes_for, read_outcomes
    from kourob.node import open_node

    cell = open_node(node)
    found = outcomes_for(cell.ledger, receipt_id) if receipt_id else read_outcomes(cell.ledger)
    if not found:
        typer.secho("no outcomes yet", fg=typer.colors.YELLOW)
        return
    for outcome in found:
        typer.echo(
            f"{outcome.id}  {outcome.verdict.value:<10} {outcome.source.value:<10} "
            f"about={outcome.about}  {outcome.note or ''}"
        )


@outcome_app.command("status")
def outcome_status(node: Annotated[Path, typer.Option()] = Path(".")) -> None:
    """How much of what this node said has been checked, and how much held up."""
    from kourob.ledger.outcomes import settlement_status
    from kourob.node import open_node

    cell = open_node(node)
    status = settlement_status(cell.ledger, cell.contracts)
    typer.echo(f"  receipts     {status.total}")
    typer.echo(
        f"  settled      {status.settled}  (accepted {status.accepted}, "
        f"corrected {status.corrected}, rejected {status.rejected})"
    )
    typer.echo(f"  pending      {status.pending}   still inside their outcome window")
    typer.echo(f"  unresolved   {status.unresolved}   window passed with nothing said")
    typer.echo(f"  settle rate  {status.settle_rate:.2f}")
    accept = "n/a" if status.accept_rate is None else f"{status.accept_rate:.2f}"
    typer.echo(f"  accept rate  {accept}")
    typer.echo(f"  quality      {status.quality_multiplier():.2f}   (unresolved counts against it)")


def main() -> None:
    """Console-script entry point (`kourob`)."""
    app()


if __name__ == "__main__":
    main()

# 2026-09-11 · antigravity · public site

Task: `kb-14g` (Public site for KouroB). Closed.

## Done

### 1. Modern Web Public Site — `site/`

Created a self-contained, high-performance public landing and interactive demonstration site for KouroB in `site/`:

- **Design & Typography**: Standards-compliant CSS using CSS custom properties, `color-scheme: light dark`, `light-dark()` with `@media (prefers-color-scheme: dark)` fallback, `text-wrap: balance` on headings, `text-wrap: pretty` on copy, and custom-styled scrollbars.
- **Interactive Node Playground**:
  - Simulates the full KouroB request handling pipeline: Authenticate & Meter &rarr; Scope Check &rarr; Tier Cascade &rarr; Answer Envelope &rarr; Signed Hash-Chained Ledger.
  - Interactive scenario toggles:
    - **T0 Exact Match**: Mined rule binds, $0.00 model cost, 8ms latency, `derived` determinism.
    - **T3 Frontier Cascade**: Grounded event retrieval over `data/silver/events.parquet`, cited answer synthesis.
    - **KNP-1 Scope Referral**: Detects Tennis domain query, refers to neighbor `predict-node` with route hint.
    - **Scope Rejection**: Unsupported request outside declared entity/capability schemas.
  - Custom query input supporting real-time interactive simulation.
  - Real cryptographic hashing via `crypto.subtle.digest('SHA-256')` for request hash, response hash, and hash-chain `prev` verification.
  - Output panels for the wire envelope `{data, rendered, citations, receipt_id}`, the cryptographic signed receipt, and the W3C PROV-O provenance graph.
- **5-Tier Cascade Breakdown**: Interactive comparison table covering T0 (Rules/SQL), T1 (Distilled Model), T2 (Specialized Model), T3 (Frontier Model), and T4 (Human in Loop) with determinism classes and cost economics.
- **KNP Protocol Specifications**: Visual breakdown of KNP-0 through KNP-5 wire contracts and core invariants.
- **Agent Connectivity Showcase**: One-click quickstarts for attaching Claude Code (`kourob attach claude-code`), Cursor, A2A, and REST.
- **CLI Runbooks**: Interactive command cheat sheet for `init`, `ingest`, `query`, `serve`, `trace`, `tend`, and `meter`.

### 2. Machine & Agent Discovery Interfaces

- `site/llms.txt`: Curated LLMs.txt manifest providing clean markdown context for AI agents reading the repository.
- `site/robots.txt`: Search engine crawling rules allowing full indexing.
- `site/sitemap.xml`: XML sitemap for SEO discovery.
- In-browser **WebMCP** integration: Dynamically exposes `kourob_query` as a client-side tool via `document.modelContext.registerTool` for browser agents when WebMCP is enabled in Chromium.

### 3. CI/CD Deployment

- `.github/workflows/deploy-site.yml`: GitHub Actions workflow to publish `site/` to GitHub Pages upon push to `main`.

## Verification

1. Local server test: Verified with Python `http.server` on port 8921; status 200 returned for `/`, `/styles.css`, `/app.js`, `/llms.txt`.
2. Full test suite: `uv run pytest -q` passed completely (`206 passed, 4 xfailed in 205s`).
3. Linter: `uv run ruff check .` passed with zero errors.

## Surprises

1. `bd` was located under Claude Desktop's package cache (`C:\Users\houck\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\npm\bd.exe`) rather than the system PATH. Added to session PATH to interact with Beads.
2. WebMCP API (`document.modelContext.registerTool`) allows native client-side tool registration for visiting browser agents without needing a backend server running.

## Not Done

- Custom domain DNS: When `kourob.org` is registered, add `site/CNAME` pointing to the GitHub Pages domain.

## Open Questions

1. Should `kourob serve --web` or `kourob serve --site` be added as a built-in CLI convenience flag to serve the `site/` directory locally?

## Resume

```bash
cd C:/Users/houck/kourob
uv run pytest -q
python -m http.server 8000 --directory site
bd ready
```

# ADR-0001: Store interface, Parquet + DuckDB default
Status: accepted
Date: 2026-09-09

Context:
  A node's event store is the canonical record of everything it knows (brief section 3).
  Every other subsystem reads it: the gate writes to it, the compile loop reads it to
  build pages, the ledger cites event ids from it, the evolve loop queries the request log
  alongside it. The store is therefore the single most load-bearing interface in the
  package, and the one most likely to be wrong for somebody else's deployment.

  Two requirements pull in opposite directions. v1 must be zero-infrastructure: `kourob
  init` has to produce a working node in under ten minutes on a laptop with no server to
  install (GOAL.md metric 1). But a node that grows past one operator will want
  transactional writes, concurrent readers, and in some cases a database that versions
  rows natively.

Options considered:
  A. **Parquet files + DuckDB for query, behind a `Store` interface.** Append-only,
     partitioned by month. No server. SQL over the files. DuckDB reads Parquet natively,
     so T0 (SQL over silver) is free.
  B. **Dolt** (a SQL database with git-style versioning). Natively versioned rows, diffs,
     merges — an attractive fit for "the repo is memory". Not explored with a spike
     because it is a server to install and a second versioning system alongside git and
     DVC; adopting it in v1 would fail the zero-infrastructure requirement. Kept as a
     first-class backend candidate behind the interface.
  C. **Postgres.** Mature, transactional, everyone knows it. Not explored with a spike
     because it fails the zero-infrastructure requirement outright for v1. Same as B: a
     backend, not the default.
  D. **SQLite.** Zero-infrastructure and transactional, but poor at columnar scans over
     event history and awkward to diff in git. Not explored with a spike because DuckDB
     covers the analytical access pattern better and Parquet diffs are handled by DVC.
  E. **No interface, just call DuckDB everywhere.** Simplest to write. Rejected: it makes
     B and C impossible without rewriting every caller, and the brief explicitly asks for
     the interface (section 9, ADR-0001).

Decision:
  Define a `Store` abstract interface in `src/kourob/store/base.py` covering: `append`,
  `query` (SQL string in, Arrow table out), `get` by event id, `partitions`, `compact`,
  and `stats`. Ship exactly one implementation in v1: `ParquetDuckDBStore` in
  `src/kourob/store/parquet_duckdb.py`, append-only, partitioned by month, with silver as
  the queryable zone.

  The interface is chosen so that a row-versioned backend (Dolt) can implement it without
  the interface changing: no method exposes a file path, a partition layout, or a DuckDB
  connection to callers. Callers that need SQL pass a SQL string against logical table
  names (`silver`, `quarantine`, `requests`, `receipts`), which the backend resolves.

Consequences:
  - Zero infrastructure for v1. `kourob init` produces a working store with no server.
  - T0 tier is cheap by construction: a rule is a SQL view over `silver`.
  - Concurrent writers are **not** supported in v1. A node is one process. This is written
    into the manifest as a constraint, not discovered later.
  - Any code that reaches for a `.parquet` path directly outside `src/kourob/store/` is a
    layering violation. CI greps for it.
  - Swapping in Dolt or Postgres later is one new module plus a manifest key, not a
    rewrite.

Revisit when:
  A node needs concurrent writers, or a set operator needs cross-node transactional reads,
  or the event count on any single node exceeds what a single-process DuckDB scan can
  serve inside the node's latency budget. Whichever comes first.

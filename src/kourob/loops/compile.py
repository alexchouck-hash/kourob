"""compile: events to pages and index.

Brief reference: section 6.1. The loop is a thin call into `knowledge.compile`; it exists
so `kourob loop run compile` and `tend` have one name for it.
"""

from __future__ import annotations

from pathlib import Path

from kourob.knowledge.compile import CompileReport, compile_pages

__milestone__ = "M2"


def run(node_dir: Path | str) -> CompileReport:
    from kourob.node import open_node

    return compile_pages(open_node(node_dir))


__all__ = ["CompileReport", "run"]

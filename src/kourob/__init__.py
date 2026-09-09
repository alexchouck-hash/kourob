"""KouroB: metered, provenance-tracked, self-specializing nodes.

A node owns a slice of the world (typed events, compiled knowledge, tools, provenance),
serves requests through standard ports, refuses or refers what is out of scope, and leaves
a signed receipt for every request.

See GOAL.md for what success means and docs/brief/07-kourob-development.md for the design.
"""

from __future__ import annotations

__version__ = "0.1.0"
__all__ = ["__version__"]

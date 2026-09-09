# Reference UI

**Lands in M5.** A thin client over a node's REST port, and nothing else.

The acceptance criterion is the constraint: *"The reference UI renders a node's answer
from REST with no node-specific code."* It fetches `{data, rendered, citations,
receipt_id}` and renders it. It knows nothing about tennis, or about this repository, or
about any schema.

A UI is just another caller (brief section 7). If this directory ever grows a dependency
on a particular node, that is the bug.

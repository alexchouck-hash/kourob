# Tools

One file per tool. Each declares:

```yaml
name: <tool-name>
description: <what it does, in one line>
schema: <ODCS contract id for its input>
scope: <what part of the node's scope it serves>
dry_run: true          # can it be called with no side effect?
review_required: false # true routes every call through T4, the human queue
audit: true            # every call is written to the tool audit log
```

A tool with `review_required: true` is the only way a request reaches T4.

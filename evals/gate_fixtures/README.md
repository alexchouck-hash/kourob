# Gate fixtures

Brief section 12, M1: *"Gate fixture eval: precision and recall of rejections ≥ 0.95 on
`evals/gate_fixtures/`."*

Each line of `events.jsonl` is a push, annotated with what the gate is supposed to do:

| Field | Meaning |
|---|---|
| `_expect` | `accept` or `reject` |
| `_reason` | for rejects, which gate step should catch it |
| `_note` | why this case exists |

Everything not prefixed with `_` is the push itself.

`malformed.jsonl` holds lines that are not valid JSON. They belong in a separate file
because a JSONL reader cannot annotate them; every line in it must be rejected at the
`parse` step.

The gate steps, in order (brief section 3.1 step 3):
`stamp` → `parse` → `validate` → `dedupe` → `classify` → `threshold` → `route`.

`threshold.novelty` has no case here, deliberately. For a shot event, "adds nothing over
what the node already holds" *is* a duplicate, and labelling it as novelty would be
pretending the step does work it does not do at this grain. Novelty thresholding earns a
fixture when pages and documents arrive in M2, where a push can be new bytes and no new
information.

Precision and recall are measured over rejections: a gate that rejects everything has
recall 1.0 and terrible precision, and a gate that accepts everything has the reverse.
Both must be at least 0.95.

# ADR-0002: License: Apache-2.0
Status: accepted
Date: 2026-09-09

Context:
  KouroB is intended to be built on by other people, and to build on projects that are
  already licensed. The nearest neighbours in the ecosystem — Beads (task graph), A2A
  (node-to-node port, Linux Foundation), Dolt (candidate store backend) — are Apache-2.0.
  The project also expects corporate contributors, which makes the patent question real
  rather than theoretical.

Options considered:
  A. **Apache-2.0.** Permissive, includes an explicit patent grant and a patent
     retaliation clause, has a NOTICE mechanism, and is the license corporate legal teams
     approve without a conversation. Matches Beads, A2A, and Dolt.
  B. **MIT.** Shorter and more widely recognised, but carries no explicit patent grant.
     Not explored with a spike because the patent grant is the deciding factor and MIT
     does not have one; the rest of MIT's advantages are stylistic.
  C. **AGPL-3.0.** Would force nodes served over a network to publish changes — superficially
     attractive for a project about provenance. Not explored with a spike because it makes
     KouroB unusable inside most companies, which directly contradicts the GOAL.md target
     that "any builder can create a node", and because it is incompatible with linking
     against the Apache-2.0 neighbours the design depends on.
  D. **Dual license (Apache-2.0 + commercial).** Not explored with a spike because there
     is no commercial offering to license, and adding a CLA now would deter the early
     contributors the project needs most.

Decision:
  Apache-2.0 for the whole repository, including `template/` (so nodes created by
  `kourob init` are unencumbered) and `examples/`. `LICENSE` at the repo root, SPDX
  identifier `Apache-2.0` in `pyproject.toml`. No CLA. No NOTICE file until there is
  third-party Apache-2.0 code vendored in that requires one.

Consequences:
  - Contributors grant patent rights on their contributions; users get a patent grant.
  - Compatible with Beads, A2A, Dolt, DVC, DuckDB, and the rest of the stack in brief
    section 9.
  - Anyone may run a KouroB node commercially without publishing changes. This is the
    intended outcome: the network is more valuable with more nodes in it.
  - Example data in `examples/` must be separately checked: data is not covered by a code
    license. Match Charting Project data used in `examples/tennis-node` carries its own
    terms and is DVC-referenced, not vendored.

Revisit when:
  A commercial offering exists that a dual license would protect, or a dependency's
  license changes in a way that makes Apache-2.0 untenable.

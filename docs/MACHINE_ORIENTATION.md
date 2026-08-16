# Machine Orientation Contract

Atlas is meant to be useful to both humans and machine actors. `atlas.json` is therefore more than a list of repositories: it is a bounded orientation contract describing stable component IDs, maturity, authority class, explicit relationships, task entry points, and freshness guidance.

It is still **non-normative**.

## Consumer sequence

A human or agent consuming Atlas should:

1. identify the requested capability, decision, or claim;
2. resolve the owning component using stable IDs and explicit relationships;
3. inspect `maturity` and `authority_class` separately;
4. follow the owning repository or governing specification;
5. verify implementation-sensitive facts before acting;
6. preserve `UNKNOWN` if the necessary evidence is missing, stale, unsupported, or contradictory.

This sequence is encoded in `atlas.json -> consumer_contract` so tooling can apply the same orientation logic.

## Why Atlas does not infer transitive authority

If A consumes B and B validates C, Atlas does not infer that A owns B, that A can issue C's claims, or that the relationship is bidirectional. Relationship records describe one bounded family edge at a time.

This is the same family rule expressed elsewhere as:

- capability is not authority;
- transport is not trust;
- execution is not conformance;
- publication is not acceptance;
- learning is not authority.

## Canonical data, derived human views

Starting with Atlas schema 0.3, the public site enhances its project registry, maturity view, institutional architecture layer, and machine-consumer summary from `atlas.json` at runtime. Static HTML remains a fallback, but the structured family map is the preferred source for data-driven orientation.

This reduces a recurring failure mode in documentation systems: a human page and a machine registry drifting into two different descriptions of the same family.

## Rights and provenance

`mncs-rights-provenance` is the first project to exercise a new kind of family relationship: institutional evidence that may eventually influence release policy without becoming a runtime dependency today.

Atlas records that distinction explicitly:

- Fabric can provide bounded execution/provenance evidence.
- Forge can provide lineage and source-analysis evidence.
- Commons can preserve findings, decisions, questions, and superseded interpretations.
- Rights & Provenance can advise future MNCS/MNCDS rules only through explicit adoption.

A provenance record can describe origin and transformation without deciding authorship, ownership, or copyrightability. Legal uncertainty is not converted to a false PASS state.

## Freshness

Atlas includes a review date and a freshness policy. An agent should treat stale orientation as a reason to verify the owning repository, not as permission to guess.

When an owning repository contradicts Atlas about its current implementation, the owning repository wins and Atlas should be updated.

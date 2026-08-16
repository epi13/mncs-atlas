# MNCS Family Maturity Model

MNCS Atlas uses maturity labels to describe the **kind of commitment a family component currently makes**. They are orientation metadata, not a universal quality score, certification, readiness ranking, or source of authority.

The canonical machine-readable definitions live in `atlas.json` under `maturity_model`.

## Incubating

An official family project whose problem and ownership are recognized but whose contracts, schemas, interfaces, or conclusions are expected to change materially.

**Dependency rule:** sibling systems should not require an incubating component unless an explicit versioned adoption decision says otherwise.

`mncs-rights-provenance` begins here. It is part of the MNCS family now, but it is intentionally not a hard runtime dependency or a replacement for Apache-2.0.

## Research

Work intended to discover, test, or characterize mechanisms and claims rather than provide a stable operational contract.

**Dependency rule:** consume results as scoped evidence or proposals, not governing truth.

## Experimental

A specification or system with a concrete usable contract that remains explicitly experimental and may change incompatibly.

**Dependency rule:** bind by explicit versions and preserve `UNKNOWN` for unsupported behavior.

## Active infrastructure

Infrastructure actively used in the reference operator environment while remaining non-normative unless separately specified.

**Dependency rule:** respect lifecycle ownership and public service boundaries. Operational use does not create conformance authority.

## Orientation

Documentation or discovery infrastructure whose purpose is to describe and route rather than govern implementation truth.

**Dependency rule:** verify implementation-sensitive claims at the owning project before acting.

## Maturity is not authority

A component may be operationally mature and still have no normative authority. A young specification may own a clearly bounded experimental vocabulary without becoming a runtime requirement. Atlas therefore records `maturity` and `authority_class` separately.

Examples:

- MNCS and MNCDS: experimental + normative specification authority.
- Fabric: active infrastructure + operator execution authority only.
- Rights & Provenance: incubating + non-normative specification work.
- Atlas: orientation + orientation-only authority.

## Promotion

Changing a maturity label should be an explicit family decision grounded in observable evidence: stable interfaces, validated use, adopted contracts, known failure modes, or clarified governance. Do not promote a component merely because it is frequently used or because another component depends on it accidentally.

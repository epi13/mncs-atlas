# Contributing to MNCS Atlas

MNCS Atlas exists to reduce orientation cost across the MNCS project family without creating a second, competing copy of each project's documentation.

## What belongs here

Good Atlas contributions include:

- family-level authority and architecture explanations;
- operator/runtime maps that clarify current deployment topology without making it normative;
- project maps and responsibility boundaries;
- lifecycle-ownership and service-consumer boundaries;
- terminology used across multiple repositories;
- human and agent onboarding paths;
- machine-readable orientation and relationship metadata;
- diagrams that explain cross-project flows;
- links to authoritative project documentation;
- corrections when the family map has drifted from implementation reality.

Implementation details that are local to one repository usually belong in that repository instead.

## Before opening a change

1. Read [AGENTS.md](AGENTS.md), even if you are a human contributor; it summarizes the authority/lifecycle boundaries Atlas is expected to preserve.
2. Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). If the change touches a running deployment, service lifecycle, model routing, Control, MNCS Harness, Fabric, or Commons, also read [docs/OPERATING_MODEL.md](docs/OPERATING_MODEL.md).
3. Read the README or specification of every project whose relationship you are changing.
4. Prefer links and concise summaries over copied implementation detail.
5. Distinguish current implementation from future intent and public projects from deployment-private/operator implementations.
6. Preserve `PASS`, `FAIL`, and `UNKNOWN` semantics. Do not turn missing evidence into positive claims.
7. Preserve lifecycle ownership. A service consumer should not be described as owning a persistent service merely because it can call or observe it.
8. Do not describe Forge, Fabric, Commons, RAVEL, MNEL, Control, MNCS Harness, a model, or Atlas itself as having MNCS conformance authority unless a normative MNCS document explicitly grants that authority. Harness, Control, Fabric, Forge, Commons, RAVEL, and MNEL are not mandatory for MNCS conformance.

## Site changes

The site is deliberately dependency-free. Keep it usable as static HTML/CSS/JavaScript unless there is a strong reason to add a build system.

`site/` is the canonical website source. The repository root contains a generated compatibility mirror so GitHub Pages also works if the repository is accidentally configured for legacy `main:/` branch publishing. Do not edit the root mirror directly.

After changing files in `site/`, refresh the compatibility mirror:

```bash
python scripts/sync_pages_root.py
```

Preview locally with:

```bash
python3 -m http.server 8000 --directory site
```

Run the dependency-free checks before opening a PR:

```bash
python scripts/sync_pages_root.py --check
python scripts/check_site.py
python scripts/check_journal.py
python -m unittest discover -s tests -t . -v
```

Check at minimum:

- desktop and narrow/mobile layout;
- keyboard navigation and visible focus states;
- readable contrast;
- internal anchor links;
- external repository links;
- consistency between the site, `atlas.json`, its schema, and `docs/` source material;
- crawler/discovery files (`robots.txt`, `sitemap.xml`);
- root mirror parity with the canonical `site/` tree.

## Machine-readable orientation

`site/atlas.json` is intentionally non-normative. Keep it versioned and aligned with the family map.

When changing it:

- preserve stable component IDs unless identity genuinely changes;
- give every relationship valid `from` and `to` component IDs;
- distinguish public `projects` from deployment-specific `operator_components`;
- keep task-oriented `entry_points` bounded and descriptive;
- update `last_reviewed` when the family map has actually been checked against current owning documentation;
- update `site/schema/atlas.schema.json` when the machine-map shape changes;
- never treat the map as a replacement for the owning project's current specifications or documentation.

CI verifies ID uniqueness, relationship references, entry-point references, schema/discovery files, and mirror parity.

## Pull requests

A useful PR description should state:

- what family-level understanding changed;
- which project documentation was consulted;
- whether the change is descriptive, architectural, operator/deployment-specific, or normative;
- which component owns any new persistent state or lifecycle;
- any areas that remain intentionally `UNKNOWN` or provisional.

Atlas changes should make the project family easier to understand without increasing ambiguity about where technical authority or lifecycle ownership lives.

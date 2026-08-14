# Contributing to MNCS Atlas

MNCS Atlas exists to reduce orientation cost across the MNCS project family without creating a second, competing copy of each project's documentation.

## What belongs here

Good Atlas contributions include:

- family-level architecture explanations;
- project maps and responsibility boundaries;
- terminology used across multiple repositories;
- human and agent onboarding paths;
- diagrams that explain cross-project flows;
- links to authoritative project documentation;
- corrections when the family map has drifted from implementation reality.

Implementation details that are local to one repository usually belong in that repository instead.

## Before opening a change

1. Read [AGENTS.md](AGENTS.md), even if you are a human contributor; it summarizes the authority boundaries Atlas is expected to preserve.
2. Read the README or specification of every project whose relationship you are changing.
3. Prefer links and concise summaries over copied implementation detail.
4. Distinguish current implementation from future intent.
5. Preserve `PASS`, `FAIL`, and `UNKNOWN` semantics. Do not turn missing evidence into positive claims.
6. Do not describe Forge, Fabric, Commons, RAVEL, MNEL, a model, or Atlas itself as having MNCS conformance authority unless a normative MNCS document explicitly grants that authority.

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
```

Check at minimum:

- desktop and narrow/mobile layout;
- keyboard navigation and visible focus states;
- readable contrast;
- internal anchor links;
- external repository links;
- consistency between the site, `atlas.json`, and `docs/` source material;
- root mirror parity with the canonical `site/` tree.

## Machine-readable orientation

`site/atlas.json` is intentionally non-normative. Keep it concise, versioned, and aligned with the family map. It may help agents discover project roles and repositories, but it must never be treated as a replacement for the owning project's current specifications or documentation.

## Pull requests

A useful PR description should state:

- what family-level understanding changed;
- which project documentation was consulted;
- whether the change is descriptive, architectural, or normative;
- any areas that remain intentionally `UNKNOWN` or provisional.

Atlas changes should make the project family easier to understand without increasing ambiguity about where technical authority lives.

# MNCS Atlas

**A family-level guide to the Machine-Native Complexity Standard (MNCS) project ecosystem.**

MNCS Atlas is the front door for the wider MNCS project family. Individual repositories keep their own detailed, authoritative documentation; Atlas explains the larger research program, keeps family terminology consistent, shows how the pieces fit together, distinguishes authority from operator topology, and gives humans and agents a reliable place to start.

**Normative / specification authority** lives in two independently versioned repositories:

- [MNCS](https://github.com/epi13/machine-native-complexity-standard) — Machine-Native Complexity Standard, the normative implementation-evidence standard.
- [MNCDS](https://github.com/epi13/machine-native-complexity-development-specification) — Machine-Native Complexity Development Specification, the independently versioned development-process specification.

The family also contains non-normative specifications, operator infrastructure, research, learning, validation, and orientation projects. Family membership does not itself create runtime dependency or normative authority.

[MNCS Rights & Provenance](https://github.com/epi13/mncs-rights-provenance) is now an official **Incubating** family project. It develops machine-native provenance and rights evidence for artifact origin, transformation lineage, contribution provenance, authorship uncertainty, rights basis, and artifact licensing while intentionally remaining non-normative and not replacing Apache-2.0.

Harness, Control, Fabric, Forge, Commons, RAVEL, MNEL, validators, language research, reference studies, Rights & Provenance, and Atlas itself are not mandatory for MNCS conformance unless a future governing specification explicitly adopts a requirement.

## What Atlas is for

Atlas should answer the questions that do not belong in any one project README:

- What is MNCS and what problem is the project family investigating?
- What is the difference between MNCS and MNCDS?
- Which repository owns which responsibility?
- How do Forge, Fabric, Commons, RAVEL, MNEL, Rights & Provenance, the language work, validators, and studies relate?
- How do current operator components such as MNCS Control MCP and MNCS Harness fit without becoming normative requirements?
- Where does authority live, and where does it explicitly *not* live?
- Which persistent service owns worker presence, execution history, knowledge state, routing policy, or remote-control state?
- What should a new human contributor or coding agent read before changing anything?
- Which terminology should mean the same thing across repositories?
- What is the maturity posture and authority class of each family component?

Atlas intentionally does **not** duplicate detailed implementation documentation. When a repository README, specification, RFC, schema, or source file is authoritative for a local question, Atlas links there instead.

## Repository layout

```text
site/                    canonical dependency-free GitHub Pages source
  index.html             overview, entry points, architecture, runtime, projects
  404.html               project-aware not-found page
  atlas.json             machine-readable family + operator orientation map
  robots.txt             crawler guidance
  sitemap.xml            public Pages sitemap
  schema/
    atlas.schema.json     machine-readable Atlas shape
  assets/
index.html                generated root compatibility mirror of site/index.html
404.html                  generated root compatibility mirror of site/404.html
atlas.json                generated root compatibility mirror of site/atlas.json
robots.txt                generated root compatibility mirror
sitemap.xml               generated root compatibility mirror
schema/                   generated root compatibility mirror of site/schema/
assets/                   generated root compatibility mirror of site/assets/
.nojekyll                 disables legacy Jekyll rendering when Pages uses main:/
docs/
  ARCHITECTURE.md         family-level authority and responsibility map
  OPERATING_MODEL.md      reference operator/runtime path and lifecycle ownership
  PROJECTS.md             project directory and responsibility boundaries
  TERMINOLOGY.md          shared terminology index
  MATURITY.md             family maturity vocabulary and dependency policy
  MACHINE_ORIENTATION.md  contract for safe human/agent use of atlas.json
  JOURNAL_MAINTAINER.md   bounded recurring Development Journal maintainer contract
  JOURNAL_MAINTAINER_IMPLEMENTATION.md
                          implemented maintainer architecture, CLI, and gates
AGENTS.md                 orientation contract for AI/coding agents
CONTRIBUTING.md           contribution guidance for Atlas
scripts/                  site integrity, Pages mirror, and Journal Maintainer CLI wrappers
journal_maintainer/       bounded Development Journal Maintainer implementation
tests/                    Journal Maintainer and publication checks
.github/workflows/        GitHub Pages deployment, site integrity CI, Journal Maintainer schedule
```

The `site/` tree is canonical. Do not hand-edit the root website mirror. After changing the canonical site, regenerate the root compatibility files with:

```bash
python scripts/sync_pages_root.py
```

CI rejects a stale mirror.

## Local preview

No build toolchain is required.

```bash
python3 -m http.server 8000 --directory site
```

Then open `http://localhost:8000`.

## GitHub Pages

The preferred configuration is **Settings → Pages → Build and deployment → Source: GitHub Actions**. The included Pages workflow uploads `site/` as a static artifact and deploys it through GitHub Pages.

Atlas also keeps a generated root compatibility mirror because GitHub's legacy branch publishing can only serve supported branch paths such as `/` or `/docs`; it cannot publish the canonical `site/` directory directly. If Pages is accidentally left on **Deploy from a branch → main → /(root)**, the root mirror and `.nojekyll` still serve the real Atlas homepage instead of GitHub rendering the repository README as the site.

This dual-mode layout makes the public front door resilient while keeping `site/` the single source of truth.

## Authority map vs operating model

Atlas deliberately keeps two related views:

- [Architecture](docs/ARCHITECTURE.md) answers **who is allowed to claim what?**
- [Operating model](docs/OPERATING_MODEL.md) answers **how does the reference operator stack actually get bounded work done?**

That distinction prevents protected remote control, model routing, persistent execution, knowledge storage, institutional provenance, and normative evaluation from collapsing into one vague "control plane."

## Machine-readable Atlas

`site/atlas.json` is a non-normative orientation surface for agents and tooling. Version 0.3 adds:

- `mncs-rights-provenance` as an official Incubating family project;
- explicit `authority_class` metadata separate from maturity;
- a machine-readable family maturity model and dependency policy;
- a machine consumer contract describing safe resolution order and UNKNOWN behavior;
- additional rights/provenance relationships across Fabric, Forge, Commons, MNCS, MNCDS, and MNEL;
- data-driven website enhancement so the project registry and maturity presentation derive from the canonical machine map;
- stable IDs, operator components, relationship records, entry points, freshness guidance, and the published JSON Schema.

The machine map is deliberately orientation data rather than a conformance or authority source. See [Machine Orientation Contract](docs/MACHINE_ORIENTATION.md).

## Family documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Operating model](docs/OPERATING_MODEL.md)
- [Project directory](docs/PROJECTS.md)
- [Terminology](docs/TERMINOLOGY.md)
- [Maturity model](docs/MATURITY.md)
- [Machine orientation contract](docs/MACHINE_ORIENTATION.md)
- [Journal Maintainer contract](docs/JOURNAL_MAINTAINER.md)
- [Journal Maintainer implementation](docs/JOURNAL_MAINTAINER_IMPLEMENTATION.md)
- [Agent orientation](AGENTS.md)
- [Contributing](CONTRIBUTING.md)
- [Machine-readable Atlas](site/atlas.json)
- [Atlas schema](site/schema/atlas.schema.json)
- [Experimental Atlas MNCS/WASM migration record](docs/ATLAS-WASM-MIGRATION.md)

## Site checks

```bash
python scripts/sync_pages_root.py --check
python scripts/check_site.py
python scripts/check_journal.py
python -m unittest discover -s tests -t . -v
```

These checks validate local links and fragments, required assets/discovery files, machine-map identity and relationship integrity, maturity vocabulary, authority classes, consumer-contract structure, `.nojekyll`, journal numbering/covered periods, and byte-for-byte parity between the canonical site and the branch-publishing compatibility mirror.

A dry-run of the Journal Maintainer (no repository mutation):

```bash
python -m journal_maintainer run --dry-run --output-dir /tmp/atlas-journal-dry-run
```

## Documentation rule

**Atlas explains the forest; project READMEs explain the trees.**

If Atlas and an authoritative project document disagree about that project's current implementation, treat the project document as authoritative and update Atlas.

## Status

Atlas is documentation and orientation infrastructure. It is not a normative MNCS or MNCDS specification, validator, evaluator, evidence source, certification system, or conformance authority.

Licensed under Apache-2.0.

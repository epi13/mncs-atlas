# MNCS Atlas

**A family-level guide to the Machine-Native Complexity Standard (MNCS) project ecosystem.**

MNCS Atlas is the front door for the wider MNCS project family. Individual repositories keep their own detailed, authoritative documentation; Atlas explains the larger research program, keeps family terminology consistent, shows how the pieces fit together, and gives humans and agents a reliable place to start.

## What Atlas is for

Atlas should answer the questions that do not belong in any one project README:

- What is MNCS and what problem is the project family investigating?
- What is the difference between MNCS and MNCDS?
- Which repository owns which responsibility?
- How do Forge, Fabric, Commons, RAVEL, MNEL, the language work, validators, and studies relate?
- Where does authority live, and where does it explicitly *not* live?
- What should a new human contributor or coding agent read before changing anything?
- Which terminology should mean the same thing across repositories?
- What is the rough maturity posture of each family component (experimental, research, infrastructure, orientation)?

Atlas intentionally does **not** duplicate detailed implementation documentation. When a repository README, specification, RFC, schema, or source file is authoritative for a local question, Atlas links there instead.

## Repository layout

```text
site/                    canonical dependency-free GitHub Pages source
  index.html             overview, architecture, projects, status, pathways
  404.html               project-aware not-found page
  atlas.json             machine-readable family orientation map
  assets/
index.html                generated root compatibility mirror of site/index.html
404.html                  generated root compatibility mirror of site/404.html
atlas.json                generated root compatibility mirror of site/atlas.json
assets/                   generated root compatibility mirror of site/assets/
.nojekyll                 disables legacy Jekyll rendering when Pages uses main:/
docs/
  ARCHITECTURE.md         family-level architecture and authority map
  PROJECTS.md             project directory and responsibility boundaries
  TERMINOLOGY.md          shared terminology index
AGENTS.md                 orientation contract for AI/coding agents
CONTRIBUTING.md           contribution guidance for Atlas
scripts/                  site integrity and Pages mirror tooling
.github/workflows/        GitHub Pages deployment + site integrity CI
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

## Machine-readable Atlas

`site/atlas.json` is a non-normative orientation surface for agents and tooling. It provides stable project-family names, roles, repositories, maturity labels, responsibility summaries, and core invariants. It is deliberately an orientation map rather than a conformance or authority source.

## Family documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Project directory](docs/PROJECTS.md)
- [Terminology](docs/TERMINOLOGY.md)
- [Agent orientation](AGENTS.md)
- [Contributing](CONTRIBUTING.md)
- [Machine-readable Atlas](site/atlas.json)

## Site checks

```bash
python scripts/sync_pages_root.py --check
python scripts/check_site.py
```

These checks validate local links and fragments, required assets, the machine-readable Atlas shape, `.nojekyll`, and byte-for-byte parity between the canonical site and the branch-publishing compatibility mirror.

## Documentation rule

**Atlas explains the forest; project READMEs explain the trees.**

If Atlas and an authoritative project document disagree about that project's current implementation, treat the project document as authoritative and update Atlas.

## Status

Atlas is documentation and orientation infrastructure. It is not a normative MNCS or MNCDS specification, validator, evaluator, evidence source, certification system, or conformance authority.

Licensed under Apache-2.0.

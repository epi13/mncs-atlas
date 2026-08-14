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

Atlas intentionally does **not** duplicate detailed implementation documentation. When a repository README, specification, RFC, schema, or source file is authoritative for a local question, Atlas links there instead.

## Repository layout

```text
site/                    dependency-free GitHub Pages site
  index.html
  assets/
docs/
  ARCHITECTURE.md        family-level architecture and authority map
  PROJECTS.md            project directory and responsibility boundaries
  TERMINOLOGY.md         shared terminology index
AGENTS.md                 orientation contract for AI/coding agents
CONTRIBUTING.md           contribution guidance for Atlas
.github/workflows/        GitHub Pages deployment
```

## Local preview

No build toolchain is required.

```bash
python3 -m http.server 8000 --directory site
```

Then open `http://localhost:8000`.

## GitHub Pages

The included Pages workflow uploads `site/` as a static artifact and deploys it through GitHub Pages. The repository must use **GitHub Actions** as its Pages source in repository settings.

## Family documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Project directory](docs/PROJECTS.md)
- [Terminology](docs/TERMINOLOGY.md)
- [Agent orientation](AGENTS.md)
- [Contributing](CONTRIBUTING.md)

## Documentation rule

**Atlas explains the forest; project READMEs explain the trees.**

If Atlas and an authoritative project document disagree about that project's current implementation, treat the project document as authoritative and update Atlas.

## Status

Atlas is documentation and orientation infrastructure. It is not a normative MNCS or MNCDS specification, validator, evaluator, evidence source, certification system, or conformance authority.

Licensed under Apache-2.0.

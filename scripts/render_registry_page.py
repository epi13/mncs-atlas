#!/usr/bin/env python3
"""Render a deterministic human view from the compiled family registry."""

from __future__ import annotations

import html
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry/compiled.json"
OUTPUT = ROOT / "site/registry.html"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def project_sections(registry: dict) -> str:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for project in registry["projects"]:
        grouped[project["category"]].append(project)
    sections = []
    for category in sorted(grouped):
        cards = []
        for project in sorted(grouped[category], key=lambda row: row["id"]):
            profile = project.get("language_profile") or "not declared"
            status = project.get("language_profile_status", "not-declared")
            cards.append(
                "<article class=\"project\">"
                f"<h3>{esc(project['name'])} <code>{esc(project['id'])}</code></h3>"
                f"<p>{esc(project['responsibility'])}</p>"
                f"<p class=\"meta\">{esc(project['lifecycle'])} · {esc(project['authority_class'])} · language {esc(profile)} ({esc(status)})</p>"
                "</article>"
            )
        sections.append(f"<section><h2>{esc(category.replace('-', ' ').title())}</h2><div class=\"projects\">{''.join(cards)}</div></section>")
    return "".join(sections)


def capability_table(registry: dict) -> str:
    rows = []
    for capability in registry["capabilities"]:
        implementations = ", ".join(
            claim["project"]
            for claim in capability["claims"]
            if claim["role"] in {"primary-implementation", "secondary-implementation", "experimental-implementation", "integration-layer"}
        ) or "—"
        rows.append(
            "<tr>"
            f"<td><code>{esc(capability['id'])}</code><br>{esc(capability['name'])}</td>"
            f"<td>{esc(capability['ownership'])}</td>"
            f"<td>{esc(capability['canonical_authority'] or 'shared / none')}</td>"
            f"<td>{esc(implementations)}</td>"
            "</tr>"
        )
    return "".join(rows)


def decision_list(registry: dict) -> str:
    return "".join(
        f"<li><code>{esc(row['id'])}</code> — {esc(row['title'])} <span class=\"meta\">({esc(row['owner'])}, {esc(row['status'])})</span></li>"
        for row in registry["decisions"]
    )


def render(registry: dict) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Generated human view of the MNCS Atlas family architecture and ownership registry.">
  <title>MNCS Atlas — Family Registry</title>
  <style>
    :root {{ color-scheme: light; font: 16px/1.55 system-ui, sans-serif; color: #172033; background: #f5f7fb; }}
    body {{ max-width: 1180px; margin: 0 auto; padding: 2rem 1.25rem 4rem; }}
    header, section {{ background: white; border: 1px solid #dce2ee; border-radius: 14px; padding: 1.25rem; margin: 1rem 0; }}
    h1, h2, h3 {{ line-height: 1.2; }} h1 {{ margin-top: 0; }} h3 {{ margin-bottom: .45rem; }}
    a {{ color: #1859a8; }} code {{ font-family: ui-monospace, monospace; font-size: .9em; }}
    .meta {{ color: #63708a; font-size: .88rem; }} .summary {{ display: flex; gap: 1rem; flex-wrap: wrap; }}
    .metric {{ background: #eef3fb; border-radius: 10px; padding: .5rem .75rem; }}
    .projects {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: .75rem; }}
    .project {{ border: 1px solid #e1e6f0; border-radius: 10px; padding: .8rem; }}
    .project p {{ margin: .3rem 0; }} table {{ border-collapse: collapse; width: 100%; }} th, td {{ border-bottom: 1px solid #e1e6f0; padding: .65rem; text-align: left; vertical-align: top; }}
    .scroll {{ overflow-x: auto; }} li {{ margin: .35rem 0; }}
  </style>
</head>
<body>
  <header>
    <p><a href="index.html">← MNCS Atlas</a></p>
    <h1>MNCS Family Registry</h1>
    <p>Generated from the deterministic compiled graph. Atlas records family architecture and ownership; owning repositories retain implementation and semantic authority.</p>
    <div class="summary">
      <span class="metric"><strong>{len(registry['projects'])}</strong> projects</span>
      <span class="metric"><strong>{len(registry['capabilities'])}</strong> capabilities</span>
      <span class="metric"><strong>{len(registry['decisions'])}</strong> indexed decisions</span>
      <span class="metric"><strong>{len(registry['edges'])}</strong> relationships</span>
      <span class="metric">revision <code>{esc(registry['registry_revision'])}</code></span>
    </div>
    <p><a href="registry.json">Machine registry JSON</a> · <a href="schema/registry.schema.json">Schema</a> · <a href="atlas.json">Human orientation map</a></p>
  </header>
  {project_sections(registry)}
  <section>
    <h2>Capability ownership</h2>
    <p class="meta">Canonical authority is a declared relationship, not authority conferred by Atlas. Shared capabilities may have multiple implementations.</p>
    <div class="scroll"><table><thead><tr><th>Capability</th><th>Mode</th><th>Canonical authority</th><th>Implementations / integrations</th></tr></thead><tbody>{capability_table(registry)}</tbody></table></div>
  </section>
  <section><h2>Indexed decisions</h2><ol>{decision_list(registry)}</ol><p class="meta">Decision text stays in the owning repository; this page only indexes identity, scope, status, and ownership.</p></section>
  <footer class="meta">Registry hash: <code>{esc(registry['registry_hash'])}</code>. Commons pressure status is intentionally external to this artifact.</footer>
</body>
</html>
"""


def main() -> int:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    OUTPUT.write_text(render(registry), encoding="utf-8")
    print(f"rendered {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

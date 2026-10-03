/* MNCS Atlas dashboard renderer: dependency-free projection viewer.
 *
 * Reads dashboard.json (same directory) and fills the section shells in
 * dashboard.html. Every UNKNOWN is rendered explicitly; no field implies
 * more than its source declares. No frameworks, no network beyond the
 * single same-origin JSON fetch.
 */
(function () {
  "use strict";

  function el(tag, text, cls) {
    var node = document.createElement(tag);
    if (text !== undefined && text !== null) node.textContent = text;
    if (cls) node.className = cls;
    return node;
  }

  function code(text) {
    return el("code", text);
  }

  function pill(text) {
    var lowered = String(text || "unknown").toLowerCase();
    var cls = "pill";
    if (lowered === "unknown") cls += " unknown";
    else if (lowered === "retired" || lowered === "deprecated" || lowered === "historical") cls += " retired";
    else if (lowered === "active") cls += " active";
    else if (lowered === "fail") cls += " fail";
    return el("span", text, cls);
  }

  function metric(label, value) {
    var span = el("span", null, "metric");
    span.appendChild(el("strong", String(value)));
    span.appendChild(document.createTextNode(" " + label));
    return span;
  }

  function row(cells) {
    var tr = document.createElement("tr");
    cells.forEach(function (cell) {
      var td = document.createElement("td");
      if (cell && cell.nodeType) td.appendChild(cell);
      else td.textContent = cell === undefined || cell === null ? "" : String(cell);
      tr.appendChild(td);
    });
    return tr;
  }

  function shortDigest(digest) {
    if (typeof digest !== "string") return "unknown";
    var parts = digest.split(":");
    var hex = parts.length > 1 ? parts[parts.length - 1] : digest;
    return hex.slice(0, 12);
  }

  function projectCard(entry) {
    var card = el("article", null, "card");
    var title = el("h3");
    title.appendChild(document.createTextNode(entry.name || entry.id));
    title.appendChild(document.createTextNode(" "));
    title.appendChild(code(entry.id));
    card.appendChild(title);
    if (entry.purpose && entry.purpose !== "unknown") {
      card.appendChild(el("p", entry.purpose));
    }
    var meta = el("p", null, "meta");
    meta.appendChild(pill(entry.lifecycle));
    meta.appendChild(document.createTextNode(" · " + (entry.category || "unknown")));
    meta.appendChild(document.createTextNode(" · " + (entry.authority_class || "unknown")));
    if (entry.maturity && entry.maturity !== "unknown") {
      meta.appendChild(document.createTextNode(" · maturity " + entry.maturity));
    } else {
      meta.appendChild(document.createTextNode(" · maturity unknown"));
    }
    card.appendChild(meta);
    var links = el("p", null, "meta");
    if (entry.repository) {
      var repo = el("a", "repository");
      repo.href = entry.repository;
      links.appendChild(repo);
      links.appendChild(document.createTextNode(" "));
    }
    var manifest = entry.manifest;
    if (manifest && manifest.status === "present") {
      links.appendChild(document.createTextNode("manifest rev " + manifest.revision));
    } else {
      links.appendChild(document.createTextNode("no manifest"));
    }
    if (entry.participation && entry.participation.state) {
      links.appendChild(document.createTextNode(" · participation " + entry.participation.state));
    }
    if (!entry.observed_in_workspace) {
      links.appendChild(document.createTextNode(" · not in local workspace"));
    }
    card.appendChild(links);
    return card;
  }

  function render(projection) {
    var envelope = projection;
    var data = projection.projection || projection;

    var metrics = document.getElementById("dash-metrics");
    metrics.textContent = "";
    metrics.appendChild(metric("projects", (data.ecosystem || {}).project_count || 0));
    metrics.appendChild(metric("commons edges", (data.relationships || {}).commons_edge_count || 0));
    metrics.appendChild(metric("pressures", ((data.pressures || {}).total || 0)));
    metrics.appendChild(metric("declared checks", ((data.verification || {}).declared_count || 0)));
    metrics.appendChild(metric("deltas", ((data.movement || {}).delta_count || 0)));

    var observed = (envelope.envelope || {}).source_epoch || "unknown observation";
    document.getElementById("dash-provenance").textContent =
      "Projection " + (data.semantic_hash || "unknown") + " observed at " + observed +
      " · projector " + ((envelope.envelope || {}).projector || "unknown") + ".";
    var hashEl = document.getElementById("dash-hash");
    if (hashEl) hashEl.textContent = data.semantic_hash || "unknown";

    var projects = ((data.ecosystem || {}).projects || []).slice();
    var lifecycleSelect = document.getElementById("filter-lifecycle");
    var lifecycles = Array.from(new Set(projects.map(function (p) { return p.lifecycle || "unknown"; }))).sort();
    lifecycles.forEach(function (lifecycle) {
      var option = el("option", lifecycle);
      option.value = lifecycle;
      lifecycleSelect.appendChild(option);
    });

    var grid = document.getElementById("dash-projects");
    var filterText = document.getElementById("filter-projects");
    function drawProjects() {
      var query = (filterText.value || "").toLowerCase();
      var wanted = lifecycleSelect.value;
      grid.textContent = "";
      var shown = 0;
      projects.forEach(function (entry) {
        var haystack = [entry.id, entry.name, entry.category, entry.lifecycle, entry.authority_class].join(" ").toLowerCase();
        if (query && haystack.indexOf(query) < 0) return;
        if (wanted && (entry.lifecycle || "unknown") !== wanted) return;
        grid.appendChild(projectCard(entry));
        shown += 1;
      });
      if (!shown) grid.appendChild(el("p", "No projects match this filter.", "meta"));
    }
    filterText.addEventListener("input", drawProjects);
    lifecycleSelect.addEventListener("change", drawProjects);
    drawProjects();

    var uncatalogued = ((data.ecosystem || {}).observed_but_uncatalogued || []);
    if (uncatalogued.length) {
      var note = el("p", "Observed in workspace but not in the Atlas catalog: " + uncatalogued.join(", "), "meta");
      grid.parentNode.insertBefore(note, grid.nextSibling);
    }

    var edgeBody = document.querySelector("#dash-edges tbody");
    ((data.relationships || {}).commons_edges || []).forEach(function (edge) {
      edgeBody.appendChild(row([edge.producer, edge.consumer, edge.contract + " rev " + edge.contract_revision, edge.provenance]));
    });
    var limits = ((data.relationships || {}).commons_limitations || []);
    document.getElementById("dash-edge-note").textContent =
      "Atlas registry revision " + (((data.relationships || {}).atlas_registry || {}).registry_revision || "unknown") +
      " · " + (((data.relationships || {}).atlas_registry || {}).edge_count || 0) + " registry edges. " +
      limits.join(" ");

    var capBody = document.querySelector("#dash-capabilities tbody");
    ((data.capabilities || {}).capabilities || []).forEach(function (cap) {
      capBody.appendChild(row([cap.id, cap.owner, cap.kind, cap.lifecycle]));
    });

    var impl = document.getElementById("dash-implementation");
    ((data.implementation || {}).declarations || []).forEach(function (decl) {
      var card = el("div", null, "card");
      card.appendChild(el("h3", decl.source + ": " + (decl.declared_status || decl.status)));
      var state = decl.classification || {};
      var p = el("p", null, "meta");
      p.appendChild(pill(state.state || "unknown"));
      p.appendChild(document.createTextNode(" " + (state.reason || decl.reason || "")));
      card.appendChild(p);
      if (decl.canonical_entrypoint) card.appendChild(el("p", "Entry: " + decl.canonical_entrypoint, "meta"));
      impl.appendChild(card);
    });
    impl.appendChild(el("p", "Per-project states: " + (data.implementation || {}).per_project_states + " — " + (data.implementation || {}).per_project_reason, "meta"));

    var counts = document.getElementById("dash-pressure-counts");
    var byRepo = ((data.pressures || {}).by_repository || {});
    Object.keys(byRepo).sort().forEach(function (repo) {
      counts.appendChild(metric(repo, byRepo[repo]));
    });
    var pressureBody = document.querySelector("#dash-pressure-table tbody");
    ((data.pressures || {}).listed || []).forEach(function (pressure) {
      var what = (pressure.capability || "") + (pressure.domain ? " / " + pressure.domain : "");
      var title = pressure.title ? " — " + pressure.title : "";
      pressureBody.appendChild(row([
        pressure.id,
        (pressure.repositories || []).join(", "),
        what + title,
        pressure.status,
      ]));
    });
    document.getElementById("dash-pressure-note").textContent =
      ((data.pressures || {}).lifecycle_note || "") +
      (((data.pressures || {}).truncated) ? " · list capped at " + ((data.pressures || {}).listed || []).length + " of " + (data.pressures || {}).total + "." : "");

    var verifyBody = document.querySelector("#dash-verification tbody");
    ((data.verification || {}).declared_checks || []).forEach(function (check) {
      verifyBody.appendChild(row([check.identity, check.contract, check.runner, check.state, check.reason]));
    });
    document.getElementById("dash-verification-note").textContent = (data.verification || {}).banner || "";

    var fresh = document.getElementById("dash-freshness");
    var freshness = data.freshness || {};
    var fp = el("p");
    fp.appendChild(pill(freshness.status || "unknown"));
    fp.appendChild(document.createTextNode(" " + (freshness.reason || "")));
    fresh.appendChild(fp);
    var sourceBody = document.querySelector("#dash-sources tbody");
    (data.sources || []).forEach(function (source) {
      sourceBody.appendChild(row([source.id, source.path, shortDigest(source.content_sha256), source.status]));
    });

    var movement = document.getElementById("dash-movement");
    ((data.movement || {}).deltas || []).forEach(function (delta, index) {
      var card = el("div", null, "card");
      card.appendChild(el("h3", "Delta " + (index + 1) + ": " + shortDigest(delta.current)));
      var list = el("ul");
      ["changed_capabilities", "added_contracts", "removed_contracts"].forEach(function (field) {
        var items = delta[field] || [];
        if (items.length) {
          var item = el("li", field + ": " + items.join(", "));
          list.appendChild(item);
        }
      });
      (delta.ownership_changes || []).forEach(function (change) {
        list.appendChild(el("li", "ownership: " + JSON.stringify(change)));
      });
      card.appendChild(list);
      movement.appendChild(card);
    });
    if (!((data.movement || {}).deltas || []).length) {
      movement.appendChild(el("p", "No recorded movement.", "meta"));
    }
  }

  fetch("dashboard.json", { cache: "no-store" })
    .then(function (response) {
      if (!response.ok) throw new Error("HTTP " + response.status);
      return response.json();
    })
    .then(render)
    .catch(function (error) {
      document.getElementById("dash-metrics").textContent =
        "dashboard.json unavailable (" + error.message + "); static fallback below remains readable.";
    });
})();

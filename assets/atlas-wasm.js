// Typed MNCS/WASM browser host for the production Atlas.
//
// This module owns browser capabilities only: fetching bytes, copying bounded
// chunks into linear memory, decoding borrowed text spans, and constructing
// DOM nodes from the typed render plan. Atlas data semantics stay in MNCS.

const CHUNK_BYTES = 64;
const MAX_MODEL_BYTES = 64 * 1024;

const PLAN = {
  complete: 0,
  maturityCounts: 8,
  nodeCount: 16,
  nodes: 24,
  projectCount: 32,
  relationshipCount: 40,
  valid: 48,
};

const NODE = {
  operation: 0,
  primary: 8,
  quaternary: 16,
  secondary: 24,
  slot: 32,
  target: 40,
  tertiary: 48,
  value: 56,
  valueAux: 64,
  valueText: 72,
  valueTextAux: 80,
};

const TEXT = { encoded: 0, length: 8, start: 16, utf8Valid: 24 };

const atlasUrl = (path) => new URL("../" + path, import.meta.url);

async function fetchBytes(url) {
  const response = await fetch(url, { cache: "no-cache" });
  if (!response.ok) throw new Error("Could not fetch " + url + ": HTTP " + response.status);
  return new Uint8Array(await response.arrayBuffer());
}

async function instantiateWasm(path) {
  const bytes = await fetchBytes(new URL(path, import.meta.url));
  return WebAssembly.instantiate(bytes, {});
}

function prepareMemory(memory) {
  if (!(memory instanceof WebAssembly.Memory)) {
    throw new Error("The MNCS/WASM artifact did not export linear memory");
  }
  return memory;
}

function hostBuffer(exports, memory, capacity) {
  if (typeof exports.mncs_host_buffer !== "function") {
    throw new Error("The MNCS/WASM artifact did not export the host-buffer ABI");
  }
  const packed = exports.mncs_host_buffer(capacity);
  const offset = Number(packed & 0xffffffffn);
  const allocated = Number((packed >> 32n) & 0xffffffffn);
  if (allocated < capacity || offset + allocated > memory.buffer.byteLength) {
    throw new Error("The MNCS/WASM host-buffer ABI returned an invalid region");
  }
  return { offset, capacity: allocated };
}

function descriptor(offset, length) {
  return (BigInt(length) << 32n) | BigInt(offset);
}

function forEachChunk(bytes, callback) {
  for (let offset = 0; offset < bytes.length; offset += CHUNK_BYTES) {
    callback(bytes.subarray(offset, Math.min(offset + CHUNK_BYTES, bytes.length)));
  }
}

function scanAtlas(instance, atlasBytes) {
  const exports = instance.exports;
  const memory = prepareMemory(exports.memory);
  const host = hostBuffer(exports, memory, CHUNK_BYTES);
  let state = exports.atlas_scan_init();
  forEachChunk(atlasBytes, (chunk) => {
    new Uint8Array(memory.buffer).set(chunk, host.offset);
    state = exports.atlas_scan_chunk(state, descriptor(host.offset, chunk.length));
    exports.mncs_host_buffer_reset();
  });
  return Number(exports.atlas_scan_finish(state));
}

function modelAtlas(instance, atlasBytes) {
  if (atlasBytes.length > MAX_MODEL_BYTES) {
    throw new Error("Atlas model input exceeds bounded " + MAX_MODEL_BYTES + "-byte artifact budget");
  }
  const exports = instance.exports;
  const memory = prepareMemory(exports.memory);
  const host = hostBuffer(exports, memory, CHUNK_BYTES);
  let state = exports.atlas_model_init();
  forEachChunk(atlasBytes, (chunk) => {
    new Uint8Array(memory.buffer).set(chunk, host.offset);
    state = exports.atlas_model_chunk(state, descriptor(host.offset, chunk.length));
  });
  return {
    exports,
    memory,
    state,
    model: exports.atlas_model_finish(state),
    plan: exports.atlas_render(state),
  };
}

function words(memory) {
  return new DataView(memory.buffer);
}

function readU32(view, address) {
  return view.getUint32(address, true);
}

function readU64(view, address) {
  return Number(view.getBigUint64(address, true));
}

function decodeEscaped(bytes) {
  const decoder = new TextDecoder("utf-8", { fatal: true });
  const decodeCodeUnit = (start) => {
    if (start + 4 > bytes.length) throw new Error("Truncated JSON Unicode escape");
    const digits = String.fromCharCode(...bytes.subarray(start, start + 4));
    const code = Number.parseInt(digits, 16);
    if (Number.isNaN(code)) throw new Error("Invalid JSON Unicode escape");
    return code;
  };
  let result = "";
  let segmentStart = 0;

  for (let index = 0; index < bytes.length; index += 1) {
    if (bytes[index] !== 92) continue;

    result += decoder.decode(bytes.subarray(segmentStart, index));
    const escaped = bytes[index + 1];
    const replacements = {
      34: '"',
      47: "/",
      92: "\\",
      98: "\b",
      102: "\f",
      110: "\n",
      114: "\r",
      116: "\t",
    };

    if (escaped !== 117) {
      if (!(escaped in replacements)) throw new Error("Invalid JSON escape in borrowed text");
      result += replacements[escaped];
      index += 1;
      segmentStart = index + 1;
      continue;
    }

    const code = decodeCodeUnit(index + 2);
    index += 5;

    if (code >= 0xdc00 && code <= 0xdfff) {
      throw new Error("Lone low surrogate in JSON Unicode escape");
    }
    if (code >= 0xd800 && code <= 0xdbff) {
      if (index + 6 >= bytes.length || bytes[index + 1] !== 92 || bytes[index + 2] !== 117) {
        throw new Error("High surrogate is not followed by a low surrogate");
      }
      const low = decodeCodeUnit(index + 3);
      if (low < 0xdc00 || low > 0xdfff) {
        throw new Error("High surrogate is not followed by a low surrogate");
      }
      result += String.fromCodePoint(0x10000 + ((code - 0xd800) << 10) + low - 0xdc00);
      index += 6;
      segmentStart = index + 1;
      continue;
    }

    result += String.fromCodePoint(code);
    segmentStart = index + 1;
  }

  return result + decoder.decode(bytes.subarray(segmentStart));
}

function readText(view, pointer, atlasBytes) {
  if (!pointer) return "";
  if (pointer + TEXT.utf8Valid + 4 > view.byteLength) throw new Error("Invalid MNCS text view pointer");
  const length = readU64(view, pointer + TEXT.length);
  const start = readU64(view, pointer + TEXT.start);
  if (start > atlasBytes.length || length > atlasBytes.length - start) {
    throw new Error("MNCS text view escaped the supplied Atlas byte stream");
  }
  const bytes = atlasBytes.subarray(start, start + length);
  if (readU32(view, pointer + TEXT.utf8Valid) === 0) {
    throw new Error("MNCS text view contains invalid UTF-8");
  }
  return readU32(view, pointer + TEXT.encoded) === 0
    ? new TextDecoder("utf-8", { fatal: true }).decode(bytes)
    : decodeEscaped(bytes);
}

function runtimeElements() {
  const production = Boolean(document.querySelector("#atlas-runtime-status"));
  return {
    production,
    status: document.querySelector("#atlas-runtime-status, #atlas-wasm-status"),
    error: document.querySelector("#atlas-runtime-error, #atlas-wasm-error"),
    fallback: document.querySelector("#atlas-wasm-fallback"),
    output: document.querySelector("#atlas-wasm-output"),
    metrics: document.querySelector("#atlas-runtime-metrics, #atlas-wasm-metrics"),
    projects: document.querySelector("#atlas-runtime-project-grid, #atlas-wasm-project-grid, #projects .project-grid"),
    statuses: document.querySelector("#atlas-runtime-status-grid, #atlas-wasm-status-grid, #status .status-grid"),
    maturity: document.querySelector("#atlas-runtime-maturity, #atlas-wasm-maturity-model"),
    contract: document.querySelector("#atlas-runtime-contract, #atlas-wasm-consumer-contract"),
    institutional: document.querySelector("#atlas-runtime-institutional, #atlas-wasm-institutional-layer"),
  };
}

function safeRepository(value) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : "";
  } catch {
    return "";
  }
}

function repoName(value) {
  try {
    const path = new URL(value).pathname.split("/").filter(Boolean);
    return path[path.length - 1] || value;
  } catch {
    return value;
  }
}

function appendProject(projects, statuses, node, view, atlasBytes) {
  const name = readText(view, readU32(view, node + NODE.primary), atlasBytes);
  const role = readText(view, readU32(view, node + NODE.secondary), atlasBytes);
  const responsibility = readText(view, readU32(view, node + NODE.tertiary), atlasBytes);
  const repository = safeRepository(readText(view, readU32(view, node + NODE.quaternary), atlasBytes));
  const maturity = readText(view, readU32(view, node + NODE.valueText), atlasBytes);
  const authority = readText(view, readU32(view, node + NODE.valueTextAux), atlasBytes);
  const relationshipCount = readU64(view, node + NODE.value);
  const maturityCode = readU64(view, node + NODE.valueAux);

  const projectCard = document.createElement(repository ? "a" : "article");
  projectCard.className = "project-card";
  if (repository) projectCard.href = repository;

  const projectType = document.createElement("span");
  projectType.className = "project-type";
  projectType.textContent = role;
  const projectTitle = document.createElement("h3");
  projectTitle.textContent = name;
  const projectBody = document.createElement("p");
  projectBody.textContent = responsibility;
  const projectFooter = document.createElement("span");
  projectFooter.className = "repo-link";
  projectFooter.textContent = repoName(repository) + " · " + maturity + " · " +
    relationshipCount + " mapped relation" + (relationshipCount === 1 ? "" : "s") + " ↗";
  projectCard.append(projectType, projectTitle, projectBody, projectFooter);

  const statusCard = document.createElement("article");
  statusCard.className = "status-card";
  const badge = document.createElement("span");
  badge.className = "status-badge";
  badge.dataset.maturityCode = String(maturityCode);
  badge.textContent = maturity;
  const statusTitle = document.createElement("h3");
  statusTitle.textContent = name;
  const statusBody = document.createElement("p");
  statusBody.textContent = authority + ". " + responsibility;
  statusCard.append(badge, statusTitle, statusBody);

  projects.append(projectCard);
  statuses.append(statusCard);
}

function metric(label, value, detail, wide = false) {
  const card = document.createElement("article");
  card.className = "wasm-metric" + (wide ? " wasm-metric-wide" : "");
  const heading = document.createElement("span");
  heading.className = "wasm-metric-label";
  heading.textContent = label;
  const number = document.createElement("strong");
  number.textContent = String(value);
  const small = document.createElement("small");
  small.textContent = detail;
  card.append(heading, number, small);
  return card;
}

function renderSummary(metrics, summary, plan, view, atlasBytes, scanResult) {
  if (!metrics || !summary) return;
  metrics.replaceChildren();
  const bytes = atlasBytes.length;
  const chunks = Math.ceil(bytes / CHUNK_BYTES);
  metrics.append(metric("Structural stream", scanResult === 1 ? "Complete" : "Code " + scanResult, bytes + " bytes · " + chunks + " bounded chunks", true));
  metrics.append(metric("Projects", readU64(view, plan + PLAN.projectCount), "typed records in the Atlas model"));
  metrics.append(metric("Relationships", readU64(view, plan + PLAN.relationshipCount), "explicit relationship records"));
  metrics.append(metric("Operator components", readU64(view, summary + NODE.valueAux), "typed operator topology"));
}

function renderMaturity(mount, maturityNodes, view, atlasBytes) {
  if (!mount) return;
  mount.replaceChildren();
  maturityNodes.forEach((node, index) => {
    const article = document.createElement("article");
    const kicker = document.createElement("p");
    kicker.className = "card-kicker";
    kicker.textContent = readText(view, readU32(view, node + NODE.primary), atlasBytes);
    const title = document.createElement("h3");
    title.textContent = readText(view, readU32(view, node + NODE.secondary), atlasBytes);
    const body = document.createElement("p");
    body.textContent = readText(view, readU32(view, node + NODE.tertiary), atlasBytes);
    article.append(kicker, title, body);
    mount.append(article);
  });
}

function renderContract(mount, header, resolutionNodes, ruleNodes, view, atlasBytes) {
  if (!mount || !header) return;
  mount.replaceChildren();

  const order = document.createElement("article");
  const orderKicker = document.createElement("p");
  orderKicker.className = "card-kicker";
  orderKicker.textContent = "Machine consumer contract";
  const orderTitle = document.createElement("h3");
  orderTitle.textContent = "Contract " + readText(view, readU32(view, header + NODE.primary), atlasBytes);
  const orderBody = document.createElement("p");
  orderBody.textContent = resolutionNodes.map((node) =>
    readText(view, readU32(view, node + NODE.primary), atlasBytes)).join(" → ");
  order.append(orderKicker, orderTitle, orderBody);

  const rules = document.createElement("article");
  const rulesKicker = document.createElement("p");
  rulesKicker.className = "card-kicker";
  rulesKicker.textContent = "Consumption rules";
  const rulesTitle = document.createElement("h3");
  rulesTitle.textContent = "Orientation remains evidence-bounded.";
  const rulesBody = document.createElement("p");
  rulesBody.textContent = ruleNodes.map((node) =>
    readText(view, readU32(view, node + NODE.primary), atlasBytes)).join(" ");
  rules.append(rulesKicker, rulesTitle, rulesBody);

  const topology = document.createElement("article");
  const topologyKicker = document.createElement("p");
  topologyKicker.className = "card-kicker";
  topologyKicker.textContent = "Current family state";
  const topologyTitle = document.createElement("h3");
  topologyTitle.textContent = "Operator topology is explicit in the typed model.";
  const topologyBody = document.createElement("p");
  topologyBody.textContent = "The page consumes stable relationship records and preserves owning-project authority when orientation data is incomplete or stale.";
  topology.append(topologyKicker, topologyTitle, topologyBody);

  mount.append(order, rules, topology);
}

function renderInstitutional(mount, node, view, atlasBytes) {
  if (!mount || !node) return;
  mount.replaceChildren();
  const layer = document.createElement("div");
  layer.className = "arch-layer";
  layer.dataset.atlasLayer = "institutional";

  const label = document.createElement("span");
  label.className = "layer-label";
  label.textContent = "Incubating / institutional";

  const rights = document.createElement("div");
  rights.className = "arch-card featured";
  const rightsName = document.createElement("strong");
  rightsName.textContent = readText(view, readU32(view, node + NODE.primary), atlasBytes);
  const rightsDetail = document.createElement("small");
  rightsDetail.textContent = "origin · lineage · rights basis · authorship uncertainty · artifact licensing";
  rights.append(rightsName, rightsDetail);

  const atlas = document.createElement("div");
  atlas.className = "arch-card";
  const atlasName = document.createElement("strong");
  atlasName.textContent = readText(view, readU32(view, node + NODE.secondary), atlasBytes);
  const atlasDetail = document.createElement("small");
  atlasDetail.textContent = "family orientation · machine discovery · no conformance authority";
  atlas.append(atlasName, atlasDetail);

  layer.append(label, rights, atlas);
  mount.replaceChildren(layer);
}

function validatePlan(model, elements) {
  const view = words(model.memory);
  const plan = model.plan;
  const valid = readU32(view, plan + PLAN.valid) !== 0;
  const complete = readU32(view, plan + PLAN.complete) !== 0;
  if (!valid || !complete) throw new Error("MNCS typed Atlas model is invalid or incomplete; static HTML retained");

  const nodeCount = readU64(view, plan + PLAN.nodeCount);
  if (nodeCount < 3 || nodeCount > 64) throw new Error("MNCS render plan has an invalid bounded node count");
  const nodes = readU32(view, plan + PLAN.nodes);
  if (nodes + nodeCount * 8 > view.byteLength) throw new Error("MNCS render plan escaped linear memory");

  const commands = [];
  for (let index = 0; index < nodeCount; index += 1) {
    const node = readU32(view, nodes + index * 8);
    if (node + NODE.valueTextAux + 8 > view.byteLength) throw new Error("MNCS render node escaped linear memory");
    const operation = readU32(view, node + NODE.operation);
    const target = readU32(view, node + NODE.target);
    if (operation === 0) continue;
    if ((operation === 1 && target !== 4) ||
        (operation === 2 && (target < 1 || target > 2)) ||
        (operation === 3 && target !== 3) ||
        (operation === 4 && target !== 5) ||
        (operation === 5 && target !== 6) ||
        ((operation === 6 || operation === 7) && target !== (operation === 6 ? 7 : 8)) ||
        (operation === 8 && target !== 9)) {
      throw new Error("MNCS render plan contains an unsupported command");
    }
    commands.push({ node, operation, target });
  }
  if (!commands.some((command) => command.operation === 3)) {
    throw new Error("MNCS render plan omitted its summary command");
  }
  return { view, plan, commands, elements };
}

function applyPlan(validated, atlasBytes, scanResult) {
  const { view, plan, commands, elements } = validated;
  const maturityNodes = [];
  const resolutionNodes = [];
  const ruleNodes = [];
  let summary = 0;
  let header = 0;
  let institution = 0;

  const clearProjects = () => elements.projects?.replaceChildren();
  const clearStatuses = () => elements.statuses?.replaceChildren();

  commands.forEach(({ node, operation, target }) => {
    if (operation === 2 && target === 1) clearProjects();
    if (operation === 2 && target === 2) clearStatuses();
    if (operation === 3) summary = node;
    if (operation === 4) maturityNodes.push(node);
    if (operation === 5) header = node;
    if (operation === 6) resolutionNodes.push(node);
    if (operation === 7) ruleNodes.push(node);
    if (operation === 8) institution = node;
  });

  if (!elements.projects || !elements.statuses || !summary || !header || !institution) {
    throw new Error("MNCS render plan did not provide all production view targets");
  }

  commands.forEach(({ node, operation }) => {
    if (operation === 1) appendProject(elements.projects, elements.statuses, node, view, atlasBytes);
  });
  renderSummary(elements.metrics, summary, plan, view, atlasBytes, scanResult);
  renderMaturity(elements.maturity, maturityNodes, view, atlasBytes);
  renderContract(elements.contract, header, resolutionNodes, ruleNodes, view, atlasBytes);
  renderInstitutional(elements.institutional, institution, view, atlasBytes);

  if (elements.status) {
    elements.status.textContent = "MNCS/WASM active · typed Atlas model complete · " +
      readU64(view, plan + PLAN.nodeCount) + " render commands applied";
  }
  if (elements.output) elements.output.hidden = false;
  if (elements.fallback) elements.fallback.hidden = true;
}

export async function runAtlasWasm() {
  const elements = runtimeElements();
  if (!elements.status) return;

  try {
    if (new URL(window.location.href).searchParams.get("mncs-wasm") === "off") {
      throw new Error("MNCS/WASM enhancement intentionally disabled for fallback verification");
    }
    const [atlasBytes, scan, model] = await Promise.all([
      fetchBytes(atlasUrl("atlas.json")),
      instantiateWasm("atlas-json-scan.wasm"),
      instantiateWasm("atlas-model.wasm"),
    ]);
    const scanResult = scanAtlas(scan.instance, atlasBytes);
    if (scanResult !== 1) throw new Error("Structural MNCS stream rejected the Atlas byte stream (code " + scanResult + ")");
    const typedModel = modelAtlas(model.instance, atlasBytes);
    const validated = validatePlan(typedModel, elements);
    applyPlan(validated, atlasBytes, scanResult);
  } catch (caught) {
    const message = caught instanceof Error ? caught.message : String(caught);
    elements.status.textContent = "Static HTML fallback active · MNCS/WASM enhancement unavailable";
    if (elements.error) elements.error.textContent = message;
    if (elements.fallback) elements.fallback.hidden = false;
  }
}

if (document.querySelector("#atlas-wasm-output")) runAtlasWasm();

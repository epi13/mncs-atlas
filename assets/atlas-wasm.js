// Thin browser host for the experimental Atlas MNCS model.
//
// Fetch, memory copies, chunk scheduling, and DOM syscalls stay here. JSON
// structure, typed project records, maturity counts, and render intent stay
// in the MNCS/WASM artifacts. The render plan crosses the boundary as the
// canonical composite-cell ABI described by atlas-wasm-manifest.json.
const CHUNK_BYTES = 64;
const MAX_MODEL_BYTES = 24 * 1024;
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
};
const TEXT = { encoded: 0, length: 8, start: 16, utf8Valid: 24 };

const atlasUrl = (path) => new URL(`../${path}`, import.meta.url);

async function fetchBytes(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Could not fetch ${url}: HTTP ${response.status}`);
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
  return { offset, capacity: allocated, view: new Uint8Array(memory.buffer) };
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
    host.view.set(chunk, host.offset);
    state = exports.atlas_scan_chunk(state, descriptor(host.offset, chunk.length));
    exports.mncs_host_buffer_reset();
  });
  return Number(exports.atlas_scan_finish(state));
}

function modelAtlas(instance, atlasBytes) {
  if (atlasBytes.length > MAX_MODEL_BYTES) {
    throw new Error(`Atlas model input exceeds bounded ${MAX_MODEL_BYTES}-byte artifact budget`);
  }
  const exports = instance.exports;
  const memory = prepareMemory(exports.memory);
  const host = hostBuffer(exports, memory, CHUNK_BYTES);
  let state = exports.atlas_model_init();
  forEachChunk(atlasBytes, (chunk) => {
    host.view.set(chunk, host.offset);
    // Do not reset this module's host region: model state retains immutable
    // composite cells and borrowed text spans until the instance is dropped.
    state = exports.atlas_model_chunk(state, descriptor(host.offset, chunk.length));
  });
  return { exports, memory, state, model: exports.atlas_model_finish(state), plan: exports.atlas_render(state) };
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
  const decoder = new TextDecoder();
  let result = "";
  let segmentStart = 0;
  for (let index = 0; index < bytes.length; index += 1) {
    if (bytes[index] !== 92) {
      continue;
    }
    result += decoder.decode(bytes.subarray(segmentStart, index));
    const escaped = bytes[++index];
    const replacements = { 34: '"', 47: "/", 92: "\\", 98: "\b", 102: "\f", 110: "\n", 114: "\r", 116: "\t" };
    if (escaped !== 117) {
      result += replacements[escaped] ?? "";
      segmentStart = index + 1;
      continue;
    }
    const code = Number.parseInt(new TextDecoder().decode(bytes.subarray(index + 1, index + 5)), 16);
    result += Number.isNaN(code) ? "" : String.fromCodePoint(code);
    index += 4;
    segmentStart = index + 1;
  }
  result += decoder.decode(bytes.subarray(segmentStart));
  return result;
}

function readText(view, pointer, atlasBytes) {
  if (!pointer) return "";
  const length = readU64(view, pointer + TEXT.length);
  const start = readU64(view, pointer + TEXT.start);
  const bytes = atlasBytes.subarray(start, start + length);
  if (readU32(view, pointer + TEXT.utf8Valid) === 0) return "[invalid UTF-8]";
  return readU32(view, pointer + TEXT.encoded) === 0 ? new TextDecoder().decode(bytes) : decodeEscaped(bytes);
}

function maturityMeta(code) {
  const entry = document.querySelector(`#atlas-maturity-legend [data-code="${code}"]`);
  return entry ? { label: entry.textContent.trim(), className: entry.dataset.class || "orientation" } : { label: "Unclassified", className: "orientation" };
}

function safeRepository(value) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : "";
  } catch {
    return "";
  }
}

function appendProject(target, node, view, atlasBytes, statusCard) {
  const name = readText(view, readU32(view, node + NODE.primary), atlasBytes);
  const role = readText(view, readU32(view, node + NODE.secondary), atlasBytes);
  const responsibility = readText(view, readU32(view, node + NODE.tertiary), atlasBytes);
  const repository = safeRepository(readText(view, readU32(view, node + NODE.quaternary), atlasBytes));
  const meta = maturityMeta(readU64(view, node + NODE.value));
  const card = document.createElement(statusCard ? "article" : "a");
  card.className = statusCard ? "status-card" : "project-card";
  if (!statusCard && repository) card.href = repository;

  const badge = document.createElement("span");
  badge.className = statusCard ? `status-badge ${meta.className}` : "project-type";
  badge.textContent = statusCard ? meta.label : role;
  const title = document.createElement("h3");
  title.textContent = name || "Unnamed project";
  const body = document.createElement("p");
  body.textContent = responsibility || "No responsibility text was supplied.";
  const footer = document.createElement("span");
  footer.className = statusCard ? "status-card-meta" : "repo-link";
  footer.textContent = statusCard ? `${role} · ${meta.label}` : `${meta.label}${repository ? " · repository ↗" : " · repository not declared"}`;
  card.append(badge, title, body, footer);
  target.append(card);
}

function metric(label, value, detail, wide = false) {
  const card = document.createElement("article");
  card.className = `wasm-metric${wide ? " wasm-metric-wide" : ""}`;
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

function renderSummary(metrics, plan, view, atlasBytes, scanResult) {
  metrics.replaceChildren();
  metrics.append(metric("Structural stream", scanResult === 1 ? "Complete" : `Code ${scanResult}`, `${atlasBytes.length} bytes · ${Math.ceil(atlasBytes.length / CHUNK_BYTES)} bounded chunks`, true));
  metrics.append(metric("Projects", readU64(view, plan + PLAN.projectCount), "typed records in the Atlas model"));
  metrics.append(metric("Relationships", readU64(view, plan + PLAN.relationshipCount), "mapped relationship records"));
  const counts = readU32(view, plan + PLAN.maturityCounts);
  for (let code = 1; code <= 5; code += 1) {
    const meta = maturityMeta(code);
    metrics.append(metric(meta.label, readU64(view, counts + (code - 1) * 8), "project records"));
  }
}

function renderPlan(model, atlasBytes, scanResult) {
  const view = words(model.memory);
  const plan = model.plan;
  const metrics = document.querySelector("#atlas-wasm-metrics");
  const projects = document.querySelector("#atlas-wasm-project-grid");
  const statuses = document.querySelector("#atlas-wasm-status-grid");
  const nodes = readU32(view, plan + PLAN.nodes);
  const nodeCount = readU64(view, plan + PLAN.nodeCount);
  projects.replaceChildren();
  statuses.replaceChildren();

  for (let index = 0; index < nodeCount; index += 1) {
    const node = readU32(view, nodes + index * 8);
    if (!node) continue;
    const operation = readU32(view, node + NODE.operation);
    const target = readU32(view, node + NODE.target);
    if (operation === 2) {
      (target === 1 ? projects : statuses).replaceChildren();
    } else if (operation === 3) {
      renderSummary(metrics, plan, view, atlasBytes, scanResult);
    } else if (operation === 1 && (target === 1 || target === 2)) {
      appendProject(target === 1 ? projects : statuses, node, view, atlasBytes, target === 2);
    }
  }

  const output = document.querySelector("#atlas-wasm-output");
  const status = document.querySelector("#atlas-wasm-status");
  const valid = readU32(view, plan + PLAN.valid) !== 0;
  const complete = readU32(view, plan + PLAN.complete) !== 0;
  status.textContent = `WASM path active · typed model ${valid && complete ? "complete" : "incomplete"} · render plan applied`;
  output.hidden = false;
  document.querySelector("#atlas-wasm-fallback").hidden = true;
}

async function run() {
  const status = document.querySelector("#atlas-wasm-status");
  const error = document.querySelector("#atlas-wasm-error");
  try {
    const [atlasBytes, scan, model] = await Promise.all([
      fetchBytes(atlasUrl("atlas.json")),
      instantiateWasm("atlas-json-scan.wasm"),
      instantiateWasm("atlas-model.wasm"),
    ]);
    const scanResult = scanAtlas(scan.instance, atlasBytes);
    if (scanResult !== 1) throw new Error(`Structural stream rejected atlas.json (code ${scanResult})`);
    const typedModel = modelAtlas(model.instance, atlasBytes);
    renderPlan(typedModel, atlasBytes, scanResult);
  } catch (caught) {
    const message = caught instanceof Error ? caught.message : String(caught);
    status.textContent = "Static fallback active · experimental WASM path unavailable";
    error.textContent = message;
    document.querySelector("#atlas-wasm-fallback").hidden = false;
  }
}

run();

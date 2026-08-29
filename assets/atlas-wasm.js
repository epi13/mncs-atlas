const CHUNK_BYTES = 64;
// Keep the host view above the current bounded arena's immutable-array
// allocations. A future allocator contract can replace this reserved slot.
const DATA_OFFSET = 900000;

const SELECTORS = [
  [0, "Maturity fields", "raw key count"],
  [1, "Experimental", "maturity member count"],
  [2, "Research", "maturity member count"],
  [3, "Active infrastructure", "maturity member count"],
  [4, "Incubating", "maturity member count"],
  [5, "Orientation", "maturity member count"],
  [6, "Relationships", "from-key count"],
];

const atlasUrl = (path) => new URL(`../${path}`, import.meta.url);

async function fetchBytes(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Could not fetch ${url}: HTTP ${response.status}`);
  }
  return new Uint8Array(await response.arrayBuffer());
}

async function instantiateWasm(path) {
  const bytes = await fetchBytes(new URL(path, import.meta.url));
  return WebAssembly.instantiate(bytes, {});
}

function prepareMemory(memory) {
  if (!memory || !(memory instanceof WebAssembly.Memory)) {
    throw new Error("The MNCS/WASM artifact did not export linear memory");
  }
  const requiredBytes = DATA_OFFSET + CHUNK_BYTES;
  const missingBytes = requiredBytes - memory.buffer.byteLength;
  if (missingBytes > 0) {
    memory.grow(Math.ceil(missingBytes / 65536));
  }
  return new Uint8Array(memory.buffer);
}

function descriptor(offset, length) {
  return (BigInt(length) << 32n) | BigInt(offset);
}

function chunks(bytes, callback) {
  for (let offset = 0; offset < bytes.length; offset += CHUNK_BYTES) {
    const chunk = bytes.subarray(offset, Math.min(offset + CHUNK_BYTES, bytes.length));
    callback(chunk);
  }
}

function scanAtlas(instance, atlasBytes) {
  const exports = instance.exports;
  const memory = prepareMemory(exports.memory);
  let state = exports.atlas_scan_init();
  chunks(atlasBytes, (chunk) => {
    memory.set(chunk, DATA_OFFSET);
    state = exports.atlas_scan_chunk(state, descriptor(DATA_OFFSET, chunk.length));
  });
  return Number(exports.atlas_scan_finish(state));
}

async function projectAtlas(moduleBytes, atlasBytes) {
  const values = [];
  for (const [selector, label, detail] of SELECTORS) {
    // The current portable lowering materializes immutable target arrays in
    // the arena. Keep selectors isolated until that allocator is reusable.
    const { instance } = await WebAssembly.instantiate(moduleBytes, {});
    const exports = instance.exports;
    const memory = prepareMemory(exports.memory);
    let state = 0n;
    chunks(atlasBytes, (chunk) => {
      memory.set(chunk, DATA_OFFSET);
      state = exports.atlas_project_chunk(
        state,
        descriptor(DATA_OFFSET, chunk.length),
        selector,
      );
    });
    values.push({
      detail,
      label,
      selector,
      value: Number(exports.atlas_project_count(state, selector)),
    });
  }
  return values;
}

function renderMetrics(scanResult, projections, atlasBytes) {
  const output = document.querySelector("#atlas-wasm-output");
  const metrics = document.querySelector("#atlas-wasm-metrics");
  const status = document.querySelector("#atlas-wasm-status");
  metrics.replaceChildren();

  const scanCard = document.createElement("article");
  scanCard.className = "wasm-metric wasm-metric-wide";
  scanCard.innerHTML = "<span class=wasm-metric-label>Structural stream</span>";
  const scanValue = document.createElement("strong");
  scanValue.textContent = scanResult === 1 ? "Complete" : `Code ${scanResult}`;
  scanCard.append(scanValue);
  const scanDetail = document.createElement("small");
  scanDetail.textContent = `Validated ${atlasBytes.length} bytes in ${Math.ceil(atlasBytes.length / CHUNK_BYTES)} chunks`;
  scanCard.append(scanDetail);
  metrics.append(scanCard);

  for (const projection of projections) {
    const card = document.createElement("article");
    card.className = "wasm-metric";
    const label = document.createElement("span");
    label.className = "wasm-metric-label";
    label.textContent = projection.label;
    card.append(label);
    const value = document.createElement("strong");
    value.textContent = String(projection.value);
    card.append(value);
    const detail = document.createElement("small");
    detail.textContent = projection.detail;
    card.append(detail);
    metrics.append(card);
  }

  status.textContent = "WASM path active · Atlas bytes stayed outside JavaScript JSON semantics";
  output.hidden = false;
  document.querySelector("#atlas-wasm-fallback").hidden = true;
}

async function run() {
  const status = document.querySelector("#atlas-wasm-status");
  const error = document.querySelector("#atlas-wasm-error");
  try {
    const [atlasBytes, scan, projectionBytes] = await Promise.all([
      fetchBytes(atlasUrl("atlas.json")),
      instantiateWasm("atlas-json-scan.wasm"),
      fetchBytes(new URL("atlas-json-projection.wasm", import.meta.url)),
    ]);
    const scanResult = scanAtlas(scan.instance, atlasBytes);
    const projections = await projectAtlas(projectionBytes, atlasBytes);
    renderMetrics(scanResult, projections, atlasBytes);
  } catch (caught) {
    const message = caught instanceof Error ? caught.message : String(caught);
    status.textContent = "Static fallback active · experimental WASM path unavailable";
    error.textContent = message;
    document.querySelector("#atlas-wasm-fallback").hidden = false;
  }
}

run();

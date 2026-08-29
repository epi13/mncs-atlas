const CHUNK_BYTES = 64;

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

function chunks(bytes, callback) {
  for (let offset = 0; offset < bytes.length; offset += CHUNK_BYTES) {
    const chunk = bytes.subarray(offset, Math.min(offset + CHUNK_BYTES, bytes.length));
    callback(chunk);
  }
}

function scanAtlas(instance, atlasBytes) {
  const exports = instance.exports;
  const memory = prepareMemory(exports.memory);
  const host = hostBuffer(exports, memory, CHUNK_BYTES);
  let state = exports.atlas_scan_init();
  chunks(atlasBytes, (chunk) => {
    host.view.set(chunk, host.offset);
    state = exports.atlas_scan_chunk(state, descriptor(host.offset, chunk.length));
    exports.mncs_host_buffer_reset();
  });
  return Number(exports.atlas_scan_finish(state));
}

async function projectAtlas(moduleBytes, atlasBytes) {
  const { instance } = await WebAssembly.instantiate(moduleBytes, {});
  const exports = instance.exports;
  const memory = prepareMemory(exports.memory);
  const host = hostBuffer(exports, memory, CHUNK_BYTES);
  const values = [];
  for (const [selector, label, detail] of SELECTORS) {
    let state = 0n;
    chunks(atlasBytes, (chunk) => {
      host.view.set(chunk, host.offset);
      state = exports.atlas_project_chunk(
        state,
        descriptor(host.offset, chunk.length),
        selector,
      );
      exports.mncs_host_buffer_reset();
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
  scanDetail.textContent = `Scanned ${atlasBytes.length} bytes in ${Math.ceil(atlasBytes.length / CHUNK_BYTES)} chunks`;
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

  status.textContent = "WASM path active · structural stream complete · Atlas bytes stayed outside JavaScript JSON semantics";
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
    if (scanResult !== 1) {
      throw new Error(`Structural stream rejected atlas.json (code ${scanResult})`);
    }
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

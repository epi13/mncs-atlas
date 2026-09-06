# Fabric capability queries for Atlas

Fabric answers Atlas-style fleet questions from the same capability
graph it schedules with — no second diagnostic system. All shapes below
are machine-readable (`SchedulerDecision.resolution`,
`FleetResolution.as_dict()`, `explain_selection()`).

## Which workers can execute this?

```python
from mncs_fabric.capability_resolution import CapabilityQuery, resolve_fleet
from mncs_fabric.scheduler import explain_eligibility

fleet = resolve_fleet(query, snapshots, replicas=1)
fleet.eligible   # worker ids satisfying every requirement
fleet.selected   # deterministic pick (prefer rank, then id)
```

`query` carries `require_all`, `require_any` (alternatives such as
native RISC-V or declared emulation), `forbid`, `prefer` (ranking
only), structured `req_env` floors (CUDA compute, eBPF/WASM/PTX,
memory/CPU, emulation permission), and workload `intent`
(`normal`/`mutating`/`privileged`).

## Why did this workload not run?

A no-placement schedule returns disposition `UNKNOWN` with reason
leading `NO_ELIGIBLE_WORKER` and a `resolution` payload:

```python
decision = schedule(plan, slots, intent="privileged")
decision.resolution["verdict"]      # "NO_ELIGIBLE_WORKER"
decision.resolution["per_worker"]   # [{worker_id, eligible, code, missing, ...}]
```

Each `missing` entry names the exact cause (`missing os:linux`,
`missing cuda.compute >= 9.0`, `missing policy for intent privileged`,
`missing one_of [...]`). Codes distinguish `CAPABILITY_UNSATISFIED`,
`POLICY_DENIED`, `PROVENANCE_UNVERIFIED`, `WORKER_STALE`,
`WORKER_UNAVAILABLE`, `WORKER_DISCONNECTED`, `TOOLCHAIN_MISSING`,
`RUNTIME_MISSING`.

## What capabilities are currently available?

`development-evidence/capability-fleet-*.json` in mncs-fabric records
per-worker observed tokens plus the outcomes of the standard query set.
Regenerate with
`python3 scripts/collect_fleet_capability_evidence.py`.

## Which experimental workers permit root-level mutation?

Workers whose declared policy includes `policy:root-mutation`:

```python
query = CapabilityQuery(intent="privileged")
```

Only workers whose operator declared `experimental` plus
`allow_root_mutation` resolve eligible. Experimental status alone never
suffices, and stable workers resolve `POLICY_DENIED`.

## Do we currently have CUDA + eBPF + x86-64?

```python
query = CapabilityQuery(req_env={
    "os": "linux", "arch": "x86_64",
    "require_cuda": True, "cuda_major": 6, "cuda_minor": 0,
    "require_ebpf": True,
})
```

A live worked example over the real fleet is checked in as
`development-evidence/capability-fleet-2026-09-06.json`
(`NO_ELIGIBLE_WORKER` included, with per-worker reasons).

## Boundaries Atlas must respect

- Capability snapshots are worker-observed facts with a 300 s
  freshness bound, not attestations or continuous availability.
- Declared policy is operator configuration, never inferred hardware.
- `prefer` ranks; it never promotes an ineligible worker.
- `NO_ELIGIBLE_WORKER` is a scheduling outcome, not an execution
  failure; `WORKER_UNAVAILABLE`/`WORKER_DISCONNECTED` mean a compatible
  machine exists but is down or undescribed — different from nothing
  existing.

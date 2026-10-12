# Phase 2 remediation evidence

**Status:** Remediation **closed** (Steps 1–7, 2026-10-12). Authoritative manifest:
`0aca5b8d63621b3118886f40b1b626b13a8bd58a8c1a9c27d0728fb2902e14d9`.  
**Plan:** [`PHASE_2_REMEDIATION_IMPLEMENTATION_PLAN.md`](./PHASE_2_REMEDIATION_IMPLEMENTATION_PLAN.md)  
**Parent:** [`PHASE_2_IMPLEMENTATION_PLAN.md`](./PHASE_2_IMPLEMENTATION_PLAN.md)

Step 1 records the pre-regeneration baseline. Step 2 regenerated the canonical
Phase 2 evaluation package in place. Historical file hashes from Step 1 remain
valid for diffing superseded content.

## Environment snapshot

| Field | Value |
| --- | --- |
| Branch | `phase4/setup` |
| `git rev-parse HEAD` | `2f7aa5e75bc3bff7114c9a4213a270f9b4f62e3d` |
| Python | 3.14.x (local inventory run) |
| Inventory script | [`scripts/phase2_remediation_inventory.py`](../../scripts/phase2_remediation_inventory.py) |

### Working tree (unrelated to remediation edits)

Recorded at Step 1 freeze; do not fold into remediation commits unless
intentional:

| Path | State |
| --- | --- |
| `.cursor/rules/docs-layout.mdc` | modified (pre-existing) |
| `docs/phase-2/PHASE_2_REMEDIATION_IMPLEMENTATION_PLAN.md` | untracked at audit; remediation doc |
| `docs/phase-2/PHASE_2_REMEDIATION_EVIDENCE.md` | created in Step 1 |
| `scripts/phase2_remediation_inventory.py` | created in Step 1 |

## Benchmark and configuration identity

| Item | SHA-256 |
| --- | --- |
| `benchmarks/split_manifest.json` (file hash, authoritative checkout) | `0aca5b8d63621b3118886f40b1b626b13a8bd58a8c1a9c27d0728fb2902e14d9` |
| `experiments/evaluation_config.json` | `5734f113b827675785d610d97702ed95b7021fe83e35714a9a9de7df057b30d8` |
| `benchmarks/reviewed_query_pairs.jsonl` (per manifest) | `8dbd3c503927006d27f18c4f41a0c3ae47c7294e583203d3371871fa2e0664cd` |

### Split and dataset

| Split | Records |
| --- | ---: |
| Source | 615 |
| Development | 400 |
| Held-out | 215 |

- `dataset_version`: `reviewed-query-pairs-2.0`
- `schema_version`: `1.1`
- `annotation_guide_version`: `1.0.0`
- Manifest `frozen_at`: `2026-10-08T15:28:12+00:00`
- Label fields on source JSONL: `correctness_label` and `preference_label` are
  null for all 615 records (`answer_availability`: `none`).

### Manifest lineage reference

| Role | SHA-256 (prefix) | Notes |
| --- | --- | --- |
| **Current checkout** | `0aca5b8d…` | Matches `benchmark_validate` output below. |
| **2026-10-10 regen package** | `68912e3b…` | WS5 held-out, WS6 held-out, WS7, WS9 dashboard. **Stale** vs current manifest. |
| **WS6 development (2026-10-08)** | `c0109b36…` | Intermediate freeze; **historical**. |
| **WS5 development sweep (2026-10-08)** | `69c90c41…` | Pre-regen development artifacts; **historical**. |

Step 2 must choose whether regeneration targets the **current** manifest
(`0aca5b8d…`) or documents a deliberate rollback. The audit recommendation is
to treat the **current** manifest as authoritative.

## WS5–WS9 artifact inventory (Step 1 snapshot)

> **Historical:** table below is the pre–Step 2 baseline. After Step 2,
> `python scripts/phase2_remediation_inventory.py` should show `current` for
> WS5/WS6/WS7/WS9 evaluation artifacts.

`lineage_status` meanings:

- **current** — `split_manifest_sha256` matches the checkout manifest file.
- **stale** — matches the documented `68912e3b…` regen, not the current file.
- **historical** — older manifest SHA on development-era artifacts.
- **unrecorded** — no manifest field on the artifact (may still be valid for
  sidecars).
- **unavailable** — explicit unavailable measurement (WS4).
- **not_comparable** — different dataset/split scope (WS4 comparison).
- **out_of_scope_manifest** — operations package without benchmark split proof.

| Path | WS | Lineage | Recorded manifest | `git_commit` (artifact) | Timestamp (UTC) |
| --- | --- | --- | --- | --- | --- |
| `artifacts/evaluation/workstream5-development-sweep.json` | 5 | historical | `69c90c41…` | `1beed4de…` | `2026-10-08T14:53:14` |
| `artifacts/evaluation/workstream5-held-out-comparison.json` | 5 | stale | `68912e3b…` | `51496c25…` | `2026-10-10T15:07:16` |
| `artifacts/evaluation/workstream5-held-out-pareto.json` | 5 | unrecorded | — | — | — |
| `artifacts/evaluation/workstream3-development.json` | 3 | historical | `69c90c41…` | `1beed4de…` | `2026-10-08T14:54:40` |
| `artifacts/evaluation/workstream6-development-freshness.json` | 6 | historical | `c0109b36…` | `88997ed1…` | `2026-10-08T18:12:14` |
| `artifacts/evaluation/workstream6-held-out-freshness.json` | 6 | stale | `68912e3b…` | `51496c25…` | `2026-10-10T15:08:01` |
| `artifacts/evaluation/workstream6-invalidation.json` | 6 | unrecorded | — | — | — |
| `artifacts/evaluation/workstream7-quality-analysis.json` | 7 | stale | `68912e3b…` | `51496c25…` | `2026-10-10T15:08:29` |
| `artifacts/evaluation/workstream9-dashboard.json` | 9 | stale | `68912e3b…` (primary identity) | `1fc78ac3…` | `2026-10-11T00:12:51` |
| `artifacts/evaluation/workstream4-real-provider-unavailable.json` | 4 | unavailable | — | `045cd71f…` | `2026-10-07T16:43:08` |
| `artifacts/evaluation/workstream4-provider-comparison.json` | 4 | not_comparable | — (`reviewed-query-pairs-1.1`) | — | `2026-10-07T17:06:49` |
| `artifacts/operations/workstream8-operational-verification.json` | 8 | out_of_scope_manifest | — | `4997e667…` | — |

File content hashes (for diff detection after Step 2):

| Path | `file_sha256` |
| --- | --- |
| `workstream5-held-out-comparison.json` | `5aa6974a56102005c579803217b07c3c063faa5a3fff8fddf24b80b93515bbf8` |
| `workstream7-quality-analysis.json` | `9d45a45b6d6eefcbe328a74eb1f7a75c8c9d0d9f40f27e2aabfd81b4b4ac9846` |
| `workstream9-dashboard.json` | `0ff755091815792baab804ed9c93f153d7040e65692b8f0e6fdad59057ef1268` |

Full per-artifact hashes: run the inventory script with `--json`.

## Verification baseline (historical; re-run after later steps)

Recorded at remediation audit; not automatically valid after Step 2+ edits.

| Command | Result (2026-10-12) |
| --- | --- |
| `python -m sscre.benchmark_validate --benchmark-dir benchmarks --phase2 --production` | passed; `split_manifest_sha256=0aca5b8d63621b3118886f40b1b626b13a8bd58a8c1a9c27d0728fb2902e14d9`; `cross_split_fingerprint_overlaps=0` |
| `python -m pytest -q` | 766 passed, 15 skipped, 21 deselected, 1 warning |

## Step 1 verification

### Manifest file hash (PowerShell)

```powershell
Get-FileHash benchmarks\split_manifest.json -Algorithm SHA256
```

Expected `Hash` (hex, case-insensitive):

`0ACA5B8D63621B3118886F40B1B626B13A8BD58A8C1A9C27D0728FB2902E14D9`

### Read-only inventory script

```powershell
python scripts/phase2_remediation_inventory.py
python scripts/phase2_remediation_inventory.py --json
```

- [x] Script `split_manifest_sha256` matches this evidence file (`0aca5b8d…`).
- [x] Tabular `lineage_status` values match the table above (2026-10-12 run).

## Step 2 — Artifact lineage repair (2026-10-12)

**Decision:** authoritative manifest is the checkout file hash `0aca5b8d…`
(not the historical `68912e3b…` regen package).

### Commands (all exit 0)

```powershell
$env:PYTHONPATH="src"
python -m sscre.evaluate --benchmark benchmarks/development.jsonl `
  --config experiments/evaluation_config.json --baseline embedding-cache `
  --split development --output artifacts/evaluation/workstream5-development-sweep.json

python -m sscre.evaluate --benchmark benchmarks/held_out_test.jsonl `
  --config experiments/evaluation_config.json --baseline all --split held-out `
  --production --output artifacts/evaluation/workstream5-held-out-comparison.json

python -m sscre.pareto --development-sweep artifacts/evaluation/workstream5-development-sweep.json `
  --held-out-benchmark benchmarks/held_out_test.jsonl `
  --config experiments/evaluation_config.json `
  --output artifacts/evaluation/workstream5-held-out-pareto.json

python -m sscre.freshness_evaluate --benchmark benchmarks/development.jsonl `
  --config experiments/evaluation_config.json --split development `
  --output artifacts/evaluation/workstream6-development-freshness.json

python -m sscre.freshness_evaluate --benchmark benchmarks/held_out_test.jsonl `
  --config experiments/evaluation_config.json --split held-out --production `
  --selected-policy artifacts/evaluation/workstream6-development-freshness.json `
  --output artifacts/evaluation/workstream6-held-out-freshness.json

python -m sscre.failure_gallery_export `
  --comparison artifacts/evaluation/workstream5-held-out-comparison.json `
  --freshness-companion artifacts/evaluation/workstream6-held-out-freshness.json `
  --output artifacts/evaluation/workstream7-quality-analysis.json `
  --html artifacts/evaluation/workstream7-quality-gallery.html

python -m sscre.gallery_export `
  artifacts/evaluation/workstream5-held-out-comparison.json `
  -o artifacts/evaluation/workstream5-held-out-comparison-gallery.html

python -m sscre.dashboard `
  --comparison artifacts/evaluation/workstream5-held-out-comparison.json `
  --pareto artifacts/evaluation/workstream5-held-out-pareto.json `
  --freshness-development artifacts/evaluation/workstream6-development-freshness.json `
  --freshness-held-out artifacts/evaluation/workstream6-held-out-freshness.json `
  --invalidation artifacts/evaluation/workstream6-invalidation.json `
  --quality artifacts/evaluation/workstream7-quality-analysis.json `
  --operations artifacts/operations/workstream8-operational-verification.json `
  --json-output artifacts/evaluation/workstream9-dashboard.json `
  --html-output artifacts/evaluation/workstream9-dashboard.html
```

### Post-regeneration artifact hashes

| Path | `file_sha256` | Recorded manifest |
| --- | --- | --- |
| `workstream5-development-sweep.json` | `dc1db8b128f58c57f46465666b10d44b173cf4dd4cf8a82bf12953fdd89c1741` | `0aca5b8d…` |
| `workstream5-held-out-comparison.json` | `e1bdaf0f3b40fbcd03782f1b3ad985097afa68f358829330a065efc38e1b4569` | `0aca5b8d…` |
| `workstream5-held-out-pareto.json` | `932f90844135010841eff7fb50f84f1cacb15cdca3de9257267a687f7ee2fef5` | not recorded on artifact |
| `workstream6-development-freshness.json` | `75cb26c7e7ac73367ef35ab13c14448d424c02f148be862eb394e5323460ee85` | `0aca5b8d…` |
| `workstream6-held-out-freshness.json` | `21fa498a4fc9d1647f466019cda56b44ce80270eac77b03d0a00eff1148b8bcb` | `0aca5b8d…` |
| `workstream7-quality-analysis.json` | `5cc4fa5c1bd19e7d8f557117c6267933f5d1f904be4b8886f9dded5e793129a4` | `0aca5b8d…` |
| `workstream9-dashboard.json` | `17336998d96edc9f3026044dfe651f183cca4200c7b632349104bb079fd0c7fc` | `0aca5b8d…` (primary identity) |

Artifact `git_commit` where present: `2f7aa5e75bc3bff7114c9a4213a270f9b4f62e3d`.

### Step 2 verification

- [x] `python scripts/phase2_remediation_inventory.py` — WS5/WS6/WS7/WS9
  evaluation rows show `current` for manifest lineage (2026-10-12).
- [x] `python -m pytest -q tests/test_workstream6_freshness.py tests/test_workstream7_failure_gallery.py tests/test_workstream9_dashboard.py`
  — **86 passed** (2026-10-12).
- [x] `tests/test_workstream9_dashboard.py` uses `file_sha256(split_manifest.json)`
  for primary identity (not the stale `68912e3b…` constant).

### Remaining gaps (Step 4+)

- `workstream3-development.json` still **historical** manifest (`69c90c41…`).
- Phase 3 / paper artifacts may still cite `68912e3b…` (out of Step 2 scope).
- WS5–WS9 evidence prose may still mention the old regen SHA until Step 4.

## Step 3 — Dashboard provenance validation (2026-10-12)

- [x] `build_dashboard_view_manifest` hashes `benchmarks/split_manifest.json`
  and compares WS5/WS6/WS7 lineage fields on comparison, quality, and
  freshness sources.
- [x] Stale lineage fails closed unless
  `allow_stale_manifest=True` / `--allow-metadata-mismatch`.
- [x] Exported packages record `repo_lineage` and
  `export_policy.repo_split_manifest_sha256`.
- [x] Regression:
  `tests/test_workstream9_dashboard.py::test_repo_lineage_fails_when_sources_agree_on_stale_manifest`.
- [x] `python -m pytest -q tests/test_workstream9_dashboard.py` — **22 passed**.
- [x] Re-exported `artifacts/evaluation/workstream9-dashboard.json` / `.html`.

## Step 4 — Plans, evidence, and claims (2026-10-12)

### Documents updated

- [`../SSCRE_PLAN.md`](../SSCRE_PLAN.md) § Phase 2 roadmap checkboxes.
- [`PHASE_2_IMPLEMENTATION_PLAN.md`](./PHASE_2_IMPLEMENTATION_PLAN.md) —
  scope/limitations block and definition-of-done narrowing.
- [`WORKSTREAM_3_EVIDENCE.md`](./WORKSTREAM_3_EVIDENCE.md) — historical 32-pair
  banner.
- [`WORKSTREAM_5_EVIDENCE.md`](./WORKSTREAM_5_EVIDENCE.md) — “closed” synthetic
  package wording.
- [`WORKSTREAM_6_EVIDENCE.md`](./WORKSTREAM_6_EVIDENCE.md) — stable-only
  held-out scope; stale WS5 item closed.
- [`WORKSTREAM_7_EVIDENCE.md`](./WORKSTREAM_7_EVIDENCE.md) — closure vs optional
  sign-off.
- [`WORKSTREAM_9_EVIDENCE.md`](./WORKSTREAM_9_EVIDENCE.md) — optional product
  gates vs implementation.

### Defensible Phase 2 conclusion (after reconciliation)

SSCRE Phase 2 supports evidence-backed claims about **compatibility-aware
semantic caching (Strategy C)** on a **615-pair synthetic replay** benchmark:
decision depth, failure-closed behavior, held-out baselines with confidence
intervals, Pareto/threshold policy (minus storage plane), stable-only held-out
freshness, failure gallery, bounded PostgreSQL ops checks, and a read-only
dashboard with repo manifest lineage validation.

**Do not claim without new evidence:** human correctness or preference quality,
live-provider cost/latency, held-out semi-dynamic/dynamic freshness,
live PostgreSQL restart safety, production capacity/SLA, or Strategy B as the
canonical safety path.

### Benchmark scale note

| Target | Status |
| --- | --- |
| Phase 2 implementation gate (≥500 reviewed pairs) | **Met** (615) |
| Roadmap aspiration (2,000+ pairs in `SSCRE_PLAN.md` §14) | **Not met** |

### Step 4 verification

- [x] Parent and master plan checkboxes align with open gaps (correctness,
  provider, optional WS9 user gates).
- [x] No reconciled document still describes manifest `68912e3b…` as the
  current Phase 2 package (Phase 3 artifacts may still reference it).

## Step 5 — Reproducibility and regression rerun (2026-10-12)

**Environment:** Windows 10, Python 3.14.5, `git rev-parse HEAD` =
`2f7aa5e75bc3bff7114c9a4213a270f9b4f62e3d`, `PYTHONPATH=src`.

### Commands (all exit 0)

Same artifact-generation sequence as Step 2 (WS5 → WS6 → WS7 gallery → WS5
lite gallery → WS9 dashboard). See Step 2 block for full PowerShell lines.

Additional verification:

```powershell
python -m sscre.benchmark_validate --benchmark-dir benchmarks --phase2 --production
python -m pytest -q
python -m pytest -q tests/test_workstream9_dashboard.py tests/test_serialization_boundary.py tests/test_workstream7_failure_gallery.py tests/test_failure_gallery_export_cli.py
python scripts/phase2_remediation_inventory.py
```

**Lint:** `ruff` not installed in this environment. IDE diagnostics on
`src/sscre/dashboard.py` and `tests/test_workstream9_dashboard.py` — no issues.

### Results summary

| Command | Result |
| --- | --- |
| `benchmark_validate --phase2 --production` | passed; `split_manifest_sha256=0aca5b8d…`; `cross_split_fingerprint_overlaps=0` |
| `python -m pytest -q` | **767 passed**, **15 skipped**, **21 deselected**, 1 warning (~156s) |
| WS7 redaction / gallery tests (subset above) | **57 passed** |
| `tests/test_workstream9_dashboard.py` (included in subset) | **22 passed** (subset total 57) |
| `phase2_remediation_inventory.py` | WS5/WS6/WS7/WS9 evaluation rows `current`; WS3 `historical`; WS4 `unavailable` / `not_comparable`; WS8 ops `out_of_scope_manifest` |

### Skipped and deselected tests (not counted as pass)

| Category | Count | Reason |
| --- | ---: | --- |
| PostgreSQL integration | 14 | `SSCRE_DATABASE_URL` unset (`tests/test_postgres_integration.py`) |
| Real provider | 1 | `SSCRE_REAL_PROVIDER_LIVE` not `true` (`tests/test_provider_integration.py`) |
| WS8 opt-in harness | 21 deselected | `pyproject.toml` `addopts` excludes `ws8_postgres_*` markers |

Live restart, credentialed provider, and opt-in WS8 PostgreSQL suites were **not
run** in this step (documented unavailable / gated).

### Post-rerun artifact file hashes

| Path | `file_sha256` |
| --- | --- |
| `workstream5-development-sweep.json` | `a336c88553399ed9d62db7d37926dc716a912932997e96be2421479aee0e44f7` |
| `workstream5-held-out-comparison.json` | `90e49c3d7d4895cc1e83f49e106cc4582190947910b0807bb0ded6e38a7f06ac` |
| `workstream5-held-out-pareto.json` | `932f90844135010841eff7fb50f84f1cacb15cdca3de9257267a687f7ee2fef5` |
| `workstream6-development-freshness.json` | `d677ac786890febe80e1c800051da8c6b2c74a52b346046fcf127712da3ac281` |
| `workstream6-held-out-freshness.json` | `084f8f74051dc32d062dd5b63c86b988127682ccdd45d8dd7fd76349f16a4ca1` |
| `workstream7-quality-analysis.json` | `aa40d318488fdddb039bf4ec0ba03731a0dc5e248f56c3896ed55ec036e818f9b` |
| `workstream9-dashboard.json` | `ef659327d80c0496dfed6dc607cd79f2742e1d9c3d54ae6eec655431d4c940fb` |

Pareto hash unchanged vs Step 2; other JSON hashes may differ when metadata
timestamps refresh while manifest lineage stays `0aca5b8d…`.

### Step 5 verification

- [x] `python -m pytest -q` passes after remediation (**767 passed**).
- [x] All required artifact-generation commands pass (exit 0).
- [x] Skipped provider/PostgreSQL tests recorded as unavailable, not passed.
- [x] Regenerated package passes inventory lineage and dashboard provenance
  checks (current manifest on WS5/WS6/WS7/WS9).

## Step 6 — Optional evidence gates (2026-10-12)

**Review outcome:** each gate is **keep-deferred**. No new experiments, spend,
annotation, benchmark expansion, or live failure injection was authorized in
this pass. Deferred is not fail; Phase 2 conclusions remain those in § Step 4.

| Gate | Decision | Basis (current checkout) | Claim boundary retained |
| --- | --- | --- | --- |
| **A** — Correctness / preference labels | `keep-deferred` | All 615 records: `correctness_label` / `preference_label` null; `answer_availability: none`. No approved annotation protocol or owner. | Compatibility and replay metrics only; no human quality conclusions. |
| **B** — Real-provider measurement | `keep-deferred` | [`WORKSTREAM_4_EVIDENCE.md`](./WORKSTREAM_4_EVIDENCE.md); `workstream4-real-provider-unavailable.json` (`live_opt_in_missing`). No approved provider budget or credentials. | Synthetic replay only; do not present intervals as live-provider. |
| **C** — Freshness coverage (semi/dynamic held-out) | `keep-deferred` | [`WORKSTREAM_6_EVIDENCE.md`](./WORKSTREAM_6_EVIDENCE.md): four-arm development replay; held-out evaluation **stable-only** on manifest `0aca5b8d…`. No approved split expansion. | Held-out freshness remains stable-class only. |
| **D** — PostgreSQL live restart | `keep-deferred` | [`WORKSTREAM_8_EVIDENCE.md`](./WORKSTREAM_8_EVIDENCE.md): bounded local package; live container restart **skipped**; opt-in `ws8_postgres_*` tests deselected in default CI. | Failure-closed and bounded ops evidence only; not production restart SLA. |
| **E** — Held-out storage / reuse–storage Pareto | `keep-deferred` | [`WORKSTREAM_5_EVIDENCE.md`](./WORKSTREAM_5_EVIDENCE.md): no held-out-aligned `storage_evaluate` companion for `reviewed-query-pairs-2.0`. | Pareto without reuse/storage plane until a future approved rerun. |

### Re-opening a gate (not done in Step 6)

Before any unchecked implementation task in the remediation plan Step 6 section
may proceed, record in this file:

- approved protocol (or storage/restart protocol),
- resource owner and budget where applicable,
- pass/fail scope tied to the frozen contracts,
- and a dated decision line changing `keep-deferred` → `approved`.

### Step 6 verification

- [x] All five gates recorded with explicit decisions (all `keep-deferred`).
- [x] Decisions align with parent
  [`PHASE_2_IMPLEMENTATION_PLAN.md`](./PHASE_2_IMPLEMENTATION_PLAN.md) scope and
  limitations (2026-10-12 reconciliation).
- [x] No Phase 3 artifact or claim used to backfill a deferred Phase 2 gate.

## Step 7 — Remediation close-out (2026-10-12)

### Broad verification (exit 0)

```powershell
$env:PYTHONPATH="src"
python -m sscre.benchmark_validate --benchmark-dir benchmarks --phase2 --production
python scripts/phase2_remediation_inventory.py
python -m pytest -q
```

| Command | Result |
| --- | --- |
| `benchmark_validate --phase2 --production` | passed; `0aca5b8d…`; `cross_split_fingerprint_overlaps=0` |
| `phase2_remediation_inventory.py` | WS5/WS6/WS7/WS9 `current`; WS3 `historical`; WS4 unavailable/not_comparable |
| `python -m pytest -q` | **767 passed**, 15 skipped, 21 deselected, 1 warning (~407s) |

`git rev-parse HEAD` at verify: `2f7aa5e75bc3bff7114c9a4213a270f9b4f62e3d`.

### Optional gates (recorded in Step 6)

| Gate | Status |
| --- | --- |
| A — labels | `keep-deferred` |
| B — real provider | `keep-deferred` |
| C — semi/dynamic held-out freshness | `keep-deferred` |
| D — live PostgreSQL restart | `keep-deferred` |
| E — held-out storage / reuse–storage Pareto | `keep-deferred` |

### Final Phase 2 limitations and conclusions

**Supported (evidence-backed on manifest `0aca5b8d…`, `reviewed-query-pairs-2.0`):**

- Strategy **C** as the canonical compatibility-aware cache path with explicit
  `SAFE` / `UNSAFE` / `UNCERTAIN`, candidate traces, and failure-closed behavior.
- **615** reviewed compatibility pairs with validated development / held-out
  splits (400 / 215) and zero cross-split fingerprint overlap.
- Synthetic replay evaluation: WS5 held-out baselines with confidence intervals,
  development threshold sweep, Pareto artifact (without reuse/storage plane),
  WS6 development four-arm freshness and **stable-only** held-out policy replay,
  WS7 failure gallery and quality analysis, WS8 bounded local PostgreSQL ops
  package, WS9 read-only dashboard with **repo** `split_manifest.json` lineage
  validation.

**Explicitly not claimed (deferred or unavailable; do not backfill from Phase 3/4):**

- Human **correctness** or **preference** quality (Gate A).
- Credentialed **live-provider** cost, latency, or tokens (Gate B; WS4 unavailable).
- Held-out **semi-dynamic** or **dynamic** freshness outcomes (Gate C).
- **Live container restart** or production capacity / SLA (Gate D; WS8 scope).
- **Reuse vs storage** Pareto frontier (Gate E; no held-out-aligned storage companion).
- Roadmap **2,000+** pair benchmark aspiration (615 meets the Phase 2 ≥500 gate only).
- Strategy **B** as the canonical safety path (opt-in embedding-only baseline).

**Remediation verdict:** The Phase 2 **implementation and evaluation package** is
complete at this defended scope. Remaining items are optional gates, roadmap scale,
or separate milestones (Phase 3+, WS9 product approval), not silent Phase 2 pass.

### Step 7 verification

- [x] Parent [`PHASE_2_IMPLEMENTATION_PLAN.md`](./PHASE_2_IMPLEMENTATION_PLAN.md)
  updated with remediation close-out pointer.
- [x] [`PHASE_2_REMEDIATION_IMPLEMENTATION_PLAN.md`](./PHASE_2_REMEDIATION_IMPLEMENTATION_PLAN.md)
  Status, exit criteria, execution sequence, and final acceptance synchronized.
- [x] [`../SSCRE_PLAN.md`](../SSCRE_PLAN.md) Phase 2 section references remediation
  close-out.
- [x] Broad verification commands pass (table above).
- [ ] Verified remediation bundle committed to git (open at close-out; see plan
  acceptance table **Git parity**).

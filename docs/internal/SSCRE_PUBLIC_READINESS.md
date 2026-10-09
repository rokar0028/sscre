# SSCRE public release plan

**Last reviewed:** 2026-10-09 (read-only scan of `rokar0028/sscre`)

**Finding:** No real keys, passwords, or database credentials in the tree; only
fake test values.

**Strategy:** Do **not** flip this repository public. After the paper is
submitted, publish a **new public repo from one clean commit** (squashed export),
authored with a GitHub **noreply** email. This working repo stays private and
keeps full benchmarks and internal docs.

---

## Hard gates (do not skip)

- [ ] **Paper submitted** (or explicit decision to release benchmark numbers)—no
  public repo before this unless you deliberately open-source code-only with zero
  unpublished results.
- [ ] **Publish bundle is a new repo**, not `git push` + “Make public” on this
  history.
- [ ] **Personal Gmail appears on all ~82 commits** today; only a fresh root
  commit on the public repo removes that from the published history.

---

## Phase A — Identity and commit hygiene (now, while private)

Do this before the next push so new work does not add more personal email.

- [ ] Copy your GitHub noreply address from **Settings → Emails** (format
  `<id>+rokar0028@users.noreply.github.com`).
- [ ] Set local Git identity for this repo (repo-local, not global, if you
  prefer):
  - [ ] `git config user.email "<noreply>@users.noreply.github.com"`
  - [ ] `git config user.name` matches your GitHub display name.
- [ ] Enable **Keep my email addresses private** on GitHub.
- [ ] Record verification (paste one line): newest commit on `main` uses noreply
  email — command: `git log -1 --format='%ae %s'`.

---

## Phase B — Define what the public repo contains

Split **ship** vs **withhold** so the export step is mechanical.

### B.1 Ship in the public bundle (target)

- [ ] Application code: `src/sscre/`, `tests/`, `alembic/` (if present), Docker /
  Compose files, `pyproject.toml` / lockfile as used today.
- [ ] Public docs: `docs/reference/`, trimmed `docs/setup/` (PostgreSQL only),
  high-level architecture without interview positioning.
- [ ] Benchmark **tooling** (not full labeled sets): e.g.
  `benchmarks/candidates/tools/filter_cacheeval_commercial.py`,
  `benchmarks/source_inventory.json` (metadata only if no row text),
  `benchmarks/README.md` rewritten for “withheld pending paper” + how to rebuild
  a **local** dev set from approved upstreams.
- [ ] Schema / contract docs: `benchmarks/EVALUATION_LABEL_CONTRACT_v1.md`,
  `benchmarks/ANNOTATION_GUIDE_v1.md` (if they contain no unpublished numbers).
- [ ] Root `README.md`, `LICENSE`, `LICENSE-DATA`, `CREDIT.md`.

### B.2 Withhold from the public bundle (keep in this private repo)

Move or copy to private storage first; **exclude entirely** from the export
commit (do not rely on `.gitignore` alone for the one-commit repo—omit files
from the export tree).

**Benchmarks and evaluation data**

- [ ] `benchmarks/reviewed_query_pairs.jsonl` (615 pairs)
- [ ] `benchmarks/held_out_test.jsonl` (215-pair held-out)
- [ ] `benchmarks/development.jsonl` (400-pair development split)
- [ ] `benchmarks/candidates/cacheeval_batch_01*.jsonl`
- [ ] `benchmarks/candidates/expansion_v1.jsonl` (if it contains reviewed labels)
- [ ] Any future `benchmarks/candidates/upstream/*.jsonl` (already gitignored;
  keep it that way)

**Experiment outputs and paper figures**

- [ ] `artifacts/evaluation/` (sweeps, Pareto, held-out comparisons)
- [ ] `experiments/milestone10_*` and other JSON reports with measured thresholds /
  hit rates / cost numbers tied to the unpublished evaluation
- [ ] `experiments/*_report.json` if they embed unpublished metrics (review each
  file during export)

**Internal and planning docs**

- [ ] `docs/internal/` (entire tree, including this file after export unless you
  want a redacted copy in public—default: omit)
- [ ] `docs/phase-1/` and `docs/phase-2/` implementation plans and
  `*_EVIDENCE.md` (thresholds, 0.95 figures, workstream numbers)
- [ ] `docs/phase-3/` until intentionally published
- [ ] `docs/internal/reports/MILESTONE_10_FINAL_EXPERIMENT_AND_INTERVIEW_REPORT.md`

**Dev environment and IDE**

- [ ] `.cursor/` (rules, skills references)
- [ ] `docs/setup/CURSOR_PORTABLE_SETUP.md`

### B.3 Sanitize docs that stay public

- [ ] `docs/SSCRE_PROJECT_ANALYSIS.md` — remove or rewrite **§ Interview
  strength / Interview positioning** for a research/engineering audience.
- [ ] `docs/SSCRE_LEARNING_AND_EXECUTION_GUIDE.md` — remove **§ 8 Interview
  Preparation** and milestone-10 interview checklist items; keep learning path
  for contributors.
- [ ] `docs/SSCRE_SYSTEM_DESIGN.md` — search for “interview report”; replace
  with pointer to paper or public evaluation doc when available.
- [ ] `docs/SSCRE_PLAN.md` — either omit from public bundle or ship a redacted
  “roadmap” without unpublished experiment results (default: omit).

- [ ] After edits, search repo for stale paths:
  `rg "docs/internal|held_out|reviewed_query_pairs|milestone10" docs/`

---

## Phase C — Licensing and attribution (can complete before paper)

Public release requires explicit licenses even if the benchmark JSONL is
withheld.

- [ ] Add root **`LICENSE`** — MIT (or chosen code license) for SSCRE code.
- [ ] Add **`LICENSE-DATA`** — CC BY-SA 4.0 for redistributable benchmark
  derivatives you eventually publish; state that the **current public repo**
  does not ship the full dataset until the paper.
- [ ] Add **`CREDIT.md`** with:
  - [ ] [BudEcosystem/CacheEval](https://github.com/BudEcosystem/CacheEval) at
    pinned revision **`cd3ff21`** (match `filter_cacheeval_commercial.py` /
    `source_inventory.json`).
  - [ ] Banking77 and CLINC (and any other upstreams listed in CacheEval
    `ATTRIBUTION.md`).
  - [ ] SSCRE filter script and human-review step (your contribution).
- [ ] Re-read CacheEval **`LICENSE`** and **`ATTRIBUTION.md`** on that pin;
  confirm CC BY-SA 4.0 still applies to filtered exports you describe.
- [ ] Confirm **no Quora QQP / NC-tagged rows** in anything you might later
  publish: document filter command and counts (1945 retained / 55 excluded at
  `cd3ff21` per phase-2 plan)—re-run if upstream or filter script changed:
  - [ ] Record command + stdout in this section or a private log.

---

## Phase D — Public repo UX (README and ignore rules)

- [ ] Add root **`README.md`** with:
  - [ ] Two-sentence problem statement (semantic cache reuse + safety).
  - [ ] Stack: Python, FastAPI, PostgreSQL + pgvector, pytest, Docker Compose.
  - [ ] Quickstart: install deps, run tests, start API (copy from existing setup
    docs).
  - [ ] **Benchmark notice:** full labeled benchmark withheld for upcoming
    paper; link to `CREDIT.md` and filter tooling for researchers rebuilding
    locally.
  - [ ] License pointers: `LICENSE`, `LICENSE-DATA`.
- [ ] Update **`.gitignore`** for contributor hygiene on the public repo:
  - [ ] Remove comment block about unrelated local folders (`fastapi/`,
    `tutorial_pydan/`) from the **export** copy (those paths are not part of
    SSCRE).
  - [ ] Ensure `venv/`, `.venv/`, `*.log`, `.env`, IDE dirs (`.vscode/`,
    `.idea/`) are ignored.
  - [ ] Keep upstream CacheEval blobs ignored (`benchmarks/candidates/upstream/`).
- [ ] Optional on **this private repo**: add gitignore entries for withheld paths
  **only if** you stop tracking them here (otherwise keep tracking for research
  and exclude at export time).

---

## Phase E — Build the publish bundle (after paper submitted)

### E.1 Export tree

- [ ] Create a clean directory (e.g. `sscre-public-export/`) with **only**
  Phase B.1 paths + Phase B.3 sanitized docs.
- [ ] Copy—not move—from this repo so private work continues unchanged.
- [ ] Manually verify withheld paths are absent:
  - [ ] `rg --files | rg -i "held_out|reviewed_query|EVIDENCE|artifacts/evaluation|docs/internal"` → no matches

### E.2 One commit, noreply author

- [ ] `git init` in export directory; single commit with noreply `user.email`.
- [ ] Commit message states “Initial public release” (no co-authored-by personal
  emails).

### E.3 Security and GitHub settings

- [ ] Run secret scan on export root; record result:
  - [ ] `gitleaks detect --source . --verbose` → exit 0 (or document findings
        fixed)
- [ ] Push to **new** GitHub repository (empty remote).
- [ ] Enable **Secret scanning** and **Push protection** (repo Settings →
  Security).
- [ ] Add branch protection on `main` if you accept external PRs later.

### E.4 Smoke test as a stranger

- [ ] Clone to a fresh path; create venv; run documented test command (e.g.
  `pytest` subset that does not require withheld JSONL).
- [ ] Start API with in-memory / test profile per project conventions.
- [ ] Confirm README links resolve and no internal paths 404 in the shipped tree.

### E.5 Go public

- [ ] Set new repository visibility to **Public**.
- [ ] Add paper DOI / arXiv link to README when available.
- [ ] Decide whether to open-source benchmark JSONL in a **separate data release**
  (same license block) or keep code-only public indefinitely.

---

## Phase F — Optional credibility before or at launch

Not strictly required for “public,” but strengthens a paper + portfolio story.

- [ ] CI green on the **export** repo (reproduce migration checksums and
  `source_dataset sha256` checks; fix CRLF/LF if needed—see
  `docs/internal/PHASE3_TRANSITION.md`).
- [ ] Single documented command to regenerate **public-safe** demo metrics (tiny
  fixture set), if full benchmark stays private.

---

## Verification log

Record evidence here as phases complete (command + date + outcome).

| Phase | Command / action | Date | Pass? |
| --- | --- | --- | --- |
| A | `git log -1 --format='%ae'` | | |
| C | CacheEval license re-check @ `cd3ff21` | | |
| E | `gitleaks detect --source .` | | |
| E | Fresh clone + pytest | | |

---

## Decisions still needed from you

- [ ] **Code-only public** before paper vs **wait until submission** (default in
  gates above: wait).
- [ ] Whether **`docs/SSCRE_PLAN.md`** ships redacted or stays private-only.
- [ ] Whether post-paper benchmark ships in-repo, Zenodo, or Hugging Face Datasets.

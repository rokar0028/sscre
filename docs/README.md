# SSCRE Documentation Hub

Start here. The tree is grouped by role so you do not have to scan fifty
filenames at the repo root.

## Quick start (reading order)

1. [SSCRE_PROJECT_ANALYSIS.md](./SSCRE_PROJECT_ANALYSIS.md) — scope and rationale
2. [SSCRE_LEARNING_AND_EXECUTION_GUIDE.md](./SSCRE_LEARNING_AND_EXECUTION_GUIDE.md) — checklist and next tasks
3. [SSCRE_PLAN.md](./SSCRE_PLAN.md) — phases, milestones, experiments
4. [SSCRE_SYSTEM_DESIGN.md](./SSCRE_SYSTEM_DESIGN.md) — architecture (read when implementing)

Implementation code lives under `src/sscre/`, `tests/`, `benchmarks/`, and
`experiments/`.

## Adding new documentation

- **Never** add project markdown at the repository root — use a folder below.
- **Phase work** → `phase-1/` or `phase-2/` (keep phase-2 files flat; paths are
  cited from code). Update that phase's `README.md`.
- **Specs and flows** → `reference/`. **Setup guides** → `setup/`.
- **Release prep, agent briefs, original brief** → `internal/` (or
  `internal/reports/` for milestone write-ups).
- After **moves or renames**, search the repo for the old path and fix links.

## Directory map

```text
docs/
├── README.md                          ← you are here
├── SSCRE_PLAN.md                      ← master research / milestone tracker
├── SSCRE_PROJECT_ANALYSIS.md
├── SSCRE_LEARNING_AND_EXECUTION_GUIDE.md
├── SSCRE_SYSTEM_DESIGN.md
├── reference/                         ← formats, flows, limits, production contract
├── setup/                             ← PostgreSQL and Cursor portable setup
├── internal/                          ← release prep, Phase 0 decisions, transition brief (see internal/README.md)
├── phase-1/                           ← Milestones 1–10 implementation plans
├── phase-2/                           ← Phase 2 plans, contracts, evidence (see phase-2/README.md)
└── phase-3/                           ← placeholder until PHASE3_PLAN.md exists
```

## Core documents (top level)

| File | Purpose |
| --- | --- |
| [SSCRE_PROJECT_ANALYSIS.md](./SSCRE_PROJECT_ANALYSIS.md) | Why the project exists and major decisions |
| [SSCRE_LEARNING_AND_EXECUTION_GUIDE.md](./SSCRE_LEARNING_AND_EXECUTION_GUIDE.md) | Active implementation checklist |
| [SSCRE_PLAN.md](./SSCRE_PLAN.md) | Phases, experiments, success criteria |
| [SSCRE_SYSTEM_DESIGN.md](./SSCRE_SYSTEM_DESIGN.md) | Components, APIs, schema, deployment |

## Reference (`reference/`)

Technical specs and evaluation notes — not milestone checklists.

| File | Topic |
| --- | --- |
| [SSCRE_BENCHMARK_FORMAT.md](./reference/SSCRE_BENCHMARK_FORMAT.md) | Reviewed pair JSON schema |
| [SSCRE_QUERY_PREPROCESSING.md](./reference/SSCRE_QUERY_PREPROCESSING.md) | Normalization and hashing |
| [SSCRE_REQUEST_FLOW.md](./reference/SSCRE_REQUEST_FLOW.md) | End-to-end request path |
| [SSCRE_EVALUATION_LIMITATIONS.md](./reference/SSCRE_EVALUATION_LIMITATIONS.md) | Known eval gaps |
| [SSCRE_STORAGE_FAILURE_GALLERY.md](./reference/SSCRE_STORAGE_FAILURE_GALLERY.md) | Cache lifecycle cases |
| [SSCRE_PRODUCTION_READINESS_CONTRACT.md](./reference/SSCRE_PRODUCTION_READINESS_CONTRACT.md) | Production gate inventory |

## Setup (`setup/`)

| File | Purpose |
| --- | --- |
| [POSTGRESQL_LOCAL_SETUP.md](./setup/POSTGRESQL_LOCAL_SETUP.md) | Local Postgres + pgvector |
| [CURSOR_PORTABLE_SETUP.md](./setup/CURSOR_PORTABLE_SETUP.md) | Cursor rules/skills on another machine |

## Internal (`internal/`)

Planning and release material that should not ship in a public repo as-is.
See [SSCRE_PUBLIC_READINESS.md](./internal/SSCRE_PUBLIC_READINESS.md).

| File | Purpose |
| --- | --- |
| [SSCRE_PUBLIC_READINESS.md](./internal/SSCRE_PUBLIC_READINESS.md) | Pre-public checklist |
| [PHASE3_TRANSITION.md](./internal/PHASE3_TRANSITION.md) | Agent brief: Phase 2 wrap-up → Phase 3 |
| [safe_semantic_llm_response_reuse_major_project.md](./internal/safe_semantic_llm_response_reuse_major_project.md) | Original project write-up |
| [reports/MILESTONE_10_FINAL_EXPERIMENT_AND_INTERVIEW_REPORT.md](./internal/reports/MILESTONE_10_FINAL_EXPERIMENT_AND_INTERVIEW_REPORT.md) | Milestone 10 final report |

## Phase plans

| Folder | Index | Contents |
| --- | --- | --- |
| [phase-1/](./phase-1/) | [phase-1/README.md](./phase-1/README.md) | Milestones 1–10 implementation plans |
| [phase-2/](./phase-2/) | [phase-2/README.md](./phase-2/README.md) | Workstreams 1–6, frozen contracts, evidence |
| [phase-3/](./phase-3/) | [phase-3/README.md](./phase-3/README.md) | Future; output target `phase-3/PHASE3_PLAN.md` |

## Authoritative sources

- **Active planning:** [SSCRE_PLAN.md](./SSCRE_PLAN.md) and
  [SSCRE_LEARNING_AND_EXECUTION_GUIDE.md](./SSCRE_LEARNING_AND_EXECUTION_GUIDE.md)
- **Original brief (read-only):**
  [internal/safe_semantic_llm_response_reuse_major_project.md](./internal/safe_semantic_llm_response_reuse_major_project.md)
  overlaps the plan; do not maintain two competing checklists.

## How to update documents

- Tick tasks in `SSCRE_LEARNING_AND_EXECUTION_GUIDE.md`.
- Update milestone status in `SSCRE_PLAN.md`.
- Touch `SSCRE_SYSTEM_DESIGN.md` only when architecture or measurements change.
- Phase 2 workstream steps: edit the relevant file under `phase-2/` and link
  evidence in the matching `WORKSTREAM_*_EVIDENCE.md`.

Documentation is not progress. A task is complete only when code, tests, and
evidence exist.

## Cursor workflows

Local [Ponytail](https://github.com/DietrichGebert/ponytail) subset:

- `.cursor/rules/ponytail-efficiency.mdc`, `.cursor/rules/concise-chat.mdc`
- `.cursor/commands/ponytail-review.md`, `.cursor/commands/immunize.md`
- `.cursor/skills/ponytail-review/SKILL.md`, `.cursor/skills/immunize/SKILL.md`

Use `/ponytail-review` after a meaningful milestone. Use `/immunize` only for
repeatable mistakes that deserve a durable rule.

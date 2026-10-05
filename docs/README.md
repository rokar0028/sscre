# SSCRE Documentation Hub

This is the starting point for the project. Read this file first.

## What is the main project?

The main project is the software and experiments that will be created in the
repository:

```text
SSCRE
├── FastAPI wrapper
├── exact and semantic cache
├── safety engine
├── PostgreSQL/pgvector storage
├── evaluation harness
├── benchmark dataset
├── tests
└── experiment results
```

The repository contains the project documentation and the initial
implementation. Ongoing implementation belongs under:

```text
src/sscre/
tests/
benchmarks/
experiments/
```

## Where should I focus?

Focus on one file at a time in this order:

1. `SSCRE_PROJECT_ANALYSIS.md` — understand the project and scope
2. `SSCRE_LEARNING_AND_EXECUTION_GUIDE.md` — follow the detailed checklist
3. `SSCRE_PLAN.md` — track milestones and experiments
4. `SSCRE_SYSTEM_DESIGN.md` — consult only while implementing a related feature

Do not try to read or implement the entire system design at once.

## Which document is authoritative?

| Document | Purpose | Use it when |
|---|---|---|
| `Downloads/safe_semantic_llm_response_reuse_major_project.md` | Original project brief/source | You need the original proposal or requirements |
| `SSCRE_PROJECT_ANALYSIS.md` | Project assessment and decisions | You need to understand why the project is worth building |
| `SSCRE_LEARNING_AND_EXECUTION_GUIDE.md` | Detailed learning and implementation checklist | You need to decide what to do next |
| `SSCRE_PLAN.md` | Research plan, phases, experiments, and success criteria | You are planning or evaluating a milestone |
| `SSCRE_SYSTEM_DESIGN.md` | Architecture, interfaces, data flow, schema, and deployment | You are implementing a specific component |

The Downloads file is the original source brief. It is not part of the working
repository and should be treated as read-only reference material. Its content
substantially overlaps with `SSCRE_PLAN.md`; use the repository copy for active
planning and checkbox tracking so there is only one working plan.

The active task tracker is:

```text
SSCRE_LEARNING_AND_EXECUTION_GUIDE.md
```

The research and milestone reference is:

```text
SSCRE_PLAN.md
```

## Current project status

- [x] Project idea and research question defined
- [x] Initial architecture documented
- [x] Risks and design corrections documented
- [x] Learning and implementation order documented
- [x] Python project scaffold created
- [x] First FastAPI endpoint working
- [x] Exact-match vertical slice working
- [x] Request metrics and reliability basics working
- [x] PostgreSQL persistence working
- [x] Evaluation baseline working
- [ ] Semantic retrieval working
- [ ] Compatibility-aware safety engine working
- [ ] Final experiments completed

## Current next task

Begin Milestone 8 in `SSCRE_LEARNING_AND_EXECUTION_GUIDE.md`:

- [ ] Define `SAFE`, `UNSAFE`, and `UNCERTAIN`
- [ ] Extract compatibility constraints
- [ ] Implement the first compatibility-aware safety decision

Complete the learning items for Milestones 0 through 5 before moving on.

## How to update documents

- Tick implementation tasks in `SSCRE_LEARNING_AND_EXECUTION_GUIDE.md`.
- Update milestone and experiment status in `SSCRE_PLAN.md`.
- Update `SSCRE_SYSTEM_DESIGN.md` only when implementation or measurements change
  the architecture.
- Keep `SSCRE_PROJECT_ANALYSIS.md` as a stable assessment; update it only when
  the project direction or major risks change.

## Important rule

Documentation is not project progress. A task is complete only when code,
tests, and evidence exist.

Use this loop:

```text
Read the next checklist item
→ learn the required concept
→ implement one small change
→ test it
→ explain it
→ tick the checkbox
```

## Cursor workflows

This project uses a small, local subset of the
[Ponytail](https://github.com/DietrichGebert/ponytail) workflow:

- `.cursor/rules/ponytail-efficiency.mdc` — always-on YAGNI and safety guidance
- `.cursor/rules/concise-chat.mdc` — concise responses
- `.cursor/commands/ponytail-review.md` — review alias
- `.cursor/commands/immunize.md` — repeatable-mistake alias
- `.cursor/skills/ponytail-review/SKILL.md` — delete-list review
- `.cursor/skills/immunize/SKILL.md` — smallest durable project fix

Use `/ponytail-review` after a meaningful implementation milestone. Use
`/immunize` only when a mistake is repeatable and deserves a durable project
rule or workflow. These workflows do not replace tests or technical review.


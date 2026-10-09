---
name: professional-git
description: >-
  Plan and create one-topic git commits (and optionally push) with conventional
  messages, tests, and safety checks. Use when the user runs /commit or /push,
  or asks for professional, review-friendly commits.
---

# Professional git (commit and push)

There is **no** built-in git command that reads your diff and splits commits by
topic automatically. This skill is the workflow: inspect changes, **propose an
ordered commit plan**, then execute **one logical change per commit** after
confirmation (unless the user explicitly says to run the plan without asking).

## When to use

- User invokes **`/commit`** → commit workflow only (never push).
- User invokes **`/push`** → push workflow only (never commit unless required
  to fix hook failures).
- User asks for "professional commits," "split commits by topic," or "prepare
  for review."

## Commit workflow

### 1. Inspect (parallel)

From repo root:

- `git status -sb`
- `git diff` and `git diff --staged`
- `git log -8 --oneline` (match existing message style)

### 2. Plan (required output before any commit)

Produce an **ordered commit plan** table or numbered list. Each row:

| # | Topic (one line) | Paths | Type | Subject line (draft) |
| --- | --- | --- | --- | --- |

**Typing (Conventional Commits–style, industry common):**

| Type | Use for |
| --- | --- |
| `feat` | User-facing or API behavior |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `test` | Tests only |
| `refactor` | Behavior-preserving code change |
| `chore` | Tooling, gitignore, deps, cursor rules |
| `ci` | CI/workflow only |
| `artifacts` | Checked-in evaluation/build outputs (when intentional) |

**Splitting rules (review-friendly):**

- **One topic per commit** — if the subject needs "and," split unless everything
  is the same doc-only theme (e.g. "fix links after docs move").
- **Separate** code vs docs vs planning vs generated artifacts when practical.
- **Never** stage secrets (`.env`, credentials), `build/`, `dist/`, or large
  accidental dumps.
- **Do not** mix unrelated milestones or workstreams in one commit.
- Respect repo rules: planning-doc commits separate from code when possible;
  Windows PowerShell → `git commit -m "subject" -m "body"` (no bash HEREDOC).

Ask the user to confirm the plan **unless** they said to execute `/commit` fully
or already approved the plan in the same thread.

### 3. Execute (sequential — never parallel commits)

**Never** run `git add`, `git commit`, or `git reset` in parallel with other
git commands (avoids `.git/index.lock` and accidental mixed staging).

If **`index.lock`** appears: stop, remove the lock only when no git process is
running, then `git status`; unstage paths not in the current plan row before
continuing.

For **each** planned commit, in order:

1. `git status -sb` — confirm the index matches **only** this plan row (if not,
   `git restore --staged` on stray paths).
2. `git add` only the paths for that commit (no blind `git add .` if unrelated
   files exist).
3. Run **relevant tests** for code/test commits (`python -m pytest -q` or a
   focused subset); report pass, fail, or skip. Skip full pytest for
   docs-only / `.cursor/` / hook-only commits unless the user asks otherwise.
4. `git commit -m "type(scope): subject" -m "Body: why, not a file list."`
5. `git show --stat HEAD` — files must match the plan row; if not, fix with
   `git reset --mixed HEAD~1` and recommit **before** starting the next topic.

If a **pre-commit hook** fails: fix the issue and create a **new** commit; do
not `--amend` unless repo rules allow.

### 4. Handoff

Print:

- Commit SHAs and subjects (new since branch diverged).
- Remaining unstaged/untracked files.
- Reminder: use **`/push`** when ready (separate step; needs explicit OK per
  project workflow).

## Push workflow

Only after commits exist and the user invoked **`/push`** or explicitly approved
push in the same request.

### 1. Inspect (parallel)

- `git status -sb`
- `git log origin/main..HEAD --oneline` (or the tracking branch if not `main`)
- Confirm branch name is intentional.

### 2. Safety (non-negotiable)

- **Never** `git push --force` to `main` or `master`; warn if requested.
- **Never** update git config.
- **Never** push if the user has not OK'd push in this conversation (project
  Phase 0 workflow).
- Prefer `git push -u origin HEAD` for a new branch.

### 3. Execute

1. Push once: `git push -u origin HEAD` (or user-specified remote/branch).
2. If GitHub Actions matter: note that CI runs on push; offer to watch/check with
   `gh run list` / PR checks when `gh` is available.
3. Report remote URL and suggest recording the green Actions run URL in the
   relevant plan doc (e.g. Phase 1 P2-CI).

### 4. Do not

- Amend pushed commits without explicit user request and force-push approval.
- Bundle "commit everything" into push — push only sends existing commits.

## Optional: split an already-made bundled commit

If the user wants history cleaned **before** push:

1. Prefer `git reset --mixed HEAD~N` only when commits are **local and not
   pushed**, then re-commit using the plan above.
2. Never rewrite history that is already on the remote unless the user
   explicitly accepts force-push consequences.

## Quick reference for the user

| Goal | What to run |
| --- | --- |
| Topic-based commits | **`/commit`** in chat |
| Send branch to GitHub | **`/push`** in chat (after OK) |
| Manual git | `git add -p` (patch staging) + your own commits |

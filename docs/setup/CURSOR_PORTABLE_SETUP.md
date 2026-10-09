# Portable Cursor Workflow Setup

Copy this entire file into another project's Cursor chat and ask Cursor to follow it.

## Task

Set up two reusable project-local Cursor workflows:

1. `/immunize`
2. `/ponytail-review`

Create the required `.cursor` rules, skills, commands, and optional hook in the current project. Do not add dependencies, commit changes, or push anything.

## Requirements

### 1. Create the portable efficiency rule

Create `.cursor/rules/ponytail-efficiency.mdc` with frontmatter:

```yaml
---
description: Prefer the smallest correct solution and avoid unnecessary complexity
alwaysApply: true
---
```

The rule must instruct Cursor to:

- Prefer YAGNI, reuse, platform features, installed dependencies, and minimal diffs.
- Delete unnecessary code instead of adding abstractions.
- Avoid new dependencies unless genuinely required.
- Never skip security, validation, authorization, tenancy checks, accessibility, or data-loss prevention.
- Keep solutions boring, focused, and proportionate.

### 2. Create the concise-chat rule

Create `.cursor/rules/concise-chat.mdc` with frontmatter:

```yaml
---
description: Keep agent responses short, direct, and useful
alwaysApply: true
---
```

Instruct Cursor to lead with the result, avoid filler, prefer short bullets, and avoid pasting large code blocks into chat when files can be edited directly.

### 3. Create the `ponytail-review` skill

Create `.cursor/skills/ponytail-review/SKILL.md` with valid frontmatter:

```yaml
---
name: ponytail-review
description: Review the current diff for over-engineering, scope creep, and unnecessary code
disable-model-invocation: true
---
```

The skill must:

1. Inspect `git status`, `git diff`, and staged changes when relevant.
2. Read only changed files unless broader inspection is necessary.
3. Return a prioritized delete-list, not a rewrite.
4. Identify:
   - unnecessary files or code,
   - one-use wrappers that can be inlined,
   - duplicated utilities,
   - unnecessary dependencies,
   - scope creep,
   - missing security, validation, authorization, tenancy, error handling, or accessibility.
5. Never recommend deleting required security, validation, authorization, tenancy, error handling, or accessibility protections.
6. Do not modify files unless explicitly asked.

Use this output format:

```markdown
## Ponytail review

**Diff size:** +N / -M lines across X files

### Delete list
1. `path` — reason and category

### Keep
- Essential item

### Net suggestion
One sentence describing the smallest cleanup.
```

### 4. Create the `immunize` skill

Create `.cursor/skills/immunize/SKILL.md` with valid frontmatter:

```yaml
---
name: immunize
description: Turn a repeatable mistake from this chat into the smallest durable project fix
disable-model-invocation: true
---
```

The skill must:

1. Summarize what went wrong, the root cause, and what fixed it.
2. Decide whether the lesson is repeatable.
3. Skip one-off mistakes and lessons already covered by existing project artifacts.
4. Treat security, authorization, validation, tenancy, and IDOR issues as worth immunizing.
5. Choose exactly one lightest durable artifact:
   - code or configuration,
   - hook,
   - existing skill extension,
   - new skill,
   - command,
   - scoped rule,
   - always-on rule only as a last resort.
6. Prefer extending existing files over creating duplicates.
7. Never add dependencies unless essential.
8. Never commit, push, or create a pull request.
9. Write the selected fix directly when appropriate.

Use this output format:

```markdown
## Immunize

**Incident:** One sentence
**Root cause:** One sentence
**Artifact:** code | hook | skill | command | rule | skip
**Why this type:** One sentence
**Verdict:** Immunized | Skipped — reason

### Changes
- `path` — what changed

### Review
`git diff` — files and behavior to inspect
```

### 5. Create slash commands

Create these thin command aliases:

`.cursor/commands/ponytail-review.md`

```markdown
# Ponytail Review

Read and follow `.cursor/skills/ponytail-review/SKILL.md`.
```

`.cursor/commands/immunize.md`

```markdown
# Immunize

Read and follow `.cursor/skills/immunize/SKILL.md`.
```

### 6. Optional artifact index hook

If the project already uses Cursor hooks, add a safe hook that refreshes an artifact index when `.cursor/rules/`, `.cursor/skills/`, `.cursor/commands/`, or `.cursor/hooks/` changes.

If no hook system exists, do not add one merely for convenience. The two workflows must work without a hook.

If implementing the hook, do not overwrite user content outside clearly marked generated markers:

```text
<!-- immunize-artifact-index:start -->
<!-- immunize-artifact-index:end -->
```

### 7. Project adaptation

Before writing files:

- Inspect the target project's existing `.cursor`, `AGENTS.md`, `CLAUDE.md`, package scripts, and repository conventions.
- Preserve existing rules and workflows.
- Do not copy rules that are specific to another application, framework, product, database, or tenancy model.
- Merge with existing files only when the behavior is compatible.
- Report any conflicts before making a destructive change.

### 8. Verification

After implementation:

1. Verify the files exist in the expected paths.
2. Validate YAML frontmatter and Markdown structure.
3. Run the project's existing checks only if they are relevant.
4. Show `git diff --stat` and summarize the created or changed files.
5. Leave all changes uncommitted for review.

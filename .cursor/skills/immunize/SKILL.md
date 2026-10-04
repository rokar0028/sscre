---
name: immunize
description: Turn a repeatable mistake from this chat into the smallest durable project fix
disable-model-invocation: true
---

# Immunize

Convert a repeatable mistake into the lightest durable project improvement.

## Workflow

1. Inspect the current incident and identify the observable failure.
2. Summarize what went wrong, the root cause, and what fixed it.
3. Decide whether the lesson is repeatable and likely to recur in this project.
4. Inspect existing rules, skills, commands, documentation indexes, and project
   conventions before proposing an artifact.
5. Skip one-off mistakes, user preference changes, and lessons already covered
   by existing project artifacts.
6. Treat security, authorization, validation, tenancy, IDOR, and data-loss
   issues as worth immunizing even after one occurrence.
7. Choose exactly one lightest durable artifact:
   - code or configuration
   - hook
   - existing skill extension
   - new skill
   - command
   - scoped rule
   - always-on rule only as a last resort
8. Prefer extending an existing artifact over creating a duplicate.
9. For documentation problems, update the canonical index or tracker instead
   of creating another standalone document.
10. For guidance that applies only to one path, use a scoped rule instead of an
    always-on rule.
11. Do not use a hook when a rule, command, or existing skill is sufficient.
12. Do not add dependencies unless essential.
13. Write the selected fix directly only when the fix is clear and low-risk.
14. Verify the changed artifact and report what should be reviewed.
15. Never commit, push, or create a pull request.

## Decision test

Before changing anything, answer:

```text
What exact behavior should change?
Why will it recur?
Where is the single best place to enforce it?
What existing artifact can be extended?
How will the fix be verified?
```

If these answers are unclear, use `skip` and explain why.

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

### Verification
- Check or test performed

### Review
`git diff` — files and behavior to inspect
```

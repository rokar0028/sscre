---
name: ponytail-review
description: Review the current diff for over-engineering, scope creep, and unnecessary code
disable-model-invocation: true
---

# Ponytail review

Review the current project changes for the smallest correct solution.

1. Inspect `git status`, `git diff`, and staged changes when relevant.
2. Read changed files first; inspect broader context only when necessary.
3. Return a prioritized delete-list, not a rewrite.
4. Identify:
   - unnecessary files or code
   - one-use wrappers that can be inlined
   - duplicated utilities
   - unnecessary dependencies
   - scope creep
   - missing security, validation, authorization, tenancy, error handling, or
     accessibility
5. Never recommend deleting required security, validation, authorization,
   tenancy, error handling, or accessibility protections.
6. Do not modify files unless explicitly asked.
7. If the project is not a Git repository, state that diff-based review is
   unavailable and review only the relevant changed artifacts if they are known.

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

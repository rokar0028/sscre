# SSCRE full review: rokar0028/sscre, as of Mon 12 Oct 2026, 09:40 IST

This was a read-only review: nothing was changed and no evaluations were run. All times are IST.
Lines marked **[judgment]** are my assessment, not repo facts. This builds on the 11 Oct reviews (`/workspace/sscre_review_2026-10-11.md`) and the Strategy C, CacheEval, token and paper findings.

---

## 1. What's new since 11 Oct ~04:19 IST

### Merged to `main` via PR #2
PR #2, "feat: WS8 eviction scope, WS9 dashboard, Phase 3 WS1 registry", went from `phase4/setup` into `main`. It was created 11 Oct 14:39 and merged 11 Oct 15:39 (merge commit `48bfb3d`): 16 commits, 54 files, +13,934/−320.

| Hash | IST | Commit |
|---|---|---|
| `e6b3f1e` | 11 Oct 04:57 | fix(sscre): scope PostgreSQL eviction to run-owned hashes |
| `509f152`, `2ccd168` | 11 Oct 04:57 | WS8 eviction-scope guard docs and refreshed ops evidence |
| `02c081c`, `43faac5`, `1fc78ac` | 11 Oct 04:57 | WS9 dashboard plan/audit, `dashboard.py` export, outputs |
| `a49221b` | 11 Oct 06:05 | chore(cursor): WS9 artifact-boundary rule |
| `1f4224b` | 11 Oct 06:06 | fix: fail-close WS9 dashboard schema alignment |
| `35b2878` | 11 Oct 06:06 | feat: opt-in WS9 dual-model runner (`dual_model.py`) |
| `3190bae`, `da323d0` | 11 Oct 06:06–06:07 | WS9 evidence; dashboard and dual-model artifacts |
| `e86178e`, `c90b7ee` | 11 Oct 14:36 | Phase 3 WS1 hypothesis registry (Features 4–8), WS5–8 plans; docs-layout rule |
| `de4cc7c` | 11 Oct 15:34 | fix: hash the split manifest as LF bytes |
| `4d56286` | 11 Oct 15:34 | feat: report cache storage bytes by component |
| `e3363cf` | 11 Oct 15:34 | docs(phase-3): sync WS2–WS4 plans and WS5 Step 1 |

### On `phase4/setup` only (9 commits ahead of `main`; no PR; no CI run)
The last push was 12 Oct 03:56–03:57.

| Hash | IST | Commit |
|---|---|---|
| `a81bbec` | 11 Oct 21:14 | chore(cursor): tighten planning/postgres rules |
| `ba3069b` | 11 Oct 21:14 | feat(phase3): dev float32 embedding storage baseline (`phase3_embedding_storage.py`) |
| `85eb5ed` | 11 Oct 21:14 | feat(phase3): 1K–100K simulated load ladder (`load_test.run_ladder`, +718 lines) |
| `7453abe` | 11 Oct 21:14 | docs: Feature 4 failure clustering (`PHASE3_FAILURE_CLUSTERS.md`) |
| `d5f45d5` | 11 Oct 21:15 | docs: tracker sync for WS5–7 |
| `530b6ca` | 12 Oct 03:36 | chore(cursor): planning checklist rules |
| `9b043d9` | 12 Oct 03:37 | docs: Feature 5 experiment-tracking audit → `keep_manual` |
| `dc72a8c` | 12 Oct 03:37 | artifacts: Phase 3 features registered in paper manifest |
| `580d73b` | 12 Oct 03:37 | docs: WS9 final sync; `SSCRE_PLAN.md` updated |
| `2f7aa5e` | 12 Oct 03:56 | docs: "close audit documentation gaps"; Phase 3 v1 marked closed |

### CI runs
- `c90b7ee` (PR #2, 11 Oct 14:39) **failed**: 4 failures in `tests/test_workstream9_dual_model.py` ("benchmark split manifest does not match declared sample identity"); 740 passed. Fixed by `de4cc7c`.
- `e3363cf` (15:36) passed; `main` `48bfb3d` (15:39) passed.
- The 9 newer `phase4/setup` commits have **no check runs**.

### Other activity
- No issues. Branches: `main` `48bfb3d`, `phase4/setup` `2f7aa5e`, `phase1/carryovers` `17e117f`, `phase2/phase3-plan` `8c65926`. The last two are stale.
- The repo is still private, with no license set.

### Corrections to my 11 Oct reviews
- **Phase 3 final run worktree.** On `phase4/setup`, `PHASE3_FINAL_EVIDENCE.md` now says the authoritative held-out artifact is commit `fe68ce3`, "clean at final artifact generation". The artifact header confirms `git_worktree_dirty: false`. The earlier "dirty, `0116657`" note is superseded.
  - `main` still carries the old dirty-tree wording.
  - Feature 1, Feature 2 and the WS9/load/quantization artifacts were generated on dirty trees.
- **Out-of-scope items now executed.** Load-ladder (#6), clustering (#9) and tracking (#10) have now been run, so their levels changed (section 7).

---

## 2. What SSCRE is and what's built

**What it is.** SSCRE (Safe Semantic Cache for Response Reuse) is a B.Tech major project. It's a FastAPI wrapper that reuses cached LLM answers only when a fail-closed check says SAFE.
- UNSAFE or UNCERTAIN means the answer is generated fresh.
- Storage is PostgreSQL + pgvector or in-memory.
- Strategies:
  - **A** exact hash;
  - **B** embedding-only;
  - **C** embedding plus rule-based compatibility (the default);
  - **D** cross-encoder, never built.

**Built so far:**
- service, migrations `000`–`011`, freshness/TTL cache controls, dedup, LRU/pattern eviction, bounded admin/ops;
- evaluation CLI with baselines, threshold sweeps, bootstrap CIs (seed 42, 1000 iterations), Pareto, freshness experiments, failure gallery;
- provider boundary (live run never executed), WS9 dashboard export, opt-in dual-model runner;
- Phase 3/4 experiment harnesses (adaptive thresholds, eviction, storage baseline, load ladder).

**Strategy C rules.** All in `compatibility.evaluate_candidate`; first rule to fire decides, in this order:
- similarity below τ → UNSAFE;
- dynamic query or candidate → UNSAFE;
- missing metadata → UNCERTAIN;
- constraint mismatch → UNSAFE; differing constraint sets → UNCERTAIN;
- entity disjoint → UNSAFE; one-sided entities → UNCERTAIN;
- intent / domain / format: both known and different → UNSAFE; either unknown → UNCERTAIN;
- temporal class mismatch → UNCERTAIN;
- otherwise SAFE.

**How metadata is extracted** (`metadata.py`):
- Regex on case-folded text.
- Domain uses unbounded substring terms (9 programming, 7 finance) and never outputs `general`.
- Entities come from a 7-term list plus a capitalisation heuristic.
- The only number parsing is a version regex. There are no negation, number, date or unit checks.
- Validator exceptions → UNCERTAIN; embedding or search failure → generate.

**Service settings:** `semantic_top_k=5`, τ `0.95`, cosine similarity (`1 - (embedding <=> q)`).

---

## 3. Phase-by-phase status

| Phase | Repo status | Notes |
|---|---|---|
| **Phase 1** (MVP M0–M10 + carryovers) | Done | Solid. CI now platform-independent (CRLF fixes `c260ec8`, `de4cc7c`) |
| **Phase 2** WS1–8 | Done | WS8 bounded local PostgreSQL package with run-owned eviction scope (`e6b3f1e`); "not a capacity guarantee"; live restart skipped |
| **Phase 2** WS9 | "Steps 1–9 complete" | Dashboard (`workstream9-dashboard.json/.html`) only reads upstream artifacts. Dual-model definition `pending_approval`, live run **not run**, user gate unchecked |
| **Phase 2** correctness labels | Open | Step 4 "Collect correctness labels" unchecked |
| **Phase 3** v1 | "closed (Phase 3 v1)" on `phase4/setup` | Features below |
| **Phase 4** | Done, with deferrals | Pareto done; provider `unavailable` (`live_opt_in_missing`); bounded scale; release with clean-checkout replay deferred |

**Phase 3 features:**
- **F1 adaptive thresholds:** "pass" on 1 of 430 requests.
- **F2 pattern eviction:** fail/defer.
- **F3 Strategy D:** deferred, trigger not met (re-checked in WS1 Step 6).
- **F4 failure clustering:** pass. A manual analysis of 13 Strategy B held-out false positives, put into 3 clusters by `failure_category`; domain, freshness and rule keys are all `unknown`.
- **F5 experiment tracking:** audit pass → `keep_manual`.
- **F6 float32 storage baseline:** `embedding_share 0.123641`, from 23,296 of 188,417 bytes over 800 dev requests at **dimension 8**.
- **F7 int8 quantization:** not authorized; the gate needs share ≥ 0.20.
- **F8 load ladder** (L1 200, L2 2,000, L3 20,000 requests): `first_bottleneck` `not_reached` on both memory and PostgreSQL.
  - Memory L3 p95: 101–111 ms.
  - PostgreSQL L3 p95: 958–1,062 ms at about 10–15 req/s, against a 3,000 ms budget.

---

## 4. Evaluation results and how far to trust them

### Final held-out package
Source: `phase3-final-held-out-comparison.json`, commit `fe68ce3`, clean tree, 430 directed requests, 85 reusable opportunities.

| Arm | Hit rate | FPR | Safe hits | Unsafe hits | Safe-reuse coverage | "tokens_saved" |
|---|---|---|---|---|---|---|
| No cache | 0 | — | 0 | — | 0 | 0 |
| A exact | 0.0535 (23) | **not computed** (`None`) | 1 | not computed | 0.0118 | 193 |
| B embedding | 0.0628 (27) | 0.481 | 2 | 13 | 0.0235 | 284 |
| C + Feature 1 | 0.0023 (1) | 0.0 | 1 | 0 | 0.0118 | 17 |

Abstention for C = 0.607 (261 UNCERTAIN, 168 UNSAFE). All costs are $0.0.

### Trust problems (all verified)
1. **Fake embeddings.** Every B/C artifact uses `fake-embedding`, 8-dim, built from a SHA-256 hash of the text. Only identical text means anything; other pairs get pseudo-random cosines. Example: B false positive `pair-0367` "nice thanks" vs "what's the boiling point of water?" at similarity 0.968. **There is no semantic result at all.**
2. **C's safe reuse is no better than exact match.** C served 1 safe hit (`pair-0002`, identical text). Exact cache A also has safe-reuse coverage 0.0118, so on this evidence C adds nothing over A. Its 0.0 FPR comes from abstaining on 60.7% of requests.
3. **Identical-text pairs labelled not reusable.** These are CacheEval conversational rows with their context stripped, e.g. `pair-0036` "incorrect"/"incorrect", `pair-0066` "yeah"/"yeah", `pair-0601` "next"/"next", all `reusable: False`.
   - 11 of B's 13 false positives have similarity 1.0.
   - Exact cache A would serve the same pairs, but its FPR isn't computed (`None`). That leaves the plan's "Strategy A: zero false positives" claim untested.
4. **False positives are attributed to the pair, not the candidate.** `reuse_outcome_indicators` judges a hit against the current record's `reusable` label, regardless of which cached entry was served. **[judgment]** That probably mis-scores some hits.
5. **Feature 1's "pass" is a tie-break artifact.** Every dev stratum had 0 hits at 0.8, 0.9 and 0.95, so 0.8 is just the lowest-threshold tie-break. The only held-out hit has similarity 1.0, which also clears global 0.95. The map is used only in evaluation and keys on the benchmark label.
6. **The quantization gate was decided at dimension 8.** **[judgment]** With a realistic 384–1536-dim float32 embedding (1.5–6 KB per entry), the embedding share would very likely clear 0.20, so "int8 not authorized" doesn't carry over to a real deployment. The repo's own `2f7aa5e` notes "int8 byte-ratio infeasibility at dim 8".
7. **The load ladder used fake providers.** Fake embedding and mock LLM (`synthetic_replay`), on a Windows laptop. PostgreSQL p95 ≈ 1 s at only a few thousand entries. **[judgment]** That fits brute-force search: migration 003 uses an untyped `vector` and there's no ANN index.
8. **Token savings are a word-count proxy.** `tokens_saved` sums `len(query.split()) + len(answer.split())` for each hit. It isn't measured tokens, and costs are zero.
9. **The held-out set is worn.** It was used by the WS5 final run, the first Phase 3 package and the protocol-reset rerun.
10. **Benchmark provenance.** 575 of 615 pairs are verbatim CacheEval (CC BY-SA 4.0) rows with mapped labels. No LICENSE or attribution is shipped.

**Bottom line [judgment].** The engineering and protocol discipline are strong, but none of the headline numbers measure semantic safe reuse. The honest current claim: "fail-closed rules achieve 0 false positives by abstaining; under hash embeddings, C's safe-reuse coverage equals exact match".

---

## 5. Code quality and engineering

**Strengths:**
- Frozen versioned contracts: safety, trace, serialization, statistics, freshness, gallery.
- Fail-closed everywhere, including the dashboard ("Malformed / missing required sources fail closed").
- Pre-registered gates; provenance (`git_commit`, config/manifest SHA-256) in every artifact; redaction checks.
- Large test suite, growing: 740 passed on CI at `c90b7ee` (with 4 failures); 766 passed, 15 skipped, 21 deselected locally on 11 Oct per `PHASE3_LOAD_EVIDENCE.md`.
- CI on `main` is green. Two jobs: `test` and `compose-config`.

**Notable defects and risks:**
- **Domain detection** is a substring test: "api" matches "capital", "code" matches "barcode". `general` is never emitted.
- **Strict unknowns:** any unknown intent, domain or format gives UNCERTAIN, so C abstains on 73% of dev and 61% of held-out.
- **Trace order bug:** `app.py` writes every Strategy C trace with `candidate_order=1`.
- **Exact hits under C** are re-validated by `evaluate_candidate`, so exact repeats with unknown metadata aren't served.
- **No vector index**, and the vector column has no fixed dimension.
- **Evaluation design gaps:** exact-cache FPR isn't computed, and false positives are attributed to the pair rather than the served candidate.
- **Defaults to fake providers:** `FakeEmbeddingClient` is the default in `evaluate.py`, `baseline.py` and the app outside production.
- **Process risk:** most work is done by an AI agent (Cursor co-authored commits, `.cursor/rules`). Evidence docs are very long and self-referential: the `WORKSTREAM_9_IMPLEMENTATION_PLAN.md` alone is 940 lines. **[judgment]** Reviewers may see this as process-heavy.
- **Git hygiene:** 9 unreviewed commits on `phase4/setup` with no CI; two stale branches; several artifacts generated on dirty trees.

---

## 6. Docs and repo hygiene

- **No root README and no LICENSE** on either branch; repo license is `None`. The documentation map is `docs/README.md`.
- **Stale docs:**
  - `docs/README.md` (both branches) still says `phase-3/ ← placeholder until PHASE3_PLAN.md exists`.
  - `SSCRE_PLAN.md` Phase 2 checklist is still unchecked for done work: ≥500 pairs, splits, Pareto, CIs, freshness, gallery, failure metrics, dashboard, dual-model.
  - On `phase4/setup`, Phase 3 boxes are now ticked, including "**Implement cross-encoder validator (D)**" and "Compare validator latency and safety improvement", although **no cross-encoder exists**. Misleading.
  - On `main`, `docs/phase-3/README.md` and `PHASE3_FINAL_EVIDENCE.md` are behind `phase4/setup`.
- **Branches:** `phase1/carryovers` and `phase2/phase3-plan` are stale and could be deleted. `phase4/setup` needs a PR.
- **Doc volume:** about 30 Phase 3 docs plus Phase 2 plans/audits. **[judgment]** Good as a lab notebook, but a reader needs a 1-page summary.

---

## 7. Scores

### In-scope (9 Oct weights: P1 25 / P2 55 / P3 20) [judgment rubric]

| Item | Max | 11 Oct claimed / adjusted | **12 Oct claimed** | **12 Oct adjusted** | Why |
|---|---|---|---|---|---|
| Phase 1 | 25 | 25 / 25 | 25 | 25 | — |
| WS1 contracts | 5 | 5 / 5 | 5 | 5 | — |
| WS2 benchmark | 8 | 8 / 7 | 8 | **6** | CacheEval-derived; context-stripped identical-text pairs labelled unsafe; no attribution |
| WS3 decision depth | 5 | 5 / 5 | 5 | 5 | — |
| WS4 provider | 6 | 6 / 3 | 6 | 3 | No live run |
| WS5 evaluation and statistics | 8 | 8 / 4 | 8 | 4 | Fake embeddings; A's FPR not computed |
| WS6 freshness | 5 | 5 / 4 | 5 | 4 | Dev-only for semi-dynamic/dynamic |
| WS7 gallery | 5 | 5 / 4 | 5 | 4 | — |
| WS8 ops | 5 | 5 / 4 | 5 | 4 | Bounded |
| WS9 dashboard / dual-model | 3 | 0 / 0 | **3** | **1.5** | Dashboard built; dual-model not run, gates open |
| Correctness labels | 5 | 0 / 0 | 0 | 0 | Open |
| **Phase 2** | 55 | 47 / 36 | **50** | **36.5** | |
| P3 hypotheses and registry | 3 | — | 3 | 3 | Strong |
| P3 F1 adaptive τ | 5 | — | 5 | 1.5 | One identical-text hit |
| P3 F2 eviction | 3 | — | 3 | 1.5 | Negative result on fake replay, cap 1 |
| P3 F3 D gate | 2 | — | 2 | 1 | Gate measured on non-semantic FPR |
| P3 final package | 3 | — | 3 | 2 | Clean tree (corrected), but zero cost, reset, worn held-out |
| P3 F4–F8 (cluster, track, storage, int8 gate, load) | 4 | — | 4 | 2 | All run on fake dim-8 providers; int8 gate not transferable |
| **Phase 3** | 20 | 20 / 10.5 | **20** | **11** | |
| **TOTAL /100** | 100 | 92 / ~72 | **95** | **≈72.5** | |

- **Movement since 11 Oct:** claimed +3 (WS9); adjusted +0.5 overall:
  - WS9 +1.5;
  - Phase 3 +0.5 (clean-tree correction plus the F4–F8 work);
  - offset by WS2 −1 (newly found identical-text, context-stripped pairs).
- **Phase 4, scored separately:** claimed ≈8/10, adjusted ≈5/10, unchanged.

### Out-of-scope (same 28 items, 0–4 levels, max 112) [judgment]
Changes since 11 Oct:
- #6 1K–100K load tests: 2→3 (ladder run; synthetic, `not_reached`).
- #9 failure clustering: 2→3 (manual, 3 clusters).
- #10 experiment tracking: 2→3 (audited; `keep_manual`).
- #4, #7 stay at 3. #5/#13 int8 stay at 2: gate decided "not authorized", no build.
- Strategy D (#2/#3/#12) stays at 2. The plan box being ticked doesn't count as a build.

**Score: 46/112 ≈ 41/100**, up from ≈38 on 11 Oct and ≈21 for the 9 Oct state on the same rubric.
- Still not touched: real embeddings, fresh external test, negation/number/date checks, LLM-judge/NLI, GPTCache baseline, adversarial/privacy, multilingual, session/multi-tenant/warming/prompt-cache.

---

## 8. Top next steps, in priority order [judgment]

1. **Real-embedding re-run, development first.** Use a local sentence-transformer (e.g. all-MiniLM-L6-v2, 384-dim) for B and C, behind a written protocol reset. Without this, there is no semantic claim.
2. **Fix the evaluation design before re-running.**
   - Compute exact-cache (A) FPR.
   - Judge hits against the served candidate's pair/answer, not the current record's label.
   - Decide how to handle context-stripped identical-text CacheEval pairs: drop them, or keep them as a "context needed" category.
   - Make the next evaluation use a fresh test split drawn from the unused CacheEval rows (about 1,330).
3. **Make Strategy C useful.** Pre-register extractor changes:
   - word-boundary domain terms;
   - don't treat unknown==unknown as UNCERTAIN when similarity is high;
   - negation, number, date and unit checks.

   Success means C has more safe coverage than A at FPR ≤ A.
4. **Merge `phase4/setup` via a PR with CI**, delete the stale branches, and fix misleading docs: the D checkbox, the `docs/README.md` placeholder line, and the Phase 2 checklist.
5. **Public-release hygiene:** a 1-page root README (problem, architecture, honest results table, how to run), a LICENSE, CacheEval CC BY-SA attribution, and `make paper-results`.
6. **One small live-provider run**, plus a pgvector HNSW index on fixed-dim real embeddings. That gives real token/₹ savings and redoes the int8 and load gates at a realistic dimension.
7. **About 100 human correctness labels**, then a workshop-paper draft built from `/workspace/sscre_lit_review.md` plus steps 1–3.

---

## 9. Readiness [judgment]

**Recruiters (private repo shared on request): ready-ish, about 6.5/10.**
- **Strong signal:** a FastAPI/Postgres/pgvector service, fail-closed design, 700+ tests, CI, typed contracts, reproducibility discipline.
- **Risks:**
  - No README or LICENSE on the landing page.
  - The doc sprawl and AI-agent co-authorship are visible.
  - "0% false positives" and "Feature 1 passed" won't survive a technical interviewer. Phrase results as "safety-first: abstains rather than mis-serves; semantic evaluation in progress".
- **Must-fix before sharing:** steps 4–5.

**Public release: not ready, about 4/10.** Needs a license and attribution (CC BY-SA ShareAlike implications for the benchmark), a README, merged branches and honest framing.

**Paper: not ready, about 2.5/10.**
- There is no draft (only the 3,287-word literature review on the box) and no semantic results.
- The main comparison shows C ≈ A on safe reuse, and the held-out set is worn.
- Minimum to reach a workshop paper:
  - steps 1–3;
  - one live-provider cost slice;
  - a fresh test set;
  - correctness labels on a subset;
  - a GPTCache-style baseline.
- **[judgment]** About 2–4 focused weeks.

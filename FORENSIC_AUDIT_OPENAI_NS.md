# Forensic Axiomatic Audit — `openai/NavierStokesAndEuler`

**Date:** 2026-09-30
**Auditor:** OpenCode / Oracle session, on the architect's instruction ("Nol Toleransi
Terhadap Pembuktian Melingkar" / anti-circularity protocol).
**Corpus audited:**
- `NavierStokesAndEuler-openai/` — plain snapshot of the target repository dated
  2026-09-10 (2,659 `.lean` files), and
- a fresh shallow clone of `github.com/openai/NavierStokesAndEuler` at commit
  `f9e8bc5` (2026-09-30).

Content diff (SHA-256 after CRLF→LF normalization): **0 of 2,669 files differ** —
the two copies are byte-identical modulo line endings (641,895 lines; delta =
exactly the CRLF count), so every number below applies to both.

**Tools actually executed:**
1. `gate.py lean` (anti-circularity skill, `C:\Users\usER\.config\opencode\skills\anti-circularity\scripts\gate.py`) — placeholder scan that ignores comments.
2. A custom comment-aware Python scanner (nested `/- -/` + `--` stripping, declaration regex with modifier/unicode coverage) over all `.lean` files.

This note records **static** evidence. It is not a kernel check of OpenAI's proofs
(see §5, Limitations). No number here was typed by hand; all are reproduced tool output.

---

## 1. Raw counts (Target 1–3 + trust flags)

Corpus: **2,659 `.lean` files, 643,991 lines, 33,721,830 bytes** (normalized).

### Target 1 — `sorry` / placeholder gaps

| Metric | Count | Location |
|---|---|---|
| `sorry` raw (incl. comments) | 5 | 2 files |
| `sorry` code-level (comments stripped) | 4 | 2 files |
| literal `sorryAx` in sources | 0 | — |
| `sorry` in proof libs `NavierStokes/`, `Euler/` | **0** | — |

Exact hits, independently reproduced by **both** tools (gate exit 1, FAIL=4; scanner
code-level = 4, same lines):

| File:line | Context |
|---|---|
| `ComparatorChallenges/Euler.lean:88` | challenge statement (Euler, unforced) |
| `ComparatorChallenges/Euler.lean:184` | challenge statement |
| `ComparatorChallenges/NavierStokes.lean:277` | challenge **(C)** breakdown on ℝ³ |
| `ComparatorChallenges/NavierStokes.lean:284` | challenge **(D)** breakdown on ℝ³/ℤ³ |

These four are **intentional challenge placeholders by design**, documented in the
file itself (`ComparatorChallenges/NavierStokes.lean:25-31`): the file is a standalone
copy of `google-deepmind/formal-conjectures/.../Millenium/NavierStokes.lean`, "including
their intentional `sorry` challenge placeholders". The comment at line 29 accounts for
the fifth (raw-only) hit. **Claim reconciliation:** the repository commit message
`a0e878c` ("4 barriers locked, 0 sorry, 0 axiom") is true for the proof libraries
`NavierStokes/` and `Euler/`, and false for the whole repository including the default
target `ComparatorChallenges` (declared in `lakefile.toml` `defaultTargets`).

### Target 2 — custom axioms ("cheat codes")

| Kind | Count |
|---|---|
| `axiom` declarations | **0** (raw keyword occurrences in code: 0) |
| `opaque` declarations | **0** |
| `constant` declarations (top-level assumptions) | **0** |
| `native_decide` | **0** |
| `unsafe` | **0** |
| `theorem … : False` | **0** |

18 regex candidates for `constant` were each inspected at its exact line and are all
**false positives**: structure fields (`constant : ℝ` inside `structure SupportedPolynomial … where`,
`GenericSupportedPolynomial.lean:172-174`), `where`-instance values (`constant := 1`,
`power := ActualPrimary.h`), and continuation lines of `have`/arithmetic expressions.
The identifier `constant` is a *definition of their own* — 7 `def constant` sites exist
(e.g. `GlobalSlowProfiles.lean:94 noncomputable def constant (S : Set ℝ) (c : ℝ) …`).

### Target 3 — domain & physics-boundary keywords

| Keyword family | Count | Reading |
|---|---|---|
| literal `1D` / `2D` | **0** | no dimension-truncated claims |
| `dimension` (word, incl. "one-/two-/three-dimensional") | 45 | prose/docs, incl. statements of *generality* |
| `Fin 3` | 4,161 | spatial index (the dimension that matters) |
| `Fin 1` / `Fin 2` | 33 / 1,808 | tensor/index sets, sample: `fun _ : Fin 2 => i` — not spatial dimension |
| `Fin 4` | 1,812 | index sets (same reading) |
| `ℝ²` | 6 | auxiliary (r,t)-plane in documentation, e.g. `GraphCalculus.lean:9` |
| `torus`/`periodic`/`cube` | 2,369 | the legitimate periodic domain of alternative (D) |
| `forcing`/`forced` | 862 | see §2 — forcing is *declared*, not hidden |
| `bounded domain`/`unit ball`/`halfspace` | 14 | local auxiliary constructions |
| `#print axioms` self-invocations | 4 (2 files) | they self-check `Euler/Solution.lean`, `NavierStokes/ComparatorSolution.lean:31-32` |

**No domain manipulation anomaly found.** The 3D whole-space and periodic-torus
settings are stated openly; no theorem is scoped to a truncated dimension.

---

## 2. Theorem scope: the formalized Navier–Stokes result is FORCED

The scope is stated identically by the repository, the paper metadata, and the Lean
statements — there is no hidden quantifier change:

- `README.md:13-18` — "For every positive viscosity, we prove two results:
  **Whole space ℝ³:** There exist smooth initial data **and forcing** for which no
  global smooth solution … exists. **Periodic torus ℝ³/ℤ³:** There exist smooth
  periodic initial data **and forcing** …"
- `formalization.yaml` — "formalizes finite-time blowup … **with smooth forcing**,
  for every positive viscosity, on Euclidean space and the periodic torus."
- `NavierStokes/ComparatorSolution.lean:16-19` (submission for alternative **(C)**):

  ```lean
  theorem navier_stokes_breakdown_R3 (nu : ℝ) (hnu : nu > 0) :
      ∃ (u₀ : ℝ³ → ℝ³) (f : ℝ³ → ℝ → ℝ³),
      InitialVelocityConditionDecay u₀ ∧ ForceConditionDecay f ∧
      ¬ (∃ v p, NavierStokesExistenceAndSmoothnessRn nu u₀ f v p)
  ```

  (analogously `:23-26` for the periodic alternative **(D)**).

- `NavierStokes/R3/ProblemStatement.lean:150-153` — the core target proposition:

  ```lean
  def breakdownStatement : Prop :=
    ∀ ν : ℝ, 0 < ν →
      ∃ u : VelocityField, ∃ p : PressureField, ∃ f : VelocityField, ∃ K : Set Space,
        CandidateProperties ν u p f K ∧ ¬ Nonempty (GlobalFiniteEnergySolution ν f)
  ```

  with the in-source docstring (:146-149): "a candidate whose **same prescribed force
  and zero datum** have no global smooth solution with uniformly bounded kinetic
  energy".

**Conclusion of the audit:** at the theorem level the formalization is *honest about
being forced* — every quantifier in the sources matches the README/yaml description,
and the audit found no axiom, placeholder, or domain trick behind that statement.

---

## 3. The unforced problem (`f = 0`) remains fully open

Nothing in the 2,659 files proves, claims, or implies global regularity (or its
failure) for the homogeneous equation. Evidence from the repository itself:

1. **The repo formalizes that zero force is solvable.**
   `NavierStokes/R3/ProblemStatement.lean:187-190`:

   ```lean
   /-- Zero velocity and pressure solve the equation for zero force at any
   viscosity. This checks that the competing-solution class is inhabited. -/
   theorem zero_force_has_global_solution (ν : ℝ) :
       Nonempty (GlobalFiniteEnergySolution ν (fun _ => 0))
   ```

2. **Breakdown forces the forcing to be nonzero.**
   `NavierStokes/R3/CandidateBreakdown.lean:51-56`:

   ```lean
   /-- A force in the paper's support class which excludes a global solution
   must be nonzero at some positive time. -/
   theorem force_nonzero_of_no_global_solution {ν : ℝ} {f : VelocityField}
       (hf : CompactPositiveTimeSupport f)
       (h : ¬ Nonempty (GlobalFiniteEnergySolution ν f)) :
       ∃ t : ℝ, 0 < t ∧ ∃ x : Space, f (t, x) ≠ 0
   ```

3. **No `f = 0` Navier–Stokes theorem exists in the corpus.** A full-text search for
   `f = 0 | unforced | zero_forcing` returns 36 matches. Inside `NavierStokes/` they
   are incidental identities (`… = 0`) plus one docstring about a *constructed object*
   solving the unforced equations (`BaseExterior.lean:146`); **no theorem asserts
   global existence, uniqueness, regularity, or blowup for `f = 0` Navier–Stokes**.
   The only *unforced* results proved are Euler's — `Euler/Solution.lean:10`
   ("the independent solution to the **unforced** Euler Comparator challenge") and
   `Euler/SolutionDefinitions.lean:63`.

4. The *challenge* statements for alternatives (C)/(D) themselves remain unproved in
   this repository (`sorry`, §1) — they are checking targets, not derived theorems.

Therefore: **the classical unforced Cauchy problem — smooth `u₀`, `f ≡ 0`, does a
unique smooth solution exist for all time on ℝ³ — is untouched by this repository and
remains an open Clay Millennium Prize Problem.** The forced blowup theorem (§2) does
not settle it: with `f ≡ 0` the equation class contains the trivial global solution
witness of item 1, and the `∃ f` quantifier of item 2's counterpart
(`ComparatorSolution.lean:17`) is exactly what the audit confirms is *not* `f = 0`.

---

## 4. What was machine-verified in this audit (and by which tool)

| Claim | Tool | Result |
|---|---|---|
| 4 code `sorry`, same lines, no others | `gate.py lean` **and** scanner | exit 1 / FAIL=4 — independent agreement |
| 0 `axiom`/`opaque`/`constant` decls, 0 `native_decide`, 0 `unsafe` | scanner (comment-aware, modifier-covered) | 0 / 0 / 0 |
| No dimension-truncated theorem | scanner keyword pass (§1, Target 3) | literal `1D`/`2D` = 0 |
| Both audited copies are content-identical | SHA-256 after CRLF→LF normalization | 0 / 2,669 files differ |
| Our own certificate for this project (context) | `lean` 4.33.1 + `#print axioms` + `gate.py lean` | exit 0; axioms = `[propext, Classical.choice, Quot.sound]` only; gate PASS |

## 5. Limitations (read before citing this note)

- **No dynamic check of OpenAI's proofs was run.** `lake build` + `#print axioms` on
  their theorems requires Lean `v4.34.0-rc2` (not installed on the auditing machine;
  only `v4.33.1`) and Mathlib at rev `85e3a25e…` (absent from disk; no
  `.lake/packages` in either copy). The repository self-invokes `#print axioms` on its
  two comparator submissions (`NavierStokes/ComparatorSolution.lean:31-32`) but does
  not store the output in-tree. Per project policy ("heavy installs wait for the
  dedicated server"), this step is deferred.
- Static scanning decides *what is written*, not *whether the proofs are correct*.
  The Lean kernel remains the only authority; a `PASS` of the anti-circularity gate
  means "the checks ran and found nothing", nothing more.
- This note makes **no claim about blowup or regularity of Navier–Stokes from
  numerical data**; the finite-window numerics of this project are recorded separately
  and are explicitly not proofs.

## 6. Reproduction

```sh
# placeholder scan (exit 1 expected on the target repo: 4 challenge sorries)
python C:/Users/usER/.config/opencode/skills/anti-circularity/scripts/gate.py lean <repo-root>

# full scanner: see session log / Temp/opencode/scan_openai_ns.py
#   (comment-stripping pass + declaration regex + keyword buckets)
```

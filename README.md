# Navier-Stokes Formalization — Verified Certificates, Numerics & Forensic Audit

Artifacts of an independent verification effort on the **3D incompressible Navier–Stokes
equations** (Clay Millennium Prize Problem): machine-checked certificates, pseudo-spectral
numerical probes, and a forensic audit of a public formalization corpus.

## Status — honest by design

- **The problem itself is OPEN.** Nothing in this repository proves or disproves global
  regularity or finite-time blowup for 3D Navier–Stokes. Numerical results are float64
  *evidence over a finite time window*, never proofs.
- Anti-circularity discipline: no `.lean` file here concludes singularity or global
  regularity; every "machine-checked" claim passes the anti-circularity `gate.py`
  (placeholder scan, comment-only-claim detection, SMT-LIB2 circularity audit) first.
- The **unforced** case `f = 0` — the exact Clay statement — remains fully open.

## Machine-checked artifacts (re-executed 2026-09-30)

| Artifact | Method | Result |
|---|---|---|
| `strain_certificate.lean` | Lean 4.33.1, core library only | compile **exit 0**; `#print axioms` on its 7 theorems → `[propext, Classical.choice, Quot.sound]` only; `gate.py lean` → **PASS** (FAIL=0) |
| `arb_certificate.py` → `arb_certificate.json` | python-flint ball arithmetic, prec=256 | **OVERALL PASS**: float64 ↔ arb agreement to 1e-12, `λmax(S) > 0` by directed Rayleigh, `trace(S)` contains 0 (incompressible point), `ωᵀSω > 0` |
| `z3_tribunal/ns_batch1..4.py` | Z3 SMT, 4 batches | re-run 2026-09-30: **4/4 UNSAT** — within their encoded bounds (sanity checks of the encoded inequalities, *not* a regularity proof) |

Known limitations (stated, not hidden):

- `lean4_kernel/NavierStokesCore.lean`: static gate **PASS** (0 code-level `sorry`), but
  it **does not compile** under Lean 4.33.1 as-is (auto-bound `Real` errors) → this
  component is **not compile-verified** on this machine.
- `legacy_archive/NavierStokesRegularity.lean` contains an `axiom` + `sorry` (archived
  draft kept for provenance only) → any repo-wide gate FAIL originates solely from it.
- Viscosity enters `NavierStokesCore.lean` as an explicit parameter
  (`constant viscosity (ν : Real) (hν : ν > 0)`), i.e. a given of the problem.

## Forensic audit: `openai/NavierStokesAndEuler` (2026-09-30)

Static scan of all **2,659 `.lean` files / 643,991 lines** (note: `FORENSIC_AUDIT_OPENAI_NS.md`):

- **4 code-level `sorry`**, all inside `ComparatorChallenges/` (intentional challenge
  placeholders, DeepMind FormalConjectures style); **0 in the proof libraries**.
- **0 `axiom`**, 0 real `constant` declarations, 0 `native_decide`, 0 `unsafe`.
- No dimensional sleight-of-hand: `Fin 3` is spatial (4,161 uses) while `Fin 1/2/4` are
  index sets; torus/periodic scope and forcing are openly declared (862 forcing mentions).
- Their breakdown theorems quantify **∃ f ≠ 0** (forced NS, with `ForceConditionDecay f`);
  the repo proves `zero_force_has_global_solution` and
  `force_nonzero_of_no_global_solution` → the **unforced** case `f = 0` is untouched and
  stays open.

The external corpus itself is **not vendored** (`.gitignore` quarantine); the working
machine keeps only a plain local snapshot.

## Numerical probes — pseudo-spectral, N=64, periodic T³, ν = 1e-4, RK4 + 2/3 dealias, single-thread

| Initial data | Files | E₀ → E(6) | ‖ω‖∞ trajectory | BKM ∫₀⁶ ‖ω‖∞ dt |
|---|---|---|---|---|
| Kida–Pelz vortex | `phase1_kida_n64.json`, `u0_kida_n64.npy` | 0.750 → 0.562 | 8.0 → 49.6 (peak 73.3 @ t ≈ 5.85) | **222.903** |
| Anti-parallel tubes | `phase1_tubes_n64.json`, `u0_tubes_n64.npy` | 0.01263 → 0.01251 | 4.54 → 5.14 | **26.326** |
| **Trefoil-knot vortex tube** — unforced `f = 0`, incompressible by spectral construction (`div = 2.8e-14`, `curl u = ω` to `2.8e-14`), E₀ = 0.75 = Kida baseline | `phase1_trefoil_n64.json`, `u0_trefoil_n64.npy`, generator `topology_hunter.py` | 0.750 → 0.645 | 17.9 → 65.7 (peak 94.4 @ t ≈ 3.14; trigger 109.92 not reached) | **356.759** |

The knotted initial data drives the hardest vorticity growth of the three: its BKM
integral is ≈ 1.60 × the Kida run at identical E₀ (356.759 vs 222.903), yet the
integrand stayed bounded (peak 94.4 < trigger 109.92) and the run completed in
5,283 s. All reported values are finite → **no blowup observed inside the simulated
window**, which does *not* exclude blowup at any later time. Energy decay is
consistent with ν > 0 dissipation in every run.

## Repository structure

```
navier-stokes-formalization/
├── strain_certificate.lean        # Lean 4 core-only certificate (compile 0, gate PASS)
├── arb_certificate.py / .json     # ball-arithmetic certificate (OVERALL PASS, prec=256)
├── phase1_u0.py                   # u0 builders (kida/tubes) + diagnostics + NS integrator
├── topology_hunter.py             # trefoil-knot u0 generator + BKM-triggered integration
├── phase1_kida_n64.json           # probe results + honesty flags
├── phase1_tubes_n64.json
├── phase1_trefoil_n64.json
├── u0_kida_n64.npy                # initial-condition matrices (N,N,N,3) float64
├── u0_tubes_n64.npy
├── u0_trefoil_n64.npy
├── NAVIER_STOKES_SINGULARITY.json # project record (+ _SPECS.md extracted prose)
├── z3_tribunal/                   # 4 SMT sanity-check batches (4/4 UNSAT)
├── lean4_kernel/                  # static gate PASS; compile issue documented above
├── exports/                       # LaTeX manuscript + verification telemetry
├── FORENSIC_AUDIT_OPENAI_NS.md    # audit note (forced vs unforced frontier)
├── PROTOCOL_ALIGNMENT_REPORT.md   # end-to-end protocol / evidence map
├── CONSOLIDATION_REPORT.md        # audit & integrity lock matrix (log)
└── legacy_archive/                # provenance only — NOT part of any claim
```

## Reproduce

```bash
python arb_certificate.py                        # ball-arithmetic certificate (PASS)
python phase1_u0.py --ic kida --no-run           # build u0 + t=0 diagnostics only
python phase1_u0.py --ic kida                    # + integrate t in [0,6], BKM monitor
python topology_hunter.py --sigma 0.24 --no-run  # trefoil u0 + t=0 diagnostics
python z3_tribunal/ns_batch1_energy.py           # ...then ns_batch2..4
lean strain_certificate.lean                     # core-only compile (exit 0)
python <anti-circularity-skill>/scripts/gate.py lean strain_certificate.lean
```

Single-threaded by design (`OMP_NUM_THREADS=1`): a long-running build shares the machine.

## Citation

```bibtex
@misc{amry2026navierstokes,
  title={Formal Verification Pipeline for 3D Incompressible Navier-Stokes Global Regularity via Spectral Rigidity and Entropy-Energy Coupling},
  author={Amry, Muhammad Aidil},
  year={2026},
  note={Lean 4 + Z3 SMT formal methods, Opsi A/B Regularity Framework, ORCID: 0009-0002-9718-9710}
}
```

## Contact

- **Author**: Muhammad Aidil Amry (Sang Arsitek)
- **ORCID**: [0009-0002-9718-9710](https://orcid.org/0009-0002-9718-9710)
- **Repository**: https://github.com/aidilamrym-ops/navier-stokes-formalization
- **Zenodo DOI**: 10.5281/zenodo.22855514

---

*Architect: Muhammad Aidil Amry*

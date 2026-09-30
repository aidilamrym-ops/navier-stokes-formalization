/-!
# VECTOR_3 Strain Certificate (standalone Lean 4.33.1, core library only)

Provenance: part of the VECTOR_3 (Navier-Stokes Singularity Hunter) audit,
folder `HR/navier-stokes-formalization`.

## What this file certifies

Structural algebraic facts about the strain tensor
`S = sym(grad u)` and the antisymmetric part `A = skew(grad u)` of a velocity
gradient `g : Fin 3 -> Fin 3 -> Rat` (`g i j = du_i/dx_j`):

1. `strain_symmetric` / `strain2_symmetric` -- S is symmetric, definitionally.
2. `strain_transpose` / `strain2_transpose` -- symmetrization is invariant
   under transposing the gradient.
3. `skw2_antisym` -- the skew part is antisymmetric: `A j i = - A i j`.
4. `skw2_diag` -- its diagonal vanishes.
5. `skw2_pair_cancel` -- for any vector `w`, the pairwise contribution of the
   skew part to the quadratic form cancels:
   `w_i A_ij w_j + w_j A_ji w_i = 0`.
   This is the algebraic core of the identity `w^T (grad u) w = w^T S w`:
   only the symmetric strain can stretch vorticity.

Everything is stated over `Rat` (exact rational arithmetic).  Standalone Lean
4 has no `Real` type, so no analytic inequalities live here.

## Scope boundary (honesty contract)

* Numeric positivity bounds for the Kida-Pelz initial condition
  (`lambda_max(S) > 0`, `omega^T S omega > 0`) are certified separately by
  ball arithmetic in `vector3_arb_certificate.json` (python-flint, directed
  rounding).  They are NOT restated or assumed here.
* This file contains no placeholders and adds no extra assumptions: every
  theorem is proved from the Lean core library alone.
* Finite-time blowup of Navier-Stokes is NOT claimed anywhere in this file
  (it is a Millennium-open problem).
-/

namespace Vector3

/-- Symmetrized gradient, division-free: `2 * S_ij = du_i/dx_j + du_j/dx_i`. -/
def strain2 (g : Fin 3 → Fin 3 → Rat) (i j : Fin 3) : Rat := g i j + g j i

/-- The strain tensor proper: `S_ij = (du_i/dx_j + du_j/dx_i) / 2`. -/
def strain (g : Fin 3 → Fin 3 → Rat) (i j : Fin 3) : Rat :=
  (g i j + g j i) / 2

/-- Skew part of the gradient, division-free: `2 * A_ij = du_i/dx_j - du_j/dx_i`. -/
def skw2 (g : Fin 3 → Fin 3 → Rat) (i j : Fin 3) : Rat := g i j - g j i

-- ---------------------------------------------------------------- symmetry

theorem strain2_symmetric (g : Fin 3 → Fin 3 → Rat) (i j : Fin 3) :
    strain2 g i j = strain2 g j i := by
  unfold strain2
  rw [Rat.add_comm]

theorem strain_symmetric (g : Fin 3 → Fin 3 → Rat) (i j : Fin 3) :
    strain g i j = strain g j i := by
  unfold strain
  rw [Rat.add_comm]

theorem strain2_transpose (g : Fin 3 → Fin 3 → Rat) (i j : Fin 3) :
    strain2 g i j = strain2 (fun a b => g b a) i j := by
  unfold strain2
  rw [Rat.add_comm]

theorem strain_transpose (g : Fin 3 → Fin 3 → Rat) (i j : Fin 3) :
    strain g i j = strain (fun a b => g b a) i j := by
  unfold strain
  rw [Rat.add_comm]

-- ------------------------------------------------------------ antisymmetry

theorem skw2_antisym (g : Fin 3 → Fin 3 → Rat) (i j : Fin 3) :
    skw2 g i j = -(skw2 g j i) := by
  unfold skw2
  simp [Rat.sub_eq_add_neg, Rat.neg_add, Rat.neg_neg, Rat.add_comm]

theorem skw2_diag (g : Fin 3 → Fin 3 → Rat) (i : Fin 3) : skw2 g i i = 0 := by
  unfold skw2
  simp [Rat.sub_self]

/-- Pairwise cancellation of the skew part inside any quadratic form
`w^T M w`: `w_i * A_ij * w_j + w_j * A_ji * w_i = 0` when `A` is the skew
part of a gradient.  Consequently the skew (vorticity) part of the gradient
cannot contribute to `w^T (grad u) w`; only the symmetric strain remains. -/
theorem skw2_pair_cancel (g : Fin 3 → Fin 3 → Rat) (w : Fin 3 → Rat)
    (i j : Fin 3) :
    w i * skw2 g i j * w j + w j * skw2 g j i * w i = 0 := by
  have hanti : skw2 g j i = -(skw2 g i j) := skw2_antisym g j i
  rw [hanti, Rat.mul_neg, Rat.neg_mul]
  -- goal: w i * S * w j + -(w j * S * w i) = 0  with S = skw2 g i j
  have hswap : w j * skw2 g i j * w i = w i * skw2 g i j * w j := by
    rw [Rat.mul_comm (w j * skw2 g i j) (w i)]
    -- goal: w i * (w j * S) = (w i * S) * w j
    rw [Rat.mul_comm (w j) (skw2 g i j)]
    -- goal: w i * (S * w j) = (w i * S) * w j
    rw [← Rat.mul_assoc (w i) (skw2 g i j) (w j)]
  rw [hswap, Rat.add_neg_cancel]

end Vector3

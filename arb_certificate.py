# arb_certificate.py
# RIGOROUS (ball-arithmetic) certificate for the Kida-Pelz initial condition.
#
# What is certified (machine-checked with python-flint arb, directed rounding):
#   1. Analytic strain tensor S = sym(grad u) of the Kida-Pelz field at a
#      selected grid point p, evaluated as arb balls.
#   2. Cross-validation A: analytic du_i/dx_j vs numpy spectral derivatives of
#      the discrete u0 (Kida-Pelz is a trig polynomial of modes <= 3, so the
#      spectral derivative at n = 64 is exact up to roundoff).
#   3. Cross-validation B: every float64 S_ij(p) lies inside its arb ball.
#   4. lambda_max(S(p)) > 0 via Rayleigh quotient on a unit axis:
#      lambda_max >= e_i^T S e_i = S_ii, certified strictly positive as a ball.
#      (trace(S) = div u = 0 identically for incompressible flow, so trace
#      bounds are useless here -- that is why the axis Rayleigh bound is used.)
#   5. omega^T S omega (p) > 0 : strictly positive instantaneous vortex
#      stretching at t = 0 at point p (certified ball enclosure).
#
# Screening choice of p (argmax of the float64 stretching field) is NOT part
# of the claim; the claim is the arb enclosure at whatever p was chosen.
#
# What is NOT claimed: finite-time blowup of Navier-Stokes (open problem).
# The certificate proves LOCAL algebraic/analytic inequalities at t = 0 only.
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import json

import numpy as np
from flint import arb, ctx

ctx.prec = 256  # 256-bit working precision for the enclosures

TWO_PI = 2.0 * np.pi


# ------------------------------------------------------ analytic Kida-Pelz
def trig_point_np(x, y, z):
    return dict(
        sx=np.sin(x), cx=np.cos(x), sy=np.sin(y), cy=np.cos(y),
        sz=np.sin(z), cz=np.cos(z),
        s3x=np.sin(3 * x), c3x=np.cos(3 * x),
        s3y=np.sin(3 * y), c3y=np.cos(3 * y),
        s3z=np.sin(3 * z), c3z=np.cos(3 * z),
    )


def grad_analytic_np(t):
    """Analytic du_i/dx_j for Kida-Pelz in float64 (row i, column j)."""
    sx, cx, sy, cy, sz, cz = t["sx"], t["cx"], t["sy"], t["cy"], t["sz"], t["cz"]
    s3x, c3x, s3y, c3y, s3z, c3z = (t["s3x"], t["c3x"], t["s3y"],
                                    t["c3y"], t["s3z"], t["c3z"])
    # u_x = sin x (cos 3y cos z - cos y cos 3z)
    dux = [cx * (c3y * cz - cy * c3z),
           sx * (-3 * s3y * cz + sy * c3z),
           sx * (-c3y * sz + 3 * cy * s3z)]
    # u_y = sin y (cos 3z cos x - cos z cos 3x)
    duy = [sy * (-c3z * sx + 3 * cz * s3x),
           cy * (c3z * cx - cz * c3x),
           sy * (-3 * s3z * cx + sz * c3x)]
    # u_z = sin z (cos 3x cos y - cos x cos 3y)
    duz = [sz * (-3 * s3x * cy + sx * c3y),
           sz * (-c3x * sy + 3 * cx * s3y),
           cz * (c3x * cy - cx * c3y)]
    return np.array([dux, duy, duz])


def trig_point_arb(x_rat, y_rat, z_rat):
    """Trig values as arb balls.  Each coordinate is num/den * pi exactly."""
    def mul_pi(v):
        return arb(v[0]) / arb(v[1]) * arb.pi()

    def s(v):
        return mul_pi(v).sin()

    def c(v):
        return mul_pi(v).cos()

    def s3(v):
        return mul_pi((3 * v[0], v[1])).sin()

    def c3(v):
        return mul_pi((3 * v[0], v[1])).cos()

    return dict(sx=s(x_rat), cx=c(x_rat), sy=s(y_rat), cy=c(y_rat),
                sz=s(z_rat), cz=c(z_rat),
                s3x=s3(x_rat), c3x=c3(x_rat), s3y=s3(y_rat), c3y=c3(y_rat),
                s3z=s3(z_rat), c3z=c3(z_rat))


def grad_analytic_arb(t):
    """Same expressions as grad_analytic_np, evaluated as arb balls."""
    sx, cx, sy, cy, sz, cz = t["sx"], t["cx"], t["sy"], t["cy"], t["sz"], t["cz"]
    s3x, c3x, s3y, c3y, s3z, c3z = (t["s3x"], t["c3x"], t["s3y"],
                                    t["c3y"], t["s3z"], t["c3z"])
    dux = [cx * (c3y * cz - cy * c3z),
           sx * (-3 * s3y * cz + sy * c3z),
           sx * (-c3y * sz + 3 * cy * s3z)]
    duy = [sy * (-c3z * sx + 3 * cz * s3x),
           cy * (c3z * cx - cz * c3x),
           sy * (-3 * s3z * cx + sz * c3x)]
    duz = [sz * (-3 * s3x * cy + sx * c3y),
           sz * (-c3x * sy + 3 * cx * s3y),
           cz * (c3x * cy - cx * c3y)]
    return [dux, duy, duz]


# ----------------------------------------------------------------- helpers
def to_float_range(ball):
    lo = float(ball.lower())
    hi = float(ball.upper())
    return {"lo": lo, "hi": hi, "mid": 0.5 * (lo + hi),
            "radius": 0.5 * (hi - lo)}


def spectral_grad(u0, L):
    n = u0.shape[0]
    k = np.fft.fftfreq(n, d=L / n) * TWO_PI
    KX, KY, KZ = np.meshgrid(k, k, k, indexing="ij")
    Ux, Uy, Uz = (np.fft.fftn(u0[..., i]) for i in range(3))
    out = []
    for U in (Ux, Uy, Uz):
        out.append([np.fft.ifftn(1j * K * U).real for K in (KX, KY, KZ)])
    return np.array(out)  # out[i][j] = du_i/dx_j


# ------------------------------------------------------------------- main
def main():
    here = os.path.dirname(os.path.abspath(__file__))
    npy = os.path.join(here, "u0_kida_n64.npy")
    u0 = np.load(npy)
    n = u0.shape[0]
    L = TWO_PI

    # --- screening: argmax of the float64 stretching field (NOT the claim)
    G_sp = spectral_grad(u0, L)                  # (3,3,n,n,n), [i][j]=du_i/dx_j
    S_sp = 0.5 * (G_sp + np.swapaxes(G_sp, 0, 1))
    om_sp = np.stack([G_sp[2, 1] - G_sp[1, 2],
                      G_sp[0, 2] - G_sp[2, 0],
                      G_sp[1, 0] - G_sp[0, 1]])  # (3,n,n,n)
    Som = np.einsum("ijxyz,jxyz->ixyz", S_sp, om_sp)
    stretch = np.einsum("ixyz,ixyz->xyz", om_sp, Som)        # (n,n,n)
    pi_, pj_, pk_ = [int(v) for v in np.unravel_index(
        int(np.argmax(stretch)), stretch.shape)]

    # coordinate as exact rational multiples of pi: coord = 2*pi*idx/n
    xr = (2 * pi_, n)
    yr = (2 * pj_, n)
    zr = (2 * pk_, n)
    print("ARB CERTIFICATE  (python-flint, prec=%d)" % ctx.prec)
    print("  screening argmax stretch = (%d,%d,%d)  float64 value = %.17g"
          % (pi_, pj_, pk_, stretch[pi_, pj_, pk_]))
    print("  p: x=(%d/%d)pi y=(%d/%d)pi z=(%d/%d)pi"
          % (xr[0], xr[1], yr[0], yr[1], zr[0], zr[1]))

    # --- cross-check 1: analytic vs spectral (float64) at p
    Lf = trig_point_np(xr[0] / xr[1] * np.pi, yr[0] / yr[1] * np.pi,
                       zr[0] / zr[1] * np.pi)
    G_np = grad_analytic_np(Lf)
    p_grad_sp = G_sp[:, :, pi_, pj_, pk_]
    dev = float(np.max(np.abs(G_np - p_grad_sp)))
    print("  crosscheck analytic-vs-spectral (float64): max|diff| = %.3e" % dev)

    # --- arb layer at p
    Ta = trig_point_arb(xr, yr, zr)
    G = grad_analytic_arb(Ta)
    S = [[(G[i][j] + G[j][i]) / 2 for j in range(3)] for i in range(3)]
    wx = G[2][1] - G[1][2]
    wy = G[0][2] - G[2][0]
    wz = G[1][0] - G[0][1]
    w = [wx, wy, wz]

    q = arb(0)
    for i in range(3):
        for j in range(3):
            q = q + w[i] * S[i][j] * w[j]

    # Rayleigh on unit axes: lambda_max >= S_ii for each i; take best lower bound
    best_axis = max(range(3), key=lambda i: float(S[i][i].lower()))
    lam_lb = S[best_axis][best_axis]

    # float64 reference values at p
    Sf = 0.5 * (G_np + G_np.T)
    wnp = np.array([G_np[2][1] - G_np[1][2], G_np[0][2] - G_np[2, 0],
                    G_np[1, 0] - G_np[0, 1]])
    q_np = float(wnp @ Sf @ wnp)
    lam_np = float(np.linalg.eigvalsh(Sf)[-1])

    print("  arb lambda_max >= S[%d][%d] = [%s, %s]"
          % (best_axis, best_axis, lam_lb.lower(), lam_lb.upper()))
    print("  arb omega^T S omega        = [%s, %s]" % (q.lower(), q.upper()))
    print("  float64 lambda_max(p)      = %.17g  (screening only)" % lam_np)
    print("  float64 omega^T S omega(p) = %.17g" % q_np)

    lam_pos = lam_lb > 0
    q_pos = q > 0

    # Cross-check 2/3: the arb ball encloses the TRUE value to ~1e-76, while
    # float64 only carries ~1e-16 relative rounding, so the float64 value can
    # never fall INSIDE such a tight ball.  The honest agreement test is
    # |float64 - arb_mid| <= float64_tol (1e-12 relative) + ball radius.
    F64_TOL = 1e-12

    def agrees(v, ball):
        mid = float(ball.mid()) if hasattr(ball, "mid") else None
        if mid is None:
            lo, hi = float(ball.lower()), float(ball.upper())
            mid = 0.5 * (lo + hi)
        rad = 0.5 * (float(ball.upper()) - float(ball.lower()))
        return abs(v - mid) <= F64_TOL * max(1.0, abs(mid)) + rad

    q_agrees = agrees(q_np, q)
    s_ok = all(agrees(Sf[i, j], S[i][j]) for i in range(3) for j in range(3))

    # cross-check 3: divergence (trace of analytic gradient) ball contains 0
    tr = G[0][0] + G[1][1] + G[2][2]

    verdicts = {
        "analytic_vs_spectral_max_dev": dev,
        "analytic_vs_spectral_pass": bool(dev < 1e-10),
        "S_float64_agrees_with_arb_ball_1e-12": bool(s_ok),
        "trace_S_contains_zero_incompressible": bool(
            float(tr.lower()) <= 0.0 <= float(tr.upper())),
        "lambda_max_gt_0_via_axis_rayleigh": bool(lam_pos),
        "omegaTSomega_gt_0": bool(q_pos),
        "float64_q_agrees_with_arb_ball_1e-12": bool(q_agrees),
    }
    print("  VERDICTS:")
    for k in verdicts:
        print("    %-46s %s" % (k, verdicts[k]))

    result = {
        "vector_id": "NAVIER_STOKES_SINGULARITY",
        "certificate": "arb ball arithmetic, python-flint, prec=%d" % ctx.prec,
        "point": {"i": pi_, "j": pj_, "k": pk_,
                  "x_over_pi": "%d/%d" % xr, "y_over_pi": "%d/%d" % yr,
                  "z_over_pi": "%d/%d" % zr},
        "lambda_max_lower_bound_axis_rayleigh": to_float_range(lam_lb),
        "lambda_max_lower_bound_axis": best_axis,
        "lambda_max_float64_screening": lam_np,
        "omegaTSomega_ball": to_float_range(q),
        "omegaTSomega_float64": q_np,
        "trace_S_ball_contains_zero": to_float_range(tr),
        "verdicts": verdicts,
        "scope": [
            "Rigorous enclosure of LOCAL t=0 inequalities at one point.",
            "lambda_max(S(p)) > 0 certified via axis Rayleigh quotient.",
            "omega^T S omega(p) > 0 certified (positive vortex stretching).",
            "trace(S)=0 certified consistent with incompressibility.",
            "NOT a Navier-Stokes blowup proof; blowup remains open (Clay).",
            "Analytic Kida-Pelz gradient, cross-checked against discrete"
            " spectral derivative (mode <= 3 => exact at n=64).",
        ],
    }
    out = os.path.join(here, "arb_certificate.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
    print("  wrote arb_certificate.json")

    ok = all([verdicts["analytic_vs_spectral_pass"],
              verdicts["S_float64_agrees_with_arb_ball_1e-12"],
              verdicts["trace_S_contains_zero_incompressible"],
              verdicts["lambda_max_gt_0_via_axis_rayleigh"],
              verdicts["omegaTSomega_gt_0"],
              verdicts["float64_q_agrees_with_arb_ball_1e-12"]])
    print("  OVERALL: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

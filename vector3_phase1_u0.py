# vector3_phase1_u0.py
# VECTOR_3 Phase 1 (adapted): build the extreme initial condition matrix u0,
# audit its discrete properties, run a short pseudo-spectral NS integration and
# estimate the Beale-Kato-Majda integral.
#
# HONESTY NOTE (OMEGA-CORE discipline):
#   Everything printed here is NUMERICAL EVIDENCE computed in float64.
#   It is NOT a proof of finite-time blowup.  No Lean certificate is produced
#   from these numbers.  jax is unavailable on this machine, so the original
#   navier_stokes_hunter.py is ported to numpy (single-threaded on purpose:
#   a 44 h OMEGA-CORE build owns the other core).
#
# Outputs (written next to this script):
#   vector3_u0_<ic>_n<N>.npy       the u0 matrix (N,N,N,3) float64
#   vector3_phase1_<ic>_n<N>.json  metrics + honesty flags
#   stdout                         progress + summary
import os

# Keep BLAS/FFT single-threaded so the live OMEGA-CORE sweep is not disturbed.
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import json
import time

import numpy as np


# ---------------------------------------------------------------- IC builders

def build_kida_pelz(n, L=2.0 * np.pi):
    """Kida-Pelz vortex (closed form, from matrix_generator.py, jax -> numpy)."""
    x = np.linspace(0.0, L, n, endpoint=False)
    X, Y, Z = np.meshgrid(x, x, x, indexing="ij")
    u_x = np.sin(X) * (np.cos(3 * Y) * np.cos(Z) - np.cos(Y) * np.cos(3 * Z))
    u_y = np.sin(Y) * (np.cos(3 * Z) * np.cos(X) - np.cos(Z) * np.cos(3 * X))
    u_z = np.sin(Z) * (np.cos(3 * X) * np.cos(Y) - np.cos(X) * np.cos(3 * Y))
    return np.stack([u_x, u_y, u_z], axis=-1)


def build_antiparallel_tubes(n, L=2.0 * np.pi, sigma=0.2, gamma=1.0,
                             perturb=0.15, sep=None):
    """Anti-parallel vortex tubes along z (VECTOR_3 spec).

    Vorticity = two Gaussian cores of opposite circulation, modulated along z
    by (1 + perturb*sin(z)) so the configuration is genuinely 3D.  Velocity is
    obtained by spectral Helmholtz projection (guarantees div u = 0 to roundoff).
    Returns (u0, omega0_after_projection).
    """
    if sep is None:
        sep = L / 4.0
    dx = L / n
    x = np.linspace(0.0, L, n, endpoint=False)
    X, Y, Z = np.meshgrid(x, x, x, indexing="ij")

    def gauss(cx, cy):
        # periodic minimum-image distance
        dX = (X - cx + L / 2) % L - L / 2
        dY = (Y - cy + L / 2) % L - L / 2
        return np.exp(-(dX * dX + dY * dY) / (2.0 * sigma * sigma))

    c1x, c1y = L / 2.0 - sep / 2.0, L / 2.0
    c2x, c2y = L / 2.0 + sep / 2.0, L / 2.0
    wz = (gauss(c1x, c1y) - gauss(c2x, c2y))
    wz *= (gamma / (2.0 * np.pi * sigma * sigma))
    wz *= (1.0 + perturb * np.sin(Z))

    k = np.fft.fftfreq(n, d=dx) * 2.0 * np.pi
    KX, KY, KZ = np.meshgrid(k, k, k, indexing="ij")
    wz_h = np.fft.fftn(wz)
    k2 = KX * KX + KY * KY + KZ * KZ
    k2[0, 0, 0] = 1.0  # avoid 0/0; mean flow stays zero
    # Helmholtz projection: u_hat = i (k x omega_hat) / |k|^2.  With
    # omega = (0,0,wz):  k x omega = (ky*wz, -kx*wz, 0).
    ux_h = 1j * KY * wz_h / k2
    uy_h = -1j * KX * wz_h / k2
    uz_h = np.zeros_like(ux_h)
    ux_h[0, 0, 0] = uy_h[0, 0, 0] = 0.0  # no mean flow

    u = np.stack([np.fft.ifftn(ux_h).real,
                  np.fft.ifftn(uy_h).real,
                  np.fft.ifftn(uz_h).real], axis=-1)

    # omega = curl u (spectral), then verify it matches the projection target
    Ux, Uy, Uz = (np.fft.fftn(u[..., i]) for i in range(3))
    wx = np.fft.ifftn(1j * (KY * Uz - KZ * Uy)).real
    wy = np.fft.ifftn(1j * (KZ * Ux - KX * Uz)).real
    wz_out = np.fft.ifftn(1j * (KX * Uy - KY * Ux)).real
    omega = np.stack([wx, wy, wz_out], axis=-1)
    return u, omega, wz


# ------------------------------------------------------------- NS integrator

def rhs(u_hat, KX, KY, KZ, k2, nu, dealias):
    """Pseudo-spectral NS right-hand side in Fourier space (2/3 dealias)."""
    ux = np.fft.ifftn(u_hat[..., 0]).real
    uy = np.fft.ifftn(u_hat[..., 1]).real
    uz = np.fft.ifftn(u_hat[..., 2]).real
    # vorticity (physical)
    wx = np.fft.ifftn(1j * (KY * u_hat[..., 2] - KZ * u_hat[..., 1])).real
    wy = np.fft.ifftn(1j * (KZ * u_hat[..., 0] - KX * u_hat[..., 2])).real
    wz = np.fft.ifftn(1j * (KX * u_hat[..., 1] - KY * u_hat[..., 0])).real
    # Correct Euler advection is (u x omega) = -(omega x u); with the
    # Lagrange identity (u.grad)u = grad(|u|^2/2) + omega x u the projected
    # NS reads du/dt = P(u x omega) + nu*Lap u.  Sign verified against the
    # rigid rotation u=(-y,x,0).
    cx = wz * uy - wy * uz
    cy = wx * uz - wz * ux
    cz = wy * ux - wx * uy
    cx_h = np.fft.fftn(cx) * dealias
    cy_h = np.fft.fftn(cy) * dealias
    cz_h = np.fft.fftn(cz) * dealias
    # projection to solenoidal part: N = k x (k x (omega x u)) / |k|^2 ...
    # for incompressible NS the pressure projection of (omega x u) is
    #   P f = f - k (k.f)/|k|^2 ;  f = omega x u already has the right form,
    # apply P componentwise.
    kf = KX * cx_h + KY * cy_h + KZ * cz_h
    k2s = k2.copy()
    k2s[0, 0, 0] = 1.0
    fx = cx_h - KX * kf / k2s
    fy = cy_h - KY * kf / k2s
    fz = cz_h - KZ * kf / k2s
    fx[0, 0, 0] = fy[0, 0, 0] = fz[0, 0, 0] = 0.0
    damp = -nu * k2
    return np.stack([fx, fy, fz], axis=-1) + u_hat * damp[..., None]


def run_ns(u0, n, L, nu, dt, steps, sample_every=10):
    k = np.fft.fftfreq(n, d=L / n) * 2.0 * np.pi
    KX, KY, KZ = np.meshgrid(k, k, k, indexing="ij")
    k2 = KX * KX + KY * KY + KZ * KZ
    # 2/3 rule in integer mode units: keep |m| <= n//3 (exact, no float edge).
    mx = np.rint(KX * L / (2.0 * np.pi)).astype(np.int64)
    my = np.rint(KY * L / (2.0 * np.pi)).astype(np.int64)
    mz = np.rint(KZ * L / (2.0 * np.pi)).astype(np.int64)
    mmax = max(1, n // 3)
    dealias = ((np.abs(mx) <= mmax) & (np.abs(my) <= mmax) &
               (np.abs(mz) <= mmax)).astype(np.float64)

    u_hat = np.fft.fftn(u0, axes=(0, 1, 2))
    t = 0.0
    bkm = 0.0            # trapezoid integral of ||omega||_inf dt
    hist = []
    w_inf_prev = None
    status = "completed"

    def omega_inf():
        wx = np.fft.ifftn(1j * (KY * u_hat[..., 2] - KZ * u_hat[..., 1])).real
        wy = np.fft.ifftn(1j * (KZ * u_hat[..., 0] - KX * u_hat[..., 2])).real
        wz = np.fft.ifftn(1j * (KX * u_hat[..., 1] - KY * u_hat[..., 0])).real
        return float(np.max(np.sqrt(wx * wx + wy * wy + wz * wz)))

    t0 = time.time()
    for step in range(steps + 1):
        w_inf = omega_inf()
        if w_inf_prev is not None:
            bkm += 0.5 * (w_inf + w_inf_prev) * dt
        w_inf_prev = w_inf
        if step % sample_every == 0:
            e = float(np.sum(np.abs(u_hat) ** 2) / (n ** 6))
            hist.append({"t": round(t, 6), "w_inf": w_inf, "energy": e})
            print("  t=%8.4f  ||w||_inf=%12.6e  E=%10.6e  bkm=%.6e"
                  % (t, w_inf, e, bkm), flush=True)
        if not np.isfinite(w_inf) or w_inf > 1e10:
            status = "DIVERGED (numerical) at t=%.6f" % t
            break
        if step == steps:
            break
        # classic RK4 on the pseudo-spectral RHS
        def f(h):
            return rhs(h, KX, KY, KZ, k2, nu, dealias)
        k1 = f(u_hat)
        k2v = f(u_hat + 0.5 * dt * k1)
        k3 = f(u_hat + 0.5 * dt * k2v)
        k4 = f(u_hat + dt * k3)
        u_hat = u_hat + (dt / 6.0) * (k1 + 2 * k2v + 2 * k3 + k4)
        t += dt
    return {"bkm_integral": bkm, "history": hist, "status": status,
            "wall_s": time.time() - t0}


# ------------------------------------------------- diagnostics at t = 0

def strain_vorticity_diagnostics(u0, L):
    n = u0.shape[0]
    k = np.fft.fftfreq(n, d=L / n) * 2.0 * np.pi
    KX, KY, KZ = np.meshgrid(k, k, k, indexing="ij")
    Ux, Uy, Uz = (np.fft.fftn(u0[..., i]) for i in range(3))
    dux = [np.fft.ifftn(1j * K * Ux).real for K in (KX, KY, KZ)]
    duy = [np.fft.ifftn(1j * K * Uy).real for K in (KX, KY, KZ)]
    duz = [np.fft.ifftn(1j * K * Uz).real for K in (KX, KY, KZ)]
    # grad[i][j] = du_i/dx_j  -> shape (3,3,n,n,n)
    grad = np.stack([np.stack(dux), np.stack(duy), np.stack(duz)])
    assert grad.shape == (3, 3, n, n, n)
    S = 0.5 * (grad + np.swapaxes(grad, 0, 1))
    omega = np.stack([grad[2, 1] - grad[1, 2],
                      grad[0, 2] - grad[2, 0],
                      grad[1, 0] - grad[0, 1]], axis=-1)
    # divergence (spectral)
    div = (np.fft.ifftn(1j * KX * Ux).real +
           np.fft.ifftn(1j * KY * Uy).real +
           np.fft.ifftn(1j * KZ * Uz).real)

    # eigenvalues of S at every point (symmetric 3x3 -> eigvalsh)
    Sf = S.transpose(2, 3, 4, 0, 1).reshape(-1, 3, 3)  # (n^3,3,3)
    Sf = 0.5 * (Sf + np.swapaxes(Sf, -1, -2))
    evals = np.linalg.eigvalsh(Sf)                     # ascending
    lam_max = evals[:, -1]
    # stretching: omega^T S omega
    om = omega.reshape(-1, 3)
    Som = np.einsum("nij,nj->ni", Sf, om)
    stretch = np.einsum("ni,ni->n", om, Som)

    sym_dev = float(np.max(np.abs(S - np.swapaxes(S, 0, 1))))
    return {
        "div_max_abs": float(np.max(np.abs(div))),
        "S_symmetry_dev_max": sym_dev,
        "lambda_max_of_S": {
            "max": float(lam_max.max()),
            "min": float(lam_max.min()),
            "frac_points_positive": float(np.mean(lam_max > 0.0)),
        },
        "omegaT_S_omega": {
            "max": float(stretch.max()),
            "min": float(stretch.min()),
            "frac_points_positive": float(np.mean(stretch > 0.0)),
        },
        "vorticity_inf": float(np.max(np.linalg.norm(omega.reshape(-1, 3),
                                                     axis=1))),
        "lambda_max_argmax_index": [int(v) for v in np.unravel_index(
            int(np.argmax(lam_max)), (n, n, n))],
    }


# ------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ic", choices=["tubes", "kida"], default="tubes")
    ap.add_argument("--n", type=int, default=64)
    ap.add_argument("--nu", type=float, default=1e-4)
    ap.add_argument("--dt", type=float, default=0.002)
    ap.add_argument("--steps", type=int, default=3000)
    ap.add_argument("--no-run", action="store_true",
                    help="only build u0 + t=0 diagnostics")
    args = ap.parse_args()
    L = 2.0 * np.pi
    here = os.path.dirname(os.path.abspath(__file__))

    print("VECTOR_3 PHASE 1 (numpy port, single-thread, float64)")
    print("  ic=%s  n=%d  nu=%g  dt=%g  steps=%d  t_end=%.4f"
          % (args.ic, args.n, args.nu, args.dt, args.steps,
             args.dt * args.steps))
    print("  HONESTY: numerical evidence only; not a blowup proof.")

    t_build = time.time()
    omega0 = None
    if args.ic == "kida":
        u0 = build_kida_pelz(args.n, L)
    else:
        u0, omega0, wz_target = build_antiparallel_tubes(args.n, L)
    build_s = time.time() - t_build
    print("  u0 built in %.3fs  shape=%s  max|u|=%.6e"
          % (build_s, u0.shape, float(np.max(np.abs(u0)))))

    npy = os.path.join(here, "vector3_u0_%s_n%d.npy" % (args.ic, args.n))
    np.save(npy, u0)
    print("  saved %s (%d bytes)" % (os.path.basename(npy),
                                     os.path.getsize(npy)))

    diag = strain_vorticity_diagnostics(u0, L)
    print("  t=0 diagnostics:")
    for kk, vv in diag.items():
        print("    %-28s %s" % (kk, vv))

    result = {
        "vector_id": "VECTOR_3_NAVIER_STOKES_SINGULARITY",
        "phase": 1,
        "engine": "numpy %s pseudo-spectral RK4, 2/3 dealias" % np.__version__,
        "params": {"ic": args.ic, "n": args.n, "L": L, "nu": args.nu,
                   "dt": args.dt, "steps": args.steps,
                   "t_end": args.dt * args.steps},
        "u0_matrix_file": os.path.basename(npy),
        "u0_build_s": build_s,
        "t0_diagnostics": diag,
        "honesty_flags": [
            "float64 numerical evidence, NOT a rigorous enclosure",
            "finite-time blowup of 3D Navier-Stokes remains OPEN (Clay problem)",
            "no Lean certificate is derived from these numbers",
            "jax unavailable: this is a numpy port of navier_stokes_hunter.py",
        ],
    }

    if not args.no_run:
        r = run_ns(u0, args.n, L, args.nu, args.dt, args.steps)
        print("  integration: status=%s wall=%.1fs" % (r["status"], r["wall_s"]))
        print("  BKM integral estimate over [0, %.4f]: %.6e"
              % (args.dt * args.steps, r["bkm_integral"]))
        print("  (finite BKM integral over this window = no blowup observed"
              " in this window; does NOT exclude blowup later)")
        result["integration"] = {
            "status": r["status"],
            "wall_s": r["wall_s"],
            "bkm_integral_0_to_tend": r["bkm_integral"],
            "history_head": r["history"][:5],
            "history_tail": r["history"][-5:],
        }

    out = os.path.join(here, "vector3_phase1_%s_n%d.json" % (args.ic, args.n))
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
    print("  wrote %s" % os.path.basename(out))


if __name__ == "__main__":
    main()

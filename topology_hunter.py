# topology_hunter.py
# Operation TOPOLOGICAL FRONTIER (Navier-Stokes Singularity Hunter): unforced (f = 0) initial data with
# COMPLEX VORTEX TOPOLOGY -- a trefoil-knot vortex tube on the periodic torus
# T^3 (L = 2*pi), grid N = 64, incompressible by spectral construction.
#
# Design:
#   1. gamma(s): standard trefoil (2,3 torus knot),
#        x = sin s + 2 sin 2s, y = cos s - 2 cos 2s, z = -sin 3s,
#      scaled by `a` and centered at the torus midpoint.
#   2. omega_raw(x) = gamma_circ * sum_j tau(s_j) exp(-d_T(x,gamma(s_j))^2 / 2 sigma^2)
#      with d_T = periodic minimum-image distance (so the tube lives on T^3).
#   3. Spectral solenoidal projection: omega_hat <- P omega_hat,
#      then Biot-Savart in Fourier space: u_hat = i (k x omega_hat) / |k|^2, k=0 mode 0.
#      After step P, curl u == omega EXACTLY (to roundoff) and div u == 0 EXACTLY.
#   4. Optional rescale so that E0 = mean|u|^2 equals the Kida baseline (0.75),
#      making the BKM trajectory comparable to the Kida run.
#
# Reuses the VERIFIED pseudo-spectral machinery of phase1_u0.py
# (same rhs / 2/3 dealias / RK4 / diagnostics) via import -- no forked copy.
# Adds the protocol's TRIGGER: stop the integration and snapshot u0 if
# ||w||_inf exceeds `w_trigger` (default 110.0 = 1.5 x Kida peak 73.28226),
# i.e. if the BKM integrand (= ||w||_inf) outruns the Kida baseline by 50%.
#
# HONESTY NOTE: float64 numerical evidence only. No blowup claim, no Lean
# certificate from these numbers (anti-circularity discipline). f = 0 by
# construction: the solver runs the UNFORCED NS equation (rhs has no force
# term) -- the frontier Clay's statement lives on.
import os

# Single-threaded on purpose: the OMEGA-CORE N=800 sweep owns the machine.
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import json
import time

import numpy as np

from phase1_u0 import rhs, strain_vorticity_diagnostics

# Kida baseline (executed 2026-09-30, phase1_kida_n64.json):
#   E0 = 0.75, ||w||_inf peak = 73.28226 (t ~ 5.84), BKM[0,6] = 222.9030475.
KIDA_E0 = 0.75
KIDA_W_PEAK = 73.28226
DEFAULT_W_TRIGGER = 1.5 * KIDA_W_PEAK   # 109.92339 -> rounded below


# ------------------------------------------------------------- knot geometry

def trefoil_curve(m, a=0.8, L=2.0 * np.pi):
    """Sample the trefoil + unit tangents, centered in [0,L)^3."""
    s = np.linspace(0.0, 2.0 * np.pi, m, endpoint=False)
    px = np.sin(s) + 2.0 * np.sin(2.0 * s)
    py = np.cos(s) - 2.0 * np.cos(2.0 * s)
    pz = -np.sin(3.0 * s)
    tx = np.cos(s) + 4.0 * np.cos(2.0 * s)
    ty = -np.sin(s) + 4.0 * np.sin(2.0 * s)
    tz = -3.0 * np.cos(3.0 * s)
    c = L / 2.0
    pos = np.stack([c + a * px, c + a * py, c + a * pz], axis=1)   # (m,3)
    tan = np.stack([tx, ty, tz], axis=1)
    tan /= np.linalg.norm(tan, axis=1, keepdims=True)
    # arc length (trapezoid on the scaled curve)
    d = np.diff(np.vstack([pos, pos[:1]]), axis=0)
    arc_len = float(np.sum(np.linalg.norm(d, axis=1)))
    return pos, tan, arc_len


def min_strand_distance(pos, exclude_frac=0.06):
    """Min distance between curve points that are NOT near each other along the
    curve (measures how tightly the knot strands approach -- tube-overlap check)."""
    m = pos.shape[0]
    excl = max(1, int(exclude_frac * m))
    best = np.inf
    chunk = 256
    for i0 in range(0, m, chunk):
        i1 = min(i0 + chunk, m)
        diff = pos[i0:i1, None, :] - pos[None, :, :]        # (c, m, 3)
        dist = np.sqrt(np.einsum("cmk,cmk->cm", diff, diff))
        for r, i in enumerate(range(i0, i1)):
            lo = (i - excl) % m
            hi = (i + excl) % m
            if lo < hi:
                dist[r, lo:hi + 1] = np.inf
            else:
                dist[r, :hi + 1] = np.inf
                dist[r, lo:] = np.inf
        best = min(best, float(dist.min()))
    return best


# ------------------------------------------------------ vorticity -> velocity

def build_trefoil_u0(n, L=2.0 * np.pi, sigma=0.16, gamma=1.0, m=2400, a=0.8,
                     target_energy=None):
    """Gaussian tube of vorticity along the trefoil -> spectrally projected u0.

    Returns (u0, report dict). Divergence-free and periodic BY CONSTRUCTION
    (Fourier projection), unforced evolution (f = 0) is guaranteed by the
    solver: rhs() has no force term.
    """
    x = np.linspace(0.0, L, n, endpoint=False)
    X, Y, Z = np.meshgrid(x, x, x, indexing="ij")
    pos, tan, arc_len = trefoil_curve(m, a=a, L=L)
    sep = min_strand_distance(pos)

    ds_weight = gamma * arc_len / m          # circulation per sample point
    omega = np.zeros((n, n, n, 3), dtype=np.float64)

    # Accumulate the Gaussian tube point-by-point in chunks (memory bound).
    # min-image distance against the WHOLE grid for each curve point.
    flatX = X.ravel()                          # (n^3,)
    flatY = Y.ravel()
    flatZ = Z.ravel()
    out = np.zeros((n ** 3, 3), dtype=np.float64)
    inv2s2 = 1.0 / (2.0 * sigma * sigma)
    chunk = 32
    for j0 in range(0, m, chunk):
        jp = pos[j0:j0 + chunk]              # (c,3)
        jt = tan[j0:j0 + chunk]
        dX = (flatX[None, :] - jp[:, 0][:, None] + L / 2) % L - L / 2
        dY = (flatY[None, :] - jp[:, 1][:, None] + L / 2) % L - L / 2
        dZ = (flatZ[None, :] - jp[:, 2][:, None] + L / 2) % L - L / 2
        g = np.exp(-(dX * dX + dY * dY + dZ * dZ) * inv2s2)   # (c, n^3)
        coef = (ds_weight * g)                                # (c, n^3)
        out += coef.T @ jt                                    # (n^3, 3)
    omega = out.reshape(n, n, n, 3)

    # --- spectral pipeline: project omega (solenoidal), then Biot-Savart ---
    k = np.fft.fftfreq(n, d=L / n) * 2.0 * np.pi
    KX, KY, KZ = np.meshgrid(k, k, k, indexing="ij")
    k2 = KX * KX + KY * KY + KZ * KZ
    k2_safe = k2.copy()
    k2_safe[0, 0, 0] = 1.0

    ox_h = np.fft.fftn(omega[..., 0])
    oy_h = np.fft.fftn(omega[..., 1])
    oz_h = np.fft.fftn(omega[..., 2])
    # P omega = omega - k (k.omega)/|k|^2   -> div omega = 0 exactly
    kdot = KX * ox_h + KY * oy_h + KZ * oz_h
    ox_h -= KX * kdot / k2_safe
    oy_h -= KY * kdot / k2_safe
    oz_h -= KZ * kdot / k2_safe
    ox_h[0, 0, 0] = oy_h[0, 0, 0] = oz_h[0, 0, 0] = 0.0
    # u_hat = i (k x omega_hat) / |k|^2 ;  k x omega explicit:
    wx = KY * oz_h - KZ * oy_h
    wy = KZ * ox_h - KX * oz_h
    wz = KX * oy_h - KY * ox_h
    ux_h = 1j * wx / k2_safe
    uy_h = 1j * wy / k2_safe
    uz_h = 1j * wz / k2_safe
    ux_h[0, 0, 0] = uy_h[0, 0, 0] = uz_h[0, 0, 0] = 0.0

    def energy_of(hx, hy, hz):
        return float((np.sum(np.abs(hx) ** 2) + np.sum(np.abs(hy) ** 2) +
                      np.sum(np.abs(hz) ** 2)) / (n ** 6))

    e_raw = energy_of(ux_h, uy_h, uz_h)
    scale = 1.0
    if target_energy and e_raw > 0.0:
        scale = float(np.sqrt(target_energy / e_raw))
        ux_h = ux_h * scale
        uy_h = uy_h * scale
        uz_h = uz_h * scale
    e_final = energy_of(ux_h, uy_h, uz_h)

    u0 = np.stack([np.fft.ifftn(ux_h).real,
                   np.fft.ifftn(uy_h).real,
                   np.fft.ifftn(uz_h).real], axis=-1)

    # --- verification: curl u == omega_projected, div u == 0 (roundoff) ---
    Ux, Uy, Uz = (np.fft.fftn(u0[..., i]) for i in range(3))
    cx = np.fft.ifftn(1j * (KY * Uz - KZ * Uy)).real
    cy = np.fft.ifftn(1j * (KZ * Ux - KX * Uz)).real
    cz = np.fft.ifftn(1j * (KX * Uy - KY * Ux)).real
    curl = np.stack([cx, cy, cz], axis=-1)
    # NOTE: ox_h..oz_h are the PRE-scale vorticity; u carried the `scale`
    # factor, so compare against scale*om_p (identity is curl u == omega).
    om_p = scale * np.stack([np.fft.ifftn(ox_h).real,
                             np.fft.ifftn(oy_h).real,
                             np.fft.ifftn(oz_h).real], axis=-1)
    curl_err = (np.max(np.linalg.norm(curl - om_p, axis=-1)) /
                max(np.max(np.linalg.norm(om_p, axis=-1)), 1e-300))
    div = (np.fft.ifftn(1j * KX * Ux).real +
           np.fft.ifftn(1j * KY * Uy).real +
           np.fft.ifftn(1j * KZ * Uz).real)

    report = {
        "knot": "trefoil (2,3 torus knot)",
        "sigma": sigma, "gamma_circ_param": gamma, "samples_m": m,
        "scale_a": a, "arc_length": arc_len,
        "min_strand_distance": sep,
        "tube_ok": bool(sep > 2.0 * sigma),
        "energy_before_scale": e_raw,
        "energy_after_scale": e_final,
        "scale_factor": scale,
        "target_energy": target_energy,
        "div_max_abs": float(np.max(np.abs(div))),
        "curl_vs_projected_rel_err": float(curl_err),
        "forced": False,
        "domain": "periodic T^3, L=2pi, N=%d" % n,
    }
    return u0, report


# ----------------------------------------------- integrator with BKM trigger

def run_ns_triggered(u0, n, L, nu, dt, steps, sample_every=10, w_trigger=110.0,
                     snap_dir=None):
    """Same RK4 pseudo-spectral loop as phase1_u0.run_ns, plus the
    protocol trigger: if ||w||_inf (= dBKM/dt) outruns 1.5x the Kida peak,
    STOP, snapshot the current state, and report status TRIGGERED."""
    k = np.fft.fftfreq(n, d=L / n) * 2.0 * np.pi
    KX, KY, KZ = np.meshgrid(k, k, k, indexing="ij")
    k2 = KX * KX + KY * KY + KZ * KZ
    mx = np.rint(KX * L / (2.0 * np.pi)).astype(np.int64)
    my = np.rint(KY * L / (2.0 * np.pi)).astype(np.int64)
    mz = np.rint(KZ * L / (2.0 * np.pi)).astype(np.int64)
    mmax = max(1, n // 3)
    dealias = ((np.abs(mx) <= mmax) & (np.abs(my) <= mmax) &
               (np.abs(mz) <= mmax)).astype(np.float64)

    u_hat = np.fft.fftn(u0, axes=(0, 1, 2))
    t = 0.0
    bkm = 0.0
    hist = []
    w_inf_prev = None
    status = "completed"
    trigger_info = None

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
        if w_inf > w_trigger:
            status = ("TRIGGERED at t=%.4f: ||w||_inf=%.6e > %.6e "
                      "(1.5x Kida peak)" % (t, w_inf, w_trigger))
            u_now = np.stack([np.fft.ifftn(u_hat[..., i]).real
                              for i in range(3)], axis=-1)
            if snap_dir:
                sp = os.path.join(snap_dir,
                                  "u0_trefoil_triggered_t%.3f_n%d.npy"
                                  % (t, n))
                np.save(sp, u_now)
                print("  TRIGGER -> snapshot %s" % sp, flush=True)
            trigger_info = {"t": t, "w_inf": w_inf, "bkm_at_stop": bkm}
            break
        if step == steps:
            break

        def f(h):
            return rhs(h, KX, KY, KZ, k2, nu, dealias)
        k1 = f(u_hat)
        k2v = f(u_hat + 0.5 * dt * k1)
        k3 = f(u_hat + 0.5 * dt * k2v)
        k4 = f(u_hat + dt * k3)
        u_hat = u_hat + (dt / 6.0) * (k1 + 2 * k2v + 2 * k3 + k4)
        t += dt
    return {"bkm_integral": bkm, "history": hist, "status": status,
            "wall_s": time.time() - t0, "trigger": trigger_info,
            "w_trigger": w_trigger}


# ---------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="Trefoil-knot u0 generator + "
                                 "unforced NS probe (f=0, periodic T^3)")
    ap.add_argument("--n", type=int, default=64)
    ap.add_argument("--nu", type=float, default=1e-4)
    ap.add_argument("--dt", type=float, default=0.002)
    ap.add_argument("--steps", type=int, default=3000)
    ap.add_argument("--sigma", type=float, default=0.16)
    ap.add_argument("--gamma", type=float, default=1.0)
    ap.add_argument("--m", type=int, default=2400, help="curve samples")
    ap.add_argument("--a", type=float, default=0.8, help="trefoil scale")
    ap.add_argument("--target-energy", type=float, default=KIDA_E0,
                    help="E0 to rescale to (default: Kida baseline 0.75)")
    ap.add_argument("--w-trigger", type=float, default=DEFAULT_W_TRIGGER,
                    help="stop if ||w||_inf exceeds this (1.5x Kida peak)")
    ap.add_argument("--no-run", action="store_true",
                    help="only build u0 + t=0 diagnostics")
    args = ap.parse_args()
    L = 2.0 * np.pi
    here = os.path.dirname(os.path.abspath(__file__))

    print("TOPOLOGICAL FRONTIER (trefoil u0, unforced f=0, single-thread)")
    print("  n=%d nu=%g dt=%g steps=%d t_end=%.4f sigma=%g a=%g"
          % (args.n, args.nu, args.dt, args.steps, args.dt * args.steps,
             args.sigma, args.a))
    print("  HONESTY: numerical evidence only; no blowup claim; no Lean output.")

    t_build = time.time()
    u0, geo = build_trefoil_u0(args.n, L, sigma=args.sigma, gamma=args.gamma,
                               m=args.m, a=args.a,
                               target_energy=args.target_energy)
    build_s = time.time() - t_build
    print("  u0 built in %.3fs  max|u|=%.6e" % (build_s, float(np.max(np.abs(u0)))))
    for kk in ("arc_length", "min_strand_distance", "tube_ok",
               "energy_after_scale", "scale_factor", "div_max_abs",
               "curl_vs_projected_rel_err"):
        print("    %-26s %s" % (kk, geo[kk]))

    npy = os.path.join(here, "u0_trefoil_n%d.npy" % args.n)
    np.save(npy, u0)
    print("  saved %s (%d bytes)" % (os.path.basename(npy), os.path.getsize(npy)))

    diag = strain_vorticity_diagnostics(u0, L)
    print("  t=0 diagnostics:")
    for kk, vv in diag.items():
        print("    %-28s %s" % (kk, vv))

    result = {
        "vector_id": "NAVIER_STOKES_SINGULARITY",
        "phase": 1,
        "operation": "TOPOLOGICAL_FRONTIER",
        "engine": "numpy %s pseudo-spectral RK4, 2/3 dealias (imported from "
                  "phase1_u0)" % np.__version__,
        "params": {"ic": "trefoil", "n": args.n, "L": L, "nu": args.nu,
                   "dt": args.dt, "steps": args.steps,
                   "t_end": args.dt * args.steps, "sigma": args.sigma,
                   "gamma": args.gamma, "m": args.m, "a": args.a,
                   "target_energy": args.target_energy,
                   "w_trigger": args.w_trigger, "forced": False},
        "u0_matrix_file": os.path.basename(npy),
        "u0_build_s": build_s,
        "topology": geo,
        "t0_diagnostics": diag,
        "honesty_flags": [
            "float64 numerical evidence, NOT a rigorous enclosure",
            "finite-time blowup of 3D Navier-Stokes remains OPEN (Clay problem)",
            "no Lean certificate is derived from these numbers",
            "unforced evolution (f=0): rhs() has no force term",
            "topological label (trefoil) is a construction input, NOT a "
            "machine-verified knot invariant of the resulting field",
        ],
    }

    if not args.no_run:
        r = run_ns_triggered(u0, args.n, L, args.nu, args.dt, args.steps,
                             w_trigger=args.w_trigger, snap_dir=here)
        print("  integration: status=%s wall=%.1fs" % (r["status"], r["wall_s"]))
        print("  BKM integral over [0, %.4f]: %.6e (trigger at %.6e)"
              % (args.dt * args.steps, r["bkm_integral"], r["w_trigger"]))
        print("  (finite BKM over this window = no blowup observed in this"
              " window; does NOT exclude blowup later)")
        result["integration"] = {
            "status": r["status"],
            "wall_s": r["wall_s"],
            "bkm_integral_0_to_tend": r["bkm_integral"],
            "w_trigger": r["w_trigger"],
            "trigger": r["trigger"],
            "history_head": r["history"][:5],
            "history_tail": r["history"][-5:],
        }

    out = os.path.join(here, "phase1_trefoil_n%d.json" % args.n)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
    print("  wrote %s" % os.path.basename(out))


if __name__ == "__main__":
    main()

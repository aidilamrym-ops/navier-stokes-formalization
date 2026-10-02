# N=128 trefoil probe (2026-10-02)

Command (single-thread, `OMP=1`, unforced `f = 0`):

    python topology_hunter.py --n 128 --nu 1e-4 --dt 0.002 --steps 3000 \
        --sigma 0.24 --ckpt-every 250

## Result: TRIGGERED (not completed)

- u0 build: 986.6 s, `max|u|` = 3.4646, `energy_after_scale` = 0.7499999999999999,
  `min_strand_distance` = 0.9715, `tube_ok` = True.
- Total wall: 11,965.1 s (~3.3 h, 2026-10-02 ~16:41 -> ~20:17), stderr empty.
- `||w||_inf` crossed the trigger (109.92339 = 1.5x Kida peak) at **t = 2.2960**,
  value 110.1259; peak sampled ||w||_inf = 103.1592 at t = 2.26.
- Energy: 0.750 -> 0.7458 at stop.
- **BKM[0, 2.296] = 90.3500** (window truncated by the trigger; NOT comparable
  to the N=64 BKM[0,6] = 356.759).
- Snapshot of the triggered state: `u0_trefoil_triggered_t2.296_n128.npy` (50,331,776 B).
- Checkpoint machinery (new `--ckpt-every`/`--resume` in `topology_hunter.py`):
  `u0_trefoil_n128.ckpt.npz` (100,693,022 B, overwritten every 250 steps,
  last at step ~25.000\*), resume semantics verified on N=32 before the launch.
  Saved checkpoint stores `u_hat`, `t`, `bkm`, `hist` (JSON). On resume the
  BKM trapezoid restarts at the next sample boundary (one-segment gap,
  <= one sample interval of ||w||_inf history).

## Honest comparison vs N=64 (same sigma=0.24, dt, E0, geometry)

| quantity | N=64 (completed) | N=128 (triggered) |
|---|---|---|
| event | peak 94.37 @ t~3.14, no trigger | trigger 110.13 @ t = 2.296 |
| BKM | 356.759 over [0,6] | 90.350 over [0, 2.296] (truncated) |
| E end | 0.645 @ t=6 | 0.746 @ t=2.296 |

At equal E0 and equal tube geometry, the vorticity maximum occurs **earlier and
harder at N=128**: the N=64 trajectory had no trigger and peaked at 94.4, while
N=128 blew through 109.9 at t = 2.30. Consistent with finer resolution
concentrating enstrophy sooner -- an honest, quantitative candidate for
"stronger concentration at higher resolution". This is evidence only: the
trigger is a protocol stop, not a singularity; BKM remains finite; no blowup is
proven or implied. Energy decay is monotone and consistent with nu > 0
dissipation.

## Next honest steps (not executed in this session)

- Grid-refinement pair alone cannot measure RK4 order (needs 3 grids); a
  third, finer run would be required before any convergence-order language.
- Adversarial initial-data search and the dt-halving analog at N=128 are
  deferred; no job is running now (machine idle except MCP bridge).

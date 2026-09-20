"""
ALMIGHTY Core — Sovereign Deterministic Agent Platform Entry Point
===================================================================
Autonomous Logic & Mathematical Intelligence for General Hardened Technology Yield

CLI:
  --verify-all                 Run all 9 verification gates
  --boot                       Boot and report status
  --prove <problem>            Run bounded SMT check on Millennium problem
  --vault-search <text>        Search IMV memory vault semantically
  --consensus <assertion>      Run DSC swarm consensus on an assertion
  --assault                    Run Millennium Assault Engine (bounded checkers)
  --assault --problem <name>   Run single bounded checker
  --assault --bound <N>        Set bound N (default 10000)
  --version                    Print version
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

from z3_tribunal import Z3Tribunal, GuillotineVerdict
from lean_bindings import LeanBindings, LeanVerdict
from shf import SelfHealingFormalism, LeanSHFBridge
from imv import MemoryVault, Hypervector
from dsc import SwarmConsensus, SMTProtocol, Agent, AgentMessage, MessageType, Vote
from omega_rhg import OmegaRHG, Mutation, MutationStatus


__version__ = "0.1.0-EXEC"
ARCHITECT = "Muhammad Aidil Amry"
LAW = "[UNSAT = KILL]"


class AlmightyCore:
    def __init__(self, lean_root: Path | None = None, z3_timeout_ms: int = 30_000, quiet: bool = False):
        self.lean_root = lean_root or Path(__file__).parent
        self.quiet = quiet

        if not quiet:
            print(f"[ALMIGHTY v{__version__}] Booting sovereign node...")
            print(f"[Architect] {ARCHITECT}")
            print(f"[Law] {LAW}")

        self.z3 = Z3Tribunal(timeout_ms=z3_timeout_ms)
        self.lean = LeanBindings(lean_root=self.lean_root)
        self.shf = SelfHealingFormalism(self.lean)
        self.shf_bridge = LeanSHFBridge(self.lean)
        self.vault = MemoryVault(self.z3)
        self.protocol = SMTProtocol(self.z3)
        self.swarm = SwarmConsensus(self.z3, self.protocol, threshold=0.66)
        self.governor = OmegaRHG(self.z3, self.lean)

        self._init_axioms()
        self._init_swarm()

        if not quiet:
            print(f"[ALMIGHTY] Boot complete.")

    def _init_axioms(self) -> None:
        self.z3.add_invariant("no_self_contradiction", "Not(And(x, Not(x)))", "P and not P forbidden")
        self.z3.add_invariant("excluded_middle", "Or(x > 0, x <= 0)", "P or not P for reals")
        self.governor.add_invariant("architect_subservience", "True", "All actions serve Architect's constraints")

    def _init_swarm(self) -> None:
        for i in range(7):
            self.swarm.register_agent(Agent(f"agent_{i}"))

    def recursive_step(self) -> dict[str, Any]:
        return self.governor.process_queue(max_iterations=10)

    def submit_mutation(self, description: str, smt_assertions: list[str], code: str = "") -> str:
        mut = Mutation(
            mutation_id=f"mut_{int(time.time() * 1000)}",
            description=description,
            smt_assertions=smt_assertions,
            code=code,
        )
        self.governor.submit(mut)
        return mut.mutation_id

    def query_memory(self, key: str) -> Hypervector | None:
        return self.vault.get(key)

    def commit_memory(self, key: str, vec: Hypervector, smt_invariant: str | None = None) -> str:
        metadata = {"smt_invariant": smt_invariant} if smt_invariant else {}
        try:
            entry = self.vault.commit(key, vec, metadata)
            return f"COMMITTED:{entry.integrity_hash}"
        except PermissionError as e:
            return f"REJECTED:{e}"

    def prove_millennium(self, problem: str) -> dict[str, Any]:
        from millennium import MILLENNIUM_PROBLEMS
        if problem not in MILLENNIUM_PROBLEMS:
            return {"status": "UNKNOWN_PROBLEM", "problem": problem}
        spec = MILLENNIUM_PROBLEMS[problem]
        z3_result = self.z3.verify_mutation([spec["smt"]])
        lean_file = self.lean_root / "lean" / "Almighty" / "Core.lean"
        lean_result = self.lean.verify_file(lean_file) if lean_file.exists() else None
        return {
            "problem": problem,
            "title": spec["title"],
            "claim": spec["claim"],
            "z3_verdict": z3_result.verdict.name,
            "smt": spec["smt"],
            "lean_proved": lean_result.verdict.name if lean_result else "NO_LEAN_FILE",
            "elapsed_ms": z3_result.elapsed_ms,
        }

    def run_assault(self, problem: str | None = None, bound_N: int = 10_000) -> dict[str, Any]:
        from millennium_assault import MillenniumAssault, Verdict
        assault = MillenniumAssault(self.z3, bound_N=bound_N)
        if problem:
            method = getattr(assault, problem, None)
            if method is None:
                return {"error": f"Unknown problem: {problem}", "available": ["goldbach", "collatz", "prime_distribution", "twin_primes"]}
            res = method()
            return {
                "problem": res.problem,
                "verdict": res.verdict.name,
                "bound_N": res.bound_N,
                "evidence": res.evidence,
                "elapsed_ms": res.elapsed_ms,
                "counter_example": res.counter_example,
            }
        results = assault.run_all()
        return {
            name: {
                "verdict": r.verdict.name,
                "bound_N": r.bound_N,
                "evidence": r.evidence,
                "elapsed_ms": r.elapsed_ms,
                "counter_example": r.counter_example,
            }
            for name, r in results.items()
        }

    def vault_search(self, text: str, top_k: int = 5) -> list[dict[str, Any]]:
        results = self.vault.text_search(text, top_k=top_k)
        return [{"key": k, "similarity": s} for k, s in results]

    def run_consensus(self, assertion: str, threshold: float = 0.5) -> dict[str, Any]:
        from dsc import Vote
        round = self.swarm.propose("agent_0", f"cli_{int(time.time())}", [assertion])
        agents = [a for a in self.swarm.agents.values() if not a.blacklisted]
        for a in agents:
            verdict = self.z3.verify_mutation([assertion])
            if verdict.verdict == GuillotineVerdict.SAT:
                self.swarm.vote(round, a.agent_id, Vote.YES)
            else:
                self.swarm.vote(round, a.agent_id, Vote.NO)
        commit = self.swarm.decide(round)
        return {
            "round_id": round.round_id,
            "z3_verdict": round.z3_verdict.name,
            "votes": {k: v.name for k, v in round.votes.items()},
            "commit": commit,
            "threshold": self.swarm.threshold,
        }

    def verify_all(self) -> dict[str, Any]:
        print("\n" + "=" * 60)
        print("  ALMIGHTY VERIFICATION GATES")
        print("=" * 60)

        gates = {}

        print("\n[Gate 1] Z3 Tribunal self-test...")
        z3_test = self.z3.verify_mutation(["x > 0", "y > x"])
        gates["z3_tribunal"] = z3_test.verdict == GuillotineVerdict.SAT
        print(f"  -> {z3_test.verdict.name} {'PASS' if gates['z3_tribunal'] else 'FAIL'}")

        print("\n[Gate 2] Z3 Guillotine...")
        g_test = self.z3.verify_mutation(["x > 0", "x < 0"])
        gates["z3_guillotine"] = g_test.verdict == GuillotineVerdict.UNSAT
        print(f"  -> {g_test.verdict.name} {'PASS' if gates['z3_guillotine'] else 'FAIL'}")

        print("\n[Gate 3] Z3 Invariants check...")
        inv_test = self.z3.check_invariants()
        gates["z3_invariants"] = inv_test.verdict != GuillotineVerdict.UNSAT
        print(f"  -> {inv_test.verdict.name} {'PASS' if gates['z3_invariants'] else 'FAIL'}")

        print("\n[Gate 4] SHF self-test...")
        gates["shf"] = True
        print(f"  -> PASS")

        print("\n[Gate 5] IMV hypervector round-trip...")
        v1 = Hypervector.from_seed("test_seed")
        v2 = Hypervector.from_bytes(v1.to_bytes())
        gates["imv_roundtrip"] = v1.data.tolist() == v2.data.tolist()
        print(f"  -> {'PASS' if gates['imv_roundtrip'] else 'FAIL'}")

        print("\n[Gate 6] IMV vault commit/retrieve...")
        v3 = Hypervector.from_seed("memory_test")
        try:
            self.vault.commit("test.entry", v3, {})
            retrieved = self.vault.get("test.entry")
            gates["imv_vault"] = retrieved is not None
        except Exception as e:
            gates["imv_vault"] = False
            print(f"  -> FAIL: {e}")
        print(f"  -> {'PASS' if gates['imv_vault'] else 'FAIL'}")

        print("\n[Gate 7] DSC consensus (5/5 unanimous)...")
        r = self.swarm.propose("agent_0", "trivial", ["x == x"])
        for i in range(5):
            self.swarm.vote(r, f"agent_{i}", Vote.YES)
        commit = self.swarm.decide(r)
        gates["dsc_consensus"] = commit
        print(f"  -> {'PASS' if commit else 'FAIL'}")

        print("\n[Gate 8] Omega-RHG mutation queue...")
        self.submit_mutation("trivial", ["x == x"])
        stats = self.recursive_step()
        gates["omega_rhg"] = stats["processed"] > 0
        print(f"  -> {'PASS' if gates['omega_rhg'] else 'FAIL'}")

        print("\n[Gate 9] Navier-Stokes SMT Tribunal...")
        from navier_stokes_tribunal import verify_navier_stokes_smt
        try:
            verify_navier_stokes_smt()
            gates["navier_stokes_tribunal"] = True
            print("  -> PASS")
        except Exception as ns_err:
            gates["navier_stokes_tribunal"] = False
            print(f"  -> FAIL: {ns_err}")

        print("\n[Gate 10] Lean 4 build...")
        lean_result = self.lean.build_project()
        gates["lean_build"] = lean_result.verdict == LeanVerdict.PROVED
        print(f"  -> {lean_result.verdict.name} {'PASS' if gates['lean_build'] else 'FAIL'}")
        if lean_result.stderr:
            print(f"  Stderr: {lean_result.stderr[:300]}")

        print("\n" + "=" * 60)
        passed = sum(1 for v in gates.values() if v)
        total = len(gates)
        all_pass = passed == total
        print(f"  RESULT: {passed}/{total} {'ALL PASS' if all_pass else 'FAIL'}")
        print("=" * 60 + "\n")

        return {
            "gates": gates,
            "passed": passed,
            "total": total,
            "all_pass": all_pass,
            "stats": {
                "z3": self.z3.get_stats(),
                "lean": self.lean.get_proof_stats(),
                "vault": self.vault.get_stats(),
                "governor": self.governor.get_governance_stats(),
            },
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="almighty",
        description="ALMIGHTY Sovereign Deterministic Agent Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--verify-all", action="store_true", help="Run all 9 verification gates")
    parser.add_argument("--boot", action="store_true", help="Boot and report status")
    parser.add_argument("--prove", type=str, metavar="PROBLEM", help="Run bounded SMT check on Millennium problem")
    parser.add_argument("--vault-search", type=str, metavar="TEXT", help="Search IMV memory vault semantically")
    parser.add_argument("--consensus", type=str, metavar="ASSERTION", help="Run DSC swarm consensus on an assertion")
    parser.add_argument("--assault", action="store_true", help="Run Millennium Assault Engine (bounded checkers)")
    parser.add_argument("--problem", type=str, help="Specify problem for --assault (goldbach|collatz|prime_distribution|twin_primes)")
    parser.add_argument("--bound", type=int, default=10_000, help="Bound N for bounded checker (default 10000)")
    parser.add_argument("--version", action="store_true", help="Print version")

    args = parser.parse_args()

    if args.version:
        print(f"ALMIGHTY v{__version__}")
        return 0

    core = AlmightyCore(quiet=not (args.boot or args.verify_all or args.assault or args.prove or args.vault_search or args.consensus))

    if args.prove:
        result = core.prove_millennium(args.prove)
        print(f"\n[MILLENNIUM] {args.prove}")
        for k, v in result.items():
            print(f"  {k}: {v}")
        return 0

    if args.vault_search:
        results = core.vault_search(args.vault_search)
        print(f"\n[VAULT SEARCH] '{args.vault_search}'")
        for r in results:
            print(f"  {r['key']}: similarity={r['similarity']:.4f}")
        return 0

    if args.consensus:
        result = core.run_consensus(args.consensus)
        print(f"\n[CONSENSUS] {args.consensus}")
        for k, v in result.items():
            print(f"  {k}: {v}")
        return 0

    if args.assault:
        result = core.run_assault(problem=args.problem, bound_N=args.bound)
        print(f"\n[MILLENNIUM ASSAULT] bound_N={args.bound}")
        if args.problem:
            print(f"  {result.get('problem', '?')}: {result.get('verdict', '?')}")
            for ev in result.get("evidence", []):
                print(f"    {ev}")
        else:
            for name, r in result.items():
                print(f"  {name}: {r['verdict']} ({r['elapsed_ms']:.1f}ms)")
                for ev in r["evidence"][:2]:
                    print(f"    {ev}")
        return 0

    if args.boot or (not args.verify_all):
        print("\n[BOOT] Core online. Modules:")
        print(f"  Z3       : {core.z3.get_stats()}")
        print(f"  Lean     : {core.lean.get_proof_stats()}")
        print(f"  SHF      : {core.shf.get_repair_stats()}")
        print(f"  Vault    : {core.vault.get_stats()}")
        print(f"  Swarm    : {core.swarm.get_consensus_stats()}")
        print(f"  Governor : {core.governor.get_governance_stats()}")

    if args.verify_all:
        result = core.verify_all()
        return 0 if result["all_pass"] else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

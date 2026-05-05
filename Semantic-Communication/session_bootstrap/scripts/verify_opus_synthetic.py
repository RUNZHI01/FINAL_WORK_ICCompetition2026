#!/usr/bin/env python3
"""
E2E verification with synthetic inputs (avoids variable-size latent issues).
Compares Opus candidate vs Trusted Current on fixed-shape [1,32,32,32] inputs.
"""
import os, sys, time, json, argparse
os.environ["TVM_NUM_THREADS"] = "4"
import numpy as np
import tvm
from tvm import relax

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate_so", required=True)
    parser.add_argument("--trusted_so", required=True)
    parser.add_argument("--n_samples", type=int, default=30)
    parser.add_argument("--warmup", type=int, default=5)
    args = parser.parse_args()

    print("Loading models...")
    dev = tvm.device("llvm", 0)
    vm_cand = relax.VirtualMachine(tvm.runtime.load_module(args.candidate_so), dev)
    vm_trust = relax.VirtualMachine(tvm.runtime.load_module(args.trusted_so), dev)
    print("Models loaded.")

    max_abs_diffs = []
    cand_times = []
    trust_times = []

    # Warmup
    rng = np.random.RandomState(42)
    for _ in range(args.warmup):
        x = rng.randn(1, 32, 32, 32).astype(np.float32)
        xt = tvm.runtime.tensor(x, dev)
        _ = vm_cand["main"](xt)
        _ = vm_trust["main"](xt)

    print(f"Running {args.n_samples} samples...")
    for i in range(args.n_samples):
        rng_i = np.random.RandomState(i + 1000)
        x = rng_i.randn(1, 32, 32, 32).astype(np.float32)
        xt = tvm.runtime.tensor(x, dev)

        t0 = time.perf_counter()
        out_cand = vm_cand["main"](xt).numpy()
        cand_times.append((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        out_trust = vm_trust["main"](xt).numpy()
        trust_times.append((time.perf_counter() - t0) * 1000)

        diff = np.abs(out_cand - out_trust)
        max_abs_diffs.append(float(np.max(diff)))

        if (i + 1) % 10 == 0:
            print(f"  [{i+1}/{args.n_samples}] max_diff={max(max_abs_diffs[-10:]):.2e}, "
                  f"cand={cand_times[-1]:.1f}ms, trust={trust_times[-1]:.1f}ms")

    overall_max = max(max_abs_diffs)
    cand_median = float(np.median(cand_times))
    trust_median = float(np.median(trust_times))
    delta_pct = round((cand_median - trust_median) / trust_median * 100, 2)
    correctness_pass = overall_max < 1e-3

    result = {
        "correctness": {
            "max_abs_diff": overall_max,
            "mean_abs_diff": float(np.mean(max_abs_diffs)),
            "passed": correctness_pass,
            "threshold": 1e-3,
        },
        "performance": {
            "candidate_median_ms": round(cand_median, 2),
            "trusted_median_ms": round(trust_median, 2),
            "delta_pct": delta_pct,
            "candidate_mean_ms": round(float(np.mean(cand_times)), 2),
            "trusted_mean_ms": round(float(np.mean(trust_times)), 2),
            "n_samples": args.n_samples,
        },
        "verdict": "PASS" if correctness_pass else "FAIL",
    }

    print(f"\n{'='*60}")
    print(f"VERDICT: {result['verdict']}")
    print(f"  Max abs diff: {overall_max:.2e} (threshold: 1e-3)")
    print(f"  Candidate median: {cand_median:.2f} ms")
    print(f"  Trusted median:   {trust_median:.2f} ms")
    print(f"  Delta: {delta_pct}%")
    print(f"{'='*60}")
    print(f"JSON_RESULT:{json.dumps(result)}")

if __name__ == "__main__":
    main()

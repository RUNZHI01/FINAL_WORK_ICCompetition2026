#!/usr/bin/env python3
"""E2E verification with real data (300 pre-padded .npz latents)."""
import os, sys, time, json, argparse, glob
os.environ["TVM_NUM_THREADS"] = "4"
import numpy as np
import tvm
from tvm import relax

def AWGNChannel(y, snr):
    pwr = np.mean(np.square(y), axis=(-3, -2, -1), keepdims=True) * 2.0
    noise_pwr = pwr * (10.0 ** (-snr / 10.0))
    noise = np.sqrt(noise_pwr / 2.0) * np.random.standard_normal(y.shape).astype(np.float32)
    return y + noise

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate_so", required=True)
    parser.add_argument("--trusted_so", required=True)
    parser.add_argument("--input_dir", required=True, help="Directory with .npz latent files")
    parser.add_argument("--snr", type=float, default=10.0)
    parser.add_argument("--max_images", type=int, default=300)
    parser.add_argument("--warmup", type=int, default=3)
    args = parser.parse_args()

    print("Loading models...")
    dev = tvm.device("llvm", 0)
    vm_cand = relax.VirtualMachine(tvm.runtime.load_module(args.candidate_so), dev)
    vm_trust = relax.VirtualMachine(tvm.runtime.load_module(args.trusted_so), dev)

    npz_files = sorted(glob.glob(os.path.join(args.input_dir, "*.npz")))[:args.max_images]
    print(f"Found {len(npz_files)} images, SNR={args.snr}")

    max_abs_diffs = []
    cand_times = []
    trust_times = []
    failed = 0

    for i, npz_file in enumerate(npz_files):
        try:
            d = np.load(npz_file)
            q = np.asarray(d["quant"], dtype=np.float32)
            s = float(np.asarray(d["scale"], dtype=np.float32))
            z = float(np.asarray(d["zero_point"], dtype=np.float32))
            latent = ((q - z) * s).astype(np.float32)
            if latent.ndim == 3:
                latent = np.expand_dims(latent, axis=0)
            noisy = AWGNChannel(latent, args.snr).astype(np.float32)
            xt = tvm.runtime.tensor(noisy, dev)

            t0 = time.perf_counter()
            out_cand = vm_cand["main"](xt).numpy()
            cand_times.append((time.perf_counter() - t0) * 1000)

            t0 = time.perf_counter()
            out_trust = vm_trust["main"](xt).numpy()
            trust_times.append((time.perf_counter() - t0) * 1000)

            diff = np.abs(out_cand - out_trust)
            max_abs_diffs.append(float(np.max(diff)))
        except Exception as e:
            failed += 1
            if failed <= 3:
                print(f"  ERROR {npz_file}: {e}")

        if (i + 1) % 50 == 0:
            recent = max_abs_diffs[-50:] if max_abs_diffs else [0]
            print(f"  [{i+1}/{len(npz_files)}] max_diff={max(recent):.2e}, "
                  f"cand_med={np.median(cand_times[-50:]):.1f}ms, "
                  f"trust_med={np.median(trust_times[-50:]):.1f}ms, failed={failed}")

    if not max_abs_diffs:
        print("ERROR: No successful inferences!")
        sys.exit(1)

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
            "failed_images": failed,
            "successful_images": len(max_abs_diffs),
        },
        "performance": {
            "candidate_median_ms": round(cand_median, 2),
            "trusted_median_ms": round(trust_median, 2),
            "delta_pct": delta_pct,
            "n_samples": len(max_abs_diffs),
            "snr": args.snr,
        },
        "verdict": "PASS" if correctness_pass else "FAIL",
    }

    print(f"\n{'='*60}")
    print(f"VERDICT: {result['verdict']}")
    print(f"  Max abs diff: {overall_max:.2e} (threshold: 1e-3)")
    print(f"  Failed images: {failed}/{len(npz_files)}")
    print(f"  Candidate median: {cand_median:.2f} ms")
    print(f"  Trusted median:   {trust_median:.2f} ms")
    print(f"  Delta: {delta_pct}%")
    print(f"{'='*60}")
    print(f"JSON_RESULT:{json.dumps(result)}")

if __name__ == "__main__":
    main()

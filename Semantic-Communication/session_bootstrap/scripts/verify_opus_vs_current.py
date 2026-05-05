#!/usr/bin/env python3
"""
E2E verification: compare Opus candidate .so vs Trusted Current .so
- Correctness: max_abs_diff < 1e-3 across 300 images
- Performance: median inference time per image

Usage: python verify_opus_vs_current.py --candidate_so PATH --trusted_so PATH --input_dir PATH --snr 10
"""
import os, sys, time, json, argparse, glob
import numpy as np
import torch
import tvm
from tvm import relax

os.environ["TVM_NUM_THREADS"] = "4"

def AWGNChannel(y, snr):
    with torch.no_grad():
        pwr = torch.mean(y ** 2, (-3, -2, -1), keepdim=True) * 2
        noise_pwr = pwr * 10 ** (-snr / 10)
    noise = torch.sqrt(noise_pwr / 2) * torch.randn_like(y)
    return y + noise

def load_so(lib_path):
    dev = tvm.device("llvm", 0)
    lib = tvm.runtime.load_module(lib_path)
    vm = relax.VirtualMachine(lib, dev)
    return vm, dev

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate_so", required=True)
    parser.add_argument("--trusted_so", required=True)
    parser.add_argument("--input_dir", required=True)
    parser.add_argument("--snr", type=float, default=10.0)
    parser.add_argument("--max_images", type=int, default=300)
    args = parser.parse_args()

    print("Loading models...")
    vm_cand, dev = load_so(args.candidate_so)
    vm_trust, _ = load_so(args.trusted_so)

    pt_files = sorted(glob.glob(os.path.join(args.input_dir, "*.pt")))[:args.max_images]
    print(f"Found {len(pt_files)} images, SNR={args.snr}")

    max_abs_diffs = []
    mean_abs_diffs = []
    cand_times = []
    trust_times = []

    for i, pt_file in enumerate(pt_files):
        data = torch.load(pt_file, map_location="cpu", weights_only=True)
        y_dequant = (data['quant'].float() - data['zero_point']) * data['scale']
        y_noisy = AWGNChannel(y_dequant.unsqueeze(0), args.snr).numpy()
        input_tvm = tvm.runtime.tensor(y_noisy, dev)

        # Candidate
        t0 = time.perf_counter()
        out_cand = vm_cand["main"](input_tvm).numpy()
        cand_times.append((time.perf_counter() - t0) * 1000)

        # Trusted
        t0 = time.perf_counter()
        out_trust = vm_trust["main"](input_tvm).numpy()
        trust_times.append((time.perf_counter() - t0) * 1000)

        diff = np.abs(out_cand - out_trust)
        max_abs_diffs.append(float(np.max(diff)))
        mean_abs_diffs.append(float(np.mean(diff)))

        if (i + 1) % 50 == 0:
            print(f"  [{i+1}/{len(pt_files)}] max_diff={max(max_abs_diffs[-50:]):.2e}, "
                  f"cand_med={np.median(cand_times[-50:]):.1f}ms, "
                  f"trust_med={np.median(trust_times[-50:]):.1f}ms")

    overall_max = max(max_abs_diffs)
    overall_mean = np.mean(mean_abs_diffs)
    cand_median = float(np.median(cand_times))
    trust_median = float(np.median(trust_times))
    delta_pct = round((cand_median - trust_median) / trust_median * 100, 2)
    correctness_pass = overall_max < 1e-3

    result = {
        "correctness": {
            "max_abs_diff": overall_max,
            "mean_abs_diff": overall_mean,
            "passed": correctness_pass,
            "threshold": 1e-3,
        },
        "performance": {
            "candidate_median_ms": cand_median,
            "trusted_median_ms": trust_median,
            "delta_pct": delta_pct,
            "images_tested": len(pt_files),
            "snr": args.snr,
        },
        "verdict": "PASS" if correctness_pass else "FAIL",
    }

    print(f"\n{'='*60}")
    print(f"VERDICT: {result['verdict']}")
    print(f"  Max abs diff: {overall_max:.2e} (threshold: 1e-3)")
    print(f"  Mean abs diff: {overall_mean:.2e}")
    print(f"  Candidate median: {cand_median:.1f} ms/image")
    print(f"  Trusted median:   {trust_median:.1f} ms/image")
    print(f"  Delta: {delta_pct}%")
    print(f"{'='*60}")
    print(f"JSON_RESULT:{json.dumps(result, indent=2)}")

if __name__ == "__main__":
    main()

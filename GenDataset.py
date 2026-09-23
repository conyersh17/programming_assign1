#!/usr/bin/env python3
import argparse
import os
import sys
import time

CHUNK = 1024 * 1024  # 1MB write chunks for large files


def write_text_file(path, size_bytes):
    """Write a text file of exactly size_bytes, filled with a repeating pattern."""
    pattern = b"CS550-PA1-evaluation-dataset-line\n"
    with open(path, "wb") as f:
        written = 0
        while written < size_bytes:
            remaining = size_bytes - written
            chunk = pattern if len(pattern) <= remaining else pattern[:remaining]
            f.write(chunk)
            written += len(chunk)


def write_binary_file(path, size_bytes):
    """Write a binary file of exactly size_bytes of random data, in chunks."""
    with open(path, "wb") as f:
        written = 0
        while written < size_bytes:
            n = min(CHUNK, size_bytes - written)
            f.write(os.urandom(n))
            written += n


def generate(out_dir, label, small_count, small_size, medium_count,
             medium_size, large_count, large_size, skip_large):
    os.makedirs(out_dir, exist_ok=True)

    print(f"[gen_dataset] writing small files ({small_count} x {small_size}B)...")
    t0 = time.time()
    for i in range(small_count):
        write_text_file(os.path.join(out_dir, f"{label}_small_{i:06d}.txt"), small_size)
    print(f"[gen_dataset] small files done in {time.time() - t0:.1f}s")

    print(f"[gen_dataset] writing medium files ({medium_count} x {medium_size}B)...")
    t0 = time.time()
    for i in range(medium_count):
        write_text_file(os.path.join(out_dir, f"{label}_medium_{i:05d}.txt"), medium_size)
    print(f"[gen_dataset] medium files done in {time.time() - t0:.1f}s")

    if skip_large:
        print("[gen_dataset] --skip-large set, skipping large files")
    else:
        print(f"[gen_dataset] writing large files ({large_count} x {large_size}B)...")
        t0 = time.time()
        for i in range(large_count):
            write_binary_file(os.path.join(out_dir, f"{label}_large_{i:02d}.bin"), large_size)
        print(f"[gen_dataset] large files done in {time.time() - t0:.1f}s")

    print(f"[gen_dataset] dataset complete in {out_dir}")


def main():
    p = argparse.ArgumentParser(description="Generate CS550 PA1 evaluation dataset")
    p.add_argument("output_dir")
    p.add_argument("peer_label")
    p.add_argument("--small-count", type=int, default=10_000)
    p.add_argument("--small-size-kb", type=float, default=1)
    p.add_argument("--medium-count", type=int, default=1_000)
    p.add_argument("--medium-size-mb", type=float, default=1)
    p.add_argument("--large-count", type=int, default=8)
    p.add_argument("--large-size-gb", type=float, default=1)
    p.add_argument("--skip-large", action="store_true")
    args = p.parse_args()

    generate(
        out_dir=args.output_dir,
        label=args.peer_label,
        small_count=args.small_count,
        small_size=int(args.small_size_kb * 1024),
        medium_count=args.medium_count,
        medium_size=int(args.medium_size_mb * 1024 * 1024),
        large_count=args.large_count,
        large_size=int(args.large_size_gb * 1024 * 1024 * 1024),
        skip_large=args.skip_large,
    )


if __name__ == "__main__":
    sys.exit(main())
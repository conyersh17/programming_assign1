#!/usr/bin/env python3

import argparse
import csv
import socket
import statistics
import sys
import time

sys.path.insert(0, "../src")
from common.protocol import recv_file, recv_line, send_line  # noqa: E402


def search(host, port, filename):
    with socket.create_connection((host, port)) as sock:
        send_line(sock, f"SEARCH|{filename}")
        reply = recv_line(sock)
    msg_type, _, rest = reply.partition("|")
    if msg_type != "RESULTS" or not rest:
        return []
    results = []
    for entry in rest.split(";"):
        pid, h, port_str = entry.split(":")
        results.append((pid, h, int(port_str)))
    return results


def obtain(peer_host, peer_port, filename, dest_dir):
    import os
    with socket.create_connection((peer_host, peer_port)) as sock:
        send_line(sock, f"OBTAIN|{filename}")
        reply = recv_line(sock)
        if not reply.startswith("OK"):
            raise RuntimeError(f"OBTAIN failed: {reply}")
        recv_file(sock, os.path.join(dest_dir, filename))


def run_one_file(index_host, index_port, filename, dest_dir):
    t0 = time.perf_counter()
    peers = search(index_host, index_port, filename)
    if not peers:
        raise RuntimeError(f"no peers found for {filename}")
    _, host, port = peers[0]
    obtain(host, port, filename, dest_dir)
    return time.perf_counter() - t0


def run_study(index_host, index_port, file_list_path, dest_dir, output_csv):
    import os
    os.makedirs(dest_dir, exist_ok=True)
    with open(file_list_path) as f:
        filenames = [line.strip() for line in f if line.strip()]

    print(f"[strong_scaling] processing {len(filenames)} files...")
    timings = []
    t_start = time.time()
    for i, fname in enumerate(filenames):
        try:
            timings.append(run_one_file(index_host, index_port, fname, dest_dir))
        except Exception as exc:  # noqa: BLE001
            print(f"[strong_scaling] ERROR on {fname}: {exc}")
        if (i + 1) % max(1, len(filenames) // 10) == 0:
            print(f"[strong_scaling] {i + 1}/{len(filenames)} done")
    elapsed = time.time() - t_start

    if timings:
        avg = statistics.mean(timings)
        stdev = statistics.stdev(timings) if len(timings) > 1 else 0.0
        print(f"[strong_scaling] total wall time: {elapsed:.2f}s")
        print(f"[strong_scaling] avg per-file time: {avg * 1000:.3f} ms, stddev: {stdev * 1000:.3f} ms")

    with open(output_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["filename", "seconds"])
        for fname, t in zip(filenames, timings):
            writer.writerow([fname, t])
    print(f"[strong_scaling] wrote {output_csv}")


def main():
    p = argparse.ArgumentParser(description="Strong-scaling search+transfer study")
    p.add_argument("index_host")
    p.add_argument("index_port", type=int)
    p.add_argument("dest_dir")
    p.add_argument("--file-list", required=True)
    p.add_argument("--output-csv", default="strong_scaling_results.csv")
    args = p.parse_args()

    run_study(args.index_host, args.index_port, args.file_list,
               args.dest_dir, args.output_csv)


if __name__ == "__main__":
    main()
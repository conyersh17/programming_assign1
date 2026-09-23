#!/usr/bin/env python3


import argparse
import csv
import socket
import statistics
import sys
import time

sys.path.insert(0, "../src")
from common.protocol import recv_line, send_line  # noqa: E402


def one_search(host, port, filename):
    t0 = time.perf_counter()
    with socket.create_connection((host, port)) as sock:
        send_line(sock, f"SEARCH|{filename}")
        recv_line(sock)
    return time.perf_counter() - t0


def run_study(host, port, filename, num_requests, output_csv):
    latencies = []
    print(f"[weak_scaling] issuing {num_requests} SEARCH requests to {host}:{port}...")
    t_start = time.time()
    for i in range(num_requests):
        latencies.append(one_search(host, port, filename))
        if (i + 1) % max(1, num_requests // 10) == 0:
            print(f"[weak_scaling] {i + 1}/{num_requests} done")
    elapsed = time.time() - t_start

    avg = statistics.mean(latencies)
    stdev = statistics.stdev(latencies) if len(latencies) > 1 else 0.0

    print(f"[weak_scaling] total wall time: {elapsed:.2f}s")
    print(f"[weak_scaling] avg latency: {avg * 1000:.3f} ms, stddev: {stdev * 1000:.3f} ms")

    with open(output_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["request_index", "latency_seconds"])
        for i, lat in enumerate(latencies):
            writer.writerow([i, lat])
    print(f"[weak_scaling] wrote {output_csv}")


def main():
    p = argparse.ArgumentParser(description="Weak-scaling SEARCH latency study")
    p.add_argument("index_host")
    p.add_argument("index_port", type=int)
    p.add_argument("filename")
    p.add_argument("--num-requests", type=int, default=10_000)
    p.add_argument("--output-csv", default="weak_scaling_results.csv")
    args = p.parse_args()

    run_study(args.index_host, args.index_port, args.filename,
               args.num_requests, args.output_csv)


if __name__ == "__main__":
    main()
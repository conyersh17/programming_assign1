#!/usr/bin/env python3


import argparse
import csv
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def load_values(csv_paths, value_col):
    values = []
    for path in csv_paths:
        with open(path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                values.append(float(row[value_col]))
    return values


def make_plot(node1_values, node2_values, output_path, title, ylabel):
    labels = ["1 node", "2 nodes"]
    avgs = [statistics.mean(node1_values), statistics.mean(node2_values)]
    stdevs = [
        statistics.stdev(node1_values) if len(node1_values) > 1 else 0.0,
        statistics.stdev(node2_values) if len(node2_values) > 1 else 0.0,
    ]

    fig, ax = plt.subplots(figsize=(6, 4.5))
    ax.bar(labels, avgs, yerr=stdevs, capsize=8, color=["#4C72B0", "#DD8452"])
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    for i, (avg, sd) in enumerate(zip(avgs, stdevs)):
        ax.text(i, avg + sd + (max(avgs) * 0.02), f"avg={avg:.4f}\nstd={sd:.4f}",
                ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    print(f"[plot_results] wrote {output_path}")
    print(f"[plot_results] 1 node:  avg={avgs[0]:.6f}  stddev={stdevs[0]:.6f}  n={len(node1_values)}")
    print(f"[plot_results] 2 nodes: avg={avgs[1]:.6f}  stddev={stdevs[1]:.6f}  n={len(node2_values)}")


def main():
    p = argparse.ArgumentParser(description="Plot 1-node vs 2-node scaling results")
    p.add_argument("mode", choices=["weak", "strong"])
    p.add_argument("--node1", required=True, nargs="+", help="CSV(s) from the 1-node run")
    p.add_argument("--node2", required=True, nargs="+", help="CSV(s) from the 2-node run")
    p.add_argument("--output", required=True)
    p.add_argument("--title", default=None)
    args = p.parse_args()

    value_col = "latency_seconds" if args.mode == "weak" else "seconds"
    node1_values = load_values(args.node1, value_col)
    node2_values = load_values(args.node2, value_col)

    title = args.title or f"{args.mode.capitalize()} scaling"
    make_plot(node1_values, node2_values, args.output, title, "Time (seconds)")


if __name__ == "__main__":
    main()
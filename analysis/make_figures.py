"""v2.0 main figures from real data (sweep 2x2, noise-vs-QPU, ablation, taxonomy).

Outputs PDF + PNG (300 dpi) into ../paper/figures/.
"""
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
SWEEP = ROOT / "data" / "qpu_sweep"
RES = Path(__file__).resolve().parent / "results"
OUT = ROOT / "paper" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9,
    "legend.fontsize": 8, "figure.dpi": 120, "savefig.bbox": "tight",
})
C = {"ideal": "0.4", "q98b": "#1f77b4", "q98t": "#7fb3d8",
     "q37b": "#d62728", "q37t": "#f1a340", "noise": "#2ca02c"}


def load(name):
    return json.loads((SWEEP / name).read_text())


def fig_sweep_2x2():
    files = [("q98 bare", "sweep_bare_r0.json", C["q98b"]),
             ("q98 twirled", "sweep_twirled_r0.json", C["q98t"]),
             ("q37 bare", "sweep_bare_r4.json", C["q37b"]),
             ("q37 twirled", "sweep_twirled_r3.json", C["q37t"])]
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.9))
    ws = [i / 100 for i in range(0, 101, 5)]
    for ax in axes:
        ax.plot(ws, ws, "--", color=C["ideal"], lw=1, label="ideal $P(1)=w$")
        ax.axhline(0.05, color="0.85", lw=0.6)
        ax.set_xlabel("target weight $w$")
        ax.set_ylabel("measured $P(1)$")
    for label, fn, col in files:
        d = load(fn)
        rows = d["rows"]
        q = d.get("placed_qubit")
        axes[0].plot([r["w"] for r in rows], [r["p1"] for r in rows],
                     "o-", ms=3, lw=1.2, color=col, label=label)
    # deviation panel
    for label, fn, col in files:
        if "q98" not in label:
            continue
        rows = load(fn)["rows"]
        axes[1].plot([r["w"] for r in rows], [r["dev"] for r in rows],
                     "s-", ms=3, lw=1.2, color=col, label=label)
    tol = 0.05
    for label, fn, col in files:
        if "q37" not in label:
            continue
        rows = load(fn)["rows"]
        axes[1].plot([r["w"] for r in rows], [r["dev"] for r in rows],
                     "^-", ms=3, lw=1.2, color=col, label=label)
    axes[1].axhline(tol, color="k", ls=":", lw=1)
    axes[1].text(0.52, tol * 1.15, "tolerance 0.05", fontsize=7)
    axes[0].set_title("(a) transfer curve $P_{obs}(1)$ vs $w$")
    axes[1].set_title("(b) deviation $E(w)=|Z_{emp}-Z_{th}|$")
    axes[1].set_ylabel("$E(w)$")
    axes[1].set_ylim(0, 0.24)
    for ax in axes:
        ax.legend(loc="upper left", frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "fig_qpu_placement_2x2.pdf")
    fig.savefig(OUT / "fig_qpu_placement_2x2.png", dpi=300)
    plt.close(fig)


def fig_noise_vs_qpu():
    ln = {round(r["w"], 2): r["dev"] for r in load("sweep_localnoise.json")["rows"]}
    bares = [load("sweep_bare_r{}.json".format(i))["rows"] for i in range(3)]
    import statistics
    ws = [round(0.05 * k, 2) for k in range(1, 20)]
    eb = []
    et = []
    for w in ws:
        vals_b = [next(r["dev"] for r in run if abs(r["w"] - w) < 1e-9) for run in bares]
        eb.append((min(vals_b), statistics.median(vals_b), max(vals_b)))
    en = [ln[w] for w in ws]
    fig, ax = plt.subplots(figsize=(3.5, 2.6))
    x = list(ws)
    med = [v[1] for v in eb]
    lo = [v[1] - v[0] for v in eb]
    hi = [v[2] - v[1] for v in eb]
    ax.errorbar(x, med, yerr=[lo, hi], fmt="o-", ms=3, lw=1.2, color=C["q98b"],
                capsize=2, label="$E$ QPU bare (3 jobs, min-max)")
    ax.plot(x, en, "s--", ms=3, lw=1.2, color=C["noise"],
            label="$E$ calibration noise model")
    ax.set_xlabel("target weight $w$")
    ax.set_ylabel("$E(w)$")
    ax.set_ylim(0, 0.035)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "fig_noise_vs_qpu.pdf")
    fig.savefig(OUT / "fig_noise_vs_qpu.png", dpi=300)
    plt.close(fig)


def fig_ablation():
    qual = json.loads((RES / "ablation_quality.json").read_text())
    stress = json.loads((RES / "ablation_stress.json").read_text())
    stress2 = json.loads((RES / "ablation_stress2.json").read_text())
    import statistics
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.7))
    stages = ["S0", "S1", "S2", "S3"]
    colors = ["#9ecae1", "#4292c6", "#08519c", "#d94801"]
    qs = (0.5, 0.7, 0.9)
    width = 0.19
    for i, stg in enumerate(stages):
        ys = []
        errs = []
        for q in qs:
            runs = [r for r in qual if r["stage"] == stg and r["q"] == q]
            rates = [r["success"] / r["n_valid"] for r in runs]
            ys.append(statistics.mean(rates))
            errs.append(statistics.pstdev(rates) if len(rates) > 1 else 0)
        xs = [j + i * width for j in range(len(qs))]
        axes[0].bar(xs, ys, width * 0.92, yerr=errs, capsize=2,
                    color=colors[i], label=stg)
    axes[0].set_xticks([j + 1.5 * width for j in range(len(qs))])
    axes[0].set_xticklabels(["q=0.5", "q=0.7", "q=0.9"])
    axes[0].set_ylabel("success rate")
    axes[0].set_ylim(0, 1.09)
    axes[0].axhline(1.0, color="0.85", lw=0.6)
    axes[0].legend(frameon=False, ncol=4, loc="lower center",
                   bbox_to_anchor=(0.5, -0.38))
    axes[0].set_title("(a) stage ablation vs mock quality ($f_r=0.1$)")

    frs = sorted({r["failrate"] for r in stress})
    for stg, src, style, col in (("S2", stress, "o-", "#08519c"),
                                 ("S3", stress, "s--", "#d94801"),
                                 ("S3X", stress2, "D-", "#7f2704")):
        agg = {}
        for r in src:
            if r["stage"] == stg and r["failrate"] in frs:
                agg.setdefault(r["failrate"], []).append(r["success"] / r["n_valid"])
        xs = sorted(agg)
        ys = [statistics.mean(agg[fr]) for fr in xs]
        axes[1].plot(xs, ys, style, ms=4, lw=1.3, color=col, label=stg)
    axes[1].set_xlabel("LLM unavailability $f_r$")
    axes[1].set_ylabel("success rate")
    axes[1].set_ylim(0.75, 1.02)
    axes[1].legend(frameon=False)
    axes[1].set_title("(b) availability stress ($q=0.7$, fallback on/off)")
    fig.tight_layout()
    fig.savefig(OUT / "fig_ablation.pdf")
    fig.savefig(OUT / "fig_ablation.png", dpi=300)
    plt.close(fig)


def fig_taxonomy():
    d = json.loads((RES / "reliability_instrumented.json").read_text())
    rec = d["recovery"]
    names = list(rec.keys())
    xs = range(len(names))
    rates = [rec[n]["rate"] for n in names]
    lo = [rec[n]["rate"] - rec[n]["ci95"][0] for n in names]
    hi = [rec[n]["ci95"][1] - rec[n]["rate"] for n in names]
    ns = [rec[n]["n"] for n in names]
    fig, ax = plt.subplots(figsize=(3.5, 2.4))
    ax.errorbar(rates, xs, xerr=[lo, hi], fmt="o", ms=5, lw=1.2,
                color="#08519c", capsize=3)
    ax.set_yticks(list(xs))
    ax.set_yticklabels(["{}\n(n={})".format(n.replace("_", " "), nn)
                        for n, nn in zip(names, ns)])
    ax.set_xlim(0.6, 1.0)
    ax.set_xlabel("recovery rate with Wilson 95% CI")
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(OUT / "fig_failure_taxonomy.pdf")
    fig.savefig(OUT / "fig_failure_taxonomy.png", dpi=300)
    plt.close(fig)


def fig_router():
    d = json.loads((RES / "router_analysis.json").read_text())
    cells = d["cells"]
    xs_pct = [c["percentile"] for c in cells]
    xs_c = [c["readout_total"] for c in cells]
    ys = [c["max_dev"] for c in cells]
    names = [str(c["q"]) for c in cells]
    rho = d["verdicts"]["spearman_C_vs_maxdev"]["rho"]
    p = d["verdicts"]["spearman_C_vs_maxdev"]["p_exact"]
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.8))
    for ax, x, xlab in ((axes[0], xs_pct, "rank percentile of $C(q)$"),
                        (axes[1], xs_c, "readout error $C(q)$")):
        ax.plot(x, ys, "o-", ms=4, lw=1.2, color="#08519c")
        for xx, yy, n in zip(x, ys, names):
            ax.annotate("q" + n, (xx, yy), textcoords="offset points",
                        xytext=(5, 5), fontsize=7)
        ax.axhline(0.05, color="k", ls=":", lw=1)
        ax.text(0.55, 0.05 * 1.15, "tolerance 0.05", fontsize=7)
        ax.set_xlabel(xlab)
        ax.set_ylim(0, 0.20)
    axes[0].set_ylabel("max deviation over $w$")
    axes[0].set_title("(a) deviation vs. rank")
    axes[1].set_title("(b) deviation vs. $C(q)$  (Spearman $\\rho_s=%.3f$, $p=%.3f$)" % (rho, p))
    fig.tight_layout()
    fig.savefig(OUT / "fig_router.pdf")
    fig.savefig(OUT / "fig_router.png", dpi=300)
    plt.close(fig)


if __name__ == "__main__":
    fig_sweep_2x2()
    fig_noise_vs_qpu()
    fig_ablation()
    fig_taxonomy()
    fig_router()
    print("figures ->", OUT)

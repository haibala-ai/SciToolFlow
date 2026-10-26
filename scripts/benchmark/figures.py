"""Publication-style figures for the benchmark README and exported reports."""

UPSTREAM = "#7185a2"
FLOW = "#227c77"
HARD = "#315877"
STANDARD = "#d7dfe7"
INK = "#243342"
GRID = "#e5e9ed"


def _pyplot():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.family": "STIXGeneral",
            "mathtext.fontset": "stix",
            "font.size": 11,
            "axes.titlesize": 12,
            "axes.labelsize": 11,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "axes.titlepad": 13,
            "axes.linewidth": 0.65,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.edgecolor": "#84919c",
            "axes.labelcolor": INK,
            "text.color": INK,
            "xtick.color": INK,
            "ytick.color": INK,
            "xtick.major.width": 0.6,
            "ytick.major.width": 0.6,
            "xtick.major.size": 3,
            "ytick.major.size": 3,
            "axes.axisbelow": True,
            "svg.fonttype": "none",
            "svg.hashsalt": "scitoolflow",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
        }
    )
    return plt


def _panel(ax, letter, title):
    ax.set_title(title, loc="left")
    ax.text(
        -0.13,
        1.065,
        "(" + letter + ")",
        transform=ax.transAxes,
        fontsize=12,
        fontweight="bold",
        va="bottom",
    )


def _save(fig, base):
    fig.savefig(
        str(base) + ".svg",
        bbox_inches="tight",
        metadata={"Creator": "SciToolFlow", "Date": None},
    )
    fig.savefig(
        str(base) + ".png",
        dpi=320,
        bbox_inches="tight",
        metadata={"Software": "SciToolFlow"},
    )
    fig.savefig(
        str(base) + ".pdf",
        bbox_inches="tight",
        metadata={"Creator": "SciToolFlow", "CreationDate": None, "ModDate": None},
    )


def plot_release_comparison(report, output):
    plt = _pyplot()
    from matplotlib.lines import Line2D

    fig, axes = plt.subplots(
        1, 3, figsize=(12.6, 3.9), gridspec_kw={"width_ratios": [0.88, 1.25, 1.02]}
    )
    fig.subplots_adjust(left=0.105, right=0.98, top=0.80, bottom=0.25, wspace=0.54)
    sources = [report["upstream"], report["scitoolflow"]]
    labels = ["SciToolEval L2", "SciToolFlow"]
    colors = [UPSTREAM, FLOW]
    ax = axes[0]
    for y, row, color in zip([1, 0], sources, colors):
        ax.barh(y, row["tasks"], height=0.40, color=color, zorder=3)
        ax.text(row["tasks"] + 12, y, f"{row['tasks']}", va="center", fontsize=11)
    ax.set_yticks([1, 0], labels)
    ax.tick_params(axis="y", length=0, pad=6)
    ax.set_xlim(0, 610)
    ax.set_ylim(-0.65, 1.65)
    ax.set_xticks([0, 200, 400, 600])
    ax.set_xlabel("Tasks")
    ax.grid(axis="x", color=GRID, linewidth=0.55)
    ax.text(
        0.98,
        0.95,
        f"+{report['change']['task_increase_percent']:.1f}% tasks",
        transform=ax.transAxes,
        ha="right",
        color=FLOW,
        fontsize=10,
    )
    _panel(ax, "a", "Benchmark scale")

    ax = axes[1]
    for row, color, style in zip(sources, colors, ["--", "-"]):
        hist = {int(k): v for k, v in row["reference_call_histogram"].items()}
        xs = [1.75]
        ys = [0]
        total = 0
        for x, n in sorted(hist.items()):
            total += n
            xs.append(x)
            ys.append(total / row["tasks"])
        xs.append(180)
        ys.append(1)
        ax.step(
            xs, ys, where="post", color=color, linestyle=style, linewidth=1.9, zorder=3
        )
        median = row["reference_calls_median"]
        ax.plot(
            [median, median],
            [0, 0.5],
            color=color,
            linewidth=0.8,
            linestyle=":",
            alpha=0.9,
        )
        ax.scatter([median], [0.5], s=18, color=color, zorder=4)
    ax.set_xscale("log", base=2)
    ax.set_xlim(1.75, 180)
    ax.set_ylim(0, 1.04)
    ax.set_xticks([2, 4, 8, 16, 32, 64, 128], [2, 4, 8, 16, 32, 64, 128])
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1], ["0", "25", "50", "75", "100"])
    ax.set_xlabel("Scientific calls per reference")
    ax.set_ylabel("Cumulative tasks (%)")
    ax.grid(color=GRID, linewidth=0.55)
    ax.text(
        0.97,
        0.10,
        f"Median: {sources[0]['reference_calls_median']:g} → {sources[1]['reference_calls_median']:g}\n"
        f"Maximum: {sources[0]['reference_calls_max']} → {sources[1]['reference_calls_max']}\n"
        f"Mean: {report['change']['reference_mean_ratio']:.2f}×",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=10,
        linespacing=1.6,
    )
    _panel(ax, "b", "Reference workflow length")

    ax = axes[2]
    for y, row, color in zip([1, 0], sources, colors):
        value = 100 * row["reference_tool_coverage"]
        ax.hlines(y, 0, value, color=color, linewidth=1.8, zorder=3)
        ax.scatter([value], [y], color=color, s=48, zorder=4)
        ax.text(value + 4, y + 0.11, f"{value:.2f}%", fontsize=11, va="bottom")
        ax.text(
            value + 4,
            y - 0.10,
            f"{row['covered_registered_tools']} / {row['scientific_tools']} tools",
            fontsize=9,
            va="top",
            color="#627180",
        )
    ax.set_yticks([1, 0], labels)
    ax.tick_params(axis="y", length=0, pad=5)
    ax.set_xlim(0, 100)
    ax.set_ylim(-0.65, 1.65)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xlabel("Coverage in own registry (%)")
    ax.grid(axis="x", color=GRID, linewidth=0.55)
    ax.text(
        0.98,
        0.95,
        f"Δ = +{report['change']['own_registry_coverage_increase_pp']:.2f} pp",
        transform=ax.transAxes,
        ha="right",
        color=FLOW,
        fontsize=10,
    )
    _panel(ax, "c", "Reference tool coverage")
    fig.legend(
        [
            Line2D([0], [0], color=UPSTREAM, linestyle="--", lw=1.8),
            Line2D([0], [0], color=FLOW, lw=1.8),
        ],
        ["SciToolEval Level2", "SciToolFlow"],
        loc="upper center",
        bbox_to_anchor=(0.53, 1.0),
        ncol=2,
        frameon=False,
        fontsize=11,
        handlelength=2.5,
        columnspacing=2.5,
    )
    fig.text(
        0.105,
        0.055,
        "Lengths: published paths (Level2) vs. actual executions (SciToolFlow). Tool coverage uses each dataset’s own registry.",
        fontsize=9,
        color="#617181",
    )
    _save(fig, output / "current")
    plt.close(fig)


def plot_benchmark_overview(stats, rows, output):
    plt = _pyplot()
    from matplotlib.patches import Patch

    fig, axes = plt.subplots(
        1, 3, figsize=(13.2, 4.15), gridspec_kw={"width_ratios": [1.12, 1.02, 1.16]}
    )
    fig.subplots_adjust(left=0.105, right=0.985, top=0.82, bottom=0.28, wspace=0.53)
    domains = ["Chemical", "Material", "Biology", "MachineLearning"]
    names = ["Chemistry", "Materials", "Biology / ecology", "ML / mathematics"]
    categories = ["high_difficulty", "tool_composition", "standard"]
    colors = [HARD, FLOW, STANDARD]
    ax = axes[0]
    for y, domain in enumerate(domains):
        left = 0
        for category, color in zip(categories, colors):
            count = sum(
                r["domain"] == domain and r["category"] == category for r in rows
            )
            if not count:
                continue
            ax.barh(
                y,
                count,
                left=left,
                height=0.53,
                color=color,
                edgecolor="white",
                linewidth=0.65,
                zorder=3,
            )
            ax.text(
                left + count / 2,
                y,
                str(count),
                ha="center",
                va="center",
                fontsize=9,
                color="white" if category != "standard" else INK,
            )
            left += count
        ax.text(left + 3, y, str(left), va="center", fontsize=10)
    ax.set_yticks(range(4), names)
    ax.invert_yaxis()
    ax.tick_params(axis="y", length=0, pad=5)
    ax.set_xlim(0, 163)
    ax.set_xticks([0, 50, 100, 150])
    ax.set_xlabel("Tasks")
    ax.grid(axis="x", color=GRID, linewidth=0.55)
    _panel(ax, "a", "Task composition")
    fig.legend(
        [Patch(facecolor=c) for c in colors],
        ["High difficulty", "Tool composition", "Standard"],
        loc="lower left",
        bbox_to_anchor=(0.102, 0.075),
        frameon=False,
        ncol=3,
        fontsize=9.5,
        handlelength=1,
        handleheight=0.8,
        columnspacing=1.2,
    )

    ax = axes[1]
    bins = [2, 4, 8, 16, 32, 64, 128, 256]
    histogram = stats["reference_scientific_calls"]["histogram"]
    counts = [
        sum(v for k, v in histogram.items() if a <= int(k) < b)
        for a, b in zip(bins[:-1], bins[1:])
    ]
    ax.bar(
        bins[:-1],
        counts,
        width=[b - a for a, b in zip(bins[:-1], bins[1:])],
        align="edge",
        color=FLOW,
        edgecolor="white",
        linewidth=1.0,
        alpha=0.92,
        zorder=3,
    )
    ax.set_xscale("log", base=2)
    ax.set_xlim(1.85, 275)
    ax.set_xticks(bins, [str(x) for x in bins])
    ax.set_xlabel(r"Scientific calls ($\log_2$ bins)")
    ax.set_ylabel("Tasks")
    ax.grid(axis="y", color=GRID, linewidth=0.55)
    values = stats["reference_scientific_calls"]
    ax.axvline(values["median"], color=HARD, linestyle="--", lw=1, zorder=4)
    ax.text(
        0.97,
        0.96,
        f"Median = {values['median']:g}\nMean = {values['mean']:.2f}\nMaximum = {values['max']}",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=10,
        linespacing=1.55,
    )
    _panel(ax, "b", "Reference execution length")

    ax = axes[2]
    tool_domains = domains + ["General"]
    tool_names = ["Chemistry", "Materials", "Biology", "ML / mathematics", "General"]
    for y, domain in enumerate(tool_domains):
        d = stats["domain_statistics"][domain]
        n = d["observed_successful_tools"]
        total = d["registered_scientific_tools"]
        value = 100 * n / total
        ax.barh(y, 100, color="#edf0f3", height=0.5, zorder=2)
        ax.barh(y, value, color=FLOW, height=0.5, zorder=3)
        ax.text(
            value - 2,
            y,
            f"{value:.1f}%",
            ha="right",
            va="center",
            color="white",
            fontsize=9,
        )
        ax.text(105, y, f"{n} / {total}", va="center", fontsize=9.5)
    ax.set_yticks(range(5), tool_names)
    ax.invert_yaxis()
    ax.tick_params(axis="y", length=0, pad=5)
    ax.set_xlim(0, 143)
    ax.set_xticks([0, 50, 100])
    ax.set_xlabel("Registered tools covered (%)")
    ax.spines["left"].set_visible(False)
    _panel(ax, "c", "Successful tool coverage")
    fig.text(
        0.105,
        0.02,
        "Primary references only (n = 500). Scientific calls exclude DescribeTools; repeated calls and failures remain in execution counts.",
        fontsize=9,
        color="#617181",
    )
    _save(fig, output / "overview")
    plt.close(fig)

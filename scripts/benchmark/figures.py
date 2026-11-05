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
    from pathlib import Path

    fig.savefig(
        str(base) + ".svg",
        bbox_inches="tight",
        metadata={"Creator": "SciToolFlow", "Date": None},
    )
    svg_path = Path(str(base) + ".svg")
    svg_path.write_text("\n".join(line.rstrip() for line in svg_path.read_text().splitlines()) + "\n")
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


def plot_mini_overview(stats, rows, output):
    """Describe task balance, observed workload and successful tool coverage."""
    from matplotlib.patches import Patch
    plt = _pyplot()
    fig, axes = plt.subplots(1, 3, figsize=(13.6, 4.2),
                             gridspec_kw={"width_ratios": [1.05, 1.05, 1.25]})
    fig.subplots_adjust(left=0.075, right=0.98, bottom=0.23, top=0.79, wspace=0.52)
    domains = ["Chemical", "Material", "Biology", "MachineLearning"]
    labels = ["Chemistry", "Materials", "Biology", "Math / ML"]
    ax = axes[0]
    designed = [stats["task_domains"][d]["origins"]["special100"] for d in domains]
    selected = [stats["task_domains"][d]["origins"]["full"] for d in domains]
    ax.barh(range(4), designed, color=HARD, height=0.52, label="Dedicated orchestration")
    ax.barh(range(4), selected, left=designed, color=FLOW, height=0.52, label="Selected from Full")
    for y, (a, b) in enumerate(zip(designed, selected)):
        ax.text(a / 2, y, str(a), ha="center", va="center", color="white", fontsize=10)
        ax.text(a + b / 2, y, str(b), ha="center", va="center", color="white", fontsize=10)
        ax.text(a + b + 1, y, str(a + b), va="center", fontsize=10)
    ax.set_yticks(range(4), labels); ax.invert_yaxis()
    ax.set_xlim(0, 59); ax.set_xticks([0, 25, 50]); ax.set_xlabel("Tasks")
    ax.grid(axis="x", color=GRID, linewidth=0.55)
    ax.tick_params(axis="y", length=0)
    _panel(ax, "a", "Balanced task design")

    ax = axes[1]
    intervals = [(1, 3), (4, 7), (8, 15), (16, 31), (32, float("inf"))]
    counts = [sum(lo <= row["scientific_calls"] <= hi for row in rows) for lo, hi in intervals]
    bars = ax.bar(range(5), counts, width=0.62, color=FLOW, zorder=3)
    ax.bar_label(bars, padding=4, fontsize=10)
    ax.set_xticks(range(5), ["1–3", "4–7", "8–15", "16–31", "32+"])
    ax.set_xlabel("Scientific calls per primary reference")
    ax.set_ylabel("Tasks"); ax.set_ylim(0, max(counts) * 1.27)
    ax.grid(axis="y", color=GRID, linewidth=0.55)
    _panel(ax, "b", "Observed execution workload")

    ax = axes[2]
    for y, domain in enumerate(domains + ["General"]):
        info = stats["tool_domains"][domain]
        value = info["coverage"] * 100
        ax.barh(y, 100, height=0.5, color=STANDARD, zorder=2)
        ax.barh(y, value, height=0.5, color=FLOW, zorder=3)
        ax.text(103, y, f"{info['observed_successful_tools']}/{info['registered_scientific_tools']}",
                va="center", fontsize=10)
    ax.set_yticks(range(5), labels + ["General"]); ax.invert_yaxis()
    ax.set_xlim(0, 127); ax.set_xticks([0, 25, 50, 75, 100], ["0", "25", "50", "75", "100"])
    ax.set_xlabel("Successful tool coverage (%)")
    ax.tick_params(axis="y", length=0); ax.grid(axis="x", color=GRID, linewidth=0.55)
    _panel(ax, "c", "Coverage by tool category")
    fig.legend(handles=[Patch(color=HARD, label="Dedicated orchestration tasks"),
                        Patch(color=FLOW, label="Full-selected tasks / observed coverage"),
                        Patch(color=STANDARD, label="Remaining registered tools")],
               loc="lower center", bbox_to_anchor=(0.52, 0.055), ncol=3, frameon=False, fontsize=10)
    fig.text(0.075, 0.95, "SciToolFlow Mini-200", fontsize=17, fontweight="bold")
    fig.text(0.075, 0.885,
             "200 tasks · 4 primary disciplines · 200 primary references · DescribeTools excluded",
             fontsize=11, color="#526475")
    _save(fig, output / "mini_overview")
    plt.close(fig)


def plot_release_comparison(report, output):
    """Compare Level2 with each released SciToolFlow suite independently."""
    from matplotlib.lines import Line2D
    plt = _pyplot()
    fig, axes = plt.subplots(1, 3, figsize=(13.6, 4.1),
                             gridspec_kw={"width_ratios": [0.95, 1.25, 1.1]})
    fig.subplots_adjust(left=0.11, right=0.98, top=0.78, bottom=0.23, wspace=0.55)
    sources = [report["upstream"], report["scitoolflow"], report["mini"]]
    labels = ["SciToolEval L2", "Full-500", "Mini-200"]
    colors = [UPSTREAM, HARD, FLOW]
    positions = [2, 1, 0]
    ax = axes[0]
    for y, row, color in zip(positions, sources, colors):
        ax.barh(y, row["tasks"], height=0.45, color=color, zorder=3)
        ax.text(row["tasks"] + 12, y, str(row["tasks"]), va="center", fontsize=11)
    ax.set_yticks(positions, labels); ax.tick_params(axis="y", length=0, pad=6)
    ax.set_xlim(0, 610); ax.set_ylim(-0.6, 2.6); ax.set_xticks([0, 200, 400, 600])
    ax.set_xlabel("Tasks"); ax.grid(axis="x", color=GRID, linewidth=0.55)
    _panel(ax, "a", "Benchmark scale")
    ax = axes[1]
    for row, color, style in zip(sources, colors, ["--", "-", "-."]):
        xs, ys, total = [1.75], [0], 0
        for x, n in sorted((int(k), v) for k, v in row["reference_call_histogram"].items()):
            total += n; xs.append(x); ys.append(total / row["tasks"])
        xs.append(180); ys.append(1)
        ax.step(xs, ys, where="post", color=color, linestyle=style, linewidth=1.9, zorder=3)
    ax.set_xscale("log", base=2); ax.set_xlim(1.75, 180); ax.set_ylim(0, 1.04)
    ax.set_xticks([2, 4, 8, 16, 32, 64, 128], [2, 4, 8, 16, 32, 64, 128])
    ax.set_yticks([0, .25, .5, .75, 1], ["0", "25", "50", "75", "100"])
    ax.set_xlabel("Scientific calls per reference"); ax.set_ylabel("Cumulative tasks (%)")
    ax.grid(color=GRID, linewidth=.55)
    _panel(ax, "b", "Reference execution burden")
    ax = axes[2]
    for y, row, color in zip(positions, sources, colors):
        value = 100 * row["reference_tool_coverage"]
        ax.hlines(y, 0, value, color=color, linewidth=1.8, zorder=3)
        ax.scatter([value], [y], color=color, s=48, zorder=4)
        ax.text(value + 3, y + .10, f"{value:.2f}%", fontsize=10, va="bottom")
        ax.text(value + 3, y - .10, f"{row['covered_registered_tools']} / {row['scientific_tools']} tools",
                fontsize=9, va="top", color="#627180")
    ax.set_yticks(positions, labels); ax.tick_params(axis="y", length=0, pad=5)
    ax.set_xlim(0, 100); ax.set_ylim(-.6, 2.6); ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xlabel("Coverage in own registry (%)"); ax.grid(axis="x", color=GRID, linewidth=.55)
    _panel(ax, "c", "Reference tool coverage")
    fig.legend([Line2D([0], [0], color=c, linestyle=st, lw=1.8)
                for c, st in zip(colors, ["--", "-", "-."])], labels,
               loc="upper center", bbox_to_anchor=(.53, 1.0), ncol=3, frameon=False, fontsize=11)
    _save(fig, output / "current")
    plt.close(fig)


def plot_full_mini_overview(full, mini, output):
    """One vector figure, with Full above Mini and consistent panel definitions."""
    plt = _pyplot()
    fig, axes = plt.subplots(2, 3, figsize=(13.6, 8.6),
                             gridspec_kw={"width_ratios": [1.05, 1.05, 1.2]})
    fig.subplots_adjust(left=.085, right=.98, bottom=.12, top=.88, wspace=.58, hspace=.82)
    domains = ["Chemical", "Material", "Biology", "MachineLearning"]
    labels = ["Chemistry", "Materials", "Biology", "Math / ML"]
    intervals = [(1, 3), (4, 7), (8, 15), (16, 31), (32, float("inf"))]
    for row, data, name, color in [(0, full, "Full-500", HARD), (1, mini, "Mini-200", FLOW)]:
        ytitle = .965 if row == 0 else .505
        fig.text(.085, ytitle, "SciToolFlow " + name, fontsize=17, fontweight="bold", color=color)
        fig.text(.085, ytitle - .036,
                 f"{data['tasks']} tasks · {data['tasks']} primary references · 472 scientific tools available",
                 fontsize=11, color="#526475")
        domain_info = data["domain_statistics"] if row == 0 else data["task_domains"]
        ax = axes[row, 0]
        values = [domain_info[d]["tasks"] for d in domains]
        bars = ax.barh(range(4), values, color=color, height=.52)
        ax.bar_label(bars, padding=4, fontsize=10)
        ax.set_yticks(range(4), labels); ax.invert_yaxis(); ax.tick_params(axis="y", length=0)
        ax.set_xlim(0, 165); ax.set_xticks([0, 50, 100, 150]); ax.set_xlabel("Tasks")
        ax.grid(axis="x", color=GRID, linewidth=.55)
        _panel(ax, chr(97 + 3 * row), "Primary task disciplines")
        ax = axes[row, 1]
        hist = {int(k): v for k, v in data["reference_scientific_calls"]["histogram"].items()}
        counts = [sum(n for k, n in hist.items() if lo <= k <= hi) for lo, hi in intervals]
        bars = ax.bar(range(5), counts, width=.62, color=color, zorder=3)
        ax.bar_label(bars, padding=4, fontsize=10)
        ax.set_xticks(range(5), ["1–3", "4–7", "8–15", "16–31", "32+"])
        ax.set_xlabel("Scientific calls per reference"); ax.set_ylabel("Tasks"); ax.set_ylim(0, 265)
        ax.grid(axis="y", color=GRID, linewidth=.55)
        _panel(ax, chr(98 + 3 * row), "Reference execution burden")
        tool_info = data["domain_statistics"] if row == 0 else data["tool_domains"]
        ax = axes[row, 2]
        for y, domain in enumerate(domains + ["General"]):
            info = tool_info[domain]
            covered, pool = info["observed_successful_tools"], info["registered_scientific_tools"]
            ax.barh(y, 100, color=STANDARD, height=.5, zorder=2)
            ax.barh(y, 100 * covered / pool, color=color, height=.5, zorder=3)
            ax.text(103, y, f"{covered}/{pool}", va="center", fontsize=10)
        ax.set_yticks(range(5), labels + ["General"]); ax.invert_yaxis()
        ax.tick_params(axis="y", length=0); ax.set_xlim(0, 127)
        ax.set_xticks([0, 25, 50, 75, 100]); ax.set_xlabel("Successful tool coverage (%)")
        ax.grid(axis="x", color=GRID, linewidth=.55)
        _panel(ax, chr(99 + 3 * row), "Coverage by tool category")
    fig.text(.085, .035,
             "Calls include failed attempts. Coverage counts successful registered names. DescribeTools is excluded.",
             fontsize=10, color="#526475")
    _save(fig, output / "full_mini_overview")
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

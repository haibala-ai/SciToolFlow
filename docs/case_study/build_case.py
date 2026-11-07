"""Build a trace-grounded SciMas case figure; no model or scientific tool calls.

Run from any directory with Python, NumPy and Matplotlib installed.
The source experiment is read-only. All outputs stay beside this script.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUN = ROOT / "exp/main_scimas"
TASK = "SMAS-0070"


def read(path):
    return json.loads(path.read_text())


def extract():
    path = RUN / "trajectories" / TASK / "trajectory.json"
    trace = read(path)
    score = next(x for x in read(RUN / "scores.json")["tasks"] if x["id"] == TASK)
    metrics = next(x for x in read(RUN / "task_metrics.json")["tasks"] if x["id"] == TASK)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    assert sha == score["evidence_integrity"]["trace_sha256"]
    assert score["runtime_completed"] and score["answer_correct"]
    calls = [c for s in trace["steps"] if s["type"] == "tools" for c in s["calls"]]
    science = [c for c in calls if c.get("kind") == "scientific"]
    assert len(science) == metrics["scientific_tool_calls"] == 11
    overlaps = []
    for i, a in enumerate(science):
        for b in science[i + 1:]:
            start = max(a["started_seconds"], b["started_seconds"])
            end = min(a["finished_seconds"], b["finished_seconds"])
            if end > start:
                overlaps.append({"nodes": [a["node"], b["node"]],
                                 "observations": [a["observation_id"], b["observation_id"]],
                                 "start_seconds": start, "end_seconds": end,
                                 "overlap_seconds": end - start})
    asset = ROOT / "tasks/mini-100/assets/SMAS-0070_water_source.qout"
    asset_sha = hashlib.sha256(asset.read_bytes()).hexdigest()
    assert asset_sha == trace["results"]["modes"]["output"]["source_sha256"]
    source = asset.read_text()
    orientation = source.split("Standard Nuclear Orientation (Angstroms)")[1]
    xyz = []
    for row in orientation.splitlines():
        match = re.match(r"\s*\d+\s+(O|H)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)", row)
        if match:
            xyz.append([float(v) for v in match.groups()[1:]])
        if len(xyz) == 3:
            break
    assert len(xyz) == 3
    modes = np.asarray(trace["results"]["modes"]["output"]["value"])
    # Independently cross-check the logged tensor and axes against the fixed source.
    block = source.split("IR Intens:")[1].split("TransDip")[0]
    printed = []
    for row in block.splitlines():
        if re.match(r"\s*[OH]\s+[-\d.]", row):
            printed.append([float(v) for v in row.split()[1:]])
    np.testing.assert_array_equal(modes, np.asarray(printed).reshape(3, 3, 3).transpose(1, 0, 2))
    frequencies = [float(v) for v in re.search(r"^ Frequency:\s*(.*)$", source, re.M)[1].split()]
    intensities = [float(v) for v in re.search(r"^ IR Intens:\s*(.*)$", source, re.M)[1].split()]
    answer = trace["final_answer"]
    M = modes.reshape(3, 9)
    W = M * np.array([4, 4, 4, 1, 1, 1, 1, 1, 1])
    computed = {"plain_gram": M @ M.T, "weighted_gram": W @ W.T,
                "plain_spectrum": np.linalg.eigvalsh(M @ M.T),
                "weighted_spectrum": np.linalg.eigvalsh(W @ W.T),
                "frequencies": frequencies, "ir_intensities": intensities,
                "intensity_fractions": np.array(intensities) / sum(intensities)}
    residuals = {}
    for field, value in computed.items():
        np.testing.assert_allclose(value, answer[field], rtol=1e-12, atol=1e-12)
        residuals[field] = float(np.max(np.abs(np.asarray(value) - answer[field])))
    candidates = []
    for tid, reason in [
        ("SMAS-0070", "主案例：振动模式、度量矩阵与真实局部修复，可结合科学可视化。"),
        ("SMAS-0004", "早停补充案例：三个连接体候选中两个被排除，四个后续描述符节点未执行。"),
        ("SMAS-0101", "科学歧义补充案例：质量与官能团证据仍允许两个结构异构体。"),
    ]:
        s = next(x for x in read(RUN / "scores.json")["tasks"] if x["id"] == tid)
        candidates.append({"id": tid, "reason": reason,
                           "answer_correct": s["answer_correct"],
                           "orchestration_credit": s["orchestration_credit"],
                           "tool_orchestration_score": s["tool_orchestration_score"]})
    evidence = {
        "task_id": TASK, "model": trace["model"], "variant": "full",
        "trace": str(path.relative_to(ROOT)), "trace_sha256": sha,
        "source_asset": str(asset.relative_to(ROOT)), "source_sha256": asset_sha,
        "selection": {"population": "Full Mini-100 selected result set",
                      "criteria": ["答案与编排通过", "科学结果可直观展示", "机制有真实执行证据"],
                      "candidates": candidates, "representativeness": "目的性案例选择，不是随机抽样或总体性能证据"},
        "question": trace["task"]["question"], "score": score, "metrics": metrics,
        "scientific_calls": [{k: c[k] for k in ["node", "tool", "observation_id", "status", "started_seconds", "finished_seconds"]} for c in science],
        "overlapping_execution_intervals": overlaps,
        "repair": {k: trace["repairs"][0][k] for k in ["request", "changes", "delta", "retained", "execution_evidence"]},
        "protocol_errors": trace["stats"]["protocol_errors"],
        "early_stop_triggered": bool(trace["gate_evaluations"]),
        "final_answer": answer, "source_geometry_angstrom": xyz,
        "source_mode_vectors": modes.tolist(), "independent_numeric_check": residuals,
        "figure_encoding": {
            "graph": "Final repaired task graph, with explicit repair annotation; not an execution timeline.",
            "molecules": "Source geometry and mode vectors projected into the molecular plane; arrows scaled uniformly by 1.05 and offset to the atom surface for readability, not physical amplitudes.",
            "matrix_table": "Signed Gram entries and ascending eigenvalues rounded to five decimal places.",
            "bar_chart": "IR intensity fractions in printed mode order, expressed as percentages.",
            "limits": ["No new quantum-chemistry calculation", "No early-stop event in this case",
                       "No cross-task experience-transfer or speedup claim", "Repair retained list is empty; IR completed in flight and was called once",
                       "One planner protocol error and one repeated mode read remain in the full trace"]}}
    (HERE / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    return evidence


BLUE, TEAL, RED, INK = "#42658b", "#338478", "#b45248", "#243449"


def draw(e):
    plt.rcParams.update({"font.family": "STIXGeneral", "font.size": 12,
                         "mathtext.fontset": "stix", "pdf.fonttype": 42,
                         "svg.fonttype": "none", "axes.spines.top": False,
                         "axes.spines.right": False})
    fig = plt.figure(figsize=(11, 10.6), facecolor="white")
    ax = fig.add_axes([0, 0, 1, 1]); ax.set(xlim=(0, 1), ylim=(0, 1)); ax.axis("off")
    pink, green, gold = "#efa6b1", "#a4ce85", "#efcf73"
    dark = "#222222"

    def text(x, y, s, size=12, **kw):
        return ax.text(x, y, s, fontsize=size, color=dark, **kw)

    def arrow(a, b, color=pink, style="-|>", lw=1.3, **kw):
        ax.add_patch(FancyArrowPatch(a, b, arrowstyle=style, mutation_scale=13,
                                    color=color, lw=lw, zorder=2, **kw))

    def frame(x, y, w, h, title, edge, fill):
        outer = FancyBboxPatch((x,y), w,h,boxstyle="round,pad=0,rounding_size=0.022",
                               fc="white",ec=edge,lw=1.15,zorder=0)
        ax.add_patch(outer)
        band = plt.Rectangle((x,y+h-.031),w,.031,fc=fill,ec="none",zorder=.5)
        band.set_clip_path(outer);ax.add_patch(band)
        ax.plot([x,x+w],[y+h-.031,y+h-.031],color=edge,lw=.8,zorder=1)
        text(x+w/2,y+h-.0155,title,14,ha="center",va="center",weight="bold")

    def box(x,y,w,h,label,fill="#fbe9ed",size=12,edge="none"):
        ax.add_patch(FancyBboxPatch((x-w/2,y-h/2),w,h,boxstyle="round,pad=0.005,rounding_size=0.008",
                                   fc=fill,ec=edge,lw=.8,zorder=3))
        text(x,y,label,size,ha="center",va="center",linespacing=1.1,zorder=4)

    text(.009,.978,"a",17,weight="bold")
    frame(.032,.855,.445,.13,"Query",gold,"#fff3cd")
    text(.048,.937,"Audit three water vibration modes and IR intensities.\n"
         "Compare ordinary and O:H = 16:1 weighted metrics;\n"
         "preserve printed mode order.",12.8,va="top",linespacing=1.32)
    frame(.525,.855,.443,.13,"Planning",green,"#e6f2db")
    text(.543,.936,"1. Parse modes, frequencies and intensities.\n"
         "2. Build ordinary and weighted Gram matrices.\n"
         "3. Check spectra and normalize IR intensities.",12.8,va="top",linespacing=1.32)
    arrow((.486,.918),(.518,.918),gold,style="simple",lw=0)
    arrow((.747,.852),(.747,.829),green,style="simple",lw=0)
    arrow((.252,.852),(.252,.829),gold,style="simple",lw=0)

    frame(.032,.494,.936,.332,"SciMas Task Graph",pink,"#f9dce2")
    # Dependency graph: grouped read operations, with the real local shape repair below.
    box(.163,.710,.228,.130,
        "ReadQChemFrequencyModes\n\nReadQChemIRIntensities\n\nGetMolecularFrequencies",size=11.6)
    box(.407,.748,.170,.060,"ScaleNumericMatrix\n"+r"$M:\;3\times9$",size=12)
    box(.628,.755,.167,.054,"MatrixMultiply\n"+r"$G=MM^{\mathsf{T}}$",size=12)
    box(.851,.755,.198,.054,"SymmetricEigen\nDecomposition",size=12)
    box(.628,.655,.167,.054,"ScaleNumericMatrix\n"+r"$MD$",size=12)
    box(.851,.655,.198,.054,"MatrixMultiply\n"+r"$G_D=(MD)(MD)^{\mathsf{T}}$",size=12)
    box(.851,.559,.198,.054,"SymmetricEigen\nDecomposition",size=12)
    box(.407,.655,.170,.054,"NormalizeNumericRows\n"+r"$f_i=I_i/I_{\mathrm{total}}$",size=11.6)
    box(.162,.596,.223,.028,"Frequencies",fill="#fdefe4",size=12)
    arrow((.282,.747),(.315,.747))
    arrow((.498,.749),(.538,.754))
    arrow((.498,.729),(.538,.659))
    arrow((.716,.755),(.746,.755))
    arrow((.716,.655),(.746,.655))
    arrow((.851,.623),(.851,.592))
    arrow((.282,.688),(.315,.662))
    arrow((.162,.640),(.162,.615),color="#555555",linestyle=":")
    text(.851,.710,r"$\lambda(G)$",12,ha="center")
    text(.851,.514,r"$\lambda(G_D)$",12,ha="center")
    box(.407,.596,.170,.028,"IR fractions",fill="#fdefe4",size=12)
    arrow((.407,.623),(.407,.615),color="#555555",linestyle=":")
    # Local repair shown as a miniature tensor-to-matrix operation, rather than prose.
    ax.add_patch(FancyBboxPatch((.055,.510),.641,.059,boxstyle="round,pad=0.003,rounding_size=0.008",
                              fc="#fff9ee",ec="#e5c18a",lw=.9,zorder=1))
    text(.071,.548,"Reviewer",11.2,weight="bold",va="center")
    text(.071,.526,r"$3\times3\times3\;\ne\;3\times9$",11.3,va="center")
    for k in range(3):
        for i in range(3):
            for j in range(3):
                ax.add_patch(plt.Rectangle((.234+j*.009+k*.008,.521+i*.009+k*.005),.009,.009,
                                          fc="#f3d9de",ec="#cb929c",lw=.45,zorder=3+k*.1))
    arrow((.299,.539),(.376,.539),color="#bb9567")
    text(.338,.554,"Repairer",10.5,ha="center")
    for i in range(3):
        for j in range(9):
            ax.add_patch(plt.Rectangle((.385+j*.009,.525+i*.009),.009,.009,
                                      fc="#e4efdc",ec="#9fbc88",lw=.45,zorder=4))
    text(.502,.542,"Explicit flatten",11.7,va="center")
    text(.502,.524,r"$3\times9\;\longrightarrow\;M$",11.7,va="center")
    # Dotted feedback refers back to the repaired flattening operation.
    arrow((.695,.540),(.724,.540),color="#bc9673",linestyle="--")
    ax.plot([.724,.724,.515],[.54,.705,.705],color="#bc9673",lw=1,ls="--")
    arrow((.515,.705),(.485,.727),color="#bc9673",linestyle="--")

    # Booktabs-style numerical result table, as in the reference figure.
    text(.009,.466,"b",17,weight="bold")
    left,right=.032,.968
    ax.hlines([.469,.430,.365,.300],left,right,colors="#222222",linewidths=[1.1,.8,.6,1.1])
    text(.122,.448,"Metric",13.4,weight="bold",ha="center",va="center")
    text(.431,.448,"Gram matrix",13.4,weight="bold",ha="center",va="center")
    text(.783,.448,"Ascending eigenvalues",13.4,weight="bold",ha="center",va="center")
    ans=e["final_answer"]
    for row,(field,eig,name) in enumerate([("plain_gram","plain_spectrum",r"Ordinary $G$"),
                                          ("weighted_gram","weighted_spectrum",r"Weighted $G_D$")]):
        y=.397-row*.065
        text(.122,y,name,13,ha="center",va="center")
        mat=np.array(ans[field])
        for i in range(3):
            for j in range(3):
                text(.322+j*.109,y+.017-i*.017,f"{mat[i,j]:.5f}",11.4,ha="center",va="center")
        # Explicit brackets make the 3 x 3 layout unambiguous.
        ax.plot([.268,.260,.260,.268],[y+.026,y+.026,y-.026,y-.026],color="#333333",lw=.8)
        ax.plot([.593,.601,.601,.593],[y+.026,y+.026,y-.026,y-.026],color="#333333",lw=.8)
        text(.786,y,"["+", ".join(f"{v:.5f}" for v in ans[eig])+"]",12.3,ha="center",va="center")

    text(.009,.279,"c",17,weight="bold")
    text(.609,.279,"d",17,weight="bold")
    # Source-derived molecule projections; uniform magnification of displacement vectors.
    xyz=np.array(e["source_geometry_angstrom"]);xyz-=xyz[0]
    u=xyz[1]/np.linalg.norm(xyz[1]);v=xyz[2]-np.dot(xyz[2],u)*u;v/=np.linalg.norm(v)
    basis=np.stack([u,v],axis=1);xy=xyz@basis
    bisector=xy[1]/np.linalg.norm(xy[1])+xy[2]/np.linalg.norm(xy[2])
    theta=np.pi/2-np.arctan2(bisector[1],bisector[0])
    rot=np.array([[np.cos(theta),np.sin(theta)],[-np.sin(theta),np.cos(theta)]])
    xy=xy@rot;projected=np.array(e["source_mode_vectors"])@basis@rot
    colors=["#83cfce","#f2a493","#abb8e6"]
    for i in range(3):
        ma=fig.add_axes([.025+i*.194,.075,.192,.183]);ma.set_aspect("equal");ma.axis("off")
        for j in [1,2]:
            ma.plot(xy[[0,j],0],xy[[0,j],1],color="#abb0b6",lw=7,zorder=1,solid_capstyle="round")
            ma.plot(xy[[0,j],0],xy[[0,j],1]+.018,color="#d9dde0",lw=2,zorder=2,solid_capstyle="round")
        for j in range(3):
            center=xy[j];radius=.15 if j==0 else .105
            # Layered vector circles give ball-and-stick depth without raster assets.
            for layer in range(16):
                t=layer/15
                base=np.array(matplotlib.colors.to_rgb("#c64440" if j==0 else "#aab9ca"))
                color=base*(1-.55*t)+np.ones(3)*.55*t
                ma.add_patch(plt.Circle(center+np.array([-.027,.035])*t,radius*(1-.75*t),fc=color,ec="none",zorder=3+layer*.01))
            ma.text(*center,"O" if j==0 else "H",ha="center",va="center",fontsize=10,color="#222222",zorder=4)
            vector=projected[i,j]
            start=center+(radius+.025)*vector/np.linalg.norm(vector)
            dest=start+1.05*vector
            ma.add_patch(FancyArrowPatch(start,dest,arrowstyle="-|>",mutation_scale=12,
                                         color="#344b6e",lw=1.6,zorder=5,shrinkA=0,shrinkB=0))
        ma.set(xlim=(-1.6,1.6),ylim=(-.48,1.7))
        ma.text(0,-.38,f"Mode {i+1}",ha="center",va="top",fontsize=12.5)
        ma.text(0,-.67,f"{ans['frequencies'][i]:.2f} cm$^{{-1}}$",ha="center",va="top",fontsize=11.5)
    text(.315,.031,"Water normal modes",13.5,ha="center")
    bars=fig.add_axes([.674,.074,.286,.183])
    x=np.arange(3);values=np.array(ans['intensity_fractions'])*100
    bars.bar(x,values,color=colors,width=.52)
    for i,value in enumerate(values):bars.text(i,value+1.5,f"{value:.2f}",ha="center",fontsize=11)
    bars.set_xticks(x,["Mode 1","Mode 2","Mode 3"])
    bars.set_ylim(0,59);bars.set_yticks([0,20,40]);bars.set_ylabel("IR intensity fraction / %",fontsize=12)
    bars.tick_params(labelsize=11,direction="out",length=3)
    bars.spines['left'].set_color('#555555');bars.spines['bottom'].set_color('#555555')
    bars.set_xlabel("Printed mode order",fontsize=12,labelpad=6)
    for ext in ["svg","pdf","png"]:
        fig.savefig(HERE/f"SMAS-0070.{ext}",dpi=220,facecolor="white",
                    metadata={"Creator":"SciMas case study; build_case.py"} if ext!="png" else None)
        if ext == "svg":
            path = HERE / "SMAS-0070.svg"
            path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")
    plt.close(fig)


if __name__ == "__main__":
    evidence=extract();draw(evidence)
    print(json.dumps({"task": TASK, "scientific_calls":len(evidence["scientific_calls"]),
                      "overlaps":len(evidence["overlapping_execution_intervals"]),
                      "max_numeric_error":max(evidence["independent_numeric_check"].values()),
                      "output":str(HERE)},ensure_ascii=False))

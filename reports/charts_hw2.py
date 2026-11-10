"""Charts of REPORT.md (homework 2), drawn from the result files in git; no model calls.

    make report-charts      # -> reports/hw2/*.png

  retrieval.png      MRR of the search configurations of step 2 (results/rag/retrieval_dev.json)
  fusion.png         the hybrid alone: MRR by the weight of BM25 in RRF, against vector search alone
  prompts.png        prompts v1 / v2 / v3 of the answers on dev, k = 5 (results/rag/answers_dev_v*.jsonl)
  dev_test.png       the final system on dev and on test (evals/results/{dev,test}.json)
  calibration.png    the judge against the manual labels (evals/calibration/judge_v1.jsonl)
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "reports" / "hw2"
# the first three slots of the categorical palette of the dataviz reference (distinct for colour-blind readers)
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK_2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"

RETRIEVAL = [   # (key of retrieval_dev.json, label)
    ("A vector | structural | minilm", "vector, MiniLM (lecture)"),
    ("A vector | structural | mpnet", "vector, mpnet"),
    ("B bm25 (lemma) | structural", "BM25, dictionary forms"),
    ("A vector | structural | e5", "vector, e5"),
    ("B hybrid | structural | e5", "hybrid (BM25 + e5)"),
    ("B hybrid + rerank jina | structural | e5", "hybrid + reranker jina"),
    ("B hybrid + rerank bge | structural | e5", "hybrid + reranker bge"),
    ("C hybrid + filters | structural | e5", "hybrid + filters"),
    ("F hybrid + rerank bge + filters | bm25 stem6, rrf, bm25 weight 1.0 (checkpoint hw2-v1) | e5",
     "hybrid + bge + filters, checkpoint"),
    ("F hybrid + rerank bge + filters | bm25 lemma, rrf, bm25 weight 0.3 (chosen) | e5",
     "hybrid + bge + filters, final"),
]
WEIGHTS = (1.0, 0.5, 0.3, 0.2, 0.15, 0.1)


def style():
    import matplotlib
    matplotlib.use("Agg")
    import seaborn as sns

    sns.set_theme(style="whitegrid", rc={
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": GRID, "grid.color": GRID, "grid.linewidth": 0.8,
        "text.color": INK, "axes.labelcolor": INK_2, "xtick.color": INK_2, "ytick.color": INK_2,
        "axes.titleweight": "bold", "axes.titlesize": 12, "axes.titlelocation": "left",
        "font.size": 10, "legend.frameon": False})
    return sns


def save(fig, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / name, dpi=150, bbox_inches="tight")
    print(f"  reports/hw2/{name}")


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.open(encoding="utf-8")]


# ---------------------------------------------------------------- data

def retrieval_data(path: Path) -> list[tuple[str, float, bool]]:
    res = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for key, label in RETRIEVAL:
        if key in res:
            out.append((label, res[key]["MRR"], label.endswith("final")))
        else:
            print(f"  (not in {path.name}: {key})")
    return out


def fusion_data(path: Path) -> dict:
    res = json.loads(path.read_text(encoding="utf-8"))
    lines = {}
    for tokens, label in (("stem6", "BM25 on 6-letter stems"), ("lemma", "BM25 on dictionary forms")):
        pts = [(w, res[k]["MRR"]) for w in WEIGHTS
               if (k := f"F hybrid | bm25 {tokens}, rrf, bm25 weight {w} | e5") in res]
        if pts:
            lines[label] = pts
    vector = res.get("A vector | structural | e5", {}).get("MRR")
    return {"lines": lines, "vector": vector}


def prompt_data(results: Path, testset: Path, k: int = 5) -> dict[str, dict[str, float]]:
    from agro.rag.verify import key_facts_found

    questions = {q["id"]: q for q in _jsonl(testset)}
    out = {}
    for version in ("v1", "v2", "v3"):
        path = results / f"answers_dev_{version}.jsonl"
        if not path.exists():
            continue
        rows = [r for r in _jsonl(path) if r["k"] == k]
        ans = [r for r in rows if questions[r["id"]]["sources"]]
        no = [r for r in rows if not questions[r["id"]]["sources"]]

        def cited(r):
            q, docs = questions[r["id"]], {c["doc_id"] for c in r["citations"]}
            exp = [s["doc_id"] for s in q["sources"]]
            return any(d in docs for d in exp) if q.get("match") == "any" else all(d in docs for d in exp)

        answered = [r for r in ans if r["outcome"] == "answer"]
        out[version] = {
            "correct\n(key facts)": sum(all(key_facts_found(r["text"], questions[r["id"]]["key_facts"]))
                                       for r in answered) / len(ans),
            "expected source\ncited": sum(cited(r) for r in answered) / len(ans),
            "refused when there\nis no answer": sum(r["outcome"] != "answer" for r in no) / len(no),
        }
    return out


DEV_TEST = [("pass", "pass"), ("judge_correct", "correct\n(judge)"), ("judge_grounded", "grounded\n(judge)"),
            ("abstained_no_answer", "refused when\nno answer"), ("recall@5", "recall@5\n(search)"),
            ("MRR", "MRR\n(search)")]


def dev_test_data(results: Path) -> dict[str, dict[str, float]]:
    out = {}
    for split in ("dev", "test"):
        path = results / f"{split}.json"
        if path.exists():
            m = json.loads(path.read_text(encoding="utf-8"))["metrics"]
            out[split] = {label: m[key]["mean"] for key, label in DEV_TEST}
    return out


def calibration_data(path: Path) -> dict[str, list[list[int]]]:
    rows = _jsonl(path)
    out = {}
    for verdict in ("correct", "grounded"):
        m = [[0, 0], [0, 0]]                  # rows: human yes / no, columns: judge yes / no
        for r in rows:
            m[0 if r[f"human_{verdict}"] else 1][0 if r[verdict] else 1] += 1
        out[verdict] = m
    return out


# ---------------------------------------------------------------- charts

def chart_retrieval(data) -> None:
    import matplotlib.pyplot as plt

    labels = [d[0] for d in data]
    values = [d[1] for d in data]
    fig, ax = plt.subplots(figsize=(8, 0.42 * len(data) + 1.2))
    bars = ax.barh(labels, values, color=[ORANGE if d[2] else BLUE for d in data], height=0.6)
    ax.invert_yaxis()
    ax.bar_label(bars, labels=[f"{v:.3f}" for v in values], padding=4, color=INK_2, fontsize=9)
    ax.set_xlim(0, 1)
    ax.set_xlabel("MRR on the dev questions with an answer (1 = the right chunk always first)")
    ax.set_title("Search: from vector search to the final chain")
    ax.grid(axis="y", visible=False)
    save(fig, "retrieval.png")


def chart_fusion(data) -> None:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    pos = {w: i for i, w in enumerate(WEIGHTS)}          # equal steps: the weights are the settings tried
    for (label, pts), color, dy in zip(data["lines"].items(), (BLUE, AQUA), (-14, 8)):
        xs, ys = zip(*pts)
        ax.plot([pos[x] for x in xs], ys, marker="o", markersize=7, linewidth=2, color=color, label=label)
        ax.annotate(f"{ys[-1]:.3f}", (pos[xs[-1]], ys[-1]), textcoords="offset points", xytext=(8, dy),
                    color=INK_2, fontsize=9)
    if data["vector"] is not None:
        ax.axhline(data["vector"], color=INK_2, linewidth=1.5, linestyle="--")
        ax.annotate(f"vector search alone: {data['vector']:.3f}", (0, data["vector"]), textcoords="offset points",
                    xytext=(0, -14), color=INK_2, fontsize=9)
    ax.set_xticks(range(len(WEIGHTS)))
    ax.set_xticklabels([f"{w:g}" for w in WEIGHTS])
    ax.set_xlim(-0.3, len(WEIGHTS) - 0.3)
    ax.set_xlabel("weight of BM25 in reciprocal rank fusion (1 = BM25 and vector lists count the same)")
    ax.set_ylabel("MRR, hybrid without reranker")
    ax.set_title("The hybrid alone: less BM25 is better on this corpus")
    ax.legend(loc="center left")
    save(fig, "fusion.png")


def grouped(ax, data: dict[str, dict[str, float]], colors) -> None:
    import numpy as np

    groups = list(next(iter(data.values())))
    n = len(data)
    width = 0.8 / n
    x = np.arange(len(groups))
    for i, ((series, values), color) in enumerate(zip(data.items(), colors)):
        bars = ax.bar(x + (i - (n - 1) / 2) * width, [values[g] for g in groups], width * 0.92,
                      color=color, label=series)
        ax.bar_label(bars, labels=[f"{values[g]:.2f}" for g in groups], padding=2, fontsize=8, color=INK_2)
    ax.set_xticks(x)
    ax.set_xticklabels(groups)
    ax.set_ylim(0, 1.12)
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=n)


def chart_prompts(data) -> None:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    grouped(ax, {f"prompt {v}": d for v, d in data.items()}, (BLUE, ORANGE, AQUA))
    ax.set_ylabel("share of the dev questions")
    ax.set_title("Answers on dev (k = 5): prompts v1, v2, v3")
    save(fig, "prompts.png")


def chart_dev_test(data) -> None:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 4.4))
    grouped(ax, data, (BLUE, ORANGE))
    ax.set_title("The final system on dev (tuned on it) and on test (held out), 3 runs")
    save(fig, "dev_test.png")


def chart_calibration(data) -> None:
    import matplotlib.pyplot as plt
    import seaborn as sns

    fig, axes = plt.subplots(1, 2, figsize=(7.5, 3.2))
    for ax, (verdict, m) in zip(axes, data.items()):
        sns.heatmap(m, ax=ax, annot=True, fmt="d", cbar=False, cmap="Blues", vmin=0, vmax=max(map(max, m)),
                    linewidths=2, linecolor=SURFACE, annot_kws={"fontsize": 13},
                    xticklabels=["judge: yes", "judge: no"], yticklabels=["human: yes", "human: no"])
        agree = m[0][0] + m[1][1]
        ax.set_title(f"{verdict}: {agree} of {sum(map(sum, m))} agree")
        ax.tick_params(left=False, bottom=False)
    fig.suptitle("The judge against the manual labels (23 dev answers)", x=0.02, ha="left", fontweight="bold")
    fig.tight_layout()
    save(fig, "calibration.png")


def main() -> None:
    style()
    print("Charts:")
    rag = ROOT / "results" / "rag"
    if (rag / "retrieval_dev.json").exists():
        chart_retrieval(retrieval_data(rag / "retrieval_dev.json"))
        chart_fusion(fusion_data(rag / "retrieval_dev.json"))
    prompts = prompt_data(rag, ROOT / "evals" / "testset_dev.jsonl")
    if prompts:
        chart_prompts(prompts)
    dev_test = dev_test_data(ROOT / "evals" / "results")
    if dev_test:
        chart_dev_test(dev_test)
    judge = ROOT / "evals" / "calibration" / "judge_v1.jsonl"
    if judge.exists():
        chart_calibration(calibration_data(judge))


if __name__ == "__main__":
    main()

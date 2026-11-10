"""Manual labels for the calibration of the judge (homework 2, step 4).

    make evals-label-dump    # answers to label -> evals/calibration/to_label.xlsx
    (fill the columns `correct` and `grounded` in Excel / LibreOffice, save the file under the same name)
    make evals-label-load    # the filled table -> evals/calibration/labels.jsonl

Which answers: the dev answers of the system (prompt v2, k = 5) to every question it answered, and,
to have wrong answers too, every other answer of the dev runs (prompt v1 and v2, k = 3 / 5 / 10) that the
key facts mark wrong, at most one per question. Refusals are not labelled: "not in the documents"
where it is needed is scored by the code.

The labelling is blind: the table shows no prompt version, no k and no automatic verdict, and the rows are
shuffled (fixed seed), so the labels are independent of the judge and of the key facts. Which answer a
row is (`L01` ... ) is in evals/calibration/selection.jsonl.

Labels (the same definitions are given to the judge):
  correct   1: the answer answers the question and agrees with the expected answer in meaning (language
            and wording do not matter, extra details from the documents are fine); 0: a wrong or missing
            value, another period or place, a part of the question left unanswered
  grounded  1: every statement of the answer is supported by the chunks given to the model; 0: something
            is not in the chunks (outside knowledge, a computed number, a value of another row or period)
"""

import json
import random
from collections import Counter

from agro.common.settings import RESULTS_RAG, ROOT
from agro.rag.chunking import load_chunks
from agro.rag.testset import load
from agro.rag.verify import key_facts_found

CALIBRATION = ROOT / "evals" / "calibration"
TO_LABEL = CALIBRATION / "to_label.xlsx"
SELECTION = CALIBRATION / "selection.jsonl"
LABELS = CALIBRATION / "labels.jsonl"
AGREEMENT = CALIBRATION / "agreement.md"
RUNS = (("v2", RESULTS_RAG / "answers_dev_v2.jsonl"), ("v1", RESULTS_RAG / "answers_dev_v1.jsonl"))
SYSTEM = ("v2", 5)
SEED = 20261110

GUIDE = [
    ("Що оцінити", "Для кожного рядка поставте 1 або 0 у колонках correct і grounded. Колонку comment — за бажанням."),
    ("correct", "1 — відповідь відповідає на питання і за змістом збігається з очікуваною відповіддю (мова й "
                "формулювання не важливі, додаткові деталі з документів — не помилка). 0 — неправильне чи "
                "відсутнє значення, інший період чи місце, частина питання без відповіді."),
    ("grounded", "1 — кожне твердження відповіді підтверджене фрагментами, які отримала модель (колонки "
                 "cited chunks і other chunks). 0 — щось не з фрагментів: знання ззовні, обчислене число, "
                 "значення з іншого рядка таблиці чи іншого періоду. Оцінюйте незалежно від correct."),
    ("Важливо", "Оцінюйте до того, як побачите оцінки судді. Рядки перемішані; версії промпту й автоматичних "
                "оцінок у таблиці немає навмисно."),
]


def _chunk_text(chunks: dict, chunk_id: str) -> str:
    c = chunks.get(chunk_id)
    return f"{c.header}\n{c.text}" if c else f"(chunk {chunk_id} is not in data/rag/chunks.jsonl)"


def select() -> list[dict]:
    questions = {q["id"]: q for q in load("dev")}
    records = []
    for version, path in RUNS:
        for line in path.open(encoding="utf-8"):
            r = json.loads(line)
            r["version"] = version
            records.append(r)
    records.sort(key=lambda r: (r["version"], r["k"]) != SYSTEM)          # the answers of the system first
    seen, chosen, wrong_per_q = set(), [], Counter()
    for r in records:
        if r["outcome"] != "answer":
            continue
        q = questions[r["id"]]
        key = (r["id"], r["text"].strip())
        if key in seen:
            continue
        correct_by_facts = all(key_facts_found(r["text"], q["key_facts"]))
        system = (r["version"], r["k"]) == SYSTEM
        if system or (not correct_by_facts and wrong_per_q[r["id"]] < 1):
            seen.add(key)
            chosen.append(r | {"correct_by_facts": correct_by_facts, "system": system})
            if not system:
                wrong_per_q[r["id"]] += 1
    random.Random(SEED).shuffle(chosen)
    for n, r in enumerate(chosen, 1):
        r["label_id"] = f"L{n:02d}"
    return chosen


def dump() -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font
    from openpyxl.worksheet.datavalidation import DataValidation

    questions = {q["id"]: q for q in load("dev")}
    chunks = {c.chunk_id: c for c in load_chunks()}
    chosen = select()
    CALIBRATION.mkdir(parents=True, exist_ok=True)
    if TO_LABEL.exists():
        raise SystemExit(f"{TO_LABEL.relative_to(ROOT)} exists: it may hold your labels. Rename it to dump again.")
    wb = Workbook()
    ws = wb.active
    ws.title = "label"
    head = ["label_id", "question", "expected answer", "answer", "cited chunks", "other chunks given",
            "correct", "grounded", "comment"]
    ws.append(head)
    for r in chosen:
        q = questions[r["id"]]
        cited = {c["chunk_id"]: c["n"] for c in r["citations"]}
        cited_text = "\n\n".join(f"[{n}] {_chunk_text(chunks, cid)}" for cid, n in cited.items())
        other = "\n\n".join(f"[{i}] {_chunk_text(chunks, cid)}" for i, cid in enumerate(r["context"], 1)
                            if cid not in cited)
        ws.append([r["label_id"], q["question"], q["expected_answer"], r["text"], cited_text, other, None, None, None])
    widths = [9, 40, 40, 60, 80, 60, 10, 10, 30]
    for col, w in zip("ABCDEFGHI", widths):
        ws.column_dimensions[col].width = w
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    for cell in ws[1]:
        cell.font = Font(bold=True)
    ws.freeze_panes = "B2"
    dv = DataValidation(type="list", formula1='"1,0"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f"G2:H{len(chosen) + 1}")
    guide = wb.create_sheet("how to label")
    for row in GUIDE:
        guide.append(list(row))
    guide.column_dimensions["A"].width = 14
    guide.column_dimensions["B"].width = 120
    for row in guide.iter_rows():
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    wb.save(TO_LABEL)
    with SELECTION.open("w", encoding="utf-8") as f:
        for r in chosen:
            f.write(json.dumps({"label_id": r["label_id"], "id": r["id"], "prompt": r["version"], "k": r["k"],
                                "system": r["system"], "correct_by_facts": r["correct_by_facts"],
                                "question": r["question"], "answer": r["text"], "context": r["context"],
                                "citations": [c["chunk_id"] for c in r["citations"]]}, ensure_ascii=False) + "\n")
    n_sys = sum(r["system"] for r in chosen)
    print(f"{len(chosen)} answers to label ({n_sys} of the system, {len(chosen) - n_sys} wrong by the key facts) "
          f"-> {TO_LABEL.relative_to(ROOT)}; which is which: {SELECTION.relative_to(ROOT)}")


def load_labels() -> None:
    from openpyxl import load_workbook

    ws = load_workbook(TO_LABEL, read_only=True)["label"]
    rows = list(ws.iter_rows(values_only=True))
    head = [str(h) for h in rows[0]]
    selection = {json.loads(line)["label_id"]: json.loads(line) for line in SELECTION.open(encoding="utf-8")}
    out, problems = [], []
    for row in rows[1:]:
        r = dict(zip(head, row))
        if not r.get("label_id"):
            continue
        labels = {}
        for name in ("correct", "grounded"):
            v = r.get(name)
            v = str(int(v)) if isinstance(v, (int, float)) else (str(v).strip() if v is not None else "")
            if v not in ("0", "1"):
                problems.append(f"{r['label_id']}: {name} is {r.get(name)!r}, must be 1 or 0")
            labels[name] = v == "1"
        out.append(selection[r["label_id"]] | labels | {"comment": r.get("comment") or ""})
    if problems:
        raise SystemExit("\n".join(["Not saved:"] + problems))
    with LABELS.open("w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(out)} labels -> {LABELS.relative_to(ROOT)}: correct {sum(r['correct'] for r in out)}, "
          f"grounded {sum(r['grounded'] for r in out)}")


# ---------------------------------------------------------------- the judge against the labels

def agreement(pairs: list[tuple[bool, bool]]) -> dict:
    """pairs: (human, judge). false pass: the judge says yes where the human says no; false fail: the reverse.
    Cohen's kappa: agreement beyond what two raters with these shares of "yes" would reach by chance."""
    n = len(pairs)
    agree = sum(h == j for h, j in pairs)
    fp = sum(j and not h for h, j in pairs)
    ff = sum(h and not j for h, j in pairs)
    ph, pj = sum(h for h, _ in pairs) / n, sum(j for _, j in pairs) / n
    chance = ph * pj + (1 - ph) * (1 - pj)
    kappa = (agree / n - chance) / (1 - chance) if chance < 1 else 1.0
    return {"n": n, "agree": agree, "agreement": agree / n, "false_pass": fp, "false_fail": ff,
            "human_yes": sum(h for h, _ in pairs), "judge_yes": sum(j for _, j in pairs), "kappa": kappa}


def calibrate() -> dict:
    from evals.judge import Judge, chunks_for

    labels = [json.loads(line) for line in LABELS.open(encoding="utf-8")]
    questions = {q["id"]: q for q in load("dev")}
    by_id = {c.chunk_id: c for c in load_chunks()}
    judge = Judge()
    prompt = judge.cfg["judge_prompt"]
    rows, cost = [], 0.0
    for r in labels:
        q = questions[r["id"]]
        v = judge.judge(q["question"], q["expected_answer"], r["answer"], chunks_for(r["context"], r["citations"], by_id))
        cost += v.cost_usd
        rows.append({"label_id": r["label_id"], "id": r["id"], "human_correct": r["correct"],
                     "human_grounded": r["grounded"], "human_comment": r.get("comment", "")} | v.to_dict())
        mark = lambda h, j: "=" if h == j else "x"
        print(f"  {r['label_id']} {r['id']}: correct {int(r['correct'])}/{int(v.correct)} {mark(r['correct'], v.correct)}"
              f"  grounded {int(r['grounded'])}/{int(v.grounded)} {mark(r['grounded'], v.grounded)}")
    with (CALIBRATION / f"judge_{prompt}.jsonl").open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    result = {k: agreement([(row[f"human_{k}"], row[k]) for row in rows]) for k in ("correct", "grounded")}
    lines = [f"# The judge against the manual labels (judge prompt {prompt})", "",
             f"Judge: {judge.cfg['model_cfg']['model']} ({judge.cfg['judge_sampling']}), prompt prompts/judge/{prompt}.txt. "
             f"Labels: {len(rows)} dev answers labelled by hand, blind (evals/calibration/to_label.xlsx, labels.jsonl). "
             f"Cost of this run: ${cost:.4f}.", "",
             "| verdict | answers | agreement | Cohen's kappa | false pass (judge yes, human no) "
             "| false fail (judge no, human yes) | human yes | judge yes |",
             "|---|---|---|---|---|---|---|---|"]
    for k, a in result.items():
        lines.append(f"| {k} | {a['n']} | {a['agree']} / {a['n']} ({a['agreement']:.2f}) | {a['kappa']:.2f} | "
                     f"{a['false_pass']} | {a['false_fail']} | {a['human_yes']} | {a['judge_yes']} |")
    lines += ["", "## Disagreements", ""]
    for row in rows:
        for k in ("correct", "grounded"):
            if row[f"human_{k}"] != row[k]:
                reason = row["correct_reason"] if k == "correct" else row["grounded_reason"]
                lines.append(f"* **{row['label_id']} ({row['id']}), {k}**: human {int(row[f'human_{k}'])}, judge "
                             f"{int(row[k])}. Judge: {reason}"
                             + (f" Unsupported: {'; '.join(row['unsupported_statements'])}." if k == "grounded"
                                and row["unsupported_statements"] else "")
                             + (f" Human comment: {row['human_comment']}" if row["human_comment"] else ""))
    if not any(row[f"human_{k}"] != row[k] for row in rows for k in ("correct", "grounded")):
        lines.append("None.")
    AGREEMENT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for k, a in result.items():
        print(f"{k}: agreement {a['agreement']:.2f}, kappa {a['kappa']:.2f}, false pass {a['false_pass']}, "
              f"false fail {a['false_fail']}")
    print(f"Saved {AGREEMENT.relative_to(ROOT)} and judge_{prompt}.jsonl (${cost:.4f})")
    return result

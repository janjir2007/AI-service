"""Compare eval runs side by side, all graded with today's rules.

    python scripts/compare_runs.py                 # the last 3 runs
    python scripts/compare_runs.py 1015 1147       # runs whose file name contains these
    python scripts/compare_runs.py --show q11,q20  # also print these answers (newest run)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_eval import MARK, QUESTIONS, RESULTS_DIR, classify  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("runs", nargs="*", help="parts of result file names, e.g. 1015 1147")
    parser.add_argument("--show", default="", help="question ids to print answers for")
    args = parser.parse_args()

    questions = {q["id"]: q for q in json.loads(QUESTIONS.read_text(encoding="utf-8"))}
    files = sorted(RESULTS_DIR.glob("*.json"))
    if args.runs:
        files = [f for f in files if any(r in f.name for r in args.runs)]
    else:
        files = files[-3:]
    if not files:
        sys.exit("No result files found.")

    for path in files:
        rows = json.loads(path.read_text(encoding="utf-8"))
        statuses = []
        for r in rows:
            q = questions.get(r["id"])
            if q is None:
                continue
            resp = {"answer_cyrillic": r.get("answer"), "intent": r.get("intent")}
            statuses.append((r["id"], classify(q, resp)))
        n = {s: sum(st == s for _, st in statuses) for s in MARK}
        print(f"{path.stem}: {n['correct']} correct, {n['honest']} honest, {n['wrong']} wrong")
        print("   ", " ".join(f"{i}:{MARK[st]}" for i, st in statuses))

    if args.show:
        latest = {r["id"]: r for r in json.loads(files[-1].read_text(encoding="utf-8"))}
        print(f"\nAnswers in {files[-1].stem}:")
        for qid in args.show.split(","):
            r = latest.get(qid.strip())
            if r:
                print(f"{qid} {r.get('cited_pages', [])[:3]} {(r.get('answer') or '').replace(chr(10), ' ')[:200]}")


if __name__ == "__main__":
    main()

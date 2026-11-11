"""Run the evaluation set against a running RCOS Norm AI server.

Usage (server must be running on port 8001):
    python scripts/run_eval.py
    python scripts/run_eval.py --only q01,q05
    python scripts/run_eval.py --base-url http://localhost:8001

Each question in eval/questions.json is sent to POST /api/v1/chat. An answer passes when:
  - every group in "must_contain" has at least one of its values in the answer,
  - for "no_distance" questions, the answer gives no distance (e.g. "15 км", "200 м"),
  - for "expected_intent" questions, the response intent matches.
Each answer gets one of three statuses:
  ✓ correct  - passes the checks above
  ~ honest   - says the book has no answer ("олдсонгүй") and gives no value with a unit
  ✗ wrong    - anything else (a wrong value, an unrelated answer)
Wrong answers are the ones to bring to zero first. Whether a cited source page matches
"pages" is reported separately (page_hit). Results are saved to eval/results/<timestamp>.json.
Compare runs with: python scripts/compare_runs.py
"""
from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS = ROOT / "eval" / "questions.json"
RESULTS_DIR = ROOT / "eval" / "results"
DISTANCE_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:км|м|km|m)\b")


def normalize(text: str) -> str:
    """Lowercase, unify dashes and decimal commas so "3,5 – 3,6" matches "3.5-3.6"."""
    text = (text or "").lower()
    text = re.sub(r"[–—−]", "-", text)
    text = re.sub(r"(?<=\d),(?=\d)", ".", text)
    text = re.sub(r"\s*-\s*(?=\d)", "-", text)
    text = re.sub(r"(?<=\d)\s*(?:м|см|мм)\s*-\s*(?=\d)", "-", text)
    return text


def contains(answer: str, value: str) -> bool:
    """Numbers must match whole: "3.75" is not found inside "3.0-3.75"."""
    value = normalize(value)
    if not value[:1].isdigit():
        return value in answer
    return re.search(rf"(?<![\d.\-]){re.escape(value)}(?![\d\-]|\.\d)", answer) is not None


def grade(q: dict, resp: dict) -> tuple[bool, list[str]]:
    """Return (passed, reasons for failure)."""
    reasons: list[str] = []
    answer = normalize(resp.get("answer_cyrillic") or resp.get("answer") or "")
    for group in q.get("must_contain", []):
        if not any(contains(answer, v) for v in group):
            reasons.append(f"missing one of {group}")
    if q.get("no_distance") and DISTANCE_RE.search(answer):
        reasons.append(f"gave a distance: {DISTANCE_RE.search(answer).group(0)!r}")
    if q.get("expected_intent") and resp.get("intent") != q["expected_intent"]:
        reasons.append(f"intent {resp.get('intent')!r}, expected {q['expected_intent']!r}")
    return not reasons, reasons


HONEST_RE = re.compile(r"олдсонгүй|байхгүй|тусгагдаагүй|заагаагүй|дурдаагүй")
VALUE_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:км/ц|км|см|мм|м|%)(?![а-яөү])")
MARK = {"correct": "✓", "honest": "~", "wrong": "✗"}


def classify(q: dict, resp: dict) -> str:
    """correct / honest / wrong."""
    passed, _ = grade(q, resp)
    if passed:
        return "correct"
    answer = normalize(resp.get("answer_cyrillic") or resp.get("answer") or "")
    if HONEST_RE.search(answer) and not VALUE_RE.search(answer):
        return "honest"
    return "wrong"


def page_hit(q: dict, resp: dict) -> bool | None:
    if not q.get("pages"):
        return None
    cited = {s.get("page") for s in resp.get("sources") or []}
    return bool(cited & set(q["pages"]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8001")
    parser.add_argument("--only", default="", help="comma-separated ids, e.g. q01,q05")
    args = parser.parse_args()

    questions = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    if args.only:
        wanted = set(args.only.split(","))
        questions = [q for q in questions if q["id"] in wanted]

    results = []
    with httpx.Client(timeout=900.0) as client:
        for q in questions:
            started = time.time()
            try:
                r = client.post(f"{args.base_url}/api/v1/chat", json={"message": q["question"]})
                r.raise_for_status()
                resp = r.json()
                passed, reasons = grade(q, resp)
            except Exception as exc:  # server error, timeout
                resp, passed, reasons = {}, False, [f"request failed: {exc}"]
            seconds = round(time.time() - started, 1)
            hit = page_hit(q, resp)
            status = classify(q, resp) if resp else "wrong"
            mark = f"{MARK[status]} {status:<7}"
            pages = "-" if hit is None else ("page ok" if hit else "page miss")
            print(f"{q['id']} {mark} {seconds:>6}s  {pages:<9} [{q['type']}] {q['question']}")
            for reason in reasons:
                print(f"      - {reason}")
            results.append({
                "id": q["id"], "type": q["type"], "question": q["question"],
                "passed": passed, "status": status, "reasons": reasons, "page_hit": hit, "seconds": seconds,
                "reference": q.get("reference"),
                "answer": resp.get("answer_cyrillic") or resp.get("answer"),
                "intent": resp.get("intent"),
                "cited_pages": [s.get("page") for s in resp.get("sources") or []],
            })

    counts = {s: sum(r["status"] == s for r in results) for s in MARK}
    hits = [r["page_hit"] for r in results if r["page_hit"] is not None]
    print(
        f"\nScore: {counts['correct']}/{len(results)} correct, {counts['honest']} honest "
        f"(not found), {counts['wrong']} wrong; right page cited {sum(hits)}/{len(hits)}"
    )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"{datetime.now():%Y%m%d-%H%M}.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

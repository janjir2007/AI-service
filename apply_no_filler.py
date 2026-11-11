"""One-time patch for rag_service.py (needs apply_number_check.py applied first).

With ANSWER_NUMBER_CHECK on:
- a blocked LLM answer becomes the honest "not found" reply (no random book sentence);
- the old "direct" speed rule only fills an empty answer when search found relevant pages,
  and never replaces an LLM answer;
- an LLM answer without decimals no longer gets unrelated extractive text appended.
Run from the project folder:  python apply_no_filler.py
"""
import pathlib
import sys

PATH = "app/services/rag_service.py"
p = pathlib.Path(PATH)
src = p.read_text(encoding="utf-8")

if "answer_number_check" not in src:
    sys.exit("STOP: run apply_number_check.py first.")
if "use_direct" in src:
    sys.exit("Already applied - nothing to do.")

edits = [
    (
        "                            logger.warning(\"LLM answer blocked, numbers not in context: %s\", bad)\n"
        "                            answer = \"\"\n",
        "                            logger.warning(\"LLM answer blocked, numbers not in context: %s\", bad)\n"
        "                            answer = _NO_DIRECT_ANSWER\n",
    ),
    (
        "        if direct and (not answer or answer == _NO_DIRECT_ANSWER or not re.search(r\"\\d\", answer)):\n",
        "        if self.settings.answer_number_check:\n"
        "            # Only fill an empty answer, and only when search found relevant pages. The old rule\n"
        "            # also fired on \"хурдны зам\" (expressway) and swapped in unrelated speed sentences.\n"
        "            use_direct = bool(direct) and relevant and not answer\n"
        "        else:\n"
        "            use_direct = bool(direct) and (\n"
        "                not answer or answer == _NO_DIRECT_ANSWER or not re.search(r\"\\d\", answer)\n"
        "            )\n"
        "        if use_direct:\n",
    ),
    (
        "            if ext_measure and not re.search(r\"\\d+[.,]\\d+\", answer) and extractive:\n",
        "            if (\n"
        "                ext_measure\n"
        "                and not self.settings.answer_number_check\n"
        "                and not re.search(r\"\\d+[.,]\\d+\", answer)\n"
        "                and extractive\n"
        "            ):\n",
    ),
]
for old, _ in edits:
    if src.count(old) != 1:
        sys.exit(f"STOP: expected text not found - nothing was changed. Tell Claude.\n---\n{old[:150]}")
for old, new in edits:
    src = src.replace(old, new)
p.write_text(src, encoding="utf-8")
print(f"{PATH}: updated. Now run: python -m pytest -q")

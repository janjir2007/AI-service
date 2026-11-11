"""One-time patch: adds the number check to rag_service.py and a setting to config.py.

Run from the project folder:  python apply_number_check.py
It changes nothing if the code doesn't look exactly as expected.
"""
import pathlib
import sys


def patch(path: str, edits: list[tuple[str, str]]) -> None:
    p = pathlib.Path(path)
    src = p.read_text(encoding="utf-8")
    for old, new in edits:
        if src.count(old) != 1:
            sys.exit(f"STOP: expected text not found in {path} - nothing was changed. Tell Claude.\n---\n{old[:120]}")
    for old, new in edits:
        src = src.replace(old, new)
    p.write_text(src, encoding="utf-8")
    print(f"{path}: updated")


config_edits = [(
    "    ollama_num_ctx: int = 8192\n",
    "    ollama_num_ctx: int = 8192\n"
    "    # Block LLM answers with numbers that are not in the context; no LLM call without relevant sources.\n"
    "    answer_number_check: bool = True\n",
)]

rag_edits = [
    (
        "from app.services.query_enhance import direct_answer_from_hits, retrieval_relevant\n",
        "from app.services.query_enhance import direct_answer_from_hits, retrieval_relevant\n"
        "from app.services.answer_guard import unsupported_numbers\n",
    ),
    (
        "        use_llm = _llm_chat_enabled(provider, self.settings.chat_use_llm)\n",
        "        use_llm = _llm_chat_enabled(provider, self.settings.chat_use_llm)\n"
        "        if not relevant and self.settings.answer_number_check:\n"
        "            # Search found nothing relevant: an LLM answer here would be a guess.\n"
        "            use_llm = False\n",
    ),
    (
        "                if llm_out and not is_degenerate(llm_out):\n"
        "                    answer = llm_out\n",
        "                if llm_out and not is_degenerate(llm_out):\n"
        "                    answer = llm_out\n"
        "                    if self.settings.answer_number_check:\n"
        "                        context_texts = [\n"
        "                            \" \".join(str(v) for v in block.values() if v is not None)\n"
        "                            for block in context_blocks\n"
        "                        ]\n"
        "                        bad = unsupported_numbers(answer, context_texts, message)\n"
        "                        if bad:\n"
        "                            # A number the book chunks don't contain: don't show a guessed answer.\n"
        "                            logger.warning(\"LLM answer blocked, numbers not in context: %s\", bad)\n"
        "                            answer = \"\"\n",
    ),
    (
        "            elif extractive:\n"
        "                # Even low-relevance extractive is better than nothing\n",
        "            elif extractive and not self.settings.answer_number_check:\n"
        "                # Even low-relevance extractive is better than nothing\n",
    ),
]

if "answer_number_check" in pathlib.Path("app/config.py").read_text(encoding="utf-8"):
    sys.exit("Already applied - nothing to do.")
patch("app/config.py", config_edits)
patch("app/services/rag_service.py", rag_edits)
print("Done. Now run: python -m pytest -q")

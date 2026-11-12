#!/usr/bin/env bash
set -euo pipefail

EMBED_MODEL="${EMBEDDING_MODEL:-bge-m3}"
CHAT_MODEL="${LLM_MODEL:-gemma4:e2b-it-qat}"

if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama is not installed. Get it from https://ollama.com"
  exit 1
fi

echo "Pulling embedding model: ${EMBED_MODEL}"
ollama pull "${EMBED_MODEL}"

echo "Pulling chat model: ${CHAT_MODEL}"
ollama pull "${CHAT_MODEL}"

echo "Done. Models ready for local RAG (no API keys)."

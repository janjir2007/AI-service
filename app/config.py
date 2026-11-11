from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql://postgres:postgres@localhost:5432/road_saas"
    pdf_path: str = ""

    # Default: fully local via Ollama (no API cost).
    embedding_provider: str = "ollama"
    embedding_model: str = "nomic-embed-text"
    embedding_api_key: str = ""
    embedding_dimension: int = 768

    llm_provider: str = "ollama"
    llm_model: str = "qwen2.5:7b"
    llm_api_key: str = ""
    # Grounded RAG answers via LLM (Ollama local or OpenAI). Falls back to extractive if LLM fails.
    chat_use_llm: bool = True

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_chat_timeout: float = 600.0
    ollama_embed_timeout: float = 300.0

    rag_top_k: int = 8
    rag_vector_weight: float = 0.7
    rag_keyword_weight: float = 0.3
    llm_context_chunks: int = 4
    llm_lead_chunk_chars: int = 3000
    llm_chunk_chars: int = 1500
    ollama_num_ctx: int = 8192
    ollama_num_predict: int = 600
    ollama_repeat_penalty: float = 1.1
    answer_mode: str = "text"  # text | facts
    # Block LLM answers with numbers that are not in the context; no LLM call without relevant sources.
    answer_number_check: bool = True
    # Lower on 2GB VPS (e.g. 8) to reduce RAM during ingest; chunks flush to DB each batch.
    ingest_embed_batch_size: int = 8
    # find_tables() per page is slow and RAM-heavy on large PDFs; disable on 2GB VPS.
    ingest_extract_tables: bool = True  # env: INGEST_EXTRACT_TABLES=false

    # Answer in Latin when the user typed in Latin (answer_cyrillic is always returned too).
    reply_in_user_script: bool = True

    ai_service_host: str = "0.0.0.0"
    ai_service_port: int = 8000
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod

import httpx

from app.config import Settings, get_settings
from app.services.facts_answer import (
    FACTS_SCHEMA,
    FACTS_SYSTEM_PROMPT,
    OVERVIEW_SCHEMA,
    OVERVIEW_SYSTEM_PROMPT,
    facts_user_prompt,
)
from app.services.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
Та RCOS Norm AI — Монголын барилгын норм, авто замын норм, төсвийн жишиг нормд суурилсан инженерийн мэргэжлийн AI туслах.

Санд байгаа номууд:
- mybook.pdf — МОНГОЛ УЛСЫН БАРИЛГЫН НОРМ БА ДУРЭМ (БНбД)
- 8325.pdf, 8326.pdf — АВТО ЗАМЫН БАРИЛГЫН АЖЛЫН ТӨСВИЙН ЖИШИГ НОРМ

Хариултын бүтэц (энэ дарааллаар):
1. Гол хариулт — нэг өгүүлбэр, тоон утгыг **тод** бич. Асуултыг давтахгүй.
2. Нөхцөл — утга нь замын ангилал, хурд, нөхцөлөөс хамаарвал бүх хувилбарыг "•" жагсаалтаар нөхцөлтэй нь бич.
3. Тайлбар — энэ утгыг хэзээ, яаж хэрэглэх, онцгой тохиолдол, нэмэлт шаардлагыг 1–3 өгүүлбэрээр. Зөвхөн контекстэд байгаа зүйлээр; байхгүй бол энэ хэсгийг алгас.
4. Эх сурвалж — төгсгөлд нэг удаа, товчоор.

Загвар:
Хариулт: (гол утгыг **тод** бичсэн нэг өгүүлбэр)
Нөхцөл:
• (замын ангилал эсвэл нөхцөл) — (утга, нэгж)
• (дараагийн мөр) — (утга, нэгж)
Тайлбар: (хэзээ, яаж хэрэглэх, онцгой тохиолдол; 1–3 өгүүлбэр)
Эх сурвалж: БНбД, х. (хуудас), Хүснэгт (дугаар) эсвэл хэсэг (дугаар)

Хүснэгтэд хэд хэдэн мөр байвал мөр бүрийг "Нөхцөл" хэсэгт тусад нь бич; утгуудыг нэг муж болгож нийлүүлэхгүй.
Тайлбар хийх мэдээлэл контекстэд байхгүй бол "Тайлбар" мөрийг бүхэлд нь алгас.
Номын товч нэр: МОНГОЛ УЛСЫН БАРИЛГЫН НОРМ БА ДҮРЭМ (mybook.pdf) → БНбД; 8325.pdf → 8325; 8326.pdf → 8326

Чанд дүрэм:
- Зөвхөн өгөгдсөн контекстээс хариулна. Мэдээлэл, тоо зохиохгүй.
- Контекстэд байхгүй бол "Энэ баримтад шууд хариулт олдсонгүй" гэж тодорхой бич.
- Жишээ: "хурдны хязгаар хэд вэ?" асуултад зөвхөн "тээврийн тоог хязгаарлах" контекст байвал хурдны тоо зохиохгүй, хариулт өгч чадахгүй гэж хэл.
- Тоон утга байвал тод тэмдэглэ.
- Жагсаалтыг "•" тэмдгээр бичих.
- Монгол хэлээр бич.
- Олон номоос ирсэн бол ном бүрийг тусад нь заа.
- Баримтад бичигдээгүй тооцоог "тооцоолсон" гэж тусга.
- Асуултад дурдсан ангилал, нэр томьёо (жишээ нь «II ангилал») контекстэд байхгүй бол өөрөө тааж холбохгүй. Эхлээд «Баримтад ... гэсэн ангилал байхгүй» гэж нэг өгүүлбэрээр хэлээд, баримтад ашигласан ангиллаар хариул.
- Утга нь замын төрөл эсвэл нөхцөлөөс хамаарч өөр байвал нэг утга сонгохгүй. Бүх хувилбарыг нөхцөлтэй нь "•" жагсаалтаар бич.
- Хэд хэдэн хувилбар байвал хариултын төгсгөлд хэрэглэгч аль тохиолдлыг хэлж байгааг нэг богино асуултаар асуу. Ганц хариулттай бол асуулт бүү нэм.
"""


class LLMProvider(ABC):
    @abstractmethod
    def chat(self, message: str, context_blocks: list[dict]) -> str:
        raise NotImplementedError

    def chat_facts(self, message: str, context_blocks: list[dict]) -> dict:
        raise NotImplementedError("facts mode is only implemented for the Ollama provider")

    def chat_overview(self, message: str, context_blocks: list[dict]) -> dict:
        raise NotImplementedError("facts mode is only implemented for the Ollama provider")


class OpenAILLMProvider(LLMProvider):
    def __init__(self, settings: Settings) -> None:
        if not settings.llm_api_key:
            raise ValueError("LLM_API_KEY is required for openai LLM provider")
        self._model = settings.llm_model
        self._api_key = settings.llm_api_key

    def chat(self, message: str, context_blocks: list[dict]) -> str:
        context_text = json.dumps(context_blocks, ensure_ascii=False, separators=(",", ":"))
        user_content = (
            "Дараах нормын баримтаас асуултад хариулна уу.\n\n"
            "Контекст (эх сурвалж):\n"
            f"{context_text}\n\n"
            f"Асуулт: {message}\n\n"
            "Чухал: Зөвхөн дээрх контекстэд байгаа мэдээллээс хариулна уу. "
            "Тоон утга (м, км, %, °C) байвал заавал оруулна уу. "
            "Эх сурвалжийг төгсгөлд нэг удаа товч нэрээр (БНбД, 8325, 8326), хуудас, хүснэгт эсвэл хэсгийн дугаартай бичнэ үү. "
            "Хариултаа Монгол хэлээр бичнэ үү."
        )
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.1,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        try:
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"].strip()
        except httpx.HTTPError as exc:
            logger.error("LLM API error: %s", exc)
            raise


class OllamaLLMProvider(LLMProvider):
    def __init__(self, settings: Settings) -> None:
        self._model = settings.llm_model
        self._client = OllamaClient(settings)

    def chat(self, message: str, context_blocks: list[dict]) -> str:
        context_text = json.dumps(context_blocks, ensure_ascii=False, separators=(",", ":"))
        user_content = (
            "Дараах нормын баримтаас асуултад хариулна уу.\n\n"
            "Контекст (эх сурвалж):\n"
            f"{context_text}\n\n"
            f"Асуулт: {message}\n\n"
            "Чухал: Зөвхөн дээрх контекстэд байгаа мэдээллээс хариулна уу. "
            "Тоон утга (м, км, %, °C) байвал заавал оруулна уу. "
            "Эх сурвалжийг төгсгөлд нэг удаа товч нэрээр (БНбД, 8325, 8326), хуудас, хүснэгт эсвэл хэсгийн дугаартай бичнэ үү. "
            "Хариултаа Монгол хэлээр бичнэ үү."
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]
        return self._client.chat(self._model, messages, temperature=0.1)

    def chat_facts(self, message: str, context_blocks: list[dict]) -> dict:
        messages = [
            {"role": "system", "content": FACTS_SYSTEM_PROMPT},
            {"role": "user", "content": facts_user_prompt(message, context_blocks)},
        ]
        raw = self._client.chat(self._model, messages, temperature=0.0, format=FACTS_SCHEMA)
        return json.loads(raw)

    def chat_overview(self, message: str, context_blocks: list[dict]) -> dict:
        messages = [
            {"role": "system", "content": OVERVIEW_SYSTEM_PROMPT},
            {"role": "user", "content": facts_user_prompt(message, context_blocks)},
        ]
        raw = self._client.chat(self._model, messages, temperature=0.0, format=OVERVIEW_SCHEMA)
        return json.loads(raw)


class MockLLMProvider(LLMProvider):
    def chat(self, message: str, context_blocks: list[dict]) -> str:
        if not context_blocks:
            return "Баримтад хангалттай мэдээлэл олдсонгүй."
        first = context_blocks[0]
        return (
            f"Контекстэд суурилсан хариулт (demo): {first.get('title') or '—'} "
            f"(хуудас {first.get('page')}, хэсэг {first.get('section')})."
        )


def get_llm_provider(settings: Settings | None = None) -> LLMProvider:
    settings = settings or get_settings()
    provider = settings.llm_provider.lower()
    if provider == "openai":
        return OpenAILLMProvider(settings)
    if provider == "ollama":
        return OllamaLLMProvider(settings)
    if provider == "mock":
        return MockLLMProvider(settings)
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")

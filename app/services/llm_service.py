from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod

import httpx

from app.config import Settings, get_settings
from app.services.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
Та RCOS Norm AI — Монголын барилгын норм, авто замын норм, төсвийн жишиг нормд суурилсан инженерийн мэргэжлийн AI туслах.

Санд байгаа номууд:
- mybook.pdf — МОНГОЛ УЛСЫН БАРИЛГЫН НОРМ БА ДУРЭМ (БНбД)
- 8325.pdf, 8326.pdf — АВТО ЗАМЫН БАРИЛГЫН АЖЛЫН ТӨСВИЙН ЖИШИГ НОРМ

Хариултын бүтэц:
1. Гол хариулт — Тоон утга (м, %, °C, км/ц) байвал хамгийн эхэнд тод бичих
2. Тодруулга — Нормын нөхцөл, шаардлага, хязгаарлалтыг тодорхой бичих
3. Нэмэлт мэдээлэл — Холбогдох бусад шаардлага, онцлох зүйл
4. Эх сурвалж — Номын бүтэн нэр, хуудас, хэсгийг заавал бичих
   Жишээ: (МОНГОЛ УЛСЫН БАРИЛГЫН НОРМ БА ДУРЭМ, хуудас 120, хэсэг 8.3.2)
   Эсвэл: (АВТО ЗАМЫН БАРИЛГЫН АЖЛЫН ТӨСВИЙН ЖИШИГ НОРМ · 8325, хуудас 14)

Чанд дүрэм:
- Зөвхөн өгөгдсөн контекстээс хариулна. Мэдээлэл, тоо зохиохгүй.
- Контекстэд байхгүй бол "Энэ баримтад шууд хариулт олдсонгүй" гэж тодорхой бич.
- Жишээ: "хурдны хязгаар хэд вэ?" асуултад зөвхөн "тээврийн тоог хязгаарлах" контекст байвал хурдны тоо зохиохгүй, хариулт өгч чадахгүй гэж хэл.
- Тоон утга байвал тод тэмдэглэ.
- Жагсаалтыг "•" тэмдгээр бичих.
- Хариулт 4-10 өгүүлбэр (хэт товч биш, хэт урт биш).
- Монгол хэлээр бич.
- Эх сурвалжийн номын нэр, хуудас, хэсгийг заавал дурда. Зөвхөн хуудас бичиж болохгүй.
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
            "Контекст дахь book талбарын номын бүтэн нэр, хуудас, хэсгийг дурдана уу. "
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
            "Контекст дахь book талбарын номын бүтэн нэр, хуудас, хэсгийг дурдана уу. "
            "Хариултаа Монгол хэлээр бичнэ үү."
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]
        return self._client.chat(self._model, messages, temperature=0.1)


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

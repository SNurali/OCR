import asyncio
from app.services.llm_extractor import llm_extractor
import json

raw_text = """OZBEKISTONIRESPUBLIKASI
SHAXSGUVOHNOMASIUHES
AM79792
SUL
01509860230078
INEDIHSCI
IV26289
00704011915837315098602300784
0009095A3203237XXX0ZB<<<<33<30
SULATOANOVSNURALISKKSSSKSKS"""

prompt = f"""Ты эксперт по восстановлению данных из паспортов с плохим OCR.

Вот сырой текст, полученный сканером с паспорта Узбекистана (ID-карта):
---
{raw_text}
---

ЗАДАЧА: Извлеки данные паспорта в JSON формате.

ПРАВИЛА ИЗВЛЕЧЕНИЯ:
1. Текст содержит много мусора и опечаток OCR (например S вместо 5, O вместо 0, S вместо <).
2. Фамилия и Имя обычно в самом низу друг за другом в слипшемся виде. Например, "SULATOANOVSNURALISKKSSSKSKS" означает SULATOANOV = SULAYMANOV (Фамилия), NURALI (Имя). Фамилии заканчиваются на -OV, -EV. Имена идут следом.
3. ПИНФЛ - это 14 цифр подряд. Если видишь "315098602300784", ПИНФЛ это 14 цифр.
4. Номер паспорта состоит из 2 букв и 7 цифр. Ищи что-то похожее (AD1234567, FA1234567, AM79792...). Если букв/цифр не хватает, склей контекст.
5. Дата выдачи/рождения и прочее: игнорируй, если их явно нет.

ОБЯЗАТЕЛЬНЫЕ ПОЛЯ (Верни чистый JSON без markdown):
{{
  "surname": "фамилия (чистая, латиницей)",
  "given_names": "имя (чистое, латиницей)",
  "passport_number": "номер",
  "nationality": "UZB",
  "pinfl": "14 цифр"
}}
"""

client = llm_extractor._get_client()
response = client.post(
    "/chat/completions",
    json={
        "model": llm_extractor.model,
        "messages": [
            {
                "role": "system",
                "content": "You are a passport logic analyzer. Output pure raw JSON.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
    },
)
res = response.json()
print("LLM RESPONSE:")
print(res["choices"][0]["message"]["content"])

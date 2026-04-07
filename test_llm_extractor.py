from dotenv import load_dotenv
load_dotenv()

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

mrz_data = {}

print(f"LLM Enabled: {llm_extractor.enabled}")
print(f"Provider: {llm_extractor.provider}")
res = llm_extractor.extract_fields(raw_text, mrz_data)
print("FINAL RESULT:")
print(json.dumps(res, indent=2, ensure_ascii=False))

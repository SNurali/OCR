import asyncio
from app.services.llm_extractor import llm_extractor
import json

raw_text = """@ZBEKISTONREEPUBUASI
SHAXS GUVOHNOMASIШшtа
в
NOV
AM9792]
Егуk;
ENURAL
Qntaю
2МпЮкОЧеН
Itailiiicau /лзыон]
51509860290078
15021996
Аn
Ви
Binuianunia /Пи&вин
Ешna
Giilmn
2400502
UDSHKENT
QPEASON
Ш[фбуимввру
ands
ИВПIЯВ5
mV 26283
DUZEAD1 191583731 509860230078 <
006
5573203237XXXUZB < < <<<<<<0
OULAYMANOV < <NURALI < < <<<<<< <<< <
{б9ЕМ"""

mrz_data = {
    "raw_mrz_lines": [
        "DUZEAD1 191583731 509860230078 <",
        "006",
        "5573203237XXXUZB < < <<<<<<0",
        "OULAYMANOV < <NURALI < < <<<<<< <<< <"
    ]
}

llm_input_text = raw_text + "\n\nMRZ_LINES:\n" + "\n".join(mrz_data["raw_mrz_lines"])

res = llm_extractor.extract_fields(llm_input_text, mrz_data)
print("LLM RESPONSE:")
print(json.dumps(res, indent=2, ensure_ascii=False))

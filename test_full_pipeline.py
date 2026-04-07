from dotenv import load_dotenv
load_dotenv()
from app.modules.parser import extract_from_text
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

res = extract_from_text(raw_text, ocr_confidence=0.84)
print("FINAL PIPELINE RESULT:")
print(json.dumps(res, indent=2, ensure_ascii=False))

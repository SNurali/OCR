import re

raw_text = """РОССИЙСКАЯ
ФЕДЕРАЦИЯ
RUSSIAN
FEDERATION
Подпись
владельца
Holdert
signature
#ls
РОССИЙСКАЯ
ПАСПОРТ
ФЕДЕРАЦИЯ
'PASSPORT
Тип
RUSSIAN
Typе
Код
FEDERATION
государства
выдачи
Code
Фамилия
RUS
Issuing
Номер
Surname
'State
паспорта
ПОЛТАВ СКИЙ
'Passport
2007752
₽ O LTAVSKII
Имя
/Given
names
АЛЕКСАНДР
ALEKS
АЛ ЕКСЕЕВ ИЧ
Гражданство
Nationality
РОССИЙСКАЯ
Дата
ФЕДЕРАЦИЯ /
рождения
25.(
Date
RUSSIAN
birth
1970"""

lines = [line.strip() for line in raw_text.split('\n') if line.strip()]

first_name = ""
last_name = ""
middle_name = ""

for i, line in enumerate(lines):
    if "Фамилия" in line or "Surname" in line:
        # Search ahead for the next ALL CAPS Cyrillic word
        for j in range(i+1, min(i+10, len(lines))):
            clean_word = re.sub(r'[^А-ЯЁ\s]', '', lines[j].upper()).strip()
            if len(clean_word) > 3 and "ПАСПОРТ" not in clean_word and "ПОЛ" not in clean_word and clean_word != "RUS":
                # Wait, "ПОЛ" might be in "ПОЛТАВ СКИЙ". 
                pass

print(lines)

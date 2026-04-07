import copy
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse


SUPPORTED_DOC_LANGS = {"ru", "uz", "en"}

API_DESCRIPTION_RU = """
# OCRUZ Passport Service — Инструкция по применению

## 🏗 Архитектура
Сервис распознавания паспортов на базе **VLM (Vision-Language Model)** следующего поколения.
- Один вызов к модели → все поля паспорта извлекаются из изображения
- Никакого PaddleOCR, Tesseract или OpenCV — только нейросетевой пайплайн
- Поддержка: узбекские паспорта/ID-карты, российские паспорта, казахские/кыргызские ID

## 🔑 Аутентификация
| Метод | Endpoint | Описание |
|-------|----------|----------|
| Login | `POST /api/auth/login` | `username` + `password` → JWT токен |
| Bearer | `Authorization: Bearer <token>` | Для всех защищённых endpoints |

**Доступ по умолчанию:** логин `admin`, пароль `admin123`

##  Быстрый старт

### Шаг 1: Получить токен
```bash
curl -X POST http://localhost:8001/api/auth/login \
  -d "username=admin&password=admin123"
# Ответ: {"access_token": "eyJhbGci..."}
```

### Шаг 2: Распознать паспорт (синхронно)
```bash
curl -X POST http://localhost:8001/api/passport/test-ocr \
  -H "Authorization: Bearer <token>" \
  -F "file=@passport.jpg"
```

**Ответ:**
```json
{
  "extracted_fields": {
    "first_name": "NURALI",
    "last_name": "SULAYMANOV",
    "birth_date": "15.09.1986",
    "gender": "M",
    "nationality": "O'ZBEKISTON",
    "passport_number": "AD1191583",
    "pinfl": "31509860230078"
  },
  "validation": {
    "overall_confidence": 0.49,
    "all_valid": true
  }
}
```

### Шаг 3: Асинхронная загрузка (для production)
```bash
# 1. Загрузить файл в очередь
curl -X POST http://localhost:8001/api/passport/scan \
  -H "Authorization: Bearer <token>" \
  -F "file=@passport.jpg"
# Ответ: {"task_id": "uuid-...", "status": "processing"}

# 2. Проверить статус
curl http://localhost:8001/api/passport/status/<task_id> \
  -H "Authorization: Bearer <token>"

# 3. Получить результат
curl http://localhost:8001/api/passport/result/<task_id> \
  -H "Authorization: Bearer <token>"
```

## 📋 Все endpoints

### Passport OCR
| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/api/passport/test-ocr` | Синхронное распознавание (мгновенный ответ) |
| POST | `/api/passport/scan` | Асинхронная загрузка в очередь |
| GET | `/api/passport/status/{id}` | Статус задачи |
| GET | `/api/passport/result/{id}` | Результат распознавания |
| GET | `/api/passport/list` | Список всех распарсенных паспортов |

### Analytics
| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/analytics/summary` | Сводка по распознанным паспортам |
| GET | `/api/analytics/gender-report` | Отчёт по полу |
| GET | `/api/analytics/age-report` | Отчёт по возрасту |
| GET | `/api/analytics/nationality-report` | Отчёт по гражданству |
| GET | `/api/analytics/export/csv` | Экспорт в CSV |

### Admin
| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/admin/users` | Список пользователей |
| POST | `/api/admin/users` | Создать пользователя |
| POST | `/api/admin/users/{id}/reset-password` | Сброс пароля |

## 📊 Дашборд
Веб-интерфейс: **http://localhost:8001/dashboard.html**
- 📷 Загрузка паспортов
- 🧪 OCR тест (мгновенное распознавание)
- 📥 Входящие паспорта (таблица всех документов)
- 📋 Отчёты (по полу, возрасту, гражданству)
- 👥 Управление пользователями

## 🎯 Поля распознавания
VLM извлекает 11 полей:
| Поле | Описание | Пример |
|------|----------|--------|
| `first_name` | Имя | NURALI |
| `last_name` | Фамилия | SULAYMANOV |
| `middle_name` | Отчество | AMIRJONOVICH |
| `birth_date` | Дата рождения | 15.09.1986 |
| `gender` | Пол | M / F |
| `nationality` | Гражданство | O'ZBEKISTON / RUS |
| `passport_number` | Номер паспорта | AD1191583 |
| `issue_date` | Дата выдачи | 24.03.2022 |
| `expiry_date` | Дата окончания | 23.03.2032 |
| `issued_by` | Кем выдан | IIV FVD |
| `pinfl` | ПИНФЛ (14 цифр) | 31509860230078 |

## 🔧 Технологии
- **Backend:** FastAPI + Uvicorn
- **VLM:** Proprietary Vision-Language Model
- **Database:** PostgreSQL 16
- **Queue:** Redis + Celery
- **Monitoring:** Prometheus + Grafana

## 📌 Поддерживаемые форматы изображений
`jpg`, `jpeg`, `png`, `tiff`, `bmp`, `webp` — макс. размер 10 МБ
"""


API_DESCRIPTION_UZ = """
# Getting Started

## Introduction
OCR Passport Service API.

## Authentication
- `POST /api/auth/login` `application/x-www-form-urlencoded` qabul qiladi va JWT qaytaradi.
- `/api/admin/*` va `POST /api/passport/test-ocr` `Authorization: Bearer <token>` ishlatadi.
- `/api/analytics/*` Swagger uchun `Authorization: Bearer <token>` va eski dashboard mosligi uchun `?token=<token>` ni qo'llab-quvvatlaydi.
- `POST /api/passport/scan`, `GET /api/passport/status/{id}`, `GET /api/passport/result/{id}` va `GET /api/passport/list` joriy realizatsiyada ochiq.

## Quick Start
1. `POST /api/auth/login` orqali token oling.
2. Faylni `POST /api/passport/scan` manziliga yuklang.
3. Holatini `GET /api/passport/status/{id}` orqali tekshiring.
4. Natijani olish uchun `GET /api/passport/result/{id}` dan foydalaning.
"""


DOC_UI = {
    "ru": {
        "html_lang": "ru",
        "page_title": "OCRUZ Passport API — Documentation",
        "toolbar_title": "OCRUZ Passport API",
        "language_label": "Язык",
        "lang_ru": "Русский",
        "lang_uz": "O'zbekcha",
        "lang_en": "English",
        "login_btn": "Войти",
        "logout_btn": "Выйти",
        "username_placeholder": "Логин",
        "password_placeholder": "Пароль",
        "login_title": "Вход в систему",
        "login_error": "Неверный логин или пароль",
        "login_subtitle": "Введите учётные данные для доступа к API",
        "authenticated_as": "Авторизован",
        "api_base": "Базовый URL",
    },
    "uz": {
        "html_lang": "uz",
        "page_title": "OCRUZ Passport API — Hujjatlar",
        "toolbar_title": "OCRUZ Passport API",
        "language_label": "Til",
        "lang_ru": "Русский",
        "lang_uz": "O'zbekcha",
        "lang_en": "English",
        "login_btn": "Kirish",
        "logout_btn": "Chiqish",
        "username_placeholder": "Login",
        "password_placeholder": "Parol",
        "login_title": "Tizimga kirish",
        "login_error": "Login yoki parol noto'g'ri",
        "login_subtitle": "API ga kirish uchun ma'lumotlarni kiriting",
        "authenticated_as": "Avtorizatsiyalangan",
        "api_base": "Asosiy URL",
    },
    "en": {
        "html_lang": "en",
        "page_title": "OCRUZ Passport API — Documentation",
        "toolbar_title": "OCRUZ Passport API",
        "language_label": "Language",
        "lang_ru": "Русский",
        "lang_uz": "O'zbekcha",
        "lang_en": "English",
        "login_btn": "Sign In",
        "logout_btn": "Sign Out",
        "username_placeholder": "Username",
        "password_placeholder": "Password",
        "login_title": "Sign In",
        "login_error": "Invalid username or password",
        "login_subtitle": "Enter credentials to access the API",
        "authenticated_as": "Authenticated as",
        "api_base": "Base URL",
    },
}


OPENAPI_TRANSLATIONS = {
    "ru": {
        "JWT токен в query. Нужен для legacy dashboard compatibility.": "JWT-токен в query. Нужен для совместимости со старым dashboard.",
        "Доступно только роли `admin`.": "Доступно только пользователю с ролью `admin`.",
    },
    "uz": {
        API_DESCRIPTION_RU.strip(): API_DESCRIPTION_UZ.strip(),
        "Получение JWT токена": "JWT token olish",
        "Управление пользователями и ролями": "Foydalanuvchilar va rollarni boshqarish",
        "Сводка и аналитические отчеты": "Analitika va hisobotlar",
        "OCR загрузка, статус и результаты распознавания": "OCR yuklash, holat va tanib olish natijalari",
        "Служебные маршруты API": "API xizmat marshrutlari",
        "Получить JWT токен": "JWT token olish",
        "Логин для dashboard и API. Запрос принимает только `application/x-www-form-urlencoded` поля `username` и `password`.": "Dashboard va API uchun login. So'rov faqat `application/x-www-form-urlencoded` formatidagi `username` va `password` maydonlarini qabul qiladi.",
        "Загрузить файл в OCR-очередь": "Faylni OCR navbatiga yuklash",
        "Асинхронная загрузка документа. В текущей реализации маршрут доступен без авторизации, а dashboard ограничивает доступ на уровне UI.": "Hujjat asinxron tarzda yuklanadi. Joriy realizatsiyada marshrut avtorizatsiyasiz ochiq, dashboard esa kirishni UI darajasida cheklaydi.",
        "Синхронный OCR тест": "Sinxron OCR testi",
        "Проверяет одно изображение без создания отдельной заявки в списке обработок.": "Bitta tasvirni qayta ishlanganlar ro'yxatida alohida yozuv yaratmasdan tekshiradi.",
        "Статус OCR-задачи": "OCR vazifasi holati",
        "Проверить статус обработки паспорта": "Pasportni qayta ishlash holatini tekshirish",
        "Результат OCR-задачи": "OCR vazifasi natijasi",
        "Получить результат распознавания паспорта": "Pasportni tanib olish natijasini olish",
        "Список обработанных загрузок": "Qayta ishlangan yuklamalar ro'yxati",
        "Список всех обработанных паспортов с фильтрацией": "Filtrlash bilan barcha qayta ishlangan pasportlar ro'yxati",
        "Получить доступные роли": "Mavjud rollarni olish",
        "Получить список доступных ролей (только админ)": "Mavjud rollar ro'yxatini olish (faqat admin)",
        "Список пользователей": "Foydalanuvchilar ro'yxati",
        "Список всех пользователей (ТОЛЬКО АДМИНИСТРАТОР)": "Barcha foydalanuvchilar ro'yxati (FAQAT ADMIN)",
        "Создать пользователя": "Foydalanuvchi yaratish",
        "Создать нового пользователя (ТОЛЬКО АДМИНИСТРАТОР)\n\nРоли:\n- admin: полный доступ\n- observer: только просмотр отчетов": "Yangi foydalanuvchi yaratish (FAQAT ADMIN)\n\nRollar:\n- admin: to'liq kirish\n- observer: faqat hisobotlarni ko'rish",
        "Текущий пользователь": "Joriy foydalanuvchi",
        "Получить информацию о текущем пользователе": "Joriy foydalanuvchi haqida ma'lumot olish",
        "Обновить пользователя": "Foydalanuvchini yangilash",
        "Обновить пользователя (ТОЛЬКО АДМИНИСТРАТОР)\n\nМожно изменить:\n- Роль (admin/observer)\n- Статус (active/inactive)\n- Пароль": "Foydalanuvchini yangilash (FAQAT ADMIN)\n\nQuyidagilarni o'zgartirish mumkin:\n- Rol (admin/observer)\n- Holat (active/inactive)\n- Parol",
        "Удалить пользователя": "Foydalanuvchini o'chirish",
        "Удалить пользователя (ТОЛЬКО АДМИНИСТРАТОР)": "Foydalanuvchini o'chirish (FAQAT ADMIN)",
        "Сбросить пароль пользователя": "Foydalanuvchi parolini tiklash",
        "Сбросить пароль пользователя (ТОЛЬКО АДМИНИСТРАТОР)": "Foydalanuvchi parolini tiklash (FAQAT ADMIN)",
        "Сводка по распознанным паспортам": "Tanib olingan pasportlar bo'yicha umumiy ko'rsatkichlar",
        "Возвращает верхнеуровневые метрики dashboard. В `total_passports` попадают только загрузки, где OCR распознал паспортные поля. `total_uploads` содержит все загруженные файлы.": "Dashboard uchun yuqori darajadagi metrikalarni qaytaradi. `total_passports` ga faqat OCR pasport maydonlarini topgan yuklamalar kiradi. `total_uploads` esa barcha yuklangan fayllarni o'z ichiga oladi.",
        "Отчет по полу": "Jins bo'yicha hisobot",
        "Отчет по полу: кто больше - мужчин или женщин\n\n🔓 Доступно: admin, observer": "Jins bo'yicha hisobot: erkaklar ko'pmi yoki ayollar\n\n🔓 Mavjud: admin, observer",
        "Отчет по возрастным группам": "Yosh guruhlari bo'yicha hisobot",
        "Отчет по возрастным группам\n\n🔓 Доступно: admin, observer": "Yosh guruhlari bo'yicha hisobot\n\n🔓 Mavjud: admin, observer",
        "Отчет по гражданству": "Fuqarolik bo'yicha hisobot",
        "Отчет по гражданству/национальности\n\n🔓 Доступно: admin, observer": "Fuqarolik yoki millat bo'yicha hisobot\n\n🔓 Mavjud: admin, observer",
        "Поступления за период": "Davr bo'yicha tushumlar",
        "Отчет по времени: поступления за период\n\n🔓 Доступно: admin, observer": "Vaqt bo'yicha hisobot: davr ichidagi tushumlar\n\n🔓 Mavjud: admin, observer",
        "Статистика по месяцам": "Oylar bo'yicha statistika",
        "Статистика по месяцам за год\n\n🔓 Доступно: admin, observer": "Yil bo'yicha oyma-oy statistika\n\n🔓 Mavjud: admin, observer",
        "Статистика по годам": "Yillar bo'yicha statistika",
        "Статистика по годам\n\n🔓 Доступно: admin, observer": "Yillar bo'yicha statistika\n\n🔓 Mavjud: admin, observer",
        "Пол по возрастным группам": "Yosh guruhlari kesimida jins",
        "Соотношение пола по возрастным группам\n\n🔓 Доступно: admin, observer": "Yosh guruhlari bo'yicha jinslar nisbati\n\n🔓 Mavjud: admin, observer",
        "Поступления по дням": "Kunlar bo'yicha tushumlar",
        "Поступления по дням\n\n🔓 Доступно: admin, observer": "Kunlar bo'yicha tushumlar\n\n🔓 Mavjud: admin, observer",
        "Логи доступа": "Kirish loglari",
        "Доступно только роли `admin`.": "Faqat `admin` roli uchun mavjud.",
        "Проверить состояние API": "API holatini tekshirish",
        "JWT токен в query. Нужен для legacy dashboard compatibility.": "Query ichidagi JWT token. Eski dashboard bilan moslik uchun kerak.",
        "Топ N национальностей": "Top N fuqaroliklar",
        "period: day, week, month, year": "Davr: day, week, month, year",
        "Год (по умолчанию текущий)": "Yil (standart qiymat - joriy yil)",
        "Количество дней": "Kunlar soni",
    },
}


_OPENAPI_CACHE: dict[tuple[int, str], dict[str, Any]] = {}


def normalize_doc_lang(lang: str | None) -> str:
    normalized = (lang or "ru").lower()
    return normalized if normalized in SUPPORTED_DOC_LANGS else "ru"


def _translate_node(node: Any, translations: dict[str, str]) -> Any:
    if isinstance(node, dict):
        return {
            key: _translate_node(value, translations) for key, value in node.items()
        }
    if isinstance(node, list):
        return [_translate_node(item, translations) for item in node]
    if isinstance(node, str):
        if node in translations:
            return translations[node]

        stripped = node.strip()
        if stripped in translations:
            return translations[stripped]

        return node
    return node


def get_localized_openapi_schema(app: FastAPI, lang: str | None) -> dict[str, Any]:
    normalized_lang = normalize_doc_lang(lang)
    cache_key = (id(app), normalized_lang)
    if cache_key in _OPENAPI_CACHE:
        return _OPENAPI_CACHE[cache_key]

    schema = copy.deepcopy(app.openapi())
    
    schema["x-tagGroups"] = [
        {"name": "Passport OCR", "tags": ["passport"]},
        {"name": "Analytics", "tags": ["analytics"]},
        {"name": "Admin", "tags": ["admin"]},
        {"name": "Auth", "tags": ["auth"]}
    ]
    
    translations = OPENAPI_TRANSLATIONS.get(normalized_lang)
    if translations:
        schema = _translate_node(schema, translations)

    _OPENAPI_CACHE[cache_key] = schema
    return schema


_TEMPLATE_PATH = Path(__file__).parent / "templates" / "redoc.html"
_LOGIN_PATH = Path(__file__).parent / "templates" / "login.html"


def build_redoc_html(app: FastAPI, lang: str | None) -> HTMLResponse:
    normalized_lang = normalize_doc_lang(lang)
    labels = DOC_UI[normalized_lang]
    spec_url = "/api/openapi-localized.json?lang=" + normalized_lang

    def lang_link(code: str, label: str) -> str:
        active_class = "active" if normalized_lang == code else ""
        return (
            '<a class="lang-link '
            + active_class
            + '" href="/api/redoc?lang='
            + code
            + '">'
            + label
            + "</a>"
        )

    replacements = {
        "__HTML_LANG__": labels["html_lang"],
        "__PAGE_TITLE__": labels["page_title"],
        "__LOGIN_BTN__": labels["login_btn"],
        "__LOGOUT_BTN__": labels["logout_btn"],
        "__USERNAME_PH__": labels["username_placeholder"],
        "__PASSWORD_PH__": labels["password_placeholder"],
        "__LOGIN_TITLE__": labels["login_title"],
        "__LOGIN_ERROR__": labels["login_error"],
        "__SPEC_URL__": spec_url,
        "__LANG_LINKS__": (
            lang_link("ru", labels["lang_ru"])
            + lang_link("uz", labels["lang_uz"])
            + lang_link("en", labels["lang_en"])
        ),
    }

    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    for key, value in replacements.items():
        template = template.replace(key, value)

    return HTMLResponse(template)


def build_login_page(lang: str | None) -> HTMLResponse:
    normalized_lang = normalize_doc_lang(lang)
    labels = DOC_UI[normalized_lang]

    replacements = {
        "__HTML_LANG__": labels["html_lang"],
        "__LOGIN_TITLE__": labels["login_title"],
        "__LOGIN_SUBTITLE__": labels["login_subtitle"],
        "__USERNAME_PH__": labels["username_placeholder"],
        "__PASSWORD_PH__": labels["password_placeholder"],
        "__LOGIN_BTN__": labels["login_btn"],
        "__LOGIN_ERROR__": labels["login_error"],
        "__LANG_LINKS__": (
            '<a class="lang-link" href="/api/redoc?lang=ru">'
            + labels["lang_ru"]
            + "</a>"
            + '<a class="lang-link" href="/api/redoc?lang=uz">'
            + labels["lang_uz"]
            + "</a>"
            + '<a class="lang-link" href="/api/redoc?lang=en">'
            + labels["lang_en"]
            + "</a>"
        ),
    }

    template = _LOGIN_PATH.read_text(encoding="utf-8")
    for key, value in replacements.items():
        template = template.replace(key, value)

    return HTMLResponse(template)

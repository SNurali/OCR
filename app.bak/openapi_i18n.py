import copy
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse


SUPPORTED_DOC_LANGS = {"ru", "uz", "en"}

API_DESCRIPTION_RU = """
API OCR Passport Service.

## Правила авторизации

- `POST /api/auth/login` принимает `application/x-www-form-urlencoded` и возвращает JWT.
- `/api/admin/*` и `POST /api/passport/test-ocr` используют `Authorization: Bearer <token>`.
- `/api/analytics/*` поддерживает `Authorization: Bearer <token>` для Swagger и `?token=<token>` для совместимости со старым dashboard.
- `POST /api/passport/scan`, `GET /api/passport/status/{task_id}`, `GET /api/passport/result/{task_id}` и `GET /api/passport/list` в текущей реализации публичны.

## Тестовые файлы

- Используйте `passport_test_valid.jpg` для позитивной OCR smoke-проверки.
- `passport_test.jpg` не является валидным примером паспорта и не подходит как позитивный тест.

## Legacy-заметка

Маршруты `/api/dashboard/*` сохранены только для обратной совместимости старого frontend и скрыты из Swagger.
"""


API_DESCRIPTION_UZ = """
OCR Passport Service API.

## Autentifikatsiya qoidalari

- `POST /api/auth/login` `application/x-www-form-urlencoded` qabul qiladi va JWT qaytaradi.
- `/api/admin/*` va `POST /api/passport/test-ocr` `Authorization: Bearer <token>` ishlatadi.
- `/api/analytics/*` Swagger uchun `Authorization: Bearer <token>` va eski dashboard mosligi uchun `?token=<token>` ni qo'llab-quvvatlaydi.
- `POST /api/passport/scan`, `GET /api/passport/status/{task_id}`, `GET /api/passport/result/{task_id}` va `GET /api/passport/list` joriy realizatsiyada ochiq.

## Test fayllari

- Ijobiy OCR smoke-tekshiruvi uchun `passport_test_valid.jpg` dan foydalaning.
- `passport_test.jpg` pasportning yaroqli namunasi emas va ijobiy test uchun mos emas.

## Legacy izoh

`/api/dashboard/*` marshrutlari eski frontend bilan moslik uchun saqlangan va Swagger'dan yashirilgan.
"""


API_DESCRIPTION_EN = """
OCR Passport Service API.

## Authorization rules

- `POST /api/auth/login` accepts `application/x-www-form-urlencoded` and returns a JWT.
- `/api/admin/*` and `POST /api/passport/test-ocr` use `Authorization: Bearer <token>`.
- `/api/analytics/*` supports `Authorization: Bearer <token>` for Swagger and `?token=<token>` for legacy dashboard compatibility.
- `POST /api/passport/scan`, `GET /api/passport/status/{task_id}`, `GET /api/passport/result/{task_id}` and `GET /api/passport/list` are public in the current implementation.

## Test files

- Use `passport_test_valid.jpg` for a positive OCR smoke test.
- `passport_test.jpg` is not a valid passport sample and is not suitable as a positive test.

## Legacy note

The `/api/dashboard/*` routes are kept only for backward compatibility with the old frontend and are hidden from Swagger.
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
        # Sidebar sections
        "sidebar_getting_started": "Начало работы",
        "sidebar_introduction": "Введение",
        "sidebar_authentication": "Аутентификация",
        "sidebar_quick_start": "Быстрый старт",
        "sidebar_passport_ocr": "Паспорт OCR",
        "sidebar_analytics": "Аналитика",
        "sidebar_admin": "Админ",
        "sidebar_auth": "Авторизация",
        # Hero
        "hero_title_1": "API OCR паспорта на базе ",
        "hero_title_2": "ИИ",
        "hero_desc": "Распознавание всех 11 полей паспорта с точностью 95%+ с помощью ИИ. Создан для скорости, надёжности и простой интеграции.",
        # Right panel
        "panel_quick_start": "Быстрый старт",
        "panel_get_token": "Получите API токен",
        "panel_get_token_desc": "Авторизуйтесь для доступа к документации и эндпоинтам.",
        "panel_example_request": "Пример запроса",
        "panel_response_example": "Пример ответа",
        "panel_extracted_fields": "Распознанные поля",
        # Code tabs
        "tab_curl": "cURL",
        "tab_python": "Python",
        "tab_js": "JavaScript",
        "code_lang_bash": "bash",
        "code_lang_python": "python",
        "code_lang_js": "javascript",
        # Field names
        "field_surname": "Фамилия",
        "field_first_name": "Имя",
        "field_patronymic": "Отчество",
        "field_birth_date": "Дата рождения",
        "field_gender": "Пол",
        "field_passport_number": "Номер паспорта",
        "field_pinfl": "ПИНФЛ",
        # Footer
        "footer_text": "OCRUZ Passport API © 2026",
        # Code comments
        "code_comment_get_token": "# Получить токен",
        "code_comment_test_ocr": "# Тест OCR",
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
        # Sidebar sections
        "sidebar_getting_started": "Boshlanish",
        "sidebar_introduction": "Kirish",
        "sidebar_authentication": "Autentifikatsiya",
        "sidebar_quick_start": "Tezkor boshlash",
        "sidebar_passport_ocr": "Pasport OCR",
        "sidebar_analytics": "Analitika",
        "sidebar_admin": "Admin",
        "sidebar_auth": "Avtorizatsiya",
        # Hero
        "hero_title_1": "AI asosida ",
        "hero_title_2": "Pasport OCR API",
        "hero_desc": "Sun'iy intellekt yordamida pasportning barcha 11 ta maydonini 95%+ aniqlikda tanib olish. Tezlik, ishonchlilik va oson integratsiya uchun yaratilgan.",
        # Right panel
        "panel_quick_start": "Tezkor boshlash",
        "panel_get_token": "API tokeningizni oling",
        "panel_get_token_desc": "Hujjatlar va endpointlarga kirish uchun tizimga kiring.",
        "panel_example_request": "So'rov namunasi",
        "panel_response_example": "Javob namunasi",
        "panel_extracted_fields": "Ajratilgan maydonlar",
        # Code tabs
        "tab_curl": "cURL",
        "tab_python": "Python",
        "tab_js": "JavaScript",
        "code_lang_bash": "bash",
        "code_lang_python": "python",
        "code_lang_js": "javascript",
        # Field names
        "field_surname": "Familiya",
        "field_first_name": "Ism",
        "field_patronymic": "Otasining ismi",
        "field_birth_date": "Tug'ilgan sana",
        "field_gender": "Jins",
        "field_passport_number": "Pasport raqami",
        "field_pinfl": "JSHSHIR",
        # Footer
        "footer_text": "OCRUZ Passport API © 2026",
        # Code comments
        "code_comment_get_token": "# Token olish",
        "code_comment_test_ocr": "# OCR testi",
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
        # Sidebar sections
        "sidebar_getting_started": "Getting Started",
        "sidebar_introduction": "Introduction",
        "sidebar_authentication": "Authentication",
        "sidebar_quick_start": "Quick Start",
        "sidebar_passport_ocr": "Passport OCR",
        "sidebar_analytics": "Analytics",
        "sidebar_admin": "Admin",
        "sidebar_auth": "Auth",
        # Hero
        "hero_title_1": "AI-Powered ",
        "hero_title_2": "Passport OCR API",
        "hero_desc": "Extract all 11 passport fields with 95%+ accuracy using our AI-powered OCR engine. Built for speed, reliability, and seamless integration.",
        # Right panel
        "panel_quick_start": "Quick Start",
        "panel_get_token": "Get your API token",
        "panel_get_token_desc": "Authenticate to access the API documentation and endpoints.",
        "panel_example_request": "Example Request",
        "panel_response_example": "Response Example",
        "panel_extracted_fields": "Extracted Fields",
        # Code tabs
        "tab_curl": "cURL",
        "tab_python": "Python",
        "tab_js": "JavaScript",
        "code_lang_bash": "bash",
        "code_lang_python": "python",
        "code_lang_js": "javascript",
        # Field names
        "field_surname": "Surname",
        "field_first_name": "First Name",
        "field_patronymic": "Patronymic",
        "field_birth_date": "Birth Date",
        "field_gender": "Gender",
        "field_passport_number": "Passport Number",
        "field_pinfl": "PINFL",
        # Footer
        "footer_text": "OCRUZ Passport API © 2026",
        # Code comments
        "code_comment_get_token": "# Get token",
        "code_comment_test_ocr": "# Test OCR",
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
    "en": {
        API_DESCRIPTION_RU.strip(): API_DESCRIPTION_EN.strip(),
        "Получение JWT токена": "Get JWT token",
        "Управление пользователями и ролями": "User and role management",
        "Сводка и аналитические отчеты": "Analytics and reports",
        "OCR загрузка, статус и результаты распознавания": "OCR upload, status and recognition results",
        "Служебные маршруты API": "API service routes",
        "Получить JWT токен": "Get JWT token",
        "Логин для dashboard и API. Запрос принимает только `application/x-www-form-urlencoded` поля `username` и `password`.": "Login for dashboard and API. Request only accepts `application/x-www-form-urlencoded` fields `username` and `password`.",
        "Загрузить файл в OCR-очередь": "Upload file to OCR queue",
        "Асинхронная загрузка документа. В текущей реализации маршрут доступен без авторизации, а dashboard ограничивает доступ на уровне UI.": "Asynchronous document upload. In the current implementation, the route is accessible without authorization, and the dashboard restricts access at the UI level.",
        "Синхронный OCR тест": "Synchronous OCR test",
        "Проверяет одно изображение без создания отдельной заявки в списке обработок.": "Checks one image without creating a separate entry in the processed list.",
        "Статус OCR-задачи": "OCR task status",
        "Проверить статус обработки паспорта": "Check passport processing status",
        "Результат OCR-задачи": "OCR task result",
        "Получить результат распознавания паспорта": "Get passport recognition result",
        "Список обработанных загрузок": "List of processed uploads",
        "Список всех обработанных паспортов с фильтрацией": "List of all processed passports with filtering",
        "Получить доступные роли": "Get available roles",
        "Получить список доступных ролей (только админ)": "Get list of available roles (admin only)",
        "Список пользователей": "User list",
        "Список всех пользователей (ТОЛЬКО АДМИНИСТРАТОР)": "List of all users (ADMIN ONLY)",
        "Создать пользователя": "Create user",
        "Создать нового пользователя (ТОЛЬКО АДМИНИСТРАТОР)\n\nРоли:\n- admin: полный доступ\n- observer: только просмотр отчетов": "Create new user (ADMIN ONLY)\n\nRoles:\n- admin: full access\n- observer: view reports only",
        "Текущий пользователь": "Current user",
        "Получить информацию о текущем пользователе": "Get current user information",
        "Обновить пользователя": "Update user",
        "Обновить пользователя (ТОЛЬКО АДМИНИСТРАТОР)\n\nМожно изменить:\n- Роль (admin/observer)\n- Статус (active/inactive)\n- Пароль": "Update user (ADMIN ONLY)\n\nCan change:\n- Role (admin/observer)\n- Status (active/inactive)\n- Password",
        "Удалить пользователя": "Delete user",
        "Удалить пользователя (ТОЛЬКО АДМИНИСТРАТОР)": "Delete user (ADMIN ONLY)",
        "Сбросить пароль пользователя": "Reset user password",
        "Сбросить пароль пользователя (ТОЛЬКО АДМИНИСТРАТОР)": "Reset user password (ADMIN ONLY)",
        "Сводка по распознанным паспортам": "Summary of recognized passports",
        "Возвращает верхнеуровневые метрики dashboard. В `total_passports` попадают только загрузки, где OCR распознал паспортные поля. `total_uploads` содержит все загруженные файлы.": "Returns top-level dashboard metrics. `total_passports` includes only uploads where OCR recognized passport fields. `total_uploads` contains all uploaded files.",
        "Отчет по полу": "Gender report",
        "Отчет по полу: кто больше - мужчин или женщин\n\n🔓 Доступно: admin, observer": "Gender report: more men or women\n\n🔓 Available: admin, observer",
        "Отчет по возрастным группам": "Age group report",
        "Отчет по возрастным группам\n\n🔓 Доступно: admin, observer": "Age group report\n\n🔓 Available: admin, observer",
        "Отчет по гражданству": "Nationality report",
        "Отчет по гражданству/национальности\n\n🔓 Доступно: admin, observer": "Citizenship/nationality report\n\n🔓 Available: admin, observer",
        "Поступления за период": "Submissions by period",
        "Отчет по времени: поступления за период\n\n🔓 Доступно: admin, observer": "Time report: submissions by period\n\n🔓 Available: admin, observer",
        "Статистика по месяцам": "Monthly statistics",
        "Статистика по месяцам за год\n\n🔓 Доступно: admin, observer": "Monthly statistics for the year\n\n🔓 Available: admin, observer",
        "Статистика по годам": "Yearly statistics",
        "Статистика по годам\n\n🔓 Доступно: admin, observer": "Yearly statistics\n\n🔓 Available: admin, observer",
        "Пол по возрастным группам": "Gender by age group",
        "Соотношение пола по возрастным группам\n\n🔓 Доступно: admin, observer": "Gender ratio by age group\n\n🔓 Available: admin, observer",
        "Поступления по дням": "Daily submissions",
        "Поступления по дням\n\n🔓 Доступно: admin, observer": "Daily submissions\n\n🔓 Available: admin, observer",
        "Логи доступа": "Access logs",
        "Доступно только роли `admin`.": "Available to `admin` role only.",
        "Проверить состояние API": "Check API health",
        "JWT токен в query. Нужен для legacy dashboard compatibility.": "JWT token in query. Needed for legacy dashboard compatibility.",
        "Топ N национальностей": "Top N nationalities",
        "period: day, week, month, year": "Period: day, week, month, year",
        "Год (по умолчанию текущий)": "Year (defaults to current)",
        "Количество дней": "Number of days",
        "JWT-токен в query. Нужен для совместимости со старым dashboard.": "JWT token in query. Needed for legacy dashboard compatibility.",
        "Доступно только пользователю с ролью `admin`.": "Available to user with `admin` role only.",
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
        "__LOGIN_SUBTITLE__": labels["login_subtitle"],
        "__FOOTER__": labels["footer_text"],
        "__SPEC_URL__": spec_url,
        "__LANG_LINKS__": (
            lang_link("ru", labels["lang_ru"])
            + lang_link("uz", labels["lang_uz"])
            + lang_link("en", labels["lang_en"])
        ),
        # Sidebar
        "__SIDEBAR_GETTING_STARTED__": labels["sidebar_getting_started"],
        "__SIDEBAR_INTRODUCTION__": labels["sidebar_introduction"],
        "__SIDEBAR_AUTHENTICATION__": labels["sidebar_authentication"],
        "__SIDEBAR_QUICK_START__": labels["sidebar_quick_start"],
        "__SIDEBAR_PASSPORT_OCR__": labels["sidebar_passport_ocr"],
        "__SIDEBAR_ANALYTICS__": labels["sidebar_analytics"],
        "__SIDEBAR_ADMIN__": labels["sidebar_admin"],
        "__SIDEBAR_AUTH__": labels["sidebar_auth"],
        # Hero
        "__HERO_TITLE_1__": labels["hero_title_1"],
        "__HERO_TITLE_2__": labels["hero_title_2"],
        "__HERO_DESC__": labels["hero_desc"],
        # Right panel
        "__PANEL_QUICK_START__": labels["panel_quick_start"],
        "__PANEL_GET_TOKEN__": labels["panel_get_token"],
        "__PANEL_GET_TOKEN_DESC__": labels["panel_get_token_desc"],
        "__PANEL_EXAMPLE_REQUEST__": labels["panel_example_request"],
        "__PANEL_RESPONSE_EXAMPLE__": labels["panel_response_example"],
        "__PANEL_EXTRACTED_FIELDS__": labels["panel_extracted_fields"],
        # Code tabs
        "__TAB_CURL__": labels["tab_curl"],
        "__TAB_PYTHON__": labels["tab_python"],
        "__TAB_JS__": labels["tab_js"],
        "__CODE_LANG_BASH__": labels["code_lang_bash"],
        "__CODE_LANG_PYTHON__": labels["code_lang_python"],
        "__CODE_LANG_JS__": labels["code_lang_js"],
        # Field names
        "__FIELD_SURNAME__": labels["field_surname"],
        "__FIELD_FIRST_NAME__": labels["field_first_name"],
        "__FIELD_PATRONYMIC__": labels["field_patronymic"],
        "__FIELD_BIRTH_DATE__": labels["field_birth_date"],
        "__FIELD_GENDER__": labels["field_gender"],
        "__FIELD_PASSPORT_NUMBER__": labels["field_passport_number"],
        "__FIELD_PINFL__": labels["field_pinfl"],
        # Code comments
        "__CODE_COMMENT_GET_TOKEN__": labels["code_comment_get_token"],
        "__CODE_COMMENT_TEST_OCR__": labels["code_comment_test_ocr"],
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
        "__FOOTER__": labels["footer_text"],
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

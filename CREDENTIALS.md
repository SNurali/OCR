# 🔐 OCRUZ Passport API Credentials

## Admin Login
- **Username:** `admin`
- **Password:** `admin123`

## Database Credentials
- **Host:** localhost
- **Port:** 5432
- **User:** ocr_user
- **Password:** ocr_secure_password
- **Database:** ocr_service

## Redis
- **URL:** redis://localhost:6379/0

## JWT Secret
- **Key:** test-secret-key-for-development-only

> ⚠️ **ВАЖНО:** Эти учетные данные только для разработки! 
> В продакшене используйте надежные пароли и секреты.

## How to reset admin password
```bash
cd /path/to/ocr-service
python3 reset_admin_password.py [new_password]
```
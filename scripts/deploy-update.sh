#!/bin/bash

# ===========================================
# Скрипт обновления боевого сервера
# OCR Service - Deployment Update Script
# ===========================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}[INFO] $1${NC}"; }
log_success() { echo -e "${GREEN}[OK] $1${NC}"; }
log_warning() { echo -e "${YELLOW}[WARN] $1${NC}"; }
log_error()   { echo -e "${RED}[ERROR] $1${NC}"; }

check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker не найден."
        exit 1
    fi
    if ! docker compose version &> /dev/null; then
        log_error "Docker Compose v2 не найден."
        exit 1
    fi
}

update_code() {
    log_info "Обновление кода из Git..."
    git fetch origin main
    if ! git diff --quiet HEAD origin/main; then
        git reset --hard origin/main
        log_success "Код обновлён"
    else
        log_info "Код актуален"
    fi
}

stop_service() {
    log_info "Остановка контейнеров проекта..."
    docker compose -f docker-compose.prod.yml down
    log_success "Контейнеры остановлены"
}

clean_cache() {
    log_info "Очистка кэша..."
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    log_success "Кэш очищен"
}

start_service() {
    log_info "Сборка и запуск..."
    docker compose -f docker-compose.prod.yml up -d --build
    log_success "Контейнеры запущены"
}

check_health() {
    log_info "Проверка здоровья сервисов..."
    sleep 5
    docker compose -f docker-compose.prod.yml ps
    echo ""
    log_info "Логи API:"
    docker compose -f docker-compose.prod.yml logs --tail=10 api
}

main() {
    check_docker
    update_code
    stop_service
    clean_cache
    start_service
    check_health
    log_success "Обновление завершено!"
}

main "$@"

# 🚀 OCR Service - Deployment Guide

## ✅ Production Deployment (Docker Compose)

### Ports
- **API:** 3000

---

## 📍 Access URLs (example)
```
http://<YOUR_SERVER_IP>:3000/health
http://<YOUR_SERVER_IP>:3000/docs
```

---

## 🛠️ Management Commands

### Start/Restart Services:
```bash
# Docker Compose (prod)
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml down
```

### Logs:
```bash
# Docker logs
docker compose -f docker-compose.prod.yml logs -f
```

---

## 📁 Project Location
```
/home/yoyo/ocr-service/
```

### Structure:
```
├── app/              # FastAPI Application
├── models/           # ONNX / OCR ML Models
├── pyproject.toml
└── docker-compose.prod.yml
```

---

## ⚙️ Configuration Files

### Environment:
```
/home/yoyo/ocr-service/.env.prod   # generated for Docker Compose
```

---

## 📊 Database

- **PostgreSQL:** localhost:5432
- **Database:** ocr_service_db
- **User:** ocr_service

---

## 🔄 Rebuild & Deploy Updates

```bash
cd /home/yoyo/ocr-service

# Pull latest changes
git pull

# Deploy
docker compose -f docker-compose.prod.yml up -d --build

# Check logs
docker compose -f docker-compose.prod.yml logs -f api
```

---

## 🆘 Troubleshooting

### API not responding:
```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs
```

### Port already in use:
```bash
sudo lsof -i :3000
sudo kill -9 <PID>
```

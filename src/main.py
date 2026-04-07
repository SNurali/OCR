"""
FastAPI сервис для OCR узбекских паспортов.
"""
import os
import io
import cv2
import numpy as np
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
from PIL import Image
import uvicorn

from passport_ocr import UzbekPassportOCR, OCRResult


app = FastAPI(
    title="Uzbek Passport OCR API",
    description="API для распознавания данных из паспортов Узбекистана с высокой точностью",
    version="1.0.0"
)

# Инициализация OCR
ocr_engine = UzbekPassportOCR()


class PassportDataResponse(BaseModel):
    """Ответ с данными паспорта."""
    surname: str
    given_name: str
    patronymic: str
    date_of_birth: str
    nationality: str
    passport_number: str
    passport_series: str
    issue_date: str
    expiry_date: str
    issuing_authority: str
    sex: str
    pinfl: str
    mrz_line1: str
    mrz_line2: str


class OCRResponse(BaseModel):
    """Полный ответ OCR."""
    success: bool
    confidence: float
    mrz_valid: bool
    data: PassportDataResponse
    errors: List[str]
    processing_time_ms: Optional[float] = None


class HealthResponse(BaseModel):
    """Ответ проверки здоровья сервиса."""
    status: str
    version: str


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Проверка работоспособности сервиса."""
    return HealthResponse(status="healthy", version="1.0.0")


@app.post("/api/v1/ocr/passport", response_model=OCRResponse)
async def process_passport(file: UploadFile = File(...)):
    """
    Обработка изображения паспорта и извлечение данных.
    
    - **file**: Изображение паспорта (JPEG, PNG)
    
    Returns извлеченные данные с уровнем уверенности.
    """
    import time
    start_time = time.time()
    
    # Проверка формата файла
    allowed_types = ['image/jpeg', 'image/png', 'image/jpg', 'image/webp']
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_types)}"
        )
    
    try:
        # Чтение файла
        contents = await file.read()
        
        # Конвертация в numpy array
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise HTTPException(
                status_code=400,
                detail="Invalid image file"
            )
        
        # Обработка OCR
        result = ocr_engine.process_image(image)
        
        processing_time = (time.time() - start_time) * 1000
        
        # Формирование ответа
        return OCRResponse(
            success=result.success,
            confidence=result.confidence,
            mrz_valid=result.mrz_valid,
            data=PassportDataResponse(
                surname=result.data.surname,
                given_name=result.data.given_name,
                patronymic=result.data.patronymic,
                date_of_birth=result.data.date_of_birth,
                nationality=result.data.nationality,
                passport_number=result.data.passport_number,
                passport_series=result.data.passport_series,
                issue_date=result.data.issue_date,
                expiry_date=result.data.expiry_date,
                issuing_authority=result.data.issuing_authority,
                sex=result.data.sex,
                pinfl=result.data.pinfl,
                mrz_line1=result.data.mrz_line1,
                mrz_line2=result.data.mrz_line2
            ),
            errors=result.errors,
            processing_time_ms=round(processing_time, 2)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/ocr/passport/debug")
async def process_passport_debug(file: UploadFile = File(...)):
    """
    Отладочная версия с сырым текстом OCR.
    
    Возвращает также сырой распознанный текст для отладки.
    """
    allowed_types = ['image/jpeg', 'image/png', 'image/jpg', 'image/webp']
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_types)}"
        )
    
    try:
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise HTTPException(status_code=400, detail="Invalid image file")
        
        result = ocr_engine.process_image(image)
        
        return {
            "success": result.success,
            "confidence": result.confidence,
            "mrz_valid": result.mrz_valid,
            "data": {
                "surname": result.data.surname,
                "given_name": result.data.given_name,
                "patronymic": result.data.patronymic,
                "date_of_birth": result.data.date_of_birth,
                "nationality": result.data.nationality,
                "passport_number": result.data.passport_number,
                "passport_series": result.data.passport_series,
                "issue_date": result.data.issue_date,
                "expiry_date": result.data.expiry_date,
                "issuing_authority": result.data.issuing_authority,
                "sex": result.data.sex,
                "pinfl": result.data.pinfl,
                "mrz_line1": result.data.mrz_line1,
                "mrz_line2": result.data.mrz_line2
            },
            "errors": result.errors,
            "raw_text": result.raw_text
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """Корневой endpoint с информацией об API."""
    return {
        "service": "Uzbek Passport OCR API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "ocr": "/api/v1/ocr/passport",
            "ocr_debug": "/api/v1/ocr/passport/debug"
        },
        "docs": "/docs"
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

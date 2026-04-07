from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import DashboardUser
from app.auth import verify_password, create_dashboard_token
from app.schemas import DashboardTokenResponse
from app.limiter import limiter

router = APIRouter()


@router.post(
    "/login",
    response_model=DashboardTokenResponse,
    summary="Получить JWT токен",
    description=(
        "Логин для dashboard и API. Запрос принимает только "
        "`application/x-www-form-urlencoded` поля `username` и `password`."
    ),
)
@limiter.limit("10/minute")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = (
        db.query(DashboardUser)
        .filter(DashboardUser.username == form_data.username)
        .first()
    )

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )

    token = create_dashboard_token(user.id, user.username)

    return DashboardTokenResponse(
        access_token=token,
        expires_in=8 * 60 * 60,
    )

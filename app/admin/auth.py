import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.core.config import settings

security = HTTPBasic()


def verify_admin(credentials: HTTPBasicCredentials = Depends(security)):
    correct_login = secrets.compare_digest(
        credentials.username, settings.ADMIN_LOGIN
    )
    correct_password = secrets.compare_digest(
        credentials.password, settings.ADMIN_PASSWORD.get_secret_value()
    )
    if not (correct_login and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

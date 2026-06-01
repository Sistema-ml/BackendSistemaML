# app/core/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.security import decode_access_token
from app.core.supabase import get_supabase

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """
    Extrae y valida el JWT del header Authorization: Bearer <token>.
    Retorna el payload del token con id, email y rol del usuario.
    """
    token = credentials.credentials
    payload = decode_access_token(token)

    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload  # {"sub": uuid, "email": ..., "rol": ..., "nombre": ...}


def require_roles(*roles: str):
    """
    Fábrica de dependencias para proteger rutas por rol.
    Uso: Depends(require_roles("administrador", "supervisor"))
    """
    def _check(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user.get("rol") not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Se requiere uno de los roles: {', '.join(roles)}",
            )
        return current_user

    return _check


# Atajos de uso común
require_admin       = require_roles("administrador")
require_supervisor  = require_roles("administrador", "supervisor")
require_any_role    = require_roles("administrador", "supervisor", "empleado")

# app/schemas/usuarios.py
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class UsuarioCreate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=100)
    apellido: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8)
    rol: str = Field(default="empleado")

    class Config:
        json_schema_extra = {
            "example": {
                "nombre": "Carlos",
                "apellido": "Quispe",
                "email": "c.quispe@municipalidadyau.gob.pe",
                "password": "Segura123!",
                "rol": "empleado",
            }
        }


class UsuarioUpdate(BaseModel):
    nombre: Optional[str] = Field(None, min_length=2, max_length=100)
    apellido: Optional[str] = Field(None, min_length=2, max_length=100)
    rol: Optional[str] = None
    activo: Optional[bool] = None


class UsuarioOut(BaseModel):
    id: str
    nombre: str
    apellido: str
    email: str
    rol: str
    activo: bool
    created_at: datetime


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioOut

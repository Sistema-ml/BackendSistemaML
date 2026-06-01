# app/schemas/ciudadanos.py
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import date, datetime


class CiudadanoCreate(BaseModel):
    dni: str = Field(..., min_length=8, max_length=8, pattern=r"^\d{8}$")
    nombre: str = Field(..., min_length=2, max_length=100)
    apellido: str = Field(..., min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    telefono: Optional[str] = Field(None, max_length=15)
    direccion: Optional[str] = None
    fecha_nac: Optional[date] = None


class CiudadanoUpdate(BaseModel):
    nombre: Optional[str] = Field(None, min_length=2, max_length=100)
    apellido: Optional[str] = Field(None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    telefono: Optional[str] = Field(None, max_length=15)
    direccion: Optional[str] = None
    fecha_nac: Optional[date] = None


class CiudadanoOut(BaseModel):
    id: str
    dni: str
    nombre: str
    apellido: str
    email: Optional[str]
    telefono: Optional[str]
    direccion: Optional[str]
    activo: bool
    created_at: datetime


# ─────────────────────────────────────────────────────────────
# app/schemas/tramites.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

ESTADOS_TRAMITE   = ["pendiente", "en_revision", "observado", "aprobado", "rechazado"]
PRIORIDADES       = ["alta", "media", "baja"]
AREAS_RESPONSABLE = [
    "Obras Públicas", "Licencias", "Rentas", "Registro Civil",
    "Medio Ambiente", "Desarrollo Social", "Administración", "Legal"
]


class TramiteCreate(BaseModel):
    ciudadano_id: str
    tipo_tramite: str = Field(..., min_length=3, max_length=80)
    descripcion: Optional[str] = None
    area_responsable: str = Field(..., max_length=80)
    nivel_urgencia: int = Field(default=2, ge=1, le=5)
    observaciones: Optional[str] = None
    usuario_asignado_id: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "ciudadano_id": "uuid-del-ciudadano",
                "tipo_tramite": "Licencia de Construcción",
                "descripcion": "Solicitud para edificio de 3 pisos",
                "area_responsable": "Obras Públicas",
                "nivel_urgencia": 3,
            }
        }


class TramiteUpdate(BaseModel):
    tipo_tramite: Optional[str]      = Field(None, max_length=80)
    descripcion: Optional[str]       = None
    area_responsable: Optional[str]  = Field(None, max_length=80)
    estado: Optional[str]            = Field(None)
    prioridad: Optional[str]         = Field(None)
    nivel_urgencia: Optional[int]    = Field(None, ge=1, le=5)
    observaciones: Optional[str]     = None
    usuario_asignado_id: Optional[str] = None
    fecha_resolucion: Optional[datetime] = None


class CiudadanoBasico(BaseModel):
    id: Optional[str] = None
    dni: Optional[str] = None
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None

    class Config:
        extra = "allow"


class TramiteOut(BaseModel):
    id: str
    codigo: str
    ciudadano_id: str
    tipo_tramite: str
    descripcion: Optional[str]
    area_responsable: str
    estado: str
    prioridad: str
    nivel_urgencia: int
    tiempo_espera_dias: int
    cantidad_documentos: int
    observaciones: Optional[str]
    usuario_asignado_id: Optional[str]
    fecha_registro: datetime
    fecha_resolucion: Optional[datetime]
    created_at: datetime
    ciudadanos: Optional[CiudadanoBasico] = None

    class Config:
        extra = "allow"


# ─────────────────────────────────────────────────────────────
# app/schemas/documentos.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class DocumentoOut(BaseModel):
    id: str
    tramite_id: str
    nombre_archivo: str
    ruta_storage: str
    bucket: str
    tipo_mime: str
    tamanio_bytes: Optional[int]
    subido_por: Optional[str]
    created_at: datetime


# ─────────────────────────────────────────────────────────────
# app/schemas/notificaciones.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class NotificacionOut(BaseModel):
    id: str
    tramite_id: str
    ciudadano_id: str
    tipo: str
    mensaje: str
    email_destino: Optional[str]
    enviado: bool
    enviado_at: Optional[datetime]
    created_at: datetime


# ─────────────────────────────────────────────────────────────
# app/schemas/ml.py
from pydantic import BaseModel, Field


class MLPredictRequest(BaseModel):
    tipo_tramite: str
    area_responsable: str
    tiempo_espera_dias: int = Field(..., ge=0)
    cantidad_documentos: int = Field(..., ge=0)
    nivel_urgencia: Optional[int] = None  # ignorado, mantenido por compatibilidad


class MLPredictResponse(BaseModel):
    prioridad: str                   # alta | media | baja
    probabilidades: dict[str, float] # {"alta": 0.7, "media": 0.2, "baja": 0.1}
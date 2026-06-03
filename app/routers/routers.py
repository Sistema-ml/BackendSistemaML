# app/routers/auth.py
from fastapi import APIRouter, HTTPException, status, Depends
from app.schemas.usuarios import LoginRequest, TokenResponse, UsuarioCreate, UsuarioOut, UsuarioUpdate
from app.services.ciudadano_auth_service import login, crear_usuario, listar_usuarios, actualizar_usuario
from app.core.dependencies import get_current_user, require_admin
from app.core.supabase import get_supabase

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/login", response_model=TokenResponse)
def do_login(body: LoginRequest):
    result = login(body.email, body.password)
    if not result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")
    return TokenResponse(access_token=result["token"], usuario=result["usuario"])


@router.get("/me", response_model=dict)
def me(current=Depends(get_current_user)):
    return current


@router.post("/usuarios", response_model=UsuarioOut, dependencies=[Depends(require_admin)])
def crear(body: UsuarioCreate):
    data = body.model_dump()
    password_plano = data["password"]
    nuevo = crear_usuario(data)
    try:
        from app.services.documento_notif_service import _enviar_email
        from app.core.config import get_settings
        cfg = get_settings()
        print(f"SMTP CONFIG: host={cfg.smtp_host} user='{cfg.smtp_user}' password='{cfg.smtp_password}'")
        if cfg.smtp_user:
            _enviar_email(
                nuevo["email"],
                "Bienvenido al Sistema - Municipalidad Provincial de Yau",
                f"Hola {nuevo['nombre']}, tu cuenta ha sido creada.<br><br>"
                f"<b>Email:</b> {nuevo['email']}<br>"
                f"<b>Contraseña:</b> {password_plano}<br>"
                f"<b>Rol:</b> {nuevo['rol']}<br><br>"
                "Por favor cambia tu contraseña al iniciar sesión.",
            )
    except Exception as e:
        print(f"ERROR EMAIL: {e}")
    return nuevo


@router.get("/usuarios", response_model=list[UsuarioOut], dependencies=[Depends(require_admin)])
def listar():
    return listar_usuarios()


@router.patch("/usuarios/{usuario_id}", response_model=UsuarioOut, dependencies=[Depends(require_admin)])
def actualizar(usuario_id: str, body: UsuarioUpdate):
    updated = actualizar_usuario(usuario_id, body.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return updated

@router.delete("/usuarios/{usuario_id}", status_code=204, dependencies=[Depends(require_admin)])
def eliminar_usuario(usuario_id: str):
    sb = get_supabase()
    res = sb.table("usuarios").delete().eq("id", usuario_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

# ─────────────────────────────────────────────────────────────
# app/routers/ciudadanos.py
from fastapi import APIRouter, HTTPException, Depends
from app.schemas.schemas import CiudadanoCreate, CiudadanoUpdate, CiudadanoOut
from app.services.ciudadano_auth_service import (
    crear_ciudadano, listar_ciudadanos, obtener_ciudadano,
    buscar_ciudadano_dni, actualizar_ciudadano, historial_ciudadano,
)
from app.core.dependencies import require_any_role
from app.core.supabase import get_supabase

router_ciudadanos = APIRouter(prefix="/ciudadanos", tags=["Ciudadanos"],
                              dependencies=[Depends(require_any_role)])


@router_ciudadanos.post("/", response_model=CiudadanoOut, status_code=201)
def crear(body: CiudadanoCreate):
    return crear_ciudadano(body.model_dump())


@router_ciudadanos.get("/", response_model=list[CiudadanoOut])
def listar(skip: int = 0, limit: int = 50):
    return listar_ciudadanos(skip, limit)


@router_ciudadanos.get("/buscar", response_model=CiudadanoOut)
def buscar_dni(dni: str):
    c = buscar_ciudadano_dni(dni)
    if not c:
        raise HTTPException(status_code=404, detail="Ciudadano no encontrado")
    return c


@router_ciudadanos.get("/{ciudadano_id}", response_model=CiudadanoOut)
def obtener(ciudadano_id: str):
    c = obtener_ciudadano(ciudadano_id)
    if not c:
        raise HTTPException(status_code=404, detail="Ciudadano no encontrado")
    return c


@router_ciudadanos.patch("/{ciudadano_id}", response_model=CiudadanoOut)
def actualizar(ciudadano_id: str, body: CiudadanoUpdate):
    updated = actualizar_ciudadano(ciudadano_id, body.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Ciudadano no encontrado")
    return updated


@router_ciudadanos.get("/{ciudadano_id}/historial")
def historial(ciudadano_id: str):
    return historial_ciudadano(ciudadano_id)

@router_ciudadanos.delete("/{ciudadano_id}", status_code=204)
def eliminar(ciudadano_id: str):
    sb = get_supabase()
    sb.table("ciudadanos").update({"activo": False}).eq("id", ciudadano_id).execute()
# ─────────────────────────────────────────────────────────────
# app/routers/tramites.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.schemas.schemas import TramiteCreate, TramiteUpdate, TramiteOut
from app.services.tramite_service import (
    crear_tramite, listar_tramites, obtener_tramite,
    buscar_tramite_codigo, actualizar_tramite, historial_tramite,
    dashboard_resumen, cambiar_estado_tramite,
)
from app.core.dependencies import require_any_role, get_current_user

router_tramites = APIRouter(prefix="/tramites", tags=["Trámites"],
                            dependencies=[Depends(require_any_role)])


@router_tramites.post("/", response_model=TramiteOut, status_code=201)
def crear(body: TramiteCreate):
    return crear_tramite(body.model_dump())


@router_tramites.get("/")
def listar(estado: str | None = None, prioridad: str | None = None,
           area: str | None = None, skip: int = 0, limit: int = 50):
    return listar_tramites(estado, prioridad, area, skip, limit)


@router_tramites.get("/buscar")
def buscar_codigo(codigo: str):
    t = buscar_tramite_codigo(codigo)
    if not t:
        raise HTTPException(status_code=404, detail="Trámite no encontrado")
    return t


@router_tramites.get("/dashboard")
def dashboard():
    return dashboard_resumen()


@router_tramites.get("/{tramite_id}", response_model=TramiteOut)
def obtener(tramite_id: str):
    t = obtener_tramite(tramite_id)
    if not t:
        raise HTTPException(status_code=404, detail="Trámite no encontrado")
    return t


ESTADO_MAP = {
    "pendiente": "pendiente",
    "en revision": "en_revision",
    "en revisión": "en_revision",
    "en_revision": "en_revision",
    "en_revisión": "en_revision",
    "observado": "observado",
    "aprobado": "aprobado",
    "rechazado": "rechazado",
}


@router_tramites.patch("/{tramite_id}", response_model=TramiteOut)
def actualizar(tramite_id: str, body: TramiteUpdate, current=Depends(get_current_user)):
    data = body.model_dump(exclude_none=True)
    if "estado" in data:
        data["estado"] = ESTADO_MAP.get(data["estado"].lower(), data["estado"].lower())
    updated = actualizar_tramite(tramite_id, data, current["sub"])
    if not updated:
        raise HTTPException(status_code=404, detail="Trámite no encontrado")
    # Enviar correo al ciudadano
    try:
        from app.services.documento_notif_service import _enviar_email
        from app.core.supabase import get_supabase
        from app.core.config import get_settings
        cfg = get_settings()
        if cfg.smtp_user and "estado" in data:
            sb = get_supabase()
            ciudadano = sb.table("ciudadanos").select("nombre, apellido, email").eq("id", updated["ciudadano_id"]).single().execute().data
            if ciudadano and ciudadano.get("email"):
                _enviar_email(
                    ciudadano["email"],
                    f"Actualización de su trámite - {updated['codigo']}",
                    f"Estimado/a {ciudadano['nombre']} {ciudadano['apellido']},<br><br>"
                    f"Su trámite <b>{updated['codigo']}</b> ha sido actualizado.<br><br>"
                    f"<b>Estado actual:</b> {updated['estado']}<br>"
                    f"<b>Asunto:</b> {updated.get('asunto', '')}<br><br>"
                    "Para más información comuníquese con la Municipalidad Provincial de Yau.",
                )
    except Exception as e:
        print(f"ERROR EMAIL TRAMITE: {e}")
    return updated


@router_tramites.get("/{tramite_id}/historial")
def historial(tramite_id: str):
    return historial_tramite(tramite_id)


class CambiarEstadoBody(BaseModel):
    estado: str
    observacion: str | None = None


@router_tramites.patch("/{tramite_id}/estado")
def cambiar_estado(tramite_id: str, body: CambiarEstadoBody, current=Depends(get_current_user)):
    estado_final = ESTADO_MAP.get(body.estado.lower(), body.estado.lower())
    updated = cambiar_estado_tramite(tramite_id, estado_final, body.observacion, current["sub"])
    if not updated:
        raise HTTPException(status_code=404, detail="Trámite no encontrado")
    # Enviar correo al ciudadano
    try:
        from app.services.documento_notif_service import _enviar_email
        from app.core.supabase import get_supabase
        from app.core.config import get_settings
        cfg = get_settings()
        if cfg.smtp_user:
            sb = get_supabase()
            ciudadano = sb.table("ciudadanos").select("nombre, apellido, email").eq("id", updated["ciudadano_id"]).single().execute().data
            if ciudadano and ciudadano.get("email"):
                observacion_texto = f"<br><b>Observación:</b> {body.observacion}" if body.observacion else ""
                _enviar_email(
                    ciudadano["email"],
                    f"Cambio de estado de su trámite - {updated['codigo']}",
                    f"Estimado/a {ciudadano['nombre']} {ciudadano['apellido']},<br><br>"
                    f"El estado de su trámite <b>{updated['codigo']}</b> ha cambiado.<br><br>"
                    f"<b>Nuevo estado:</b> {estado_final}<br>"
                    f"<b>Asunto:</b> {updated.get('asunto', '')}<br>"
                    f"{observacion_texto}<br><br>"
                    "Para más información comuníquese con la Municipalidad Provincial de Yau.",
                )
    except Exception as e:
        print(f"ERROR EMAIL ESTADO: {e}")
    return updated

@router_tramites.patch("/{tramite_id}/estado")
def cambiar_estado(tramite_id: str, body: TramiteUpdate, current=Depends(get_current_user)):
    updated = actualizar_tramite(tramite_id, body.model_dump(exclude_none=True), current["sub"])
    if not updated:
        raise HTTPException(status_code=404, detail="Trámite no encontrado")
    return updated

@router_tramites.delete("/{tramite_id}", status_code=204)
def eliminar(tramite_id: str):
    sb = get_supabase()
    sb.table("tramites").update({"activo": False}).eq("id", tramite_id).execute()

# ─────────────────────────────────────────────────────────────
# app/routers/documentos.py
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from app.services.documento_notif_service import subir_documento, listar_documentos, url_descarga, eliminar_documento
from app.core.dependencies import require_any_role, get_current_user

router_documentos = APIRouter(prefix="/documentos", tags=["Documentos"],
                              dependencies=[Depends(require_any_role)])

MAX_SIZE = 10 * 1024 * 1024  # 10 MB


@router_documentos.post("/{tramite_id}", status_code=201)
async def subir(tramite_id: str, file: UploadFile = File(...), current=Depends(get_current_user)):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Solo se permiten archivos PDF")
    contenido = await file.read()
    if len(contenido) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="El archivo supera los 10 MB")
    return subir_documento(tramite_id, file.filename, contenido, file.content_type, current["sub"])


@router_documentos.get("/{tramite_id}")
def listar(tramite_id: str):
    return listar_documentos(tramite_id)


@router_documentos.get("/{documento_id}/url")
def get_url(documento_id: str):
    from app.core.supabase import get_supabase
    sb = get_supabase()
    doc = sb.table("documentos").select("ruta_storage").eq("id", documento_id).single().execute().data
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return {"url": url_descarga(doc["ruta_storage"])}


@router_documentos.delete("/{documento_id}", status_code=204)
def eliminar(documento_id: str):
    ok = eliminar_documento(documento_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Documento no encontrado")


# ─────────────────────────────────────────────────────────────
# app/routers/ml.py
from fastapi import APIRouter, Depends
from app.schemas.schemas import MLPredictRequest, MLPredictResponse
from app.services.ml_service import predecir_con_probabilidades, entrenar_modelo
from app.core.dependencies import require_admin, require_any_role

router_ml = APIRouter(prefix="/ml", tags=["Machine Learning"])


@router_ml.post("/predecir", response_model=MLPredictResponse, dependencies=[Depends(require_any_role)])
def predecir(body: MLPredictRequest):
    result = predecir_con_probabilidades(**body.model_dump())
    return MLPredictResponse(**result)


@router_ml.post("/entrenar", dependencies=[Depends(require_admin)])
def entrenar():
    """Re-entrena el modelo (solo administradores)."""
    return entrenar_modelo()

from fastapi import APIRouter, Depends
from app.core.dependencies import require_any_role
from app.core.supabase import get_supabase

router_notificaciones = APIRouter(
    prefix="/notificaciones",
    tags=["Notificaciones"],
    dependencies=[Depends(require_any_role)],
)

@router_notificaciones.get("/")
def listar(no_leidas: bool | None = None):
    sb = get_supabase()
    query = sb.table("notificaciones").select("*").order("created_at", desc=True)
    if no_leidas:
        query = query.eq("leida", False)
    return query.execute().data

@router_notificaciones.patch("/{notificacion_id}/leida")
def marcar_leida(notificacion_id: str):
    sb = get_supabase()
    res = sb.table("notificaciones").update({"leida": True}).eq("id", notificacion_id).execute()
    return res.data[0] if res.data else {}

@router_notificaciones.patch("/marcar-todas-leidas")
def marcar_todas_leidas():
    sb = get_supabase()
    sb.table("notificaciones").update({"leida": True}).eq("leida", False).execute()
    return {"ok": True}
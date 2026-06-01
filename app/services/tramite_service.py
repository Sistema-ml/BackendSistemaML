# app/services/tramite_service.py
from app.core.supabase import get_supabase
from app.services.ml_service import predecir_prioridad
from app.services.documento_notif_service import crear_notificacion


def crear_tramite(data: dict) -> dict:
    """
    Registra un trámite nuevo.
    1. Llama al modelo ML para predecir prioridad.
    2. Inserta en la base de datos.
    3. Crea la notificación de registro.
    """
    sb = get_supabase()

    # 1. Predicción ML
    prioridad = predecir_prioridad(
        tipo_tramite=data["tipo_tramite"],
        nivel_urgencia=data.get("nivel_urgencia", 2),
        area_responsable=data["area_responsable"],
        tiempo_espera_dias=data.get("tiempo_espera_dias", 0),
        cantidad_documentos=data.get("cantidad_documentos", 0),
    )
    data["prioridad"] = prioridad

    # 2. Insertar
    res = sb.table("tramites").insert(data).execute()
    tramite = res.data[0]

    # 3. Notificación
    crear_notificacion(
        tramite_id=tramite["id"],
        ciudadano_id=tramite["ciudadano_id"],
        tipo="registro",
        mensaje=f"Su trámite {tramite['codigo']} ha sido registrado con prioridad {prioridad}.",
    )

    return tramite


def listar_tramites(
    estado: str | None = None,
    prioridad: str | None = None,
    area: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list:
    sb = get_supabase()
    query = (
        sb.table("tramites")
        .select("*, ciudadanos(dni, nombre, apellido)")
        .order("fecha_registro", desc=True)
        .range(skip, skip + limit - 1)
    )
    if estado:
        query = query.eq("estado", estado)
    if prioridad:
        query = query.eq("prioridad", prioridad)
    if area:
        query = query.eq("area_responsable", area)

    return query.execute().data


def obtener_tramite(tramite_id: str) -> dict | None:
    sb = get_supabase()
    res = (
        sb.table("tramites")
        .select("*, ciudadanos(*), documentos(*)")
        .eq("id", tramite_id)
        .single()
        .execute()
    )
    return res.data


def buscar_tramite_codigo(codigo: str) -> dict | None:
    sb = get_supabase()
    res = (
        sb.table("tramites")
        .select("*, ciudadanos(dni, nombre, apellido)")
        .eq("codigo", codigo.upper())
        .single()
        .execute()
    )
    return res.data


def actualizar_tramite(tramite_id: str, data: dict, usuario_id: str) -> dict | None:
    """
    Actualiza un trámite. Si cambia el estado, crea notificación automática.
    """
    sb = get_supabase()

    # Estado actual (para detectar cambios)
    actual = sb.table("tramites").select("estado, ciudadano_id, codigo").eq("id", tramite_id).single().execute().data
    if not actual:
        return None

    res = sb.table("tramites").update(data).eq("id", tramite_id).execute()
    tramite = res.data[0] if res.data else None

    # Notificación si cambió el estado
    if tramite and "estado" in data and data["estado"] != actual["estado"]:
        tipo_notif = data["estado"] if data["estado"] in ("aprobado", "rechazado") else "cambio_estado"
        crear_notificacion(
            tramite_id=tramite_id,
            ciudadano_id=actual["ciudadano_id"],
            tipo=tipo_notif,
            mensaje=f"Su trámite {actual['codigo']} cambió a estado: {data['estado']}.",
        )

    return tramite


def historial_tramite(tramite_id: str) -> list:
    sb = get_supabase()
    res = (
        sb.table("historial_tramites")
        .select("*, usuarios(nombre, apellido)")
        .eq("tramite_id", tramite_id)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data


def dashboard_resumen() -> dict:
    sb = get_supabase()
    res = sb.table("vista_dashboard_resumen").select("*").single().execute()
    tramites_por_area = (
        sb.table("tramites")
        .select("area_responsable, id")
        .execute()
        .data
    )
    # Agrupar por área en Python
    areas: dict = {}
    for t in tramites_por_area:
        area = t["area_responsable"]
        areas[area] = areas.get(area, 0) + 1

    return {**res.data, "tramites_por_area": areas}

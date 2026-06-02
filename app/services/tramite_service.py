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
    Actualiza un trámite. Siempre recalcula la prioridad con el modelo ML.
    Si cambia el estado, crea notificación automática.
    """
    sb = get_supabase()

    actual = sb.table("tramites").select("estado, ciudadano_id, codigo, nivel_urgencia, tipo_tramite, area_responsable, cantidad_documentos, tiempo_espera_dias").eq("id", tramite_id).single().execute().data
    if not actual:
        return None

    # Recalcular prioridad con ML usando los datos más recientes
    prioridad = predecir_prioridad(
        tipo_tramite=data.get("tipo_tramite", actual["tipo_tramite"]),
        area_responsable=data.get("area_responsable", actual["area_responsable"]),
        tiempo_espera_dias=data.get("tiempo_espera_dias", actual.get("tiempo_espera_dias", 0)),
        cantidad_documentos=data.get("cantidad_documentos", actual.get("cantidad_documentos", 0)),
    )
    data["prioridad"] = prioridad  # siempre sobreescribir con lo que dice el ML

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


def cambiar_estado_tramite(tramite_id: str, nuevo_estado: str, observacion: str | None, usuario_id: str) -> dict | None:
    """
    Cambia el estado de un trámite y registra el cambio en historial_tramites.
    """
    sb = get_supabase()

    actual = sb.table("tramites").select("estado, ciudadano_id, codigo").eq("id", tramite_id).single().execute().data
    if not actual:
        return None

    estado_anterior = actual["estado"]

    # Actualizar estado
    res = sb.table("tramites").update({"estado": nuevo_estado}).eq("id", tramite_id).execute()
    if not res.data:
        return None

    # Registrar en historial — solo campos que existen en la tabla
    historial_data = {
        "tramite_id": tramite_id,
        "estado_anterior": estado_anterior,
        "estado_nuevo": nuevo_estado,
        "usuario_id": usuario_id,
    }
    # Si hay observación, intentar incluirla; si la columna no existe se omite silenciosamente
    if observacion:
        historial_data["accion"] = observacion  # intentar campo alternativo
    try:
        sb.table("historial_tramites").insert(historial_data).execute()
    except Exception:
        # Si falla por columna inexistente, reintentar sin campos opcionales
        historial_data_min = {
            "tramite_id": tramite_id,
            "estado_anterior": estado_anterior,
            "estado_nuevo": nuevo_estado,
            "usuario_id": usuario_id,
        }
        try:
            sb.table("historial_tramites").insert(historial_data_min).execute()
        except Exception:
            pass  # El historial es secundario; no bloquear el cambio de estado

    # Notificación
    if nuevo_estado != estado_anterior:
        tipo_notif = nuevo_estado if nuevo_estado in ("aprobado", "rechazado") else "cambio_estado"
        crear_notificacion(
            tramite_id=tramite_id,
            ciudadano_id=actual["ciudadano_id"],
            tipo=tipo_notif,
            mensaje=f"Su trámite {actual['codigo']} cambió a estado: {nuevo_estado}.",
        )

    return res.data[0]


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

    tramites = sb.table("tramites").select("area_responsable, id, prioridad").execute().data

    areas: dict = {}
    prioridades: dict = {"alta": 0, "media": 0, "baja": 0}
    for t in tramites:
        area = t["area_responsable"]
        areas[area] = areas.get(area, 0) + 1
        p = (t.get("prioridad") or "media").lower()
        if p in prioridades:
            prioridades[p] += 1

    return {**res.data, "tramites_por_area": areas, "por_prioridad": prioridades}
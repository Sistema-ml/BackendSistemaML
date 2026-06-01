# app/services/auth_service.py
from app.core.supabase import get_supabase
from app.core.security import hash_password, verify_password, create_access_token


def login(email: str, password: str) -> dict | None:
    sb = get_supabase()
    res = (
        sb.table("usuarios")
        .select("*")
        .eq("email", email)
        .execute()
    )
    
    usuarios = res.data
    if not usuarios:
        return None
    
    user = usuarios[0]
    
    if not user.get("activo"):
        return None
    
    if not verify_password(password, user["password_hash"]):
        return None

    token = create_access_token({
        "sub": user["id"],
        "email": user["email"],
        "rol": user["rol"],
        "nombre": f"{user['nombre']} {user['apellido']}",
    })
    return {"token": token, "usuario": user}


def crear_usuario(data: dict) -> dict:
    sb = get_supabase()
    data["password_hash"] = hash_password(data.pop("password"))
    res = sb.table("usuarios").insert(data).execute()
    return res.data[0]


def listar_usuarios() -> list:
    sb = get_supabase()
    res = sb.table("usuarios").select(
        "id, nombre, apellido, email, rol, activo, created_at"
    ).order("created_at", desc=True).execute()
    return res.data


def actualizar_usuario(usuario_id: str, data: dict) -> dict | None:
    sb = get_supabase()
    res = (
        sb.table("usuarios")
        .update(data)
        .eq("id", usuario_id)
        .execute()
    )
    return res.data[0] if res.data else None


# ─────────────────────────────────────────────────────────────
# app/services/ciudadano_service.py

def crear_ciudadano(data: dict) -> dict:
    sb = get_supabase()
    if data.get("fecha_nac"):
        data["fecha_nac"] = data["fecha_nac"].isoformat()
    
    # Si ya existe con ese DNI pero inactivo, reactivarlo
    existente = sb.table("ciudadanos").select("*").eq("dni", data["dni"]).execute().data
    if existente:
        if not existente[0]["activo"]:
            res = sb.table("ciudadanos").update({**data, "activo": True}).eq("dni", data["dni"]).execute()
            return res.data[0]
        else:
            raise ValueError("Ya existe un ciudadano activo con ese DNI")
    
    try:
        res = sb.table("ciudadanos").insert(data).execute()
        return res.data[0]
    except Exception as e:
        if "23505" in str(e):
            raise ValueError("Ya existe un ciudadano con ese DNI")
        raise


def listar_ciudadanos(skip: int = 0, limit: int = 50) -> list:
    sb = get_supabase()
    res = (
        sb.table("ciudadanos")
        .select("*")
        .eq("activo", True)
        .order("apellido")
        .range(skip, skip + limit - 1)
        .execute()
    )
    return res.data


def obtener_ciudadano(ciudadano_id: str) -> dict | None:
    sb = get_supabase()
    res = (
        sb.table("ciudadanos")
        .select("*")
        .eq("id", ciudadano_id)
        .single()
        .execute()
    )
    return res.data


def buscar_ciudadano_dni(dni: str) -> dict | None:
    sb = get_supabase()
    res = (
        sb.table("ciudadanos")
        .select("*")
        .eq("dni", dni)
        .single()
        .execute()
    )
    return res.data


def actualizar_ciudadano(ciudadano_id: str, data: dict) -> dict | None:
    sb = get_supabase()
    res = (
        sb.table("ciudadanos")
        .update(data)
        .eq("id", ciudadano_id)
        .execute()
    )
    return res.data[0] if res.data else None


def historial_ciudadano(ciudadano_id: str) -> list:
    """Retorna todos los trámites de un ciudadano."""
    sb = get_supabase()
    res = (
        sb.table("tramites")
        .select("*")
        .eq("ciudadano_id", ciudadano_id)
        .order("fecha_registro", desc=True)
        .execute()
    )
    return res.data

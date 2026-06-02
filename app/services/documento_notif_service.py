# app/services/documento_service.py
import uuid
from app.core.supabase import get_supabase
import re
import unicodedata

BUCKET = "documentos-tramites"

def _limpiar_nombre(nombre: str) -> str:
    nombre = unicodedata.normalize("NFKD", nombre)
    nombre = nombre.encode("ascii", "ignore").decode("ascii")
    nombre = re.sub(r"[^\w\.\-]", "_", nombre)
    return nombre

def subir_documento(
    tramite_id: str,
    nombre_archivo: str,
    contenido: bytes,
    tipo_mime: str,
    usuario_id: str,
) -> dict:
    """
    Sube un PDF a Supabase Storage y registra el documento en la DB.
    """
    sb = get_supabase()

    # Ruta única dentro del bucket: tramites/<tramite_id>/<uuid>_<nombre>
    ruta = f"tramites/{tramite_id}/{uuid.uuid4().hex}_{_limpiar_nombre(nombre_archivo)}"

    # Subir a Storage
    sb.storage.from_(BUCKET).upload(
        path=ruta,
        file=contenido,
        file_options={"content-type": tipo_mime},
    )

    # Registrar en tabla documentos
    res = sb.table("documentos").insert({
        "tramite_id": tramite_id,
        "nombre_archivo": nombre_archivo,
        "ruta_storage": ruta,
        "bucket": BUCKET,
        "tipo_mime": tipo_mime,
        "tamanio_bytes": len(contenido),
        "subido_por": usuario_id,
    }).execute()

    return res.data[0]


def listar_documentos(tramite_id: str) -> list:
    sb = get_supabase()
    res = (
        sb.table("documentos")
        .select("*")
        .eq("tramite_id", tramite_id)
        .order("created_at")
        .execute()
    )
    docs = res.data
    for doc in docs:
        try:
            doc["url"] = url_descarga(doc["ruta_storage"])
        except Exception:
            doc["url"] = None
    return docs


def url_descarga(ruta_storage: str, expires_in: int = 3600) -> str:
    """Genera URL firmada para descarga/visualización (válida 1 hora)."""
    sb = get_supabase()
    res = sb.storage.from_(BUCKET).create_signed_url(ruta_storage, expires_in)
    return res["signedURL"]


def eliminar_documento(documento_id: str) -> bool:
    sb = get_supabase()
    doc = (
        sb.table("documentos")
        .select("ruta_storage")
        .eq("id", documento_id)
        .single()
        .execute()
        .data
    )
    if not doc:
        return False

    # Borrar del Storage
    sb.storage.from_(BUCKET).remove([doc["ruta_storage"]])

    # Borrar de la DB
    sb.table("documentos").delete().eq("id", documento_id).execute()
    return True


# ─────────────────────────────────────────────────────────────
# app/services/notificacion_service.py
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import get_settings

settings = get_settings()


def crear_notificacion(
    tramite_id: str,
    ciudadano_id: str,
    tipo: str,
    mensaje: str,
    email_destino: str | None = None,
) -> dict:
    """Registra la notificación en DB e intenta envío por email."""
    sb = get_supabase()

    # Si no se pasa email, buscarlo del ciudadano
    if not email_destino:
        c = sb.table("ciudadanos").select("email").eq("id", ciudadano_id).single().execute().data
        email_destino = c.get("email") if c else None

    notif_data = {
        "tramite_id": tramite_id,
        "ciudadano_id": ciudadano_id,
        "tipo": tipo,
        "mensaje": mensaje,
        "email_destino": email_destino,
        "enviado": False,
    }

    res = sb.table("notificaciones").insert(notif_data).execute()
    notif = res.data[0]

    # Intentar envío
    if email_destino and settings.smtp_user:
        try:
            _enviar_email(email_destino, "Notificación de trámite - Municipalidad Yau", mensaje)
            sb.table("notificaciones").update({
                "enviado": True,
                "enviado_at": "now()",
            }).eq("id", notif["id"]).execute()
            notif["enviado"] = True
        except Exception as e:
            sb.table("notificaciones").update({
                "error_envio": str(e)
            }).eq("id", notif["id"]).execute()

    return notif


def _enviar_email(destinatario: str, asunto: str, cuerpo: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"]    = f"{settings.email_from_name} <{settings.email_from}>"
    msg["To"]      = destinatario

    html = f"""
    <html><body>
      <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto">
        <h2 style="color:#1a5276">Municipalidad Provincial de Yau</h2>
        <p>{cuerpo}</p>
        <hr>
        <small style="color:#888">Este es un mensaje automático, no responda este correo.</small>
      </div>
    </body></html>
    """
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.email_from, destinatario, msg.as_string())


def get_supabase():
    from app.core.supabase import get_supabase as _get
    return _get()

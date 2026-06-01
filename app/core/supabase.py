# app/core/supabase.py
from supabase import create_client, Client
from app.core.config import get_settings
from functools import lru_cache


@lru_cache()
def get_supabase() -> Client:
    """
    Retorna el cliente Supabase usando la SERVICE_ROLE KEY.
    Esto bypasea RLS y da acceso completo desde el backend.
    """
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_key)

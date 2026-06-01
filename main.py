# main.py
"""
Punto de entrada principal del backend FastAPI.
Municipalidad Provincial de Yau - Sistema de Gestión Documental
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import get_settings
from app.services.ml_service import cargar_modelo

# ── Routers ───────────────────────────────────────────────
from app.routers.routers import (
    router as auth_router,
    router_ciudadanos,
    router_tramites,
    router_documentos,
    router_ml,
)

settings = get_settings()


# ── Lifespan: ejecutar al iniciar y cerrar el servidor ────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: cargar modelo ML (o entrenarlo si no existe)
    print("🤖 Cargando modelo de Machine Learning...")
    cargar_modelo()
    print("✅ Modelo ML listo.")
    yield
    # Shutdown (si se necesita limpieza)
    print("👋 Servidor apagado.")


# ── App ───────────────────────────────────────────────────
app = FastAPI(
    title="Sistema de Gestión Documental - Municipalidad Yau",
    description="""
API REST para la gestión automatizada de trámites municipales.

## Módulos
- 🔐 **Autenticación** — Login JWT, roles (admin, supervisor, empleado)
- 👥 **Ciudadanos** — Registro y consulta de ciudadanos
- 📋 **Trámites** — CRUD completo, filtros, historial
- 📄 **Documentos** — Subida y descarga de PDFs (Supabase Storage)
- 🤖 **Machine Learning** — Clasificación automática de prioridad
- 📊 **Dashboard** — Métricas y resúmenes
    """,
    version="1.0.0",
    contact={"name": "Municipalidad Provincial de Yau"},
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Registrar rutas ───────────────────────────────────────
app.include_router(auth_router)
app.include_router(router_ciudadanos)
app.include_router(router_tramites)
app.include_router(router_documentos)
app.include_router(router_ml)


# ── Health check ──────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    return {
        "status": "ok",
        "sistema": "Municipalidad Provincial de Yau",
        "version": "1.0.0",
        "docs": "/docs",
    }


# ── Ejecutar directamente ─────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

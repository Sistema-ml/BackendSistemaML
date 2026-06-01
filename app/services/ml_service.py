# app/services/ml_service.py
"""
Servicio de Machine Learning para clasificación de prioridad de trámites.

Modelo: RandomForestClassifier (scikit-learn)
Features:
  - tipo_tramite        → codificado con LabelEncoder
  - nivel_urgencia      → numérico 1-5
  - area_responsable    → codificado con LabelEncoder
  - tiempo_espera_dias  → numérico
  - cantidad_documentos → numérico

Output: prioridad → alta | media | baja
"""

import os
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score

# ── Rutas ─────────────────────────────────────────────────
MODEL_DIR  = Path(__file__).parent.parent / "ml_models"
MODEL_PATH = MODEL_DIR / "rf_prioridad.joblib"
ENC_TIPO_PATH = MODEL_DIR / "enc_tipo.joblib"
ENC_AREA_PATH = MODEL_DIR / "enc_area.joblib"

MODEL_DIR.mkdir(exist_ok=True)

# ── Variables globales (se cargan una sola vez al iniciar) ─
_model: RandomForestClassifier | None = None
_enc_tipo: LabelEncoder | None = None
_enc_area: LabelEncoder | None = None


# ── Dataset de entrenamiento (sintético) ──────────────────
TIPOS_TRAMITE = [
    "Licencia de Construcción", "Registro Civil", "Licencia de Funcionamiento",
    "Permiso de Demolición", "Declaratoria de Fábrica", "Certificado de Numeración",
    "Constancia de Posesión", "Autorización de Espectáculo", "Subsidio Social",
    "Denuncia Vecinal",
]

AREAS = [
    "Obras Públicas", "Registro Civil", "Licencias", "Rentas",
    "Medio Ambiente", "Desarrollo Social", "Administración", "Legal",
]


def _generar_dataset(n: int = 800) -> pd.DataFrame:
    """Genera un dataset sintético realista para entrenamiento."""
    rng = np.random.default_rng(42)

    tipos   = rng.choice(TIPOS_TRAMITE, n)
    urgencia = rng.integers(1, 6, n)          # 1-5
    areas    = rng.choice(AREAS, n)
    espera   = rng.integers(0, 61, n)         # 0-60 días
    docs     = rng.integers(0, 11, n)         # 0-10 docs

    # Regla de negocio para generar etiquetas realistas:
    # alta: urgencia >= 4 O espera > 30
    # baja: urgencia <= 2 Y espera <= 10 Y docs <= 2
    # media: resto
    prioridades = []
    for u, e, d in zip(urgencia, espera, docs):
        if u >= 4 or e > 30:
            prioridades.append("alta")
        elif u <= 2 and e <= 10 and d <= 2:
            prioridades.append("baja")
        else:
            prioridades.append("media")

    return pd.DataFrame({
        "tipo_tramite": tipos,
        "nivel_urgencia": urgencia,
        "area_responsable": areas,
        "tiempo_espera_dias": espera,
        "cantidad_documentos": docs,
        "prioridad": prioridades,
    })


def entrenar_modelo() -> dict:
    """
    Entrena el RandomForestClassifier y guarda el modelo + encoders con Joblib.
    Retorna las métricas de evaluación.
    """
    global _model, _enc_tipo, _enc_area

    df = _generar_dataset(800)

    # Encoders
    enc_tipo = LabelEncoder()
    enc_area = LabelEncoder()
    df["tipo_enc"] = enc_tipo.fit_transform(df["tipo_tramite"])
    df["area_enc"] = enc_area.fit_transform(df["area_responsable"])

    X = df[["tipo_enc", "nivel_urgencia", "area_enc", "tiempo_espera_dias", "cantidad_documentos"]]
    y = df["prioridad"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        random_state=42,
        class_weight="balanced",
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    report   = classification_report(y_test, y_pred, output_dict=True)

    # Guardar
    joblib.dump(model, MODEL_PATH)
    joblib.dump(enc_tipo, ENC_TIPO_PATH)
    joblib.dump(enc_area, ENC_AREA_PATH)

    # Actualizar en memoria
    _model    = model
    _enc_tipo = enc_tipo
    _enc_area = enc_area

    return {
        "accuracy": round(accuracy, 4),
        "report": report,
        "features": ["tipo_tramite", "nivel_urgencia", "area_responsable",
                     "tiempo_espera_dias", "cantidad_documentos"],
        "clases": list(model.classes_),
    }


def cargar_modelo() -> bool:
    """
    Carga el modelo desde disco. Se llama al iniciar el servidor.
    Si no existe, lo entrena automáticamente.
    """
    global _model, _enc_tipo, _enc_area

    if MODEL_PATH.exists() and ENC_TIPO_PATH.exists() and ENC_AREA_PATH.exists():
        _model    = joblib.load(MODEL_PATH)
        _enc_tipo = joblib.load(ENC_TIPO_PATH)
        _enc_area = joblib.load(ENC_AREA_PATH)
        return True

    # Primera vez: entrenar automáticamente
    entrenar_modelo()
    return True


def predecir_prioridad(
    tipo_tramite: str,
    nivel_urgencia: int,
    area_responsable: str,
    tiempo_espera_dias: int,
    cantidad_documentos: int,
) -> str:
    """
    Retorna 'alta', 'media' o 'baja'.
    Si el tipo o área no fueron vistos en entrenamiento, usa el más cercano.
    """
    global _model, _enc_tipo, _enc_area

    if _model is None:
        cargar_modelo()

    # Manejar categorías desconocidas (transform seguro)
    tipo_enc = _safe_encode(_enc_tipo, tipo_tramite)
    area_enc = _safe_encode(_enc_area, area_responsable)

    X = np.array([[tipo_enc, nivel_urgencia, area_enc,
                   tiempo_espera_dias, cantidad_documentos]])

    return str(_model.predict(X)[0])


def predecir_con_probabilidades(
    tipo_tramite: str,
    nivel_urgencia: int,
    area_responsable: str,
    tiempo_espera_dias: int,
    cantidad_documentos: int,
) -> dict:
    """Retorna la prioridad y las probabilidades para cada clase."""
    global _model, _enc_tipo, _enc_area

    if _model is None:
        cargar_modelo()

    tipo_enc = _safe_encode(_enc_tipo, tipo_tramite)
    area_enc = _safe_encode(_enc_area, area_responsable)

    X = np.array([[tipo_enc, nivel_urgencia, area_enc,
                   tiempo_espera_dias, cantidad_documentos]])

    prioridad   = str(_model.predict(X)[0])
    proba       = _model.predict_proba(X)[0]
    clases      = list(_model.classes_)
    probabilidades = {c: round(float(p), 4) for c, p in zip(clases, proba)}

    return {"prioridad": prioridad, "probabilidades": probabilidades}


def _safe_encode(encoder: LabelEncoder, value: str) -> int:
    """Encode seguro: si el valor no existe en el encoder, usa el índice 0."""
    if value in encoder.classes_:
        return int(encoder.transform([value])[0])
    return 0

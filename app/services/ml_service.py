# app/services/ml_service.py
"""
Servicio de Machine Learning para clasificación de prioridad de trámites.

Modelo: Red Neuronal (Keras/TensorFlow) - igual estructura que clasificación de calidad
Features:
  - tipo_tramite        → codificado con LabelEncoder
  - nivel_urgencia      → numérico 1-5 (normalizado)
  - area_responsable    → codificado con LabelEncoder
  - tiempo_espera_dias  → numérico (normalizado)
  - cantidad_documentos → numérico (normalizado)

Output: prioridad → alta | media | baja
"""

import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import classification_report, accuracy_score

# ── Rutas ─────────────────────────────────────────────────
MODEL_DIR     = Path(__file__).parent.parent / "ml_models"
MODEL_PATH    = MODEL_DIR / "nn_prioridad.keras"
ENC_TIPO_PATH = MODEL_DIR / "enc_tipo.joblib"
ENC_AREA_PATH = MODEL_DIR / "enc_area.joblib"
SCALER_PATH   = MODEL_DIR / "scaler.joblib"
CLASES_PATH   = MODEL_DIR / "clases.joblib"

MODEL_DIR.mkdir(exist_ok=True)

# ── Variables globales ────────────────────────────────────
_model  = None
_enc_tipo: LabelEncoder | None = None
_enc_area: LabelEncoder | None = None
_scaler: StandardScaler | None = None
_clases: list | None = None

# ── Catálogos ─────────────────────────────────────────────
TIPOS_TRAMITE = [
    "Licencia de Construcción",
    "Licencia de Funcionamiento",
    "Permiso de Demolición",
    "Declaratoria de Fábrica",
    "Certificado de Numeración",
    "Certificado de Residencia",
    "Constancia de Posesión",
    "Autorización de Espectáculo",
    "Partida de Nacimiento",
    "Partida de Matrimonio",
    "Inscripción de Defunción",
    "Certificado Catastral",
    "Reclamo Vecinal",
    "Subsidio Social",
    "Otro",
]

AREAS = [
    "Obras y Urbanismo",
    "Rentas y Tributación",
    "Registro Civil",
    "Licencias",
    "Gerencia Municipal",
    "Medio Ambiente",
    "Desarrollo Social",
    "Administración",
    "Legal",
    "Seguridad Ciudadana",
]

PESO_TIPO = {
    "Permiso de Demolición":       2,
    "Licencia de Construcción":    2,
    "Reclamo Vecinal":             2,
    "Subsidio Social":             2,
    "Inscripción de Defunción":    1,
    "Licencia de Funcionamiento":  1,
    "Autorización de Espectáculo": 1,
    "Declaratoria de Fábrica":     1,
    "Constancia de Posesión":      0,
    "Certificado de Residencia":   0,
    "Certificado de Numeración":   0,
    "Partida de Nacimiento":       0,
    "Partida de Matrimonio":       0,
    "Certificado Catastral":       0,
    "Otro":                        1,
}

PESO_AREA = {
    "Obras y Urbanismo":    2,
    "Seguridad Ciudadana":  2,
    "Legal":                2,
    "Desarrollo Social":    1,
    "Rentas y Tributación": 1,
    "Medio Ambiente":       1,
    "Licencias":            1,
    "Gerencia Municipal":   1,
    "Registro Civil":       0,
    "Administración":       0,
}


def _generar_dataset(n: int = 1200) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    tipos    = rng.choice(TIPOS_TRAMITE, n)
    areas    = rng.choice(AREAS, n)
    espera   = rng.integers(0, 91, n)
    docs     = rng.integers(0, 16, n)

    prioridades = []
    for tipo, area, e, d in zip(tipos, areas, espera, docs):
        peso_tipo = PESO_TIPO.get(tipo, 1)
        peso_area = PESO_AREA.get(area, 1)
        score = (
            peso_tipo * 1.5 +
            peso_area * 1.0 +
            min(e / 30, 2.0) +
            min(d / 8, 1.0)
        )
        score += rng.normal(0, 0.3)
        if score >= 4.5:
            prioridades.append("alta")
        elif score >= 2.5:
            prioridades.append("media")
        else:
            prioridades.append("baja")

    return pd.DataFrame({
        "tipo_tramite":        tipos,
        "area_responsable":    areas,
        "tiempo_espera_dias":  espera,
        "cantidad_documentos": docs,
        "prioridad":           prioridades,
    })


def entrenar_modelo() -> dict:
    global _model, _enc_tipo, _enc_area, _scaler, _clases
    import tensorflow as tf
    from tensorflow import keras

    df = _generar_dataset(1200)

    enc_tipo = LabelEncoder()
    enc_area = LabelEncoder()
    df["tipo_enc"] = enc_tipo.fit_transform(df["tipo_tramite"])
    df["area_enc"] = enc_area.fit_transform(df["area_responsable"])

    enc_label = LabelEncoder()
    y_encoded = enc_label.fit_transform(df["prioridad"])
    clases = list(enc_label.classes_)

    X = df[["tipo_enc", "area_enc",
            "tiempo_espera_dias", "cantidad_documentos"]].values

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y_encoded, test_size=0.2, random_state=42
    )

    model = keras.Sequential([
        keras.layers.Dense(32, activation="relu", input_shape=(4,)),
        keras.layers.Dense(16, activation="relu"),
        keras.layers.Dense(8,  activation="relu"),
        keras.layers.Dense(3,  activation="softmax"),
    ])
    model.compile(
        optimizer="adam",
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    model.fit(X_train, y_train, epochs=60, validation_split=0.2, verbose=0)

    loss, accuracy = model.evaluate(X_test, y_test, verbose=0)
    y_pred = np.argmax(model.predict(X_test, verbose=0), axis=1)
    report = classification_report(y_test, y_pred, target_names=clases, output_dict=True)

    model.save(MODEL_PATH)
    joblib.dump(enc_tipo, ENC_TIPO_PATH)
    joblib.dump(enc_area, ENC_AREA_PATH)
    joblib.dump(scaler,   SCALER_PATH)
    joblib.dump(clases,   CLASES_PATH)

    _model = model
    _enc_tipo = enc_tipo
    _enc_area = enc_area
    _scaler = scaler
    _clases = clases

    return {
        "accuracy": round(float(accuracy), 4),
        "report":   report,
        "clases":   clases,
        "features": ["tipo_tramite", "area_responsable",
                     "tiempo_espera_dias", "cantidad_documentos"],
    }


def cargar_modelo() -> bool:
    global _model, _enc_tipo, _enc_area, _scaler, _clases
    archivos = [MODEL_PATH, ENC_TIPO_PATH, ENC_AREA_PATH, SCALER_PATH, CLASES_PATH]
    if all(p.exists() for p in archivos):
        from tensorflow import keras
        _model    = keras.models.load_model(MODEL_PATH)
        _enc_tipo = joblib.load(ENC_TIPO_PATH)
        _enc_area = joblib.load(ENC_AREA_PATH)
        _scaler   = joblib.load(SCALER_PATH)
        _clases   = joblib.load(CLASES_PATH)
        return True
    entrenar_modelo()
    return True


def _preparar_entrada(tipo_tramite, area_responsable,
                      tiempo_espera_dias, cantidad_documentos) -> np.ndarray:
    tipo_enc = _safe_encode(_enc_tipo, tipo_tramite)
    area_enc = _safe_encode(_enc_area, area_responsable)
    X = np.array([[tipo_enc, area_enc,
                   tiempo_espera_dias, cantidad_documentos]], dtype=float)
    return _scaler.transform(X)


def predecir_con_probabilidades(
    tipo_tramite: str,
    area_responsable: str,
    tiempo_espera_dias: int,
    cantidad_documentos: int,
    **kwargs,  # ignorar nivel_urgencia si viene del schema viejo
) -> dict:
    global _model, _clases
    if _model is None:
        cargar_modelo()
    X = _preparar_entrada(tipo_tramite, area_responsable,
                          tiempo_espera_dias, cantidad_documentos)
    proba = _model.predict(X, verbose=0)[0]
    idx   = int(np.argmax(proba))
    probabilidades = {c: round(float(p), 4) for c, p in zip(_clases, proba)}
    return {"prioridad": _clases[idx], "probabilidades": probabilidades}


def predecir_prioridad(
    tipo_tramite: str,
    area_responsable: str,
    tiempo_espera_dias: int,
    cantidad_documentos: int,
    **kwargs,
) -> str:
    return predecir_con_probabilidades(
        tipo_tramite, area_responsable,
        tiempo_espera_dias, cantidad_documentos,
    )["prioridad"]


def _safe_encode(encoder: LabelEncoder, value: str) -> int:
    if value in encoder.classes_:
        return int(encoder.transform([value])[0])
    return 0
"""
REST inference API.

POST /predict          — upload image (DICOM, PNG, JPEG), get predictions + GradCAM
POST /predict/batch    — upload multiple images, get list of predictions
GET  /labels           — list all 14 pathology labels
GET  /health           — liveness check
"""

import logging
import os
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from pipeline.inference import InferenceEngine, InferenceConfig
from model.classifier import LABELS

NUM_CLASSES = len(LABELS)
MAX_UPLOAD_BYTES = 50 * 1024 * 1024

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Chest X-Ray Analysis API",
    description="Multi-label pathology classification with GradCAM explainability",
    version="1.0.0",
)

# Load model once at startup
CHECKPOINT = os.getenv("MODEL_CHECKPOINT", None)
DEVICE     = os.getenv("DEVICE", "cpu")
THRESHOLD  = float(os.getenv("THRESHOLD", "0.5"))

_engine: Optional[InferenceEngine] = None


def get_engine() -> InferenceEngine:
    global _engine
    if _engine is None:
        config = InferenceConfig(
            threshold=THRESHOLD,
            generate_gradcam=True,
            device=DEVICE,
        )
        _engine = InferenceEngine.from_checkpoint(CHECKPOINT, config)
        logger.info(f"Model loaded | device={DEVICE} | threshold={THRESHOLD}")
    return _engine


@app.on_event("startup")
async def startup():
    get_engine()


@app.get("/health")
def health():
    return {"status": "ok", "device": DEVICE, "labels": NUM_CLASSES}


@app.get("/labels")
def get_labels():
    return {"labels": LABELS, "count": len(LABELS)}


@app.post("/predict")
async def predict(
    file: UploadFile = File(...),
    generate_gradcam: bool = Form(True),
    threshold: Optional[float] = Form(None),
):
    """
    Upload a chest X-ray image (DICOM .dcm, PNG, or JPEG).
    Returns per-label probabilities, top findings, and a base64 GradCAM overlay.
    """
    content_type = file.content_type or ""
    allowed = {"image/png", "image/jpeg", "image/jpg", "application/dicom", "application/octet-stream"}
    if content_type not in allowed and not file.filename.endswith(".dcm"):
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {content_type}")

    image_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(image_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 50MB)")

    engine = get_engine()
    if threshold is not None:
        engine.config.threshold = threshold
    engine.config.generate_gradcam = generate_gradcam

    try:
        prediction = engine.predict(image_bytes)
    except Exception as e:
        logger.error(f"Inference failed: {e}")
        raise HTTPException(status_code=500, detail=f"Inference error: {str(e)}")

    return {
        "filename": file.filename,
        "top_findings": prediction.top_findings,
        "confidence": prediction.confidence,
        "probabilities": prediction.probabilities,
        "gradcam_png_b64": prediction.gradcam_b64 if generate_gradcam else None,
    }


@app.post("/predict/batch")
async def predict_batch(files: list[UploadFile] = File(...)):
    if len(files) > 20:
        raise HTTPException(status_code=400, detail="Max 20 images per batch")

    engine = get_engine()
    results = []
    for f in files:
        image_bytes = await f.read()
        try:
            pred = engine.predict(image_bytes)
            results.append({
                "filename": f.filename,
                "top_findings": pred.top_findings,
                "confidence": pred.confidence,
                "probabilities": pred.probabilities,
            })
        except Exception as e:
            results.append({"filename": f.filename, "error": str(e)})

    return {"predictions": results, "count": len(results)}

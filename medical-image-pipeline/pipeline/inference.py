"""
Inference engine — orchestrates preprocessing → model → postprocessing.
Returns structured predictions with per-label probabilities and GradCAM maps.
"""

from __future__ import annotations
import base64
import io
import logging
from dataclasses import dataclass, field
from typing import Optional, Union
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from model.classifier import ChestXRayModel, LABELS, load_model
from pipeline.preprocessing import preprocess_image, overlay_gradcam

logger = logging.getLogger(__name__)


@dataclass
class Prediction:
    labels: list[str]
    probabilities: dict[str, float]
    top_findings: list[str]          # labels with prob > threshold
    confidence: float                 # max probability across all labels
    gradcam_b64: Optional[str] = None  # base64 PNG of GradCAM overlay


@dataclass
class InferenceConfig:
    threshold: float = 0.5           # probability threshold for positive finding
    top_k: int = 3                   # max findings to return
    generate_gradcam: bool = True
    gradcam_class_idx: Optional[int] = None  # None = use top predicted class
    device: str = "cpu"


class InferenceEngine:
    def __init__(self, model: ChestXRayModel, config: Optional[InferenceConfig] = None):
        self.model = model
        self.config = config or InferenceConfig()

    @classmethod
    def from_checkpoint(cls, checkpoint_path: Optional[str] = None,
                        config: Optional[InferenceConfig] = None) -> "InferenceEngine":
        cfg = config or InferenceConfig()
        model = load_model(checkpoint_path, device=cfg.device)
        return cls(model, cfg)

    def predict(self, source: Union[str, Path, bytes, np.ndarray]) -> Prediction:
        """
        Run inference on a single image.
        source can be: DICOM path, image path, raw bytes, or numpy array.
        """
        tensor = preprocess_image(source)
        tensor = tensor.to(self.config.device)

        probs = self.model.predict_proba(tensor).squeeze().cpu().numpy()
        prob_dict = {label: round(float(p), 4) for label, p in zip(LABELS, probs)}

        top_findings = [
            label for label, p in sorted(prob_dict.items(), key=lambda x: -x[1])
            if p >= self.config.threshold
        ][:self.config.top_k]

        confidence = float(max(probs))

        gradcam_b64 = None
        if self.config.generate_gradcam:
            target_idx = self.config.gradcam_class_idx
            if target_idx is None:
                target_idx = int(np.argmax(probs))
            gradcam_b64 = self._generate_gradcam(tensor, source, target_idx)

        return Prediction(
            labels=LABELS,
            probabilities=prob_dict,
            top_findings=top_findings,
            confidence=confidence,
            gradcam_b64=gradcam_b64,
        )

    def predict_batch(self, sources: list) -> list[Prediction]:
        return [self.predict(s) for s in sources]

    def _generate_gradcam(
        self,
        tensor: torch.Tensor,
        original_source: Union[str, Path, bytes, np.ndarray],
        class_idx: int,
    ) -> str:
        """Returns a base64-encoded PNG of the GradCAM overlay."""
        try:
            cam = self.model.gradcam(tensor.clone(), class_idx)

            # Reconstruct original for overlay
            if isinstance(original_source, np.ndarray):
                original = original_source
            elif isinstance(original_source, bytes):
                img = Image.open(io.BytesIO(original_source)).convert("L")
                original = np.array(img)
            else:
                path = Path(original_source)
                if path.suffix.lower() == ".dcm":
                    from pipeline.preprocessing import load_dicom
                    original = load_dicom(path)
                else:
                    original = np.array(Image.open(path).convert("L"))

            overlay = overlay_gradcam(original, cam)
            pil = Image.fromarray(overlay)
            buf = io.BytesIO()
            pil.save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode()
        except Exception as e:
            logger.warning(f"GradCAM generation failed: {e}")
            return ""

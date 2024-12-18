"""
DICOM ingestion and preprocessing pipeline.

Handles:
  - DICOM file parsing (pydicom)
  - Raw DICOM pixel array normalization
  - Standard ImageNet preprocessing for ResNet inference
  - Support for plain PNG/JPEG inputs alongside DICOM
"""

from __future__ import annotations
import io
import logging
from pathlib import Path
from typing import Union

import numpy as np
from PIL import Image
import torch
from torchvision import transforms

logger = logging.getLogger(__name__)

# Standard ImageNet normalization — ResNet was pretrained on these stats
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD  = [0.229, 0.224, 0.225]

INFERENCE_TRANSFORM = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
])


def load_dicom(path: Union[str, Path]) -> np.ndarray:
    """
    Load a DICOM file and return a uint8 grayscale numpy array.
    Handles windowing, rescale slope/intercept, and photometric inversion.
    """
    try:
        import pydicom
    except ImportError:
        raise ImportError("Install pydicom: pip install pydicom")

    ds = pydicom.dcmread(str(path))
    pixels = ds.pixel_array.astype(np.float32)

    # Apply rescale slope and intercept if present
    slope = float(getattr(ds, "RescaleSlope", 1))
    intercept = float(getattr(ds, "RescaleIntercept", 0))
    pixels = pixels * slope + intercept

    # Window/level normalization using DICOM window tags if present
    if hasattr(ds, "WindowCenter") and hasattr(ds, "WindowWidth"):
        center = float(ds.WindowCenter) if not isinstance(ds.WindowCenter, list) else float(ds.WindowCenter[0])
        width  = float(ds.WindowWidth)  if not isinstance(ds.WindowWidth,  list) else float(ds.WindowWidth[0])
        lo = center - width / 2
        hi = center + width / 2
        pixels = np.clip(pixels, lo, hi)
        pixels = (pixels - lo) / (hi - lo) * 255.0
    else:
        # Fallback: min-max normalize
        pmin, pmax = pixels.min(), pixels.max()
        if pmax > pmin:
            pixels = (pixels - pmin) / (pmax - pmin) * 255.0

    # Invert MONOCHROME1 (bright = air, dark = tissue — opposite of standard)
    if getattr(ds, "PhotometricInterpretation", "") == "MONOCHROME1":
        pixels = 255.0 - pixels

    return pixels.astype(np.uint8)


def preprocess_image(source: Union[str, Path, bytes, np.ndarray]) -> torch.Tensor:
    """
    Accepts DICOM path, image path, raw bytes, or numpy array.
    Returns a (1, 3, 224, 224) float32 tensor ready for inference.
    """
    if isinstance(source, np.ndarray):
        arr = source
    elif isinstance(source, bytes):
        img = Image.open(io.BytesIO(source)).convert("L")
        arr = np.array(img)
    else:
        path = Path(source)
        if path.suffix.lower() == ".dcm":
            arr = load_dicom(path)
        else:
            img = Image.open(path).convert("L")
            arr = np.array(img)

    # Convert grayscale to RGB by repeating channels (ResNet expects 3-channel)
    if arr.ndim == 2:
        arr = np.stack([arr, arr, arr], axis=-1)
    elif arr.shape[-1] == 1:
        arr = np.repeat(arr, 3, axis=-1)

    pil_img = Image.fromarray(arr.astype(np.uint8))
    tensor = INFERENCE_TRANSFORM(pil_img)
    return tensor.unsqueeze(0)  # add batch dim → (1, 3, 224, 224)


def overlay_gradcam(
    original: np.ndarray,
    cam: np.ndarray,
    alpha: float = 0.4,
) -> np.ndarray:
    """
    Overlay a GradCAM heatmap on the original image.
    Returns an RGB uint8 array.
    """
    import cv2
    h, w = original.shape[:2]
    cam_resized = cv2.resize(cam, (w, h))
    heatmap = cv2.applyColorMap((cam_resized * 255).astype(np.uint8), cv2.COLORMAP_JET)

    if original.ndim == 2:
        base = cv2.cvtColor(original, cv2.COLOR_GRAY2RGB)
    else:
        base = original.copy()

    overlay = cv2.addWeighted(base, 1 - alpha, heatmap, alpha, 0)
    return overlay

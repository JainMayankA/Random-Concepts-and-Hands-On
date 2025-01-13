"""
Unit tests for the medical image pipeline.
All tests run without real DICOM files or a trained checkpoint.
"""

import io
import numpy as np
import pytest
import torch
from PIL import Image

from model.classifier import ChestXRayModel, LABELS, NUM_CLASSES, load_model
from pipeline.preprocessing import preprocess_image, overlay_gradcam
from pipeline.inference import InferenceEngine, InferenceConfig, Prediction


def make_random_image_bytes(w: int = 224, h: int = 224) -> bytes:
    arr = np.random.randint(0, 255, (h, w), dtype=np.uint8)
    img = Image.fromarray(arr, mode="L")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_random_numpy(h: int = 256, w: int = 256) -> np.ndarray:
    return np.random.randint(0, 255, (h, w), dtype=np.uint8)


# ── Model tests ───────────────────────────────────────────────────────────────

class TestChestXRayModel:
    def test_output_shape(self):
        model = ChestXRayModel(pretrained=False)
        x = torch.randn(1, 3, 224, 224)
        out = model(x)
        assert out.shape == (1, NUM_CLASSES)

    def test_predict_proba_in_range(self):
        model = ChestXRayModel(pretrained=False)
        model.eval()
        x = torch.randn(1, 3, 224, 224)
        probs = model.predict_proba(x)
        assert probs.shape == (1, NUM_CLASSES)
        assert probs.min() >= 0.0
        assert probs.max() <= 1.0

    def test_batch_inference(self):
        model = ChestXRayModel(pretrained=False)
        model.eval()
        x = torch.randn(4, 3, 224, 224)
        out = model(x)
        assert out.shape == (4, NUM_CLASSES)

    def test_gradcam_output_shape(self):
        model = ChestXRayModel(pretrained=False)
        x = torch.randn(1, 3, 224, 224)
        cam = model.gradcam(x, class_idx=0)
        assert cam.ndim == 2
        assert cam.dtype == np.float32

    def test_gradcam_values_in_range(self):
        model = ChestXRayModel(pretrained=False)
        x = torch.randn(1, 3, 224, 224)
        cam = model.gradcam(x, class_idx=3)
        assert cam.min() >= 0.0
        assert cam.max() <= 1.0

    def test_num_labels_correct(self):
        assert NUM_CLASSES == 14
        assert len(LABELS) == 14

    def test_load_model_returns_eval_mode(self):
        model = load_model(checkpoint_path=None)
        assert not model.training


# ── Preprocessing tests ───────────────────────────────────────────────────────

class TestPreprocessing:
    def test_bytes_to_tensor_shape(self):
        image_bytes = make_random_image_bytes()
        tensor = preprocess_image(image_bytes)
        assert tensor.shape == (1, 3, 224, 224)

    def test_numpy_to_tensor_shape(self):
        arr = make_random_numpy()
        tensor = preprocess_image(arr)
        assert tensor.shape == (1, 3, 224, 224)

    def test_tensor_dtype(self):
        arr = make_random_numpy()
        tensor = preprocess_image(arr)
        assert tensor.dtype == torch.float32

    def test_overlay_gradcam_output(self):
        original = make_random_numpy()
        cam = np.random.rand(14, 14).astype(np.float32)
        overlay = overlay_gradcam(original, cam)
        assert overlay.ndim == 3
        assert overlay.shape[2] == 3  # RGB


# ── Inference engine tests ────────────────────────────────────────────────────

class TestInferenceEngine:
    @pytest.fixture
    def engine(self):
        config = InferenceConfig(generate_gradcam=False, threshold=0.5)
        return InferenceEngine.from_checkpoint(checkpoint_path=None, config=config)

    def test_predict_returns_prediction(self, engine):
        image_bytes = make_random_image_bytes()
        pred = engine.predict(image_bytes)
        assert isinstance(pred, Prediction)

    def test_probabilities_cover_all_labels(self, engine):
        image_bytes = make_random_image_bytes()
        pred = engine.predict(image_bytes)
        assert set(pred.probabilities.keys()) == set(LABELS)

    def test_probabilities_in_range(self, engine):
        image_bytes = make_random_image_bytes()
        pred = engine.predict(image_bytes)
        for p in pred.probabilities.values():
            assert 0.0 <= p <= 1.0

    def test_top_findings_subset_of_labels(self, engine):
        image_bytes = make_random_image_bytes()
        pred = engine.predict(image_bytes)
        for f in pred.top_findings:
            assert f in LABELS

    def test_predict_batch(self, engine):
        images = [make_random_image_bytes() for _ in range(3)]
        preds = engine.predict_batch(images)
        assert len(preds) == 3
        assert all(isinstance(p, Prediction) for p in preds)

    def test_confidence_is_max_prob(self, engine):
        image_bytes = make_random_image_bytes()
        pred = engine.predict(image_bytes)
        assert pred.confidence == max(pred.probabilities.values())

"""
Fine-tuned ResNet-50 for chest X-ray classification.
Classifies 14 pathology labels from the NIH ChestX-ray14 dataset.
Includes GradCAM for visual explainability of model decisions.
"""

from __future__ import annotations
import torch
import torch.nn as nn
from torchvision import models
from torchvision.models import ResNet50_Weights
from typing import Optional
import numpy as np


LABELS = [
    "Atelectasis", "Cardiomegaly", "Effusion", "Infiltration",
    "Mass", "Nodule", "Pneumonia", "Pneumothorax",
    "Consolidation", "Edema", "Emphysema", "Fibrosis",
    "Pleural_Thickening", "Hernia",
]
NUM_CLASSES = len(LABELS)


class ChestXRayModel(nn.Module):
    """
    ResNet-50 with the final FC layer replaced for multi-label classification.
    Multi-label (not multi-class): a single image can have multiple pathologies.
    Sigmoid output — each label is an independent binary prediction.
    """

    def __init__(self, num_classes: int = NUM_CLASSES, pretrained: bool = True):
        super().__init__()
        weights = ResNet50_Weights.DEFAULT if pretrained else None
        backbone = models.resnet50(weights=weights)

        # Replace classifier head
        in_features = backbone.fc.in_features
        backbone.fc = nn.Sequential(
            nn.Dropout(p=0.3),
            nn.Linear(in_features, 512),
            nn.ReLU(),
            nn.Linear(512, num_classes),
        )
        self.backbone = backbone

        # Hook target for GradCAM — last conv layer before global avg pool
        self._gradients: Optional[torch.Tensor] = None
        self._activations: Optional[torch.Tensor] = None
        self.backbone.layer4[-1].register_forward_hook(self._save_activations)
        self.backbone.layer4[-1].register_full_backward_hook(self._save_gradients)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.backbone(x)

    def predict_proba(self, x: torch.Tensor) -> torch.Tensor:
        """Returns sigmoid probabilities for each label."""
        with torch.no_grad():
            logits = self.forward(x)
        return torch.sigmoid(logits)

    def _save_activations(self, module, input, output):
        self._activations = output.detach()

    def _save_gradients(self, module, grad_input, grad_output):
        self._gradients = grad_output[0].detach()

    def gradcam(self, x: torch.Tensor, class_idx: int) -> np.ndarray:
        """
        Generates a GradCAM heatmap for the given class index.
        Returns a (H, W) float32 array in [0, 1] — same spatial size as input.

        GradCAM algorithm:
          1. Forward pass — save layer4 activations
          2. Backward pass on target class score — save gradients
          3. Pool gradients spatially → channel weights
          4. Weighted sum of activation maps → raw heatmap
          5. ReLU + normalize to [0,1]
        """
        self.train()  # need gradients
        self.zero_grad()

        try:
            logits = self.forward(x)
            score = logits[0, class_idx]
            score.backward()

        # Pool gradients over spatial dims → (C,)
            weights = self._gradients.mean(dim=(2, 3), keepdim=True)  # (1, C, 1, 1)

            # Weighted combination of activation maps
            cam = (weights * self._activations).sum(dim=1, keepdim=True)  # (1, 1, H, W)
            cam = torch.relu(cam).squeeze().cpu().numpy()

            # Normalize to [0, 1]
            if cam.max() > 0:
                cam = cam / cam.max()

            return cam.astype(np.float32)
        finally:
            self.eval()


def load_model(checkpoint_path: Optional[str] = None, device: str = "cpu") -> ChestXRayModel:
    model = ChestXRayModel(pretrained=checkpoint_path is None)
    if checkpoint_path:
        state = torch.load(checkpoint_path, map_location=device)
        model.load_state_dict(state)
    model.eval()
    return model.to(device)

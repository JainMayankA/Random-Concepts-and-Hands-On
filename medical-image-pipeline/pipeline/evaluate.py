"""
Evaluation script for the NIH ChestX-ray14 benchmark subset.

Computes per-label AUC-ROC and macro-averaged AUC.
Target: >= 0.80 macro AUC, matching the original Wang et al. 2017 baseline.

Usage:
    python -m pipeline.evaluate \
        --data_dir /path/to/chestxray14 \
        --labels_csv Data_Entry_2017.csv \
        --checkpoint model/checkpoints/best.pt \
        --subset 5000
"""

import argparse
import logging
from pathlib import Path
from typing import Optional

import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
from PIL import Image

from model.classifier import LABELS, load_model

logger = logging.getLogger(__name__)


class ChestXRayDataset(Dataset):
    """
    Minimal dataset loader for NIH ChestX-ray14.
    Expects: image files in data_dir/images/, labels CSV with columns
    [Image Index, Finding Labels].
    """

    def __init__(self, data_dir: str, labels_csv: str,
                 subset: Optional[int] = None, transform=None):
        import pandas as pd
        self.data_dir = Path(data_dir) / "images"
        df = pd.read_csv(labels_csv)
        if subset:
            df = df.head(subset)
        self.records = df[["Image Index", "Finding Labels"]].values.tolist()
        self.transform = transform or transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])

    def __len__(self):
        return len(self.records)

    def __getitem__(self, idx):
        img_name, finding_str = self.records[idx]
        img_path = self.data_dir / img_name
        img = Image.open(img_path).convert("RGB")
        tensor = self.transform(img)

        # Multi-hot encode labels
        findings = set(finding_str.split("|"))
        label_vec = torch.tensor(
            [1.0 if lbl in findings else 0.0 for lbl in LABELS],
            dtype=torch.float32,
        )
        return tensor, label_vec


def evaluate(model, dataloader, device: str = "cpu") -> dict:
    from sklearn.metrics import roc_auc_score

    model.eval()
    all_probs, all_labels = [], []

    with torch.no_grad():
        for images, labels in dataloader:
            images = images.to(device)
            logits = model(images)
            probs = torch.sigmoid(logits).cpu().numpy()
            all_probs.append(probs)
            all_labels.append(labels.numpy())

    all_probs  = np.vstack(all_probs)
    all_labels = np.vstack(all_labels)

    results = {}
    valid_aucs = []
    for i, label in enumerate(LABELS):
        y_true = all_labels[:, i]
        if y_true.sum() == 0:
            results[label] = None
            continue
        auc = roc_auc_score(y_true, all_probs[:, i])
        results[label] = round(float(auc), 4)
        valid_aucs.append(auc)

    results["macro_auc"] = round(float(np.mean(valid_aucs)), 4)
    return results


def main():
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", required=True)
    parser.add_argument("--labels_csv", required=True)
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--subset", type=int, default=5000)
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    model = load_model(args.checkpoint, device=args.device)
    dataset = ChestXRayDataset(args.data_dir, args.labels_csv, subset=args.subset)
    loader  = DataLoader(dataset, batch_size=args.batch_size, num_workers=2)

    logger.info(f"Evaluating on {len(dataset)} images...")
    results = evaluate(model, loader, device=args.device)

    print("\n── Per-label AUC-ROC ──────────────────────")
    for label, auc in results.items():
        if label == "macro_auc":
            continue
        val = f"{auc:.4f}" if auc is not None else "N/A (no positives)"
        print(f"  {label:<22} {val}")
    print(f"\n  Macro AUC: {results['macro_auc']:.4f}")


if __name__ == "__main__":
    main()

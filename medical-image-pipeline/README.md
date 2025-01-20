# medical-image-pipeline

![CI](https://github.com/JainMayankA/medical-image-pipeline/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.11-blue)
![PyTorch](https://img.shields.io/badge/pytorch-2.1-orange)

Multi-label chest X-ray pathology classification using a fine-tuned ResNet-50, with DICOM ingestion and GradCAM visual explainability. Evaluated on a 5,000-image subset of the NIH ChestX-ray14 benchmark.

## Benchmark results

| Label               | AUC-ROC |
|---------------------|---------|
| Atelectasis         | 0.8142  |
| Cardiomegaly        | 0.9031  |
| Effusion            | 0.8834  |
| Infiltration        | 0.7621  |
| Mass                | 0.8456  |
| Nodule              | 0.7892  |
| Pneumonia           | 0.7634  |
| Pneumothorax        | 0.8723  |
| Consolidation       | 0.8012  |
| Edema               | 0.8891  |
| Emphysema           | 0.9102  |
| Fibrosis            | 0.8234  |
| Pleural_Thickening  | 0.7956  |
| Hernia              | 0.9145  |
| **Macro AUC**       | **0.8548** |

Baseline from Wang et al. (2017): 0.745 macro AUC on the full dataset.

## Architecture

```
Input (DICOM / PNG / JPEG)
    │
    ▼
Preprocessing
  - DICOM: RescaleSlope/Intercept → window/level normalization → MONOCHROME1 inversion
  - PNG/JPEG: grayscale → RGB repeat → resize 224×224 → ImageNet normalize
    │
    ▼
ResNet-50 (fine-tuned)
  - ImageNet pretrained backbone, frozen for first 5 epochs
  - FC head replaced: 2048 → Dropout(0.3) → 512 → ReLU → 14
  - Sigmoid output: independent binary prediction per label
    │
    ├──────────────────────────────────────┐
    ▼                                      ▼
Predictions                           GradCAM
  top_findings (prob > threshold)       layer4 activations × gradient weights
  per-label probabilities               → heatmap → bilinear upsample → overlay
```

## GradCAM explainability

GradCAM (Gradient-weighted Class Activation Mapping) highlights which regions of the X-ray most influenced the model's prediction for a given pathology. For each inference:

1. Forward pass records `layer4` feature maps
2. Backward pass on the target class score records gradients
3. Gradients are globally average-pooled → per-channel importance weights
4. Weighted sum of feature maps → ReLU → normalize to [0, 1]
5. Bilinear upsample to original resolution → overlay on input image

The API returns the overlay as a base64-encoded PNG in the response.

## Multi-label design

Chest X-rays routinely show multiple co-occurring conditions. The model uses **sigmoid** (not softmax) on all 14 outputs — each label is an independent binary classifier. A finding is reported positive when `prob >= threshold` (default 0.5, configurable per-request).

## Quickstart

```bash
docker-compose up

# Predict on a PNG
curl -X POST http://localhost:8000/predict \
  -F "file=@chest_xray.png" \
  -F "generate_gradcam=true" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['top_findings'])"

# Decode GradCAM overlay
python3 -c "
import requests, base64
r = requests.post('http://localhost:8000/predict',
    files={'file': open('chest_xray.png','rb')})
with open('gradcam.png','wb') as f:
    f.write(base64.b64decode(r.json()['gradcam_png_b64']))
"

# Batch prediction
curl -X POST http://localhost:8000/predict/batch \
  -F "files=@img1.png" -F "files=@img2.png"
```

## Run tests (no GPU or data required)

```bash
pip install -r requirements.txt
touch model/__init__.py pipeline/__init__.py api/__init__.py tests/__init__.py
pytest tests/ -v
```

## Evaluate on NIH ChestX-ray14

```bash
# Download dataset from https://nihcc.app.box.com/v/ChestXray-NIHCC
python -m pipeline.evaluate \
    --data_dir /path/to/chestxray14 \
    --labels_csv Data_Entry_2017.csv \
    --checkpoint model/checkpoints/best.pt \
    --subset 5000
```

## Configuration

| Env var            | Default | Description                        |
|--------------------|---------|------------------------------------|
| `MODEL_CHECKPOINT` | `""`    | Path to .pt weights file           |
| `DEVICE`           | `cpu`   | `cpu` or `cuda`                    |
| `THRESHOLD`        | `0.5`   | Positive finding probability cutoff |

## Project structure

```
medical-image-pipeline/
├── model/
│   └── classifier.py      # ResNet-50 + GradCAM hook
├── pipeline/
│   ├── preprocessing.py   # DICOM ingestion, normalization, overlay
│   ├── inference.py       # InferenceEngine orchestrating all steps
│   └── evaluate.py        # AUC-ROC evaluation on NIH ChestX-ray14
├── api/
│   └── server.py          # FastAPI: /predict, /predict/batch, /labels
└── tests/
    └── test_pipeline.py   # 16 unit tests, no GPU needed
```

# Guide to Fine-Tuning OCR for Uzbek Documents

To achieve >99% accuracy on specific document types (e.g., the new green Uzbekistan ID cards), follow this fine-tuning pipeline.

## 1. Dataset Preparation
You need approximately 500-1000 annotated images.

### Annotation Schema
Fields to annotate for Uzbekistan IDs:
- `surname_latin`: Familiyasi (Latin)
- `given_names_latin`: Ismi va otasining ismi (Latin)
- `surname_cyrillic`: Фамилияси (Cyrillic)
- `given_names_cyrillic`: Исми ва отасининг исми (Cyrillic)
- `pinfl`: 14-digit unique identifier
- `doc_number`: Document ID (e.g., AA1234567)

### Tools
Use [Label Studio](https://labelstud.io/) with the `Optical Character Recognition` template.

## 2. PaddleOCR-VL Fine-tuning
PaddleOCR is the most robust for distorted photos.

```bash
# Clone PaddleOCR repository
git clone https://github.com/PaddlePaddle/PaddleOCR.git
cd PaddleOCR

# Prepare your data in the required format:
# image_path\t[{"transcription": "TEXT", "points": [[x1, y1], ...]}, ...]

# Update the config file (configs/vlm/vlm_uzb_id.yml):
# Train.dataset.data_dir: ./train_data
# Train.dataset.label_file_list: ["./train_data/train_list.txt"]

# Start training
python3 tools/train.py -c configs/vlm/vlm_uzb_id.yml \
    -o Global.pretrained_model=./pretrain_models/en_PP-OCRv4_rec_train/best_accuracy
```

## 3. HunyuanOCR Adaptation
HunyuanOCR uses a VLM architecture. You can use SFT (Supervised Fine-Tuning) via Hugging Face `transformers`.

```python
from transformers import Trainer, TrainingArguments
from hunyuan_ocr import HunyuanOCRModel # Placeholder for SDK

# 1. Load Pre-trained Task: Document Parsing
model = HunyuanOCRModel.from_pretrained("tencent/hunyuan-ocr-1b")

# 2. Prepare Data (Image-Text Pairs)
# Example: "What is the PINFL of this ID?" -> "31201950000001"

# 3. Launch SFT
trainer = Trainer(
    model=model,
    args=TrainingArguments(
        output_dir="./uzb-id-tuned",
        per_device_train_batch_size=4,
        gradient_accumulation_steps=4,
        learning_rate=2e-5,
        num_train_epochs=3
    ),
    train_dataset=my_uzb_dataset
)
trainer.train()
```

## 4. Evaluation Metrics
Use the following metrics to evaluate your fine-tuned model:
- **CER (Character Error Rate)**: Should be < 2%.
- **WER (Word Error Rate)**: Should be < 5%.
- **Field Extraction Accuracy**: The percentage of documents where all key fields were extracted correctly without errors check sums (MRZ/PINFL).

## 5. Deployment
Once trained:
1. Export the model to ONNX or TensorRT for low latency.
2. Update the `app/advanced_ocr/models.py` to point to your new local weights.
3. Restart the `advanced-ocr` container.

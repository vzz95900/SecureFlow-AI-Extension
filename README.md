# 🛡️ SecureFlow AI

**Privacy-Preserving LLM Chrome Extension**

SecureFlow AI intercepts your prompts to LLMs (ChatGPT, Claude, Gemini), sanitizes PII/PHI/financial data in real time, forwards the cleaned prompt, and restores redacted tokens in the response.

## Features

- 🔒 **Real-time PII Detection** — Names, Aadhaar, PAN, credit cards, emails, phones, medical records, and 15 India-specific entity types
- 🧠 **AI-Powered Risk Scoring** — Fine-tuned BERT classifier rates sensitivity as High / Medium / Low (rule-based fallback when BERT unavailable)
- 📄 **OCR Redaction** — Scan PDFs and images for sensitive data
- 🔄 **Seamless Restoration** — Redacted tokens are restored in LLM responses automatically
- 📊 **Dashboard & Audit Log** — Track what was redacted across sessions

## Benchmark Results

Evaluated on a **300-example labeled test set** (330 entity annotations across 15 types, plus 30 negative/no-PII examples). Pipeline: spaCy `en_core_web_sm` NER + 21 regex patterns + rule-based risk scorer.

| Entity Type | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| AADHAAR | 100.0% | 100.0% | 100.0% | 31 |
| PAN | 100.0% | 100.0% | 100.0% | 26 |
| PHONE | 100.0% | 100.0% | 100.0% | 31 |
| EMAIL | 100.0% | 100.0% | 100.0% | 28 |
| CREDIT_CARD | 100.0% | 100.0% | 100.0% | 15 |
| IFSC | 100.0% | 100.0% | 100.0% | 15 |
| GSTIN | 100.0% | 100.0% | 100.0% | 15 |
| DOB | 100.0% | 100.0% | 100.0% | 20 |
| PASSPORT | 100.0% | 100.0% | 100.0% | 20 |
| VOTER_ID | 100.0% | 100.0% | 100.0% | 18 |
| DRIVING_LICENCE | 100.0% | 100.0% | 100.0% | 20 |
| IP_ADDRESS | 100.0% | 100.0% | 100.0% | 10 |
| MEDICAL_RECORD | 100.0% | 100.0% | 100.0% | 10 |
| PERSON | 91.1% | 82.0% | 86.3% | 50 |
| UPI_ID | 100.0% | 71.4% | 83.3% | 21 |
| **Micro-average** | **70.5%** | **95.5%** | **81.1%** | **330** |
| **Macro-average (PII types only)** | **99.4%** | **96.9%** | **98.0%** | **330** |

> **Notes:**
> - Micro-precision is lowered by NER false positives on non-PII types (ORG, DATE, LOCATION, etc.) — these are spaCy detections of entities like city names and organizations that are not in our PII taxonomy.
> - Excluding non-PII NER types, the pipeline achieves **99.4% precision** and **96.9% recall** across the 15 target PII categories.
> - PERSON recall (82%) is limited by spaCy `en_core_web_sm`; upgrading to `en_core_web_trf` is expected to improve this.
> - UPI_ID recall (71.4%) reflects the intentional exclusion of email-like UPI addresses to prevent false-positive email → UPI misclassification.

### Reproducing

```bash
cd backend
python scripts/generate_eval_set.py          # generate 300-example test set
python scripts/evaluate.py --dataset data/eval_set_300.json --report --verbose
```

## Quick Start

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
python -m spacy download en_core_web_sm
uvicorn app.main:app --reload
```

### Chrome Extension

1. Open `chrome://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked** → select the `extension/` folder
4. Navigate to ChatGPT / Claude / Gemini and start chatting

### Docker

```bash
docker-compose up --build
```

## Architecture

```
User → Content Script → Service Worker → Backend /sanitize
                                              ↓
                                     spaCy NER + Regex + BERT
                                              ↓
                                     Sanitized prompt → LLM
                                              ↓
                                     LLM response → /restore → User
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Extension | Chrome Manifest V3, vanilla JS |
| Backend | Python 3.11, FastAPI, Uvicorn |
| NER | spaCy (en_core_web_trf / en_core_web_sm) |
| Classifier | HuggingFace Transformers (BERT) |
| OCR | Tesseract + PaddleOCR |
| Database | SQLite (dev) / PostgreSQL (prod) |

## License

MIT


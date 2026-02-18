# 🛡️ SecureFlow AI

**Privacy-Preserving LLM Chrome Extension**

SecureFlow AI intercepts your prompts to LLMs (ChatGPT, Claude, Gemini), sanitizes PII/PHI/financial data in real time, forwards the cleaned prompt, and restores redacted tokens in the response.

## Features

- 🔒 **Real-time PII Detection** — Names, SSNs, credit cards, emails, phone numbers, medical records
- 🧠 **AI-Powered Risk Scoring** — Fine-tuned BERT classifier rates sensitivity as High / Medium / Low
- 📄 **OCR Redaction** — Scan PDFs and images for sensitive data
- 🔄 **Seamless Restoration** — Redacted tokens are restored in LLM responses automatically
- 📊 **Dashboard & Audit Log** — Track what was redacted across sessions

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

# SecureFlow AI — Architecture

## Overview

SecureFlow AI is a privacy-preserving proxy for LLM interactions. It consists of two main components:

1. **Chrome Extension** (Manifest V3) — Intercepts user prompts on LLM sites
2. **Backend API** (Python/FastAPI) — Runs the sanitization pipeline

## Data Flow

```
User types prompt → Content Script captures text
  → Service Worker sends to Backend /sanitize
    → spaCy NER + Regex + BERT Risk Classifier
    → Redaction Engine replaces PII with tokens
  → Sanitized prompt returned to Content Script
  → Content Script forwards to LLM
  → LLM responds
  → Service Worker sends response to /restore
  → Original values reinjected
  → User sees clean response
```

## Extension Components

| Component | File | Purpose |
|-----------|------|---------|
| Content Script | `content/content.js` | Injected into LLM pages, intercepts prompts |
| Service Worker | `background/service-worker.js` | Routes API calls to backend |
| Popup | `popup/` | Toggle switch, stats, sensitivity selector |
| Options | `options/` | Backend config, site toggles, privacy settings |
| Dashboard | `dashboard/` | Session history, entity breakdown, CSV export |

## Backend Pipeline

```
Raw Text → NER Detector → Regex Detector → Merge & Deduplicate
  → BERT Risk Classifier → Redaction Engine → Sanitized Text + Token Map
```

## Security Model

- Token maps never leave the backend
- HTTPS-only communication
- API key authentication
- Rate limiting via slowapi
- Token maps auto-expire after 30 minutes

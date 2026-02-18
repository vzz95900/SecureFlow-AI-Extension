# SecureFlow AI — API Reference

## Base URL

```
http://localhost:8000/api/v1
```

## Authentication

Include `X-API-Key` header if authentication is enabled.

---

## Endpoints

### `POST /sanitize`

Sanitize text by detecting and redacting PII/PHI.

**Request:**
```json
{
  "text": "My name is John Doe, SSN 123-45-6789",
  "session_id": null,
  "sensitivity": "high"
}
```

**Response:**
```json
{
  "sanitized_text": "My name is [REDACTED_NAME_1], SSN [REDACTED_SSN_1]",
  "session_id": "abc123",
  "entities_found": 2,
  "risk_level": "HIGH",
  "entity_summary": [
    { "type": "PERSON", "count": 1, "risk": "MEDIUM" },
    { "type": "SSN", "count": 1, "risk": "HIGH" }
  ]
}
```

---

### `POST /restore`

Restore redacted tokens in LLM response.

**Request:**
```json
{
  "text": "[REDACTED_NAME_1] lives in New York",
  "session_id": "abc123"
}
```

**Response:**
```json
{
  "restored_text": "John Doe lives in New York"
}
```

---

### `GET /health`

Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

---

### `GET /stats/{session_id}`

Get redaction statistics for a session.

**Response:**
```json
{
  "session_id": "abc123",
  "entities_found": 5,
  "risk_level": "HIGH",
  "entity_breakdown": { "PERSON": 2, "SSN": 1, "EMAIL": 2 }
}
```

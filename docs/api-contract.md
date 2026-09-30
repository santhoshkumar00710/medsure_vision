# MedSure Vision — API Contract v1.0

> **Source of truth for both frontend and backend.**  
> All JSON field names, enum values, and error shapes in this document must be matched exactly.  
> Do not rename fields. If something is impossible, document it rather than changing a field name.

---

## Base URL

```
http://localhost:8000
```

All responses are `application/json` unless noted (PDF endpoint returns `application/pdf`, CSV returns `text/csv`).

---

## Error Envelope

Every error response uses this exact shape:

```json
{
  "error": {
    "code": "SNAKE_CASE_CODE",
    "message": "Human-readable explanation"
  }
}
```

Common codes: `INVALID_INPUT`, `NOT_FOUND`, `QUALITY_INSUFFICIENT`, `RATE_LIMITED`, `INTERNAL_ERROR`.

Stack traces must **never** appear in error responses.

---

## Shared Enums

### `label` (scan result verdict)
| Value | Meaning |
|---|---|
| `low_risk` | No inconsistencies found across all three layers |
| `needs_verification` | Anomaly or weak evidence; check before dispensing |
| `high_suspicion` | Hard rule triggered; do not dispense |
| `insufficient_quality` | Image too blurry/dark/glare; rescan |

### `severity`
`high` · `needs_verification` · `note`

### `confidence`
`low` · `moderate` · `high`

### `code_type`
`gs1` · `url` · `demo` · `unknown`

### `cross_check_status`
`match` · `mismatch` · `not_comparable`

---

## Endpoints

---

### POST `/scan`

Multipart form data. Runs the full pipeline.

**Request fields (multipart)**

| Field | Type | Required | Notes |
|---|---|---|---|
| `image` | file | YES | JPEG or PNG of the medicine pack |
| `image2` | file | NO | Optional second angle |
| `device_token` | string | YES | Rotating opaque token from client |
| `lat` | float | NO | Will be rounded to 2 decimals server-side |
| `lng` | float | NO | Will be rounded to 2 decimals server-side |
| `language` | string | NO | `en` (default) / `hi` / `ta` |

**Response `200 OK`** — `ScanResult`

```json
{
  "id": "uuid-string",
  "ts": "2026-09-30T14:22:00+05:30",
  "label": "high_suspicion",
  "partial": false,

  "quality": {
    "ok": true,
    "blur": 142.3,
    "brightness": 0.61,
    "glare": 0.04,
    "contrast": 48.2,
    "resolution_min": 1080,
    "tips": ["Reduce glare, tilt the pack"]
  },

  "ocr": {
    "ran": true,
    "name": { "value": "Cefix-O 200mg Tablets", "confidence": 0.91 },
    "strength": { "value": "200mg", "confidence": 0.95 },
    "form": { "value": "Tablet", "confidence": 0.88 },
    "batch": { "value": "CFX-88219", "confidence": 0.97 },
    "mfg_date": { "value": "01/2025", "confidence": 0.82 },
    "expiry": { "value": "11/2026", "confidence": 0.96 },
    "manufacturer": { "value": "Alkem Laboratories", "confidence": 0.89 }
  },

  "code": {
    "ran": true,
    "type": "gs1",
    "raw": "]d201089012345678903410CFX-882101711093021SERIAL001",
    "gtin": "08901234567890",
    "batch": "CFX-88210",
    "expiry": "09/2025",
    "serial": "SERIAL001",
    "has_serial": true,
    "gtin_valid": true,
    "payload_source": "gs1",
    "url_offline_note": null
  },

  "cross_check": [
    {
      "field": "batch",
      "printed": "CFX-88219",
      "code": "CFX-88210",
      "status": "mismatch",
      "bbox": [0.12, 0.45, 0.42, 0.58]
    },
    {
      "field": "expiry",
      "printed": "11/2026",
      "code": "09/2025",
      "status": "mismatch",
      "bbox": [0.52, 0.62, 0.78, 0.72]
    },
    {
      "field": "name",
      "printed": "Cefix-O",
      "code": null,
      "status": "not_comparable",
      "bbox": null
    }
  ],

  "visual": {
    "ran": true,
    "identity_score": 0.61,
    "alignment_ok": true,
    "heatmap_url": "/media/heatmap_uuid.png",
    "anomaly_score": 0.89,
    "anomaly_regions": [
      { "label": "Font kerning divergence", "bbox": [0.12, 0.45, 0.42, 0.58], "score": 0.89 },
      { "label": "Logo colour shift", "bbox": [0.05, 0.10, 0.30, 0.25], "score": 0.72 }
    ]
  },

  "authenticity": {
    "ran": true,
    "registry": {
      "status": "already_used",
      "simulated": true
    },
    "alert": {
      "match_level": "exact",
      "alert_id": "CDSCO-2024-08-003",
      "source_month": "August 2024",
      "source_url": "https://cdsco.gov.in/...",
      "snapshot_date": "2026-09-01",
      "snapshot_stale": false
    },
    "clone": {
      "signal": "moderate",
      "verdict_text": "Unusual scan activity for this code. Verify with the manufacturer before use."
    }
  },

  "reasons": [
    {
      "id": "CODE_PRINT_MISMATCH",
      "text": "The batch number on the pack (CFX-88219) does not match the code (CFX-88210).",
      "severity": "high",
      "contribution": 35
    },
    {
      "id": "EXPIRED",
      "text": "The code says this pack expired in September 2025.",
      "severity": "high",
      "contribution": 30
    },
    {
      "id": "CLONE_MODERATE",
      "text": "Unusual scan activity for this code. Verify with the manufacturer before use.",
      "severity": "needs_verification",
      "contribution": 20
    }
  ],

  "score": 72,
  "score_breakdown": {
    "visual_similarity": 20,
    "anomaly": 20,
    "ocr_confidence": 0,
    "unusual_scan_count": 15,
    "unclear_fields": 0
  },

  "checked": [
    "OCR text consistency",
    "2D matrix structure",
    "CDSCO recalled batch list",
    "Blister packaging typography"
  ],
  "not_checked": [
    "Serial not verified with manufacturer (simulated)"
  ],

  "confidence": "high",
  "confidence_note": "3 of 3 layers ran and agreed",

  "field_rows": [
    {
      "field": "batch",
      "printed": "CFX-88219",
      "code_value": "CFX-88210",
      "expected": null,
      "status": "mismatch",
      "bbox": [0.12, 0.45, 0.42, 0.58]
    },
    {
      "field": "expiry",
      "printed": "11/2026",
      "code_value": "09/2025",
      "expected": null,
      "status": "mismatch",
      "bbox": [0.52, 0.62, 0.78, 0.72]
    }
  ],

  "next_steps": [
    "Do not dispense or ingest this pack under any circumstance.",
    "Quarantine pack in the designated pharmacy returns / suspicious batch bin.",
    "Inform upstream drug distributor and file digital escalation to state drug regulatory authority."
  ],

  "simulated_flags": ["registry", "clone_seed"],
  "disclaimer": "Screening only. This does not confirm authenticity."
}
```

**bbox** format: `[x_min, y_min, x_max, y_max]` normalised to `[0, 1]`.
Only returned for `mismatch` fields where OCR confidence was above threshold.

**Error responses**
- `400` - missing image or invalid device_token format
- `429` - rate limit (60 scans / device / hour)
- Quality fail still returns `200` with `label: "insufficient_quality"` (not an error code)

---

### POST `/scan/manual`

JSON body. Runs field validators and rules only. No image, no visual layer.
Always sets `partial: true`. **Never returns `label: "low_risk"`**.

**Request body**

```json
{
  "name": "Cefix-O 200mg Tablets",
  "batch": "CFX-88219",
  "expiry": "11/2026",
  "mfg_date": "01/2025",
  "manufacturer": "Alkem Laboratories",
  "strength": "200mg",
  "form": "Tablet",
  "device_token": "tok_abc123",
  "language": "en"
}
```

All fields optional except `device_token`. At least one of `name`, `batch`, or `expiry` must be present.

**Response `200 OK`** - same `ScanResult` shape with these differences:
- `partial: true`
- `quality: null`
- `visual: { "ran": false }`
- `code: { "ran": false }`
- `label` is never `"low_risk"` (minimum `"needs_verification"`)

---

### GET `/demo/{case_id}`

Runs the real pipeline on a prebuilt demo image.

**Path params**

| `case_id` | Expected label |
|---|---|
| `genuine` | `low_risk` |
| `expiry_tampered` | `high_suspicion` |
| `logo_shifted` | `needs_verification` |
| `clone_code` | `high_suspicion` |
| `alert_match` | `high_suspicion` |
| `blurry` | `insufficient_quality` |

**Response `200 OK`** - `ScanResult` (all `simulated_flags` will include `"demo_case"`)
**Response `404`** - `{ "error": { "code": "NOT_FOUND", "message": "Unknown demo case" } }`

---

### GET `/scans`

Returns paginated scan history for the requesting device.

**Query params**

| Param | Type | Default | Notes |
|---|---|---|---|
| `result` | string | - | Filter by label enum |
| `limit` | int | 20 | Max 100 |
| `offset` | int | 0 | |

**Headers**
- `X-Device-Token: <token>` - required

**Response `200 OK`**

```json
{
  "total": 42,
  "items": [
    {
      "id": "uuid",
      "ts": "2026-09-30T14:22:00+05:30",
      "label": "high_suspicion",
      "name": "Cefix-O 200mg Tablets",
      "batch": "CFX-88219",
      "expiry": "11/2026",
      "manufacturer": "Aristo Pharmaceuticals",
      "top_reason": "Batch number does not match the code.",
      "partial": false
    }
  ]
}
```

---

### GET `/scans/{id}`

Returns full `ScanResult` for one scan.

**Response `404`** if the scan does not belong to the requesting device.

---

### DELETE `/scans`

Deletes all scan rows belonging to the `X-Device-Token` in the header.

**Response `204 No Content`**

---

### GET `/scans/{id}/report.pdf`

Returns a PDF report for the scan.
Content-Type: `application/pdf`
**Response `404`** if not found.

---

### GET `/serial/{hash}/trail`

Clone / scan trail for a serial.

**Path param:** `hash` - HMAC-SHA256 hash of the serial number (hex, lowercase).

**Response `200 OK`**

```json
{
  "serial_hash": "abc123...",
  "simulated": true,
  "verdict_text": "Scanned in Chennai and Delhi within 2 hours. This is unusual.",
  "events": [
    {
      "district": "Chennai",
      "lat": 13.08,
      "lng": 80.27,
      "ts": "2026-09-30T08:30:00+05:30",
      "flagged": false
    },
    {
      "district": "Delhi",
      "lat": 28.61,
      "lng": 77.20,
      "ts": "2026-09-30T09:55:00+05:30",
      "flagged": true
    }
  ]
}
```

---

### GET `/batch/{hash}/status`

Community batch anomaly status.

**Path param:** `hash` - HMAC-SHA256 hash of the normalised batch number.

**Response `200 OK`**

```json
{
  "batch_hash": "def456...",
  "band": "several",
  "simulated": false,
  "districts": [
    {
      "district": "Chennai",
      "lat": 13.08,
      "lng": 80.27,
      "flagged_share": 0.6
    }
  ]
}
```

**`band` values:** `none` / `few` / `several` / `many`
`band` above `"none"` requires >= 5 distinct devices.
Exact counts are never returned.

---

### POST `/batch-report`

User community report for a batch.

**Request body**

```json
{
  "scan_id": "uuid",
  "note": "Hologram looks different from what I've seen before."
}
```

**Response `201 Created`**

```json
{ "id": "report-uuid" }
```

Rate-limited: 1 report per device per batch per day.

---

### GET `/alerts`

List of CDSCO-sourced alert entries.

**Response `200 OK`**

```json
{
  "snapshot_date": "2026-09-01",
  "snapshot_stale": false,
  "items": [
    {
      "id": "CDSCO-2024-08-003",
      "brand": "Monocef 1g Injection",
      "generic": "Ceftriaxone",
      "batch_norm": "MN0994",
      "mfg": "Aristo Pharmaceuticals Ltd.",
      "exp": "12/2025",
      "status": "recalled",
      "reason": "Sub-standard labeling, non-registered DataMatrix serialization",
      "source_month": "August 2024",
      "source_url": "https://cdsco.gov.in/...",
      "simulated": true
    }
  ]
}
```

`snapshot_stale` is `true` when `snapshot_date` is older than 45 days.

---

### GET `/stats`

Global statistics.

**Response `200 OK`**

```json
{
  "total": 128,
  "by_label": {
    "low_risk": 95,
    "needs_verification": 22,
    "high_suspicion": 8,
    "insufficient_quality": 3
  },
  "top_batches": [
    { "batch": "MN-0994", "count": 6, "label": "high_suspicion" }
  ],
  "top_issues": [
    { "rule_id": "CODE_PRINT_MISMATCH", "count": 14 }
  ]
}
```

---

### GET `/health`

Startup health check.

**Response `200 OK`**

```json
{
  "status": "ok",
  "components": {
    "easyocr": true,
    "tesseract": true,
    "pylibdmtx": false,
    "patchcore": false,
    "mobilenet": true
  },
  "db": "ok",
  "version": "1.0.0"
}
```

---

### Receiving Mode

#### POST `/receiving/sessions`

```json
{ "supplier": "MedPlus Wholesale", "invoice_no": "INV-2024-881" }
```

**Response `201`**

```json
{ "id": "session-uuid" }
```

---

#### POST `/receiving/sessions/{id}/scan`

Same multipart format as `/scan`. Links result to session.
**Response** - `ScanResult` with `session_id` added.

---

#### GET `/receiving/sessions/{id}/summary`

```json
{
  "id": "session-uuid",
  "supplier": "MedPlus Wholesale",
  "scanned": 24,
  "flagged": 3,
  "accepted": 20,
  "batch_conflicts": [
    {
      "batch": "MN-0994",
      "conflict_type": "expiry_mismatch",
      "detail": "Pack 12 shows expiry 11/2026, others show 09/2025"
    }
  ],
  "groups": [
    {
      "name": "Monocef 1g Injection",
      "batch": "MN-0994",
      "count": 4,
      "worst_label": "high_suspicion"
    }
  ]
}
```

---

#### POST `/receiving/sessions/{id}/accept`

Marks non-flagged packs accepted; sets serial to `already_used` in simulated registry.

**Response `200`**

```json
{ "accepted": 20, "registry_updated": 18 }
```

---

#### GET `/receiving/sessions/{id}/export`

**Query param:** `format=pdf` or `format=csv`
Returns PDF or CSV of the Hold/Return list.

---

## Privacy Notes

- Serial and batch hashes: HMAC-SHA256 with a salted key from env (`MEDSURE_HASH_SALT`)
- Location: round lat/lng to 2 decimal places before storing
- Device token: opaque, rotating, accepted from client
- No image stored in community tables
- `DELETE /scans` removes all rows for the device; serial hashes in `scan_events` remain (they are anonymised)

---

## Wording Constraints

User-facing strings must **never** use `"fake"`, `"genuine"`, or `"cloned"` as verdicts.
Allowed language: `"inconsistencies found"`, `"needs verification"`, `"unusual scan activity"`.

All `ScanResult` responses must include:

```
"disclaimer": "Screening only. This does not confirm authenticity."
```

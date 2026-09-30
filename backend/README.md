# MedSure Vision — Backend

AI-assisted first-line screening tool for medicine packs.  
**Python 3.11+ · FastAPI · SQLite · Fully offline**

---

## Quick Start

```powershell
# 1. Install dependencies
python -m pip install -r requirements.txt

# 2. Seed the database (run once)
python scripts\seed_db.py

# 3. Start the API server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 4. Visit interactive docs
# http://localhost:8000/docs
```

Or use the convenience script:

```powershell
.\run.bat
```

---

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `MEDSURE_HASH_SALT` | `medsure-dev-salt-change-in-prod` | HMAC salt for serial/batch hashing — **change in production** |
| `DATABASE_URL` | `sqlite:///./medsure.db` | SQLAlchemy connection string |
| `VISUAL_ENABLED` | `true` | Enable MobileNetV2 visual engine |
| `PATCHCORE_ENABLED` | `false` | Enable PatchCore-lite anomaly heatmap (slow, needs reference images) |
| `QUALITY_BLUR_MIN` | `80.0` | Minimum Laplacian variance for a quality-ok image |
| `QUALITY_BRIGHTNESS_MIN` | `0.20` | Minimum HSV-V mean (0–1) |
| `QUALITY_BRIGHTNESS_MAX` | `0.95` | Maximum HSV-V mean (0–1) |
| `QUALITY_GLARE_MAX` | `0.15` | Max fraction of pixels with V >= 250 |
| `QUALITY_RESOLUTION_MIN` | `400` | Minimum image dimension in pixels |
| `OCR_CONFIDENCE_MIN` | `0.55` | Fields below this are "unclear" — never count as confirmed mismatch |
| `NAME_FUZZY_OK` | `95` | RapidFuzz score for name match "ok" |
| `NAME_FUZZY_WARN` | `80` | RapidFuzz score for "possible misspelling" |
| `CLONE_SPEED_KMH` | `900.0` | Speed threshold for impossible-travel detection |
| `CLONE_DEVICE_THRESHOLD` | `5` | Distinct devices above which = moderate clone signal |
| `ALERT_STALE_DAYS` | `45` | Days before snapshot_stale becomes true |
| `RATE_SCAN_PER_HOUR` | `60` | Max scans per device per hour |

---

## One-Time Model Download (for fully offline operation)

EasyOCR and PyTorch weights download automatically on first use. To pre-download:

```powershell
# EasyOCR English model
python -c "import easyocr; easyocr.Reader(['en'], gpu=False)"

# MobileNetV2 (visual engine)
python -c "import torchvision.models as m; m.mobilenet_v2(weights=m.MobileNet_V2_Weights.IMAGENET1K_V1)"
```

After downloading once, everything works without internet.

---

## Reference Images (Visual Engine)

Place your own reference photos at:

```
data/reference_images/{medicine_id}/*.jpg
```

Where `medicine_id` matches the `id` field in `data/medicines.json` (e.g., `med_005`).

Then build the embeddings:

```powershell
python scripts\build_reference_embeddings.py
```

**Without reference images:** the visual layer returns `ran: false` and the result can never be `low_risk` (since all 3 layers must run for that label).

---

## Running Tests

```powershell
python -m pytest tests/ -v
```

Key test files:
- `tests/test_gs1.py` — GS1 parser (all formats, bad dates, GTIN check digit)
- `tests/test_quality.py` — Image quality gate
- `tests/test_rules.py` — Hard rules + decision tree truth table
- `tests/test_privacy.py` — HMAC hashing, batch normalisation, DELETE isolates by device

---

## What Is Real vs Simulated

| Feature | Status |
|---|---|
| OCR (EasyOCR + Tesseract) | **Real** |
| Barcode / QR decode (pyzbar) | **Real** |
| GS1 parsing | **Real** |
| Quality metrics (blur, brightness, glare) | **Real** |
| Fuzzy name match against `medicines.json` | **Real** |
| Expiry / batch rule evaluation | **Real** |
| MobileNetV2 identity score | **Real** (needs reference images) |
| CDSCO alert matching | Real logic, **seeded demo data** |
| Manufacturer registry lookup | **Simulated** (local SQLite table, `simulated: true` always set) |
| Clone / scan trail | **Simulated** seed data (Chennai→Delhi scenario) |
| Community batch band | Real aggregation, **simulated seed events** |

All simulated data is flagged in `simulated_flags[]` on every response.  
Responses always include: `"disclaimer": "Screening only. This does not confirm authenticity."`

---

## API Documentation

Interactive docs at `http://localhost:8000/docs`  
Full contract: [`/docs/api-contract.md`](../docs/api-contract.md)

---

## Repo Layout

```
backend/
  app/
    main.py              FastAPI app, CORS, static /media, exception handler
    config.py            All thresholds and env vars
    db.py                SQLAlchemy engine + session
    models.py            ORM table definitions
    schemas.py           Pydantic models (exact contract field names)
    pipeline/
      quality.py         Blur / brightness / glare / contrast
      ocr.py             EasyOCR + Tesseract + preprocessing
      fields.py          Regex extraction, fuzzy name match, expiry validation
      codes.py           pyzbar / pylibdmtx / cv2 decoder
      gs1.py             GS1 element-string parser
      visual.py          MobileNetV2 embedding, ORB alignment, PatchCore-lite
      authenticity.py    HMAC hashing, alert matcher, registry, clone signals
      rules.py           Hard rules engine
      fusion.py          Decision tree and score computation
      explain.py         EN / HI / TA translation table
    routes/
      scan.py            POST /scan  POST /scan/manual  GET /demo/{case_id}
      scans.py           GET /scans  GET /scans/{id}  DELETE /scans
      serial.py          GET /serial/{hash}/trail
      batch.py           GET /batch/{hash}/status  POST /batch-report
      alerts.py          GET /alerts
      receiving.py       Receiving mode
      stats.py           GET /stats
    reports/
      pdf.py             ReportLab PDF generation
  data/
    medicines.json       15 medicine entries
    alerts.json          Seeded CDSCO-style alerts (all simulated: true)
    demo_cases/          6 subdirs for demo pipeline runs
    reference_images/    Place your photos here: {medicine_id}/*.jpg
  scripts/
    seed_db.py           Load medicines, alerts, registry, clone scenario
    build_reference_embeddings.py
  tests/
    test_gs1.py
    test_quality.py
    test_rules.py
    test_privacy.py
    test_manual.py
  requirements.txt
  run.bat
```

---

## Wording Policy

User-facing strings **never** use `"fake"`, `"genuine"`, or `"cloned"` as verdicts.  
Approved language: `"inconsistencies found"`, `"needs verification"`, `"unusual scan activity"`.

Low risk label means: **"No inconsistencies found across all three layers"** — not authenticity confirmation.

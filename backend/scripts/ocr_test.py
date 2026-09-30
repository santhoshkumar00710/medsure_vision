"""
scripts/ocr_test.py — Task 2 OCR test harness.

Usage:
  python scripts/ocr_test.py --photos test_photos/ --gt test_photos/ground_truth.csv

Reads ground_truth.csv (filename, name, batch, expiry).
Posts each image to POST /scan (or runs pipeline directly if --offline).
Writes ocr_report.csv and prints per-field accuracy.
"""
import argparse, csv, sys, json, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FIELDS = ["name", "batch", "expiry"]


def run_pipeline(image_path: Path) -> dict:
    """Run fields pipeline directly (offline, no HTTP)."""
    import cv2, numpy as np
    from app.pipeline.quality import assess_quality
    from app.pipeline.ocr import run_ocr
    from app.pipeline.fields import extract_fields

    img_bytes = image_path.read_bytes()
    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    qr = assess_quality(img_bytes)
    if not qr.ok:
        return {}

    ocr_r = run_ocr(img_bytes)
    fields = extract_fields(ocr_r, code_result=None)
    return {
        "name":   fields.name.value   if fields.name   else None,
        "batch":  fields.batch.value  if fields.batch  else None,
        "expiry": fields.expiry.value if fields.expiry else None,
    }


def normalise(v: str | None) -> str:
    if v is None:
        return ""
    return v.strip().upper().replace(" ", "").replace("-", "").replace("/", "").replace(".", "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--photos", required=True)
    ap.add_argument("--gt", required=True)
    ap.add_argument("--out", default="ocr_report.csv")
    args = ap.parse_args()

    photos_dir = Path(args.photos)
    gt_path    = Path(args.gt)
    out_path   = Path(args.out)

    if not gt_path.exists():
        print(f"ERROR: ground_truth.csv not found: {gt_path}")
        sys.exit(1)

    with open(gt_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print("ground_truth.csv is empty — nothing to test.")
        sys.exit(0)

    results = []
    counts  = {f: {"total": 0, "match": 0} for f in FIELDS}

    for row in rows:
        filename = row.get("filename", "").strip()
        photo = photos_dir / filename
        if not photo.exists():
            print(f"  SKIP (not found): {filename}")
            continue

        t0 = time.time()
        try:
            got = run_pipeline(photo)
        except Exception as e:
            print(f"  ERROR {filename}: {e}")
            got = {}
        latency = round((time.time() - t0) * 1000)

        rec = {"filename": filename, "latency_ms": latency}
        for field in FIELDS:
            expected = row.get(field, "").strip()
            actual   = got.get(field) or ""
            match    = normalise(expected) == normalise(actual) if expected else "n/a"
            rec[f"{field}_expected"] = expected
            rec[f"{field}_got"]      = actual
            rec[f"{field}_match"]    = match
            if expected:
                counts[field]["total"] += 1
                if match is True:
                    counts[field]["match"] += 1
        results.append(rec)

    # Write report
    fieldnames = ["filename", "latency_ms"]
    for f in FIELDS:
        fieldnames += [f"{f}_expected", f"{f}_got", f"{f}_match"]

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(results)

    print(f"\nOCR Report saved to {out_path}")
    print("\n=== Per-field accuracy ===")
    for field in FIELDS:
        c = counts[field]
        if c["total"] == 0:
            print(f"  {field:10s}  n/a (no expected values in ground truth)")
        else:
            pct = 100 * c["match"] / c["total"]
            print(f"  {field:10s}  {c['match']}/{c['total']}  ({pct:.1f}%)")

    print("\n=== Failures ===")
    any_fail = False
    for r in results:
        for field in FIELDS:
            if r[f"{field}_match"] is False:
                print(f"  {r['filename']}  {field}: got={r[f'{field}_got']!r}  expected={r[f'{field}_expected']!r}")
                any_fail = True
    if not any_fail:
        print("  None")


if __name__ == "__main__":
    main()

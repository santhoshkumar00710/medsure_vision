"""
scripts/evaluate.py — Task 5: Model evaluation.

Reads eval_data/labels.csv (filename, true_class: untampered|tampered).
Runs each image through the pipeline.
Outputs:
  - false-safe rate (tampered images labelled low_risk)
  - confusion matrix
  - per-label counts
  - mean and p95 latency
Saves: eval_results.json and eval_results.md

NOTE: Tampered images are synthetic and self-made for internal testing only.
      Results do not constitute clinical validation.
"""
import csv, sys, json, time, statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

EVAL_DIR  = ROOT / "eval_data"
OUT_JSON  = ROOT / "eval_results.json"
OUT_MD    = ROOT / "eval_results.md"


def run_pipeline_on_image(image_path: Path) -> tuple[str, float]:
    """Returns (label, latency_ms)."""
    import cv2, numpy as np
    from app.pipeline.quality import assess_quality
    from app.pipeline.ocr import run_ocr
    from app.pipeline.fields import extract_fields
    from app.pipeline.rules import evaluate_hard_rules
    from app.pipeline.fusion import fuse
    from app.pipeline.codes import DecodeResult
    from app.schemas import AlertResult, CloneResult, RegistryResult

    t0 = time.time()
    img_bytes = image_path.read_bytes()
    qr = assess_quality(img_bytes)
    if not qr.ok:
        return "insufficient_quality", round((time.time()-t0)*1000, 1)

    nparr = np.frombuffer(img_bytes, np.uint8)
    img_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    ocr_r  = run_ocr(img_bytes)
    fields = extract_fields(ocr_r, code_result=None)
    code   = DecodeResult(ran=False)
    hard   = evaluate_hard_rules(fields, code, None, None, None)
    result = fuse(
        quality_ok=True,
        hard_rules=hard,
        fields=fields,
        code=code,
        visual=None,
        alert=AlertResult(),
        clone=CloneResult(),
        registry=RegistryResult(status="valid"),
        partial=True,
    )
    return result.label, round((time.time()-t0)*1000, 1)


def main():
    labels_csv = EVAL_DIR / "labels.csv"
    if not labels_csv.exists():
        print(f"ERROR: {labels_csv} not found.")
        print("Create eval_data/labels.csv with columns: filename, true_class")
        print("Then add images to eval_data/")
        sys.exit(1)

    rows = list(csv.DictReader(open(labels_csv, encoding="utf-8")))
    if not rows:
        print("labels.csv is empty.")
        sys.exit(0)

    latencies = []
    results   = []
    confusion  = {}   # true_class -> predicted_label -> count
    label_counts = {}

    false_safe = 0    # tampered labelled low_risk
    total_tampered = 0

    for row in rows:
        fname      = row["filename"].strip()
        true_class = row["true_class"].strip()   # untampered | tampered
        img_path   = EVAL_DIR / fname

        if not img_path.exists():
            print(f"  SKIP (missing): {fname}")
            continue

        try:
            label, ms = run_pipeline_on_image(img_path)
        except Exception as e:
            print(f"  ERROR {fname}: {e}")
            continue

        latencies.append(ms)
        results.append({"filename": fname, "true_class": true_class, "predicted": label, "latency_ms": ms})

        confusion.setdefault(true_class, {})
        confusion[true_class][label] = confusion[true_class].get(label, 0) + 1
        label_counts[label] = label_counts.get(label, 0) + 1

        if true_class == "tampered":
            total_tampered += 1
            if label == "low_risk":
                false_safe += 1

    if not latencies:
        print("No images processed.")
        return

    latencies.sort()
    mean_ms = round(statistics.mean(latencies), 1)
    p95_idx = int(0.95 * len(latencies))
    p95_ms  = latencies[min(p95_idx, len(latencies)-1)]
    fs_rate = round(false_safe / total_tampered * 100, 1) if total_tampered else 0

    summary = {
        "note": "Tampered images are synthetic and self-made for internal testing only. Not clinical validation.",
        "total_images": len(results),
        "total_tampered": total_tampered,
        "false_safe_count": false_safe,
        "false_safe_rate_pct": fs_rate,
        "mean_latency_ms": mean_ms,
        "p95_latency_ms": p95_ms,
        "confusion_matrix": confusion,
        "per_label_counts": label_counts,
    }
    json.dump(summary, open(OUT_JSON, "w"), indent=2)

    # Markdown report
    md = f"""# MedSure Vision — Evaluation Results

> **Note:** Tampered images are synthetic and self-made for internal testing only.
> These results do not constitute clinical validation.

## Summary

| Metric | Value |
|---|---|
| Total images | {len(results)} |
| Tampered images | {total_tampered} |
| False-safe rate (tampered → low_risk) | **{fs_rate}%** |
| Mean latency | {mean_ms} ms |
| p95 latency | {p95_ms} ms |

## Per-label counts

| Label | Count |
|---|---|
"""
    for lbl, cnt in sorted(label_counts.items()):
        md += f"| {lbl} | {cnt} |\n"

    md += "\n## Confusion matrix\n\n| True class | Predicted → |\n|---|---|\n"
    all_preds = sorted({p for row in confusion.values() for p in row})
    md += "| true_class | " + " | ".join(all_preds) + " |\n"
    md += "|---|" + "---|" * len(all_preds) + "\n"
    for tc in sorted(confusion):
        row = confusion[tc]
        md += f"| {tc} | " + " | ".join(str(row.get(p, 0)) for p in all_preds) + " |\n"

    open(OUT_MD, "w", encoding="utf-8").write(md)
    print(f"Saved {OUT_JSON} and {OUT_MD}")
    print(f"False-safe rate: {fs_rate}% ({false_safe}/{total_tampered} tampered labelled low_risk)")
    print(f"Mean latency: {mean_ms} ms  p95: {p95_ms} ms")


if __name__ == "__main__":
    main()

"""
scripts/ingest_cdsco.py — Task 6: parse a CDSCO monthly alert PDF into alerts.json.

Usage:
  python scripts/ingest_cdsco.py path/to/alert.pdf
  python scripts/ingest_cdsco.py path/to/alert.pdf --confirm

Without --confirm: writes alerts_review.csv only (safe, no changes).
With --confirm:    merges new rows into data/alerts.json.
"""
import argparse, csv, json, re, sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
ALERTS_JSON = ROOT / "data" / "alerts.json"
REVIEW_CSV  = ROOT / "alerts_review.csv"


def _normalise_batch(b: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", b.upper())


def parse_pdf(pdf_path: Path) -> list[dict]:
    try:
        import pdfplumber
    except ImportError:
        print("ERROR: pdfplumber not installed. Run: pip install pdfplumber")
        sys.exit(1)

    rows = []
    today = date.today().strftime("%b %Y")
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if not table:
                    continue
                # Try to detect column headers
                headers = [str(c).lower().strip() if c else "" for c in table[0]]
                name_col = next((i for i, h in enumerate(headers) if "name" in h or "drug" in h or "product" in h), 0)
                batch_col = next((i for i, h in enumerate(headers) if "batch" in h or "lot" in h), None)
                mfr_col   = next((i for i, h in enumerate(headers) if "manuf" in h or "firm" in h), None)
                reason_col= next((i for i, h in enumerate(headers) if "reason" in h or "fail" in h or "remark" in h), None)
                status_col= next((i for i, h in enumerate(headers) if "status" in h or "action" in h or "class" in h), None)

                for data_row in table[1:]:
                    if not data_row or not any(data_row):
                        continue
                    def cell(idx):
                        if idx is None or idx >= len(data_row):
                            return ""
                        v = data_row[idx]
                        return str(v).strip() if v else ""

                    brand = cell(name_col)
                    if not brand or len(brand) < 3:
                        continue
                    batch_raw = cell(batch_col) if batch_col is not None else ""
                    rows.append({
                        "brand": brand,
                        "generic": "",
                        "batch_raw": batch_raw,
                        "batch_norm": _normalise_batch(batch_raw),
                        "manufacturer": cell(mfr_col) if mfr_col else "",
                        "reason": cell(reason_col) if reason_col else "",
                        "status": cell(status_col).lower() if status_col else "recalled",
                        "source": str(pdf_path.name),
                        "source_month": today,
                        "simulated": False,
                    })

    return rows


def load_alerts():
    if not ALERTS_JSON.exists():
        return []
    return json.load(open(ALERTS_JSON, encoding="utf-8"))


def save_alerts(alerts, snapshot_date: str):
    # Add snapshot_date as the first item (sentinel) or update it
    json.dump(alerts, open(ALERTS_JSON, "w", encoding="utf-8"), indent=2)
    # Also update the snapshot date in the JSON (handled by /alerts route reading it)
    # Write a separate date file
    (ROOT / "data" / "alerts_snapshot_date.txt").write_text(snapshot_date)
    print(f"Snapshot date set to: {snapshot_date}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", help="Path to the CDSCO alert PDF")
    ap.add_argument("--confirm", action="store_true", help="Merge into alerts.json after review")
    args = ap.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"ERROR: PDF not found: {pdf_path}")
        sys.exit(1)

    print(f"Parsing {pdf_path.name}…")
    new_rows = parse_pdf(pdf_path)
    print(f"Extracted {len(new_rows)} rows.")

    # Write review CSV
    with open(REVIEW_CSV, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["brand","generic","batch_raw","batch_norm","manufacturer","reason","status","source","source_month","simulated"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(new_rows)
    print(f"Review file: {REVIEW_CSV}")
    print("Check the CSV for errors before running with --confirm.")

    if not args.confirm:
        print("\nDry-run complete. Re-run with --confirm to merge into alerts.json.")
        return

    # Merge — skip rows with duplicate batch_norm+brand
    existing = load_alerts()
    existing_keys = {(a.get("brand","").lower(), a.get("batch_norm","")) for a in existing}
    added = 0
    for r in new_rows:
        key = (r["brand"].lower(), r["batch_norm"])
        if key not in existing_keys:
            existing.append(r)
            existing_keys.add(key)
            added += 1

    snapshot = date.today().strftime("%Y-%m-%d")
    save_alerts(existing, snapshot)
    print(f"Added {added} new alerts. Total: {len(existing)}. Snapshot: {snapshot}")


if __name__ == "__main__":
    main()

"""
scripts/gen_synthetic_eval.py — Task 1: Generate synthetic medicine pack images
for the eval dataset so evaluate.py / make_eval_set.py can run without real photos.

Usage:
  python scripts/gen_synthetic_eval.py [--count N]

Creates N synthetic medicine pack images (default 20) in backend/eval_data/,
then calls make_eval_set.py to produce tampered variants + labels.csv.

Each synthetic image contains realistic-looking:
  - Brand name, generic name, strength
  - Batch No, Mfg date, Expiry date
  - Manufacturer name
  - MRP and qty
  - A coloured border + header bar to simulate real packaging
"""
from __future__ import annotations
import argparse, csv, json, random, subprocess, sys
from pathlib import Path
from datetime import date, timedelta

ROOT     = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
EVAL_DIR = ROOT / "eval_data"
EVAL_DIR.mkdir(exist_ok=True)

# ── Medicine library for synthetic generation ─────────────────────────────

MEDICINES = [
    {"name": "Dolo 650",     "generic": "Paracetamol 650mg",     "mfg": "Micro Labs Ltd."},
    {"name": "Calpol 500",   "generic": "Paracetamol 500mg",     "mfg": "GSK Pharma"},
    {"name": "Augmentin 625","generic": "Amoxicillin + Clav. 625mg","mfg": "GSK Pharma"},
    {"name": "Azithral 500", "generic": "Azithromycin 500mg",    "mfg": "Alembic Pharma"},
    {"name": "Combiflam",    "generic": "Ibuprofen + Para. 400mg","mfg": "Sanofi India"},
    {"name": "Pan 40",       "generic": "Pantoprazole 40mg",     "mfg": "Alkem Labs"},
    {"name": "Shelcal 500",  "generic": "Calcium + Vit D3 500mg","mfg": "Torrent Pharma"},
    {"name": "Metformin 500","generic": "Metformin HCL 500mg",   "mfg": "Sun Pharma"},
    {"name": "Amlokem 5",    "generic": "Amlodipine 5mg",        "mfg": "Cipla Ltd."},
    {"name": "Cetzine",      "generic": "Cetirizine 10mg",       "mfg": "Dr. Reddy's"},
]

PALETTE = [
    ((73, 62, 229),  (225, 230, 255)),  # Purple / light purple
    ((0, 105, 92),   (204, 241, 236)),  # Teal / mint
    ((183, 28, 28),  (255, 224, 224)),  # Red / light red
    ((2, 119, 189),  (204, 235, 255)),  # Blue / light blue
    ((106, 27, 154), (237, 214, 255)),  # Violet / light violet
    ((27, 94, 32),   (200, 240, 200)),  # Green / light green
    ((230, 81, 0),   (255, 236, 204)),  # Orange / light orange
    ((74, 20, 140),  (228, 208, 255)),  # Deep purple / lavender
    ((0, 77, 64),    (200, 230, 222)),  # Dark teal / soft mint
    ((21, 101, 192), (210, 230, 255)),  # Royal blue / pale blue
]

def random_batch() -> str:
    prefix = random.choice(["DL", "MH", "KA", "TN", "GJ", "UP"])
    return f"{prefix}-{random.randint(1000, 9999)}"

def random_dates() -> tuple[str, str]:
    mfg_days_ago = random.randint(180, 730)
    mfg = date.today() - timedelta(days=mfg_days_ago)
    shelf = random.randint(24, 36)
    exp = date(mfg.year + shelf // 12, (mfg.month + shelf % 12 - 1) % 12 + 1, 1)
    return mfg.strftime("%m/%Y"), exp.strftime("%m/%Y")


def make_synthetic_pack(med: dict, seed: int = 0) -> "PIL.Image.Image":
    """Render a synthetic medicine pack as a PIL Image."""
    from PIL import Image, ImageDraw, ImageFont

    random.seed(seed)
    palette = PALETTE[seed % len(PALETTE)]
    header_col, bg_col = palette

    W, H = 640, 420
    img = Image.new("RGB", (W, H), color=bg_col)
    draw = ImageDraw.Draw(img)

    # Header bar
    draw.rectangle([0, 0, W, 90], fill=header_col)

    # Border
    draw.rectangle([4, 4, W - 4, H - 4], outline=header_col, width=3)

    # Load fonts (fall back to default if Arial not available)
    try:
        f_title  = ImageFont.truetype("arial.ttf", 30)
        f_sub    = ImageFont.truetype("arial.ttf", 17)
        f_small  = ImageFont.truetype("arial.ttf", 14)
        f_label  = ImageFont.truetype("arialbd.ttf", 14)
    except Exception:
        f_title  = ImageFont.load_default()
        f_sub    = f_title
        f_small  = f_title
        f_label  = f_title

    # Brand name in header
    draw.text((20, 18), med["name"], fill=(255, 255, 255), font=f_title)

    # Generic + manufacturer in header
    draw.text((20, 58), med["generic"], fill=(220, 220, 255), font=f_small)

    # --- Body fields ---
    batch       = random_batch()
    mfg_str, exp_str = random_dates()
    mrp         = round(random.uniform(25, 350), 2)
    qty         = random.choice([10, 15, 20, 30])

    y = 108
    def line(label: str, val: str):
        nonlocal y
        draw.text((20, y), f"{label}:", fill=header_col, font=f_label)
        draw.text((170, y), val, fill=(30, 30, 30), font=f_sub)
        y += 30

    line("Manufacturer", med["mfg"])
    line("Composition",  med["generic"])
    line("Batch No",     batch)
    line("Mfg. Date",    mfg_str)
    line("Exp. Date",    exp_str)
    line("MRP",          f"Rs. {mrp:.2f} (Incl. of all taxes)")
    line("Net Contents", f"{qty} Tablets")
    y += 6
    draw.line([20, y, W - 20, y], fill=header_col, width=1)
    y += 10
    draw.text((20, y), "Store below 25°C. Keep out of reach of children.", fill=(100, 100, 100), font=f_small)
    y += 20
    draw.text((20, y), "For a drug complaint contact: complaint@medsure.example.in", fill=(100, 100, 100), font=f_small)

    # Decorative barcode placeholder (just lines)
    bx, by = W - 130, H - 95
    draw.rectangle([bx, by, bx + 110, by + 70], fill=(255, 255, 255), outline=(180, 180, 180))
    for xi in range(bx + 5, bx + 105, 4):
        h_bar = random.randint(30, 60)
        draw.rectangle([xi, by + 5, xi + 2, by + 5 + h_bar], fill=(30, 30, 30))
    draw.text((bx + 5, by + 55), batch[-4:], fill=(30, 30, 30), font=f_small)

    return img, batch, exp_str, mfg_str


def main():
    ap = argparse.ArgumentParser(description="Generate synthetic eval images")
    ap.add_argument("--count", type=int, default=20, help="Number of unique source images (default 20)")
    args = ap.parse_args()

    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        print("ERROR: Pillow not installed. Run: pip install Pillow")
        sys.exit(1)

    print(f"Generating {args.count} synthetic medicine pack images in {EVAL_DIR}/")

    meta_rows: list[dict] = []

    for i in range(args.count):
        med    = MEDICINES[i % len(MEDICINES)]
        img, batch, exp_str, mfg_str = make_synthetic_pack(med, seed=i + 1)
        fname  = f"synthetic_{i + 1:03d}_{med['name'].replace(' ', '_')}.jpg"
        out    = EVAL_DIR / fname
        if not out.exists():
            img.save(str(out), quality=92)
            print(f"  Created {fname}")
        else:
            print(f"  Exists  {fname} (skipped)")
        meta_rows.append({
            "filename":  fname,
            "true_class": "untampered",
            "name":      med["name"],
            "batch":     batch,
            "expiry":    exp_str,
        })

    # Write a minimal ground_truth.csv for ocr_test.py
    gt_csv = EVAL_DIR / "ground_truth.csv"
    with open(gt_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["filename", "name", "batch", "expiry"])
        w.writeheader()
        for r in meta_rows:
            w.writerow({"filename": r["filename"], "name": r["name"], "batch": r["batch"], "expiry": r["expiry"]})
    print(f"\nGround truth CSV → {gt_csv}")

    # Write labels.csv stub (make_eval_set will expand it with tampered variants)
    labels_csv = EVAL_DIR / "labels.csv"
    if not labels_csv.exists():
        with open(labels_csv, "w", newline="", encoding="utf-8") as f:
            w2 = csv.DictWriter(f, fieldnames=["filename", "true_class"])
            w2.writeheader()
            for r in meta_rows:
                w2.writerow({"filename": r["filename"], "true_class": "untampered"})
        print(f"Labels stub → {labels_csv}")

    print(f"\nDone. Now run:")
    print(f"  cd {ROOT}")
    print(f"  python scripts/make_eval_set.py     # generates tampered variants")
    print(f"  python scripts/evaluate.py           # full pipeline benchmark")
    print(f"  python scripts/ocr_test.py --photos eval_data/ --gt eval_data/ground_truth.csv")


if __name__ == "__main__":
    main()

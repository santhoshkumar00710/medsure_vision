"""
scripts/make_eval_set.py — Task 5b: auto-creates tampered variants from eval_data/.

Usage: python scripts/make_eval_set.py

For each untampered image in eval_data/ it creates 4 tampered variants:
  expiry_edit, batch_edit, logo_shift, blur

Updates eval_data/labels.csv automatically.
"""
import csv, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
EVAL_DIR = ROOT / "eval_data"
EVAL_DIR.mkdir(exist_ok=True)
LABELS_CSV = EVAL_DIR / "labels.csv"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
VARIANTS = ["expiry_edit", "batch_edit", "logo_shift", "blur"]


def make_expiry_edit(img):
    from PIL import ImageDraw, ImageFont
    img = img.copy()
    draw = ImageDraw.Draw(img)
    w, h = img.size
    draw.rectangle([0, h-60, w//2, h], fill=(240, 240, 240))
    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except Exception:
        font = ImageFont.load_default()
    draw.text((5, h-50), "Exp: 03/2099", fill=(0, 0, 0), font=font)
    return img


def make_batch_edit(img):
    from PIL import ImageDraw, ImageFont
    img = img.copy()
    draw = ImageDraw.Draw(img)
    w, h = img.size
    draw.rectangle([0, h//3, w//2, h//3+40], fill=(240, 240, 240))
    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except Exception:
        font = ImageFont.load_default()
    draw.text((5, h//3+5), "Batch No: XXXFAKE", fill=(0, 0, 0), font=font)
    return img


def make_logo_shift(img):
    import numpy as np, colorsys
    from PIL import Image
    img = img.copy().convert("RGB")
    arr = np.array(img, dtype=np.float32)
    h = min(100, arr.shape[0])
    w = min(100, arr.shape[1])
    for y in range(h):
        for x in range(w):
            r, g, b = arr[y,x,0]/255, arr[y,x,1]/255, arr[y,x,2]/255
            hh, s, v = colorsys.rgb_to_hsv(r, g, b)
            hh = (hh + 0.4) % 1.0
            nr, ng, nb = colorsys.hsv_to_rgb(hh, s, v)
            arr[y,x,0] = nr*255; arr[y,x,1] = ng*255; arr[y,x,2] = nb*255
    return Image.fromarray(arr.astype("uint8"))


def make_blur(img):
    from PIL import ImageFilter
    return img.filter(ImageFilter.GaussianBlur(radius=5))


MAKERS = {
    "expiry_edit": make_expiry_edit,
    "batch_edit":  make_batch_edit,
    "logo_shift":  make_logo_shift,
    "blur":        make_blur,
}


def main():
    from PIL import Image

    # Load existing labels
    existing = {}
    if LABELS_CSV.exists():
        for row in csv.DictReader(open(LABELS_CSV, encoding="utf-8")):
            existing[row["filename"]] = row["true_class"]

    sources = [f for f in EVAL_DIR.iterdir()
               if f.suffix.lower() in IMAGE_EXTS
               and not any(v in f.stem for v in VARIANTS)
               and "tampered" not in f.stem]

    if not sources:
        print(f"No untampered images found in {EVAL_DIR}/")
        print("Add medicine pack photos there, then re-run.")
        return

    new_rows = []
    for src in sources:
        existing.setdefault(src.name, "untampered")
        try:
            base = Image.open(src).convert("RGB")
        except Exception as e:
            print(f"  SKIP {src.name}: {e}")
            continue
        for variant in VARIANTS:
            out_name = f"{src.stem}_{variant}{src.suffix}"
            out_path = EVAL_DIR / out_name
            if out_path.exists():
                existing.setdefault(out_name, "tampered")
                continue
            try:
                tampered = MAKERS[variant](base)
                tampered.save(str(out_path))
                existing[out_name] = "tampered"
                print(f"  Created {out_name}")
            except Exception as e:
                print(f"  ERROR {out_name}: {e}")

    # Write labels.csv
    with open(LABELS_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["filename", "true_class"])
        w.writeheader()
        for fname, tc in sorted(existing.items()):
            w.writerow({"filename": fname, "true_class": tc})

    print(f"\nLabels written to {LABELS_CSV}")
    print(f"Total: {len(existing)} images ({sum(1 for v in existing.values() if v=='untampered')} untampered, "
          f"{sum(1 for v in existing.values() if v=='tampered')} tampered)")


if __name__ == "__main__":
    main()

"""
scripts/make_demo_cases.py — Task 3: generates demo case images + QR codes.
Run: python scripts/make_demo_cases.py

Uses a real reference photo if available, else synthesises a placeholder pack.
Saves images + metadata to data/demo_cases/<case_id>/.
"""
import json, sys, random, textwrap
from pathlib import Path
import numpy as np

ROOT      = Path(__file__).resolve().parent.parent
DATA      = ROOT / "data"
DEMO_DIR  = DATA / "demo_cases"
REF_DIR   = DATA / "reference_images"
MED_JSON  = DATA / "medicines.json"
ALT_JSON  = DATA / "alerts.json"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

DEMO_DIR.mkdir(parents=True, exist_ok=True)

# ── helpers ────────────────────────────────────────────────────────────────

def luhn14(base13: str) -> str:
    total = sum(int(d)*3 if i%2==0 else int(d) for i, d in enumerate(reversed(base13)))
    return base13 + str((10 - total%10)%10)

def load_meds():
    return json.load(open(MED_JSON))

def load_alerts():
    try:
        return json.load(open(ALT_JSON))
    except Exception:
        return []

def save_alerts(alerts):
    json.dump(alerts, open(ALT_JSON, "w"), indent=2)

def get_reference_photo(med_id=None):
    """Return (PIL.Image, med_id) for a reference photo or a generated placeholder."""
    from PIL import Image
    ids_with_photos = []
    for folder in REF_DIR.iterdir():
        if not folder.is_dir():
            continue
        imgs = [f for f in folder.iterdir() if f.suffix.lower() in IMAGE_EXTS]
        if imgs:
            ids_with_photos.append((folder.name, imgs[0]))
    if ids_with_photos:
        chosen_fp = None
        chosen_fid = None
        if med_id:
            for fid, fp in ids_with_photos:
                if fid == med_id:
                    chosen_fid, chosen_fp = fid, fp
                    break
        if not chosen_fp:
            chosen_fid, chosen_fp = ids_with_photos[0]
        img = Image.open(chosen_fp).convert("RGB")
        w, h = img.size
        if min(w, h) < 480:
            scale = 480.0 / min(w, h)
            img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
        return img, chosen_fid
    # Synthesise placeholder
    return _make_placeholder(), "dolo_650"

def _make_placeholder():
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (600, 400), color=(235, 240, 250))
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, 580, 380], outline=(73, 62, 229), width=4)
    draw.rectangle([20, 20, 580, 80], fill=(73, 62, 229))
    try:
        font_big = ImageFont.truetype("arial.ttf", 28)
        font_sm  = ImageFont.truetype("arial.ttf", 16)
    except Exception:
        font_big = ImageFont.load_default()
        font_sm  = font_big
    draw.text((30, 35), "Dolo 650", fill="white", font=font_big)
    draw.text((30, 100), "Paracetamol 650 mg | Micro Labs Ltd.", fill=(30,30,30), font=font_sm)
    draw.text((30, 130), "Batch No: DEMO001", fill=(30,30,30), font=font_sm)
    draw.text((30, 155), "Mfg: 06/2024   Exp: 11/2026", fill=(30,30,30), font=font_sm)
    draw.text((30, 185), "MRP Rs. 30.00  Net Qty: 15 Tablets", fill=(30,30,30), font=font_sm)
    return img

def add_watermark(img, text="TEST SAMPLE"):
    from PIL import Image, ImageDraw, ImageFont
    img = img.copy()
    draw = ImageDraw.Draw(img, "RGBA")
    try:
        font = ImageFont.truetype("arial.ttf", 36)
    except Exception:
        font = ImageFont.load_default()
    w, h = img.size
    draw.text((w//2 - 80, h//2 - 20), text, fill=(255, 0, 0, 140), font=font)
    return img

def make_qr(content: str, out_path: Path):
    try:
        import qrcode
        qr = qrcode.make(content)
        qr.save(str(out_path))
        return True
    except ImportError:
        try:
            import segno
            qr = segno.make(content)
            qr.save(str(out_path), scale=5)
            return True
        except ImportError:
            # Fallback: write a plain text file with the payload
            out_path.with_suffix(".txt").write_text(content)
            return False

def write_meta(case_dir: Path, data: dict):
    json.dump(data, open(case_dir / "meta.json", "w"), indent=2)

# ── Case generators ────────────────────────────────────────────────────────

def case_genuine():
    """Valid pack image + matching GS1 QR code."""
    case_dir = DEMO_DIR / "genuine"
    case_dir.mkdir(exist_ok=True)
    img, mid = get_reference_photo()
    meds = {m["id"]: m for m in load_meds()}
    med  = meds.get(mid, list(meds.values())[0])
    gtin = med["gtin"]
    batch = "DEMO001"
    expiry = "261100"  # GS1 YYMMDD (11/2026)
    serial = "SN000001"
    gs1 = f"]d201{gtin}10{batch}\x1d17{expiry}21{serial}"
    img.save(str(case_dir / "pack.jpg"))
    make_qr(gs1, case_dir / "code.png")
    write_meta(case_dir, {"label_hint": "low_risk", "gtin": gtin, "batch": batch, "expiry": "11/2026"})
    print("  genuine        OK")

def case_expiry_tampered():
    """Pack image with expiry painted over and changed."""
    from PIL import ImageDraw, ImageFont
    case_dir = DEMO_DIR / "expiry_tampered"
    case_dir.mkdir(exist_ok=True)
    img, mid = get_reference_photo()
    img = img.copy()
    draw = ImageDraw.Draw(img)
    w, h = img.size
    # Paint a block over bottom-left area (typical expiry location)
    draw.rectangle([0, h-80, 300, h], fill=(235, 240, 250))
    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except Exception:
        font = ImageFont.load_default()
    draw.text((10, h-65), "Exp: 03/2099", fill=(0, 0, 0), font=font)
    img = add_watermark(img)
    img.save(str(case_dir / "pack.jpg"))
    meds = load_meds()
    gtin = meds[0]["gtin"]
    batch = "DEMO001"
    expiry = "261100"  # GS1 YYMMDD: Nov 2026, mismatches pack Exp 03/2099
    gs1 = f"]d201{gtin}10{batch}\x1d17{expiry}21SN000001"
    make_qr(gs1, case_dir / "code.png")
    write_meta(case_dir, {"label_hint": "high_suspicion", "tamper": "expiry_overwritten", "gtin": gtin})
    print("  expiry_tampered OK")

def case_logo_shifted():
    """Pack image with hue-shifted and cropped region to simulate logo tampering."""
    from PIL import ImageDraw
    import colorsys
    case_dir = DEMO_DIR / "logo_shifted"
    case_dir.mkdir(exist_ok=True)
    img, mid = get_reference_photo()
    img = img.copy().convert("RGB")
    arr = np.array(img, dtype=np.float32)
    # Shift hue of top-left 250x250 region
    region = arr[:250, :250, :]
    r, g, b = region[:,:,0]/255, region[:,:,1]/255, region[:,:,2]/255
    for y in range(region.shape[0]):
        for x in range(region.shape[1]):
            h, s, v = colorsys.rgb_to_hsv(r[y,x], g[y,x], b[y,x])
            h = (h + 0.35) % 1.0
            nr, ng, nb = colorsys.hsv_to_rgb(h, s, v)
            arr[y, x, 0] = nr*255
            arr[y, x, 1] = ng*255
            arr[y, x, 2] = nb*255
    from PIL import Image
    img = Image.fromarray(arr.astype(np.uint8))
    # Shift (translate) the region slightly
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 40, 250], fill=(235, 240, 250))
    img = add_watermark(img)
    img.save(str(case_dir / "pack.jpg"))
    write_meta(case_dir, {"label_hint": "needs_verification", "tamper": "logo_hue_shifted"})
    print("  logo_shifted    OK")

def case_clone_code():
    """QR whose serial matches the seeded Chennai-to-Delhi clone scenario."""
    case_dir = DEMO_DIR / "clone_code"
    case_dir.mkdir(exist_ok=True)
    img, mid = get_reference_photo()
    # Serial that was seeded in the DB: see scripts/seed_db.py
    clone_serial = "SERIAL_MN_002"
    gtin = "08901234000034"
    batch = "MN-0994"
    expiry = "261200"
    gs1 = f"]d201{gtin}10{batch}\x1d17{expiry}21{clone_serial}"
    img.save(str(case_dir / "pack.jpg"))
    make_qr(gs1, case_dir / "code.png")
    write_meta(case_dir, {"label_hint": "high_suspicion", "note": "serial matches clone scan scenario", "serial": clone_serial})
    print("  clone_code      OK")

def case_alert_match():
    """Image+code whose name+batch match a CDSCO alert entry."""
    case_dir = DEMO_DIR / "alert_match"
    case_dir.mkdir(exist_ok=True)
    img, mid = get_reference_photo("dolo_650")
    # Matches CDSCO-2024-07-012 for Dolo 650 DL-3341
    alert_batch = "DL-3341"
    alert_brand = "Dolo 650"
    meds = load_meds()
    gtin = meds[0]["gtin"]
    expiry = "250600"
    gs1 = f"]d201{gtin}10{alert_batch}\x1d17{expiry}"
    img.save(str(case_dir / "pack.jpg"))
    make_qr(gs1, case_dir / "code.png")
    write_meta(case_dir, {"label_hint": "high_suspicion", "alert_batch": alert_batch, "alert_brand": alert_brand})
    print("  alert_match     OK")

def case_blurry():
    """Gaussian-blurred copy of reference photo."""
    from PIL import ImageFilter
    case_dir = DEMO_DIR / "blurry"
    case_dir.mkdir(exist_ok=True)
    img, mid = get_reference_photo()
    watermarked = add_watermark(img)
    blurred = watermarked.filter(ImageFilter.GaussianBlur(radius=15))
    blurred.save(str(case_dir / "pack.jpg"))
    write_meta(case_dir, {"label_hint": "insufficient_quality", "note": "blurred to trigger quality gate"})
    print("  blurry          OK")

# ── Main ───────────────────────────────────────────────────────────────────

def main():
    print("Generating demo cases...")
    case_genuine()
    case_expiry_tampered()
    case_logo_shifted()
    case_clone_code()
    case_alert_match()
    case_blurry()
    print("\nAll demo cases saved to data/demo_cases/")
    print("Run: python -m uvicorn app.main:app --port 8000")
    print("Then: curl http://localhost:8000/demo/genuine")

if __name__ == "__main__":
    main()

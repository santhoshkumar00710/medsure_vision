"""
scripts/check_reference_images.py
Audits data/reference_images/ against data/medicines.json.
For each medicine: count images, flag < 3 images, warn blurry images.
Also warns about folders with no matching id and vice versa.
"""
import sys, json, cv2
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF  = ROOT / "data" / "reference_images"
MED  = ROOT / "data" / "medicines.json"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
BLUR_THRESH = 80.0

def laplacian_var(path):
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return None
    return float(cv2.Laplacian(img, cv2.CV_64F).var())

def main():
    meds   = json.load(open(MED))
    med_ids = {m["id"] for m in meds}
    folders = {f.name for f in REF.iterdir() if f.is_dir()}

    print("=" * 60)
    print("Reference image audit")
    print("=" * 60)

    issues = 0

    # --- Check every medicine id has a folder and enough images ---
    for mid in sorted(med_ids):
        folder = REF / mid
        if not folder.exists():
            print(f"  MISSING folder  : {mid}")
            issues += 1
            continue
        images = [f for f in folder.iterdir() if f.suffix.lower() in IMAGE_EXTS]
        n = len(images)
        status = "OK   " if n >= 3 else ("WARN " if n > 0 else "EMPTY")
        print(f"  {status} {mid:25s} {n} image(s)")
        if n < 3:
            issues += 1
        for img_path in images:
            var = laplacian_var(img_path)
            if var is not None and var < BLUR_THRESH:
                print(f"    BLURRY: {img_path.name}  (var={var:.1f} < {BLUR_THRESH})")
                issues += 1

    # --- Folders with no matching medicine id ---
    orphans = folders - med_ids
    for o in sorted(orphans):
        print(f"  ORPHAN folder   : {o}  (no matching id in medicines.json)")
        issues += 1

    print()
    print(f"Total issues: {issues}")
    return issues

if __name__ == "__main__":
    sys.exit(0 if main() == 0 else 1)

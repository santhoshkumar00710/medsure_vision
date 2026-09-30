"""
scripts/build_reference_embeddings.py
Builds MobileNetV2 L2-normalised embeddings for every reference image.
Skips empty folders gracefully. Prints a per-medicine summary.
Saves to data/embeddings.npz (keys = medicine ids, values = (N, 1280) arrays).
"""
import sys, json, warnings
from pathlib import Path
import numpy as np

warnings.filterwarnings("ignore")

ROOT       = Path(__file__).resolve().parent.parent
REF        = ROOT / "data" / "reference_images"
MED_JSON   = ROOT / "data" / "medicines.json"
OUT        = ROOT / "data" / "embeddings.npz"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

def load_model():
    import torch
    import torchvision.models as models
    import torchvision.transforms as T
    weights = models.MobileNet_V2_Weights.IMAGENET1K_V1
    model = models.mobilenet_v2(weights=weights)
    model.classifier = torch.nn.Identity()
    model.eval()
    tfm = T.Compose([
        T.Resize(256), T.CenterCrop(224), T.ToTensor(),
        T.Normalize([0.485,0.456,0.406],[0.229,0.224,0.225]),
    ])
    return model, tfm

def embed_image(path, model, tfm, device):
    import torch
    from PIL import Image
    try:
        img = Image.open(path).convert("RGB")
        x = tfm(img).unsqueeze(0).to(device)
        with torch.no_grad():
            feat = model.features(x)
            feat = torch.nn.functional.adaptive_avg_pool2d(feat, 1)
            vec  = feat.view(1, -1).cpu().numpy()[0]
        norm = np.linalg.norm(vec)
        return vec / (norm + 1e-8)
    except Exception as e:
        print(f"    ERROR embedding {path.name}: {e}")
        return None

def main():
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")

    meds   = json.load(open(MED_JSON))
    med_ids = [m["id"] for m in meds]

    model, tfm = load_model()
    model.to(device)

    results  = {}
    covered  = 0
    skipped  = 0
    total_imgs = 0

    print("\nPer-medicine embedding summary:")
    print("-" * 50)

    for mid in med_ids:
        folder = REF / mid
        if not folder.exists():
            print(f"  SKIP  {mid:25s}  (folder missing)")
            skipped += 1
            continue
        images = [f for f in folder.iterdir() if f.suffix.lower() in IMAGE_EXTS]
        if not images:
            print(f"  EMPTY {mid:25s}  (no images)")
            skipped += 1
            continue
        vecs = []
        for p in images:
            v = embed_image(p, model, tfm, device)
            if v is not None:
                vecs.append(v)
        if vecs:
            results[mid] = np.stack(vecs, axis=0)
            covered += 1
            total_imgs += len(vecs)
            print(f"  OK    {mid:25s}  {len(vecs)} image(s) embedded")
        else:
            print(f"  FAIL  {mid:25s}  (all embeds failed)")
            skipped += 1

    if results:
        np.savez(str(OUT), **results)
        print(f"\nSaved {OUT.name}: {covered} medicines, {total_imgs} images total.")
    else:
        print("\nNo embeddings produced — add photos to data/reference_images/.")

    print(f"Covered: {covered}  Skipped/empty: {skipped}")
    return 0

if __name__ == "__main__":
    sys.exit(main())

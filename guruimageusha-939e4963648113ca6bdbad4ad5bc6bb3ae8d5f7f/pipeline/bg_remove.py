"""
PNG Library - Background Remover V2 (Clean)
═══════════════════════════════════════════════════════
Model   : BRIA-RMBG-2.0
Rule    : MODEL ONLY — zero post-processing
═══════════════════════════════════════════════════════

V2 CHANGES:
  REMOVED: _refine_edges()      — was blurring alpha, softening edges
  REMOVED: _gentle_edge_clean() — was modifying alpha pixels
  REMOVED: remove_background_enhanced() — no more extra pipeline

  NOW: BRIA model output → save directly. That's it.
  The model is good enough. Extra processing was making it worse.
"""

import torch
import numpy as np
from PIL import Image
from pathlib import Path
import gc


# ─────────────────────────────────────────────────────────────
# BRIA-RMBG-2.0 — Model Only
# ─────────────────────────────────────────────────────────────
class BackgroundRemover:

    def __init__(self):
        self.model     = None
        self.transform = None
        self.device    = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"BG Remover device: {self.device}")

    def load_model(self):
        from transformers import AutoModelForImageSegmentation
        from torchvision import transforms

        print("Loading BRIA-RMBG-2.0 ...")
        self.model = AutoModelForImageSegmentation.from_pretrained(
            "briaai/RMBG-2.0",
            trust_remote_code=True
        )
        self.model.to(self.device).eval()

        self.transform = transforms.Compose([
            transforms.Resize((1024, 1024)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406],
                                  [0.229, 0.224, 0.225]),
        ])
        print("BRIA-RMBG-2.0 loaded!\n")
        return self

    def remove_background(self, img: Image.Image) -> Image.Image:
        """
        BRIA model inference → RGBA output. Nothing else.
        No edge smoothing. No alpha cleanup. No post-processing.
        """
        original_size = img.size
        img_rgb = img.convert("RGB")

        inp = self.transform(img_rgb).unsqueeze(0).to(self.device)

        with torch.no_grad():
            result = self.model(inp)

        mask = result[0][0] if isinstance(result, (list, tuple)) else result[0]
        if mask.dim() > 2:
            mask = mask.squeeze()

        mask = torch.sigmoid(mask).cpu().numpy()
        mask = (mask * 255).astype(np.uint8)

        mask_pil = Image.fromarray(mask, mode="L")
        mask_pil = mask_pil.resize(original_size, Image.LANCZOS)

        img_rgba = img_rgb.convert("RGBA")
        img_rgba.putalpha(mask_pil)
        return img_rgba

    def process_image_file(self, input_path: str, output_path: str) -> str:
        img = Image.open(input_path).convert("RGB")
        result = self.remove_background(img)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        result.save(output_path, "PNG")
        return output_path

    def process_folder(self, input_folder: str, output_folder: str, skip_existing: bool = True) -> dict:
        input_path  = Path(input_folder)
        output_path = Path(output_folder)

        image_files = (
            list(input_path.rglob("*.png"))
            + list(input_path.rglob("*.jpg"))
            + list(input_path.rglob("*.jpeg"))
        )
        print(f"Found {len(image_files)} images")

        stats = {"processed": 0, "skipped": 0, "failed": 0}

        for img_file in image_files:
            rel      = img_file.relative_to(input_path)
            out_file = output_path / rel.with_suffix(".png")

            if skip_existing and out_file.exists():
                stats["skipped"] += 1
                continue

            out_file.parent.mkdir(parents=True, exist_ok=True)
            category = str(rel.parent).lower()

            try:
                img = Image.open(str(img_file)).convert("RGB")

                # Smoke/fire/effects → luminosity method
                # Everything else → BRIA model direct output
                if is_smoke_category(category):
                    result = SmokeEffectRemover.remove_background(img)
                else:
                    result = self.remove_background(img)

                result.save(str(out_file), "PNG")
                stats["processed"] += 1

                if stats["processed"] % 50 == 0:
                    print(f"  Done: {stats['processed']} | Skip: {stats['skipped']} | Fail: {stats['failed']}")
                    gc.collect()
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()

            except Exception as e:
                print(f"  FAIL: {img_file.name} — {e}")
                stats["failed"] += 1

        print(f"\nBG removal complete!")
        print(f"  Processed : {stats['processed']}")
        print(f"  Skipped   : {stats['skipped']}")
        print(f"  Failed    : {stats['failed']}")
        return stats

    def unload(self):
        del self.model
        self.model = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        print("BG remover unloaded")


# ─────────────────────────────────────────────────────────────
# SMOKE / EFFECTS — luminosity-based (no model needed)
# ─────────────────────────────────────────────────────────────
SMOKE_KEYWORDS = {"effects/smoke", "effects/colored_smoke", "effects/fire",
                  "effects/sparkle", "smoke_effects", "fire_effects", "light_effects"}


def is_smoke_category(category: str) -> bool:
    return any(kw in category for kw in SMOKE_KEYWORDS)


class SmokeEffectRemover:

    @staticmethod
    def remove_background(img: Image.Image) -> Image.Image:
        """Luminosity-based: lighter pixel = more transparent."""
        img_rgba = img.convert("RGBA")
        data = np.array(img_rgba, dtype=np.float32)

        r, g, b = data[:, :, 0], data[:, :, 1], data[:, :, 2]
        lum = 0.299 * r + 0.587 * g + 0.114 * b

        new_alpha = np.clip(255 - lum, 0, 255).astype(np.uint8)
        new_alpha[new_alpha < 12] = 0

        result = np.array(img_rgba, dtype=np.uint8)
        result[:, :, 3] = new_alpha
        return Image.fromarray(result, "RGBA")


# ─────────────────────────────────────────────────────────────
# STANDALONE
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    remover = BackgroundRemover()
    remover.load_model()

    if len(sys.argv) >= 3:
        remover.process_folder(sys.argv[1], sys.argv[2])
    else:
        remover.process_folder(
            "/kaggle/working/generated_images",
            "/kaggle/working/transparent_pngs",
        )

    remover.unload()

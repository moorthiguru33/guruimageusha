"""
✂️ PNG Library - Background Remover
═══════════════════════════════════════════════════════
Model   : BRIA-RMBG-2.0  (best 2025 segmentation model)
Handles : food, smoke, flowers, hair, fur, fine edges
═══════════════════════════════════════════════════════

FIX LOG (v2):
  • REMOVED: _clean_background() — was deleting white/light-colored
    subjects (white flowers, white objects, etc.) because it treated
    any opaque white pixel as background. BRIA already handles this.
  • FIXED:  _refine_edges() — now uses a gentler SMOOTH (not SMOOTH_MORE)
    to avoid over-blurring fine edge detail.
  • ADDED:  _gentle_edge_clean() — only removes pixels where alpha < 15
    (near-invisible artifacts), never touches subject pixels.
  • IMPROVED: smoke routing logic made more explicit.
"""

import torch
import numpy as np
from PIL import Image, ImageFilter
from pathlib import Path
import os
import gc
from typing import Union


# ─────────────────────────────────────────────────────────────
# BRIA-RMBG-2.0
# ─────────────────────────────────────────────────────────────
class BackgroundRemover:
    """
    BRIA-RMBG-2.0 — state-of-the-art background removal.
    Produces clean transparent PNGs for any subject type.
    """

    def __init__(self):
        self.model     = None
        self.transform = None
        self.device    = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"🔧 Background Remover device: {self.device}")

    def load_model(self):
        from transformers import AutoModelForImageSegmentation
        from torchvision import transforms

        print("📦 Loading BRIA-RMBG-2.0 ...")
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
        print("✅ BRIA-RMBG-2.0 loaded!\n")
        return self

    # ── Core removal ──────────────────────────────────────────
    def remove_background(self, img: Image.Image) -> Image.Image:
        """
        Core BRIA inference.
        Returns RGBA with alpha = foreground mask.
        """
        original_size = img.size
        img_rgb       = img.convert("RGB")

        inp = self.transform(img_rgb).unsqueeze(0).to(self.device)

        with torch.no_grad():
            result = self.model(inp)

        # Handle both list/tuple and direct tensor outputs
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

    # ── Enhanced removal (with gentle post-processing) ────────
    def remove_background_enhanced(self, img: Image.Image) -> Image.Image:
        """
        Full pipeline:
          1. BRIA core removal
          2. Gentle edge smoothing
          3. Artifact-only cleanup  ← FIXED (was destroying white subjects)
        """
        result = self.remove_background(img)
        result = self._refine_edges(result)
        result = self._gentle_edge_clean(result)   # ✅ SAFE replacement
        return result

    # ── Edge refinement ───────────────────────────────────────
    def _refine_edges(self, img_rgba: Image.Image) -> Image.Image:
        """
        Slight alpha smoothing to reduce jagged edges.
        Uses SMOOTH (not SMOOTH_MORE) to preserve fine details
        like hair, fur, flower petals.
        """
        r, g, b, a = img_rgba.split()
        a_smooth   = a.filter(ImageFilter.SMOOTH)   # ✅ gentler than SMOOTH_MORE
        return Image.merge("RGBA", (r, g, b, a_smooth))

    # ── Artifact-only cleanup ─────────────────────────────────
    def _gentle_edge_clean(self, img_rgba: Image.Image) -> Image.Image:
        """
        ✅ SAFE: Only removes near-invisible artifact pixels (alpha < 15).
        Does NOT touch opaque/semi-opaque pixels regardless of color.

        ❌ OLD _clean_background() removed opaque white pixels — this
           destroyed white flowers, white objects, light-colored subjects.
        """
        data = np.array(img_rgba, dtype=np.uint8)

        # Only fully erase pixels that are nearly invisible already
        # These are edge artifacts from the segmentation mask, not subject pixels
        near_invisible = data[:, :, 3] < 15
        data[near_invisible, 3] = 0

        return Image.fromarray(data, "RGBA")

    # ── Single file ───────────────────────────────────────────
    def process_image_file(self, input_path: str, output_path: str) -> str:
        img    = Image.open(input_path).convert("RGB")
        result = self.remove_background_enhanced(img)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        result.save(output_path, "PNG", optimize=True)
        return output_path

    # ── Folder batch ──────────────────────────────────────────
    def process_folder(
        self,
        input_folder:  str,
        output_folder: str,
        skip_existing: bool = True,
    ) -> dict:
        """
        Process all images in a folder (maintains subfolder structure).
        Routes smoke/effects images through SmokeEffectRemover.
        """
        input_path  = Path(input_folder)
        output_path = Path(output_folder)

        image_files = (
            list(input_path.rglob("*.png"))
            + list(input_path.rglob("*.jpg"))
            + list(input_path.rglob("*.jpeg"))
        )
        print(f"📂 Found {len(image_files)} images")

        stats = {"processed": 0, "skipped": 0, "failed": 0}

        for i, img_file in enumerate(image_files):
            rel      = img_file.relative_to(input_path)
            out_file = output_path / rel.with_suffix(".png")

            if skip_existing and out_file.exists():
                stats["skipped"] += 1
                continue

            out_file.parent.mkdir(parents=True, exist_ok=True)

            # Determine category from folder path
            category = str(rel.parent)

            try:
                img    = Image.open(str(img_file)).convert("RGB")
                result = process_with_smart_routing(img, category, self)
                result.save(str(out_file), "PNG", optimize=True)
                stats["processed"] += 1

                if stats["processed"] % 50 == 0:
                    print(f"  ✅ Processed: {stats['processed']}  "
                          f"| Skipped: {stats['skipped']}  "
                          f"| Failed: {stats['failed']}")
                    gc.collect()
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()

            except Exception as e:
                print(f"  ❌ Failed: {img_file.name} — {e}")
                stats["failed"] += 1

        print(f"\n🎉 Background removal complete!")
        print(f"  ✅ Processed : {stats['processed']}")
        print(f"  ⏭️  Skipped  : {stats['skipped']}")
        print(f"  ❌ Failed   : {stats['failed']}")
        return stats

    def unload(self):
        del self.model
        self.model = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        print("🗑️  Background remover unloaded")


# ─────────────────────────────────────────────────────────────
# SMOKE / EFFECTS — special handler
# ─────────────────────────────────────────────────────────────
class SmokeEffectRemover:
    """
    For smoke, fire, light rays on WHITE backgrounds.
    Luminosity-based: darker pixel = more opaque.
    Do NOT use this for solid objects.
    """

    @staticmethod
    def remove_white_background(img: Image.Image) -> Image.Image:
        img_rgba = img.convert("RGBA")
        data     = np.array(img_rgba, dtype=np.float32)

        r, g, b = data[:,:,0], data[:,:,1], data[:,:,2]

        # Luminosity (ITU-R BT.601)
        lum      = 0.299*r + 0.587*g + 0.114*b

        # White → transparent, dark → opaque
        new_alpha = np.clip(255 - lum, 0, 255).astype(np.uint8)

        # Hard threshold: near-white artifacts → fully transparent
        new_alpha[new_alpha < 12] = 0

        result        = np.array(img_rgba, dtype=np.uint8)
        result[:,:,3] = new_alpha
        return Image.fromarray(result, "RGBA")


# ─────────────────────────────────────────────────────────────
# SMART ROUTING
# ─────────────────────────────────────────────────────────────
SMOKE_CATEGORIES = {"effects/smoke", "smoke_effects", "fire_effects", "light_effects"}

def process_with_smart_routing(
    img:      Image.Image,
    category: str,
    remover:  BackgroundRemover,
) -> Image.Image:
    """
    Route each image to the correct removal method:
      • Smoke / fire / light effects → luminosity method
      • Everything else              → BRIA-RMBG-2.0
    """
    cat_lower = category.lower()
    if any(s in cat_lower for s in SMOKE_CATEGORIES):
        return SmokeEffectRemover.remove_white_background(img)
    return remover.remove_background_enhanced(img)


# ─────────────────────────────────────────────────────────────
# STANDALONE USAGE
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    remover = BackgroundRemover()
    remover.load_model()

    if len(sys.argv) >= 3:
        input_dir  = sys.argv[1]
        output_dir = sys.argv[2]
        remover.process_folder(input_dir, output_dir)
    else:
        remover.process_folder(
            "/kaggle/working/generated_images",
            "/kaggle/working/transparent_pngs",
        )

    remover.unload()

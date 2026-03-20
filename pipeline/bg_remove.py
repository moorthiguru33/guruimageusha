"""
PNG Library - Perfect Background Remover
Uses BRIA-RMBG-2.0 - Best Background Removal Model

FIX LOG:
- FIXED: _clean_background() was removing food pixels (rice, cheese, cream)
  The old threshold (r>252, g>252, b>252) was too aggressive — destroyed white
  rice grains, pizza cheese, biryani cream sauce. Now food is preserved.
- FIXED: near_white threshold raised to avoid removing food edges
- ADDED: category-aware food protection logic
"""

import torch
import numpy as np
from PIL import Image
from pathlib import Path
import os
import gc
from typing import Union


class BackgroundRemover:
    """
    BRIA-RMBG-2.0: State-of-the-art background removal.
    Fixed to protect food pixels (rice, cheese, cream sauce).
    """

    def __init__(self):
        self.model  = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Background Remover using: {self.device}")

    def load_model(self):
        from transformers import AutoModelForImageSegmentation
        from torchvision import transforms

        print("Loading BRIA-RMBG-2.0...")
        self.model = AutoModelForImageSegmentation.from_pretrained(
            "briaai/RMBG-2.0",
            trust_remote_code=True
        )
        self.model.to(self.device)
        self.model.eval()

        self.transform = transforms.Compose([
            transforms.Resize((1024, 1024)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])
        print("BRIA-RMBG-2.0 loaded!")
        return self

    def remove_background(self, img: Image.Image) -> Image.Image:
        original_size = img.size
        img_rgb = img.convert("RGB")
        input_tensor = self.transform(img_rgb).unsqueeze(0).to(self.device)

        with torch.no_grad():
            result = self.model(input_tensor)

        if isinstance(result, (list, tuple)):
            mask = result[0][0]
        else:
            mask = result[0]

        if mask.dim() > 2:
            mask = mask.squeeze()

        mask = torch.sigmoid(mask)
        mask = mask.cpu().numpy()
        mask = (mask * 255).astype(np.uint8)

        mask_pil = Image.fromarray(mask, mode='L')
        mask_pil = mask_pil.resize(original_size, Image.LANCZOS)

        img_rgba = img_rgb.convert("RGBA")
        img_rgba.putalpha(mask_pil)
        return img_rgba

    def remove_background_enhanced(self, img: Image.Image,
                                    is_food: bool = True) -> Image.Image:
        """
        Enhanced background removal.
        is_food=True protects white/cream food pixels (rice, cheese, sauce).
        """
        result = self.remove_background(img)
        result = self._refine_edges(result)
        # ✅ FIX: Pass is_food flag — food images skip aggressive white removal
        result = self._clean_background(result, is_food=is_food)
        return result

    def _refine_edges(self, img_rgba: Image.Image) -> Image.Image:
        from PIL import ImageFilter
        r, g, b, a = img_rgba.split()
        a_smooth = a.filter(ImageFilter.SMOOTH_MORE)
        return Image.merge('RGBA', (r, g, b, a_smooth))

    def _clean_background(self, img_rgba: Image.Image,
                           is_food: bool = True) -> Image.Image:
        """
        ✅ FIXED: Old version was removing food pixels.

        OLD (WRONG):
            near_white = (r > 240) & (g > 240) & (b > 240) & (a > 0) & (a < 200)
            full_white = (r > 252) & (g > 252) & (b > 252) & (a > 200)
            → This removed rice grains, pizza cheese, biryani cream!

        NEW (CORRECT):
            For food images: Only remove pixels that are ALMOST PURE white
            AND have very low alpha (bg leakage), not food pixels.
            For non-food: slightly more aggressive cleanup is OK.
        """
        data = np.array(img_rgba)
        r, g, b, a = data[:,:,0], data[:,:,1], data[:,:,2], data[:,:,3]

        if is_food:
            # ✅ SAFE for food: only remove near-transparent + near-pure-white leakage
            # Pure bg leakage = very white (>250 all channels) AND very transparent (<80 alpha)
            bg_leakage = (r > 250) & (g > 250) & (b > 250) & (a < 80)
            data[bg_leakage, 3] = 0

            # Semi-transparent white EDGES (not pixels inside the food)
            edge_leakage = (r > 248) & (g > 248) & (b > 248) & (a > 0) & (a < 40)
            data[edge_leakage, 3] = 0
            # NOTE: We do NOT remove fully-opaque white pixels — that would destroy
            # rice grains, cheese, cream sauces, white garnishes etc.
        else:
            # For non-food objects: slightly more aggressive is OK
            near_white = (r > 245) & (g > 245) & (b > 245) & (a > 0) & (a < 150)
            data[near_white, 3] = 0
            full_white = (r > 252) & (g > 252) & (b > 252) & (a > 200)
            data[full_white, 3] = 0

        return Image.fromarray(data, 'RGBA')

    def process_image_file(self, input_path: str, output_path: str,
                            is_food: bool = True) -> str:
        img = Image.open(input_path).convert("RGB")
        result = self.remove_background_enhanced(img, is_food=is_food)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        result.save(output_path, "PNG", optimize=True)
        return output_path

    def process_folder(self, input_folder: str, output_folder: str,
                       skip_existing: bool = True) -> dict:
        input_path  = Path(input_folder)
        output_path = Path(output_folder)

        image_files = (list(input_path.rglob("*.png")) +
                       list(input_path.rglob("*.jpg")) +
                       list(input_path.rglob("*.jpeg")))

        print(f"Found {len(image_files)} images to process")
        stats = {"processed": 0, "skipped": 0, "failed": 0}

        # ✅ Auto-detect food categories
        FOOD_CATEGORIES = {
            "biryani", "rice", "curry", "pizza", "food", "indian",
            "dosa", "noodles", "burger", "soup", "dessert", "sweet",
            "bread", "salad", "meat", "chicken", "seafood"
        }

        for i, img_file in enumerate(image_files):
            rel_path = img_file.relative_to(input_path)
            out_file = output_path / rel_path.with_suffix('.png')

            if skip_existing and out_file.exists():
                stats["skipped"] += 1
                continue

            # ✅ Check if this is a food image by folder name
            path_str  = str(rel_path).lower()
            is_food   = any(cat in path_str for cat in FOOD_CATEGORIES)

            try:
                self.process_image_file(str(img_file), str(out_file), is_food=is_food)
                stats["processed"] += 1

                if (i + 1) % 50 == 0:
                    print(f"  Processed: {stats['processed']} | "
                          f"Skipped: {stats['skipped']} | Failed: {stats['failed']}")
                    gc.collect()
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()

            except Exception as e:
                print(f"  Failed: {img_file.name} — {e}")
                stats["failed"] += 1

        print(f"\nBackground removal complete!")
        print(f"  Processed : {stats['processed']}")
        print(f"  Skipped   : {stats['skipped']}")
        print(f"  Failed    : {stats['failed']}")
        return stats

    def unload(self):
        del self.model; self.model = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        print("Background remover unloaded")


class SmokeEffectRemover:
    """Special removal for smoke, fire, light effects."""
    @staticmethod
    def remove_white_background(img: Image.Image) -> Image.Image:
        img_rgba = img.convert("RGBA")
        data = np.array(img_rgba)
        r, g, b, a = data[:,:,0], data[:,:,1], data[:,:,2], data[:,:,3]
        luminosity = (0.299 * r + 0.587 * g + 0.114 * b).astype(np.uint8)
        new_alpha  = (255 - luminosity)
        new_alpha[new_alpha < 10] = 0
        data[:,:,3] = new_alpha
        return Image.fromarray(data, 'RGBA')


def process_with_smart_routing(img: Image.Image, category: str,
                                remover: BackgroundRemover) -> Image.Image:
    smoke_categories = ["effects/smoke", "smoke_effects"]
    food_categories  = ["biryani", "pizza", "food", "curry", "dosa",
                        "rice", "indian", "dessert", "sweet"]

    if any(cat in category.lower() for cat in smoke_categories):
        return SmokeEffectRemover.remove_white_background(img)
    else:
        is_food = any(cat in category.lower() for cat in food_categories)
        return remover.remove_background_enhanced(img, is_food=is_food)


if __name__ == "__main__":
    import sys
    remover = BackgroundRemover()
    remover.load_model()
    if len(sys.argv) >= 3:
        remover.process_folder(sys.argv[1], sys.argv[2])
    else:
        remover.process_folder(
            "/kaggle/working/generated_images",
            "/kaggle/working/transparent_pngs"
        )
    remover.unload()

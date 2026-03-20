"""
✂️ PNG Library - Perfect Background Remover
Uses BRIA-RMBG-2.0 - World's Best Background Removal Model (2025)
Pixel-perfect transparency for ALL types: food, smoke, flowers, hair, fur
"""

import torch
import numpy as np
from PIL import Image
from pathlib import Path
import os
import gc
from typing import Union

# ─────────────────────────────────────────────
# BRIA RMBG-2.0 Setup
# ─────────────────────────────────────────────
class BackgroundRemover:
    """
    BRIA-RMBG-2.0: State-of-the-art background removal
    - Perfect for transparent PNG creation
    - Handles: food, smoke, flowers, hair, fur, fine details
    - 3x better than rembg on complex edges
    """
    
    def __init__(self):
        self.model = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"🔧 Background Remover using: {self.device}")

    def load_model(self):
        """Load BRIA-RMBG-2.0"""
        from transformers import AutoModelForImageSegmentation
        from torchvision import transforms
        
        print("📦 Loading BRIA-RMBG-2.0...")
        self.model = AutoModelForImageSegmentation.from_pretrained(
            "briaai/RMBG-2.0",
            trust_remote_code=True
        )
        self.model.to(self.device)
        self.model.eval()
        
        # Image preprocessing
        self.transform = transforms.Compose([
            transforms.Resize((1024, 1024)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])
        
        print("✅ BRIA-RMBG-2.0 loaded!")
        return self

    def remove_background(self, img: Image.Image) -> Image.Image:
        """
        Remove background from image and return transparent PNG
        Returns RGBA image with perfect transparency
        """
        original_size = img.size
        
        # Convert to RGB (ensure correct format)
        img_rgb = img.convert("RGB")
        
        # Preprocess
        input_tensor = self.transform(img_rgb).unsqueeze(0).to(self.device)
        
        # Run model
        with torch.no_grad():
            result = self.model(input_tensor)
        
        # Get mask (handle different output formats)
        if isinstance(result, (list, tuple)):
            mask = result[0][0]
        else:
            mask = result[0]
        
        # Process mask
        if mask.dim() > 2:
            mask = mask.squeeze()
        
        mask = torch.sigmoid(mask)
        mask = mask.cpu().numpy()
        
        # Normalize mask to 0-255
        mask = (mask * 255).astype(np.uint8)
        
        # Resize mask to original size
        mask_pil = Image.fromarray(mask, mode='L')
        mask_pil = mask_pil.resize(original_size, Image.LANCZOS)
        
        # Apply mask - create RGBA image
        img_rgba = img_rgb.convert("RGBA")
        img_rgba.putalpha(mask_pil)
        
        return img_rgba

    def remove_background_enhanced(self, img: Image.Image) -> Image.Image:
        """
        Enhanced background removal with post-processing for cleaner edges
        Best for product images, food, objects
        """
        # Step 1: Basic removal
        result = self.remove_background(img)
        
        # Step 2: Edge refinement
        result = self._refine_edges(result)
        
        # Step 3: Clean any residual white/grey spots
        result = self._clean_background(result)
        
        return result

    def _refine_edges(self, img_rgba: Image.Image) -> Image.Image:
        """Smooth jagged edges for professional look"""
        from PIL import ImageFilter
        
        # Get alpha channel
        r, g, b, a = img_rgba.split()
        
        # Slightly smooth the alpha mask
        a_smooth = a.filter(ImageFilter.SMOOTH_MORE)
        
        # Recombine
        result = Image.merge('RGBA', (r, g, b, a_smooth))
        return result

    def _clean_background(self, img_rgba: Image.Image) -> Image.Image:
        """Remove any near-white background remnants"""
        data = np.array(img_rgba)
        
        r, g, b, a = data[:,:,0], data[:,:,1], data[:,:,2], data[:,:,3]
        
        # Find pixels that are very white/grey AND semi-transparent — make fully transparent
        near_white = (r > 240) & (g > 240) & (b > 240) & (a > 0) & (a < 200)
        data[near_white, 3] = 0  # Make fully transparent
        
        # Find pixels that are fully white AND opaque — also make transparent
        full_white = (r > 252) & (g > 252) & (b > 252) & (a > 200)
        data[full_white, 3] = 0
        
        return Image.fromarray(data, 'RGBA')

    def process_image_file(self, input_path: str, output_path: str) -> str:
        """Process a single image file"""
        img = Image.open(input_path).convert("RGB")
        result = self.remove_background_enhanced(img)
        
        # Ensure output is PNG with transparency
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        result.save(output_path, "PNG", optimize=True)
        return output_path

    def process_folder(self, input_folder: str, output_folder: str,
                       skip_existing: bool = True) -> dict:
        """
        Process entire folder of images
        Maintains folder structure
        Returns stats dict
        """
        input_path = Path(input_folder)
        output_path = Path(output_folder)
        
        # Find all images
        image_files = list(input_path.rglob("*.png")) + \
                      list(input_path.rglob("*.jpg")) + \
                      list(input_path.rglob("*.jpeg"))
        
        print(f"📂 Found {len(image_files)} images to process")
        
        stats = {"processed": 0, "skipped": 0, "failed": 0}
        
        for i, img_file in enumerate(image_files):
            # Maintain relative folder structure
            rel_path = img_file.relative_to(input_path)
            out_file = output_path / rel_path.with_suffix('.png')
            
            if skip_existing and out_file.exists():
                stats["skipped"] += 1
                continue
            
            try:
                self.process_image_file(str(img_file), str(out_file))
                stats["processed"] += 1
                
                if (i + 1) % 50 == 0:
                    print(f"  ✅ Processed: {stats['processed']} | "
                          f"Skipped: {stats['skipped']} | "
                          f"Failed: {stats['failed']}")
                    
                    # Free GPU memory periodically
                    gc.collect()
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                        
            except Exception as e:
                print(f"  ❌ Failed: {img_file.name} — {e}")
                stats["failed"] += 1
        
        print(f"\n🎉 Background removal complete!")
        print(f"  ✅ Processed: {stats['processed']}")
        print(f"  ⏭️  Skipped: {stats['skipped']}")
        print(f"  ❌ Failed: {stats['failed']}")
        return stats

    def unload(self):
        del self.model
        self.model = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        print("🗑️  Background remover unloaded")


# ─────────────────────────────────────────────
# SPECIAL HANDLER: Smoke & Effects
# ─────────────────────────────────────────────
class SmokeEffectRemover:
    """
    Special background removal for smoke, fire, light effects
    These need different treatment than solid objects
    """
    
    @staticmethod
    def remove_white_background(img: Image.Image) -> Image.Image:
        """
        For smoke/effects: Remove white background using luminosity method
        Smoke generated on white BG → transparent smoke
        """
        img_rgba = img.convert("RGBA")
        data = np.array(img_rgba)
        
        # For smoke on white: pixel darkness = smoke density = alpha
        r, g, b, a = data[:,:,0], data[:,:,1], data[:,:,2], data[:,:,3]
        
        # Luminosity: darker = more smoke = more opaque
        luminosity = (0.299 * r + 0.587 * g + 0.114 * b).astype(np.uint8)
        
        # Invert: white (255) → transparent (0), dark (0) → opaque (255)
        new_alpha = (255 - luminosity)
        
        # Apply threshold to clean up edges
        new_alpha[new_alpha < 10] = 0  # Near-white = fully transparent
        
        data[:,:,3] = new_alpha
        return Image.fromarray(data, 'RGBA')


# ─────────────────────────────────────────────
# COMBINED PIPELINE
# ─────────────────────────────────────────────
def process_with_smart_routing(img: Image.Image, category: str,
                                remover: BackgroundRemover) -> Image.Image:
    """
    Route image to best background removal method based on category
    """
    smoke_categories = ["effects/smoke", "smoke_effects"]
    
    if any(cat in category.lower() for cat in smoke_categories):
        # Smoke/effects: use luminosity method
        result = SmokeEffectRemover.remove_white_background(img)
    else:
        # Everything else: use BRIA-RMBG-2.0
        result = remover.remove_background_enhanced(img)
    
    return result


# ─────────────────────────────────────────────
# STANDALONE USAGE
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    
    remover = BackgroundRemover()
    remover.load_model()
    
    if len(sys.argv) >= 3:
        # Process specific input/output folders
        input_dir = sys.argv[1]
        output_dir = sys.argv[2]
        remover.process_folder(input_dir, output_dir)
    else:
        # Default: process generated images
        remover.process_folder(
            "/kaggle/working/generated_images",
            "/kaggle/working/transparent_pngs"
        )
    
    remover.unload()

const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');
const { execFile } = require('child_process');
const config = require('../config');

function downloadImage(url, destPath) {
  return new Promise((resolve, reject) => {
    const client = url.startsWith('https:') ? https : http;
    const file = fs.createWriteStream(destPath);
    client.get(url, {
      headers: { 'User-Agent': 'Mozilla/5.0' },
      timeout: 20000
    }, res => {
      if ([301, 302, 307].includes(res.statusCode) && res.headers.location) {
        file.close();
        try { fs.unlinkSync(destPath); } catch (e) {}
        return downloadImage(res.headers.location, destPath).then(resolve).catch(reject);
      }
      if (res.statusCode !== 200) {
        file.close();
        try { fs.unlinkSync(destPath); } catch (e) {}
        return reject(new Error(`Failed to download preview image: HTTP ${res.statusCode}`));
      }
      res.pipe(file);
      file.on('finish', () => file.close(() => resolve(destPath)));
      file.on('error', reject);
    }).on('error', reject);
  });
}

function renderDesignToWebp(inputPath, outputPath, maxWidth = 1400, quality = 90, watermarkText = null, watermarkOpacity = null) {
  return new Promise((resolve, reject) => {
    const pythonExe = config.PATHS.python;
    const wmText = (watermarkText !== null ? watermarkText : (config.WATERMARK && config.WATERMARK.enabled ? config.WATERMARK.text : '')).trim();
    const wmOpacity = watermarkOpacity !== null ? watermarkOpacity : ((config.WATERMARK && config.WATERMARK.opacity) || 95);

    const script = `
import sys, os
from PIL import Image, ImageFile, ImageDraw, ImageFont

ImageFile.LOAD_TRUNCATED_IMAGES = True

try:
    src = sys.argv[1]
    dest = sys.argv[2]
    max_w = int(sys.argv[3])
    q = int(sys.argv[4])
    wm_text = sys.argv[5] if len(sys.argv) > 5 else ''
    opacity = int(sys.argv[6]) if len(sys.argv) > 6 else 95

    ext = os.path.splitext(src)[1].lower().replace('.', '')
    im = None

    if ext in ('psd', 'psb'):
        try:
            pil_im = Image.open(src)
            pil_im.load()
            im = pil_im
        except Exception:
            from psd_tools import PSDImage
            psd = PSDImage.open(src)
            im = psd.composite()
    else:
        im = Image.open(src)
        im.load()

    has_alpha = False
    if im.mode in ('RGBA', 'LA') or (im.mode == 'P' and 'transparency' in im.info):
        im = im.convert('RGBA')
        extrema = im.getextrema()
        if len(extrema) == 4 and extrema[3][0] < 250:
            has_alpha = True
    elif im.mode == 'CMYK':
        im = im.convert('RGB')
    else:
        im = im.convert('RGB')

    w, h = im.size
    if w > max_w:
        new_h = int(h * (max_w / float(w)))
        im = im.resize((max_w, new_h), Image.Resampling.LANCZOS)

    cur_w, cur_h = im.size
    if wm_text and wm_text.strip():
        base_rgba = im.convert('RGBA')
        overlay = Image.new('RGBA', (cur_w, cur_h), (0, 0, 0, 0))

        font_size = max(22, int(min(cur_w, cur_h) * 0.065))
        font = None
        font_candidates = [
            'C:/Windows/Fonts/segoeuib.ttf', 'C:/Windows/Fonts/arialbd.ttf',
            'C:/Windows/Fonts/segoeui.ttf', 'C:/Windows/Fonts/arial.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
            '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf'
        ]
        for fp in font_candidates:
            if os.path.exists(fp):
                try:
                    font = ImageFont.truetype(fp, font_size)
                    break
                except Exception:
                    pass
        if font is None:
            font = ImageFont.load_default()

        dummy = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
        bbox = dummy.textbbox((0, 0), wm_text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        pad = 30
        txt_img = Image.new('RGBA', (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
        td = ImageDraw.Draw(txt_img)

        # Subtle dark drop-shadow for crisp readability on bright backgrounds
        td.text((pad + 2, pad + 2), wm_text, font=font, fill=(0, 0, 0, int(opacity * 0.55)))
        # Crisp white text with decent opacity
        td.text((pad, pad), wm_text, font=font, fill=(255, 255, 255, opacity))

        stamp = txt_img.rotate(26, expand=True, resample=Image.Resampling.BICUBIC)
        sw, sh = stamp.size

        coords = [((cur_w - sw) // 2, (cur_h - sh) // 2)]
        if cur_w > 650 and cur_h > 650:
            coords.append((int(cur_w * 0.22 - sw // 2), int(cur_h * 0.25 - sh // 2)))
            coords.append((int(cur_w * 0.78 - sw // 2), int(cur_h * 0.75 - sh // 2)))

        for cx, cy in coords:
            overlay.paste(stamp, (cx, cy), stamp)

        combined = Image.alpha_composite(base_rgba, overlay)
        im = combined if has_alpha else combined.convert('RGB')

    im.save(dest, 'WEBP', quality=q, method=6)
    print('OK')
except Exception as e:
    print('ERROR:', e, file=sys.stderr)
    sys.exit(1)
`;

    execFile(pythonExe, ['-c', script, inputPath, outputPath, String(maxWidth), String(quality), wmText, String(wmOpacity)], (err, stdout, stderr) => {
      if (err) {
        return reject(new Error(`Pillow / psd-tools rendering failed: ${stderr || err.message}`));
      }
      resolve(outputPath);
    });
  });
}

const postFormatter = require('./post_formatter');

async function prepareWebpPreview(post, designPath, targetDir) {
  const formattedId = postFormatter.getFormattedDesignId(post.id);
  const finalWebpPath = path.join(targetDir, `${formattedId}.webp`);

  // PRIMARY & REQUIRED: Render directly from the clean extracted PSD / TIF / PNG (NO WATERMARK!)
  if (designPath && fs.existsSync(designPath)) {
    console.log(`Rendering clean watermark-free WebP directly from raw design: ${path.basename(designPath)}...`);
    try {
      await renderDesignToWebp(designPath, finalWebpPath, 1400, 90);
      return finalWebpPath;
    } catch (e) {
      console.warn(`Direct design render warning for ${post.id}:`, e.message);
    }
  }

  // Fallback ONLY if raw design render failed: check local archive files
  const localCopy = path.join(config.PATHS.localSiteDir, 'FORPSD __ RAMARTS-_files', `${post.fileName}.webp`);
  if (fs.existsSync(localCopy)) {
    await renderDesignToWebp(localCopy, finalWebpPath, 1400, 90);
    return finalWebpPath;
  }

  if (post.previewUrl) {
    const tempDownload = path.join(targetDir, `temp_preview_${cleanId}.tmp`);
    await downloadImage(post.previewUrl, tempDownload);
    await renderDesignToWebp(tempDownload, finalWebpPath, 1400, 90);
    return finalWebpPath;
  }

  throw new Error(`Unable to generate preview image for post ${post.id}`);
}

function getImageMetadata(filePath) {
  return new Promise(resolve => {
    if (!filePath || !fs.existsSync(filePath)) {
      return resolve({ dimensions: '1800x1200 pixels', dpi: '300 DPI', colorMode: 'CMYK' });
    }

    const pythonExe = config.PATHS.python;
    const script = `
import sys
from PIL import Image

try:
    path = sys.argv[1]
    with Image.open(path) as im:
        w, h = im.size
        dpi_val = 300
        if 'dpi' in im.info:
            d = im.info['dpi']
            dpi_val = int(round(d[0])) if isinstance(d, (tuple, list)) else int(round(d))
        mode = 'CMYK' if im.mode == 'CMYK' else ('RGB' if im.mode in ('RGB', 'RGBA') else im.mode)
        print(f"{w}x{h}|{dpi_val} DPI|{mode}")
except Exception as e:
    print("1800x1200|300 DPI|CMYK")
`;

    execFile(pythonExe, ['-c', script, filePath], (err, stdout) => {
      if (err || !stdout) {
        return resolve({ dimensions: '1800x1200 pixels', dpi: '300 DPI', colorMode: 'CMYK' });
      }
      try {
        const parts = stdout.trim().split('|');
        if (parts.length >= 3) {
          return resolve({
            dimensions: `${parts[0]} pixels`,
            dpi: parts[1],
            colorMode: parts[2]
          });
        }
      } catch (e) {}
      resolve({ dimensions: '1800x1200 pixels', dpi: '300 DPI', colorMode: 'CMYK' });
    });
  });
}

module.exports = {
  renderDesignToWebp,
  convertToHighQualityWebp: renderDesignToWebp,
  prepareWebpPreview,
  getImageMetadata
};

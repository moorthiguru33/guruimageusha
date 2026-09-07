const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');
const { execFile } = require('child_process');
const config = require('../config');

function downloadFileRaw(url, destPath, cookie = '') {
  return new Promise((resolve, reject) => {
    const isHttps = url.startsWith('https:');
    const client = isHttps ? https : http;
    const fileStream = fs.createWriteStream(destPath);

    const req = client.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Cookie': cookie
      },
      timeout: 60000
    }, res => {
      // Handle Google Drive confirm tokens or redirects
      if ([301, 302, 303, 307].includes(res.statusCode) && res.headers.location) {
        fileStream.close();
        try { fs.unlinkSync(destPath); } catch (e) {}
        let nextUrl = res.headers.location;
        if (!nextUrl.startsWith('http')) {
          const u = new URL(url);
          nextUrl = `${u.origin}${nextUrl}`;
        }
        return downloadFile(nextUrl, destPath, cookie).then(resolve).catch(reject);
      }

      if (res.statusCode !== 200) {
        fileStream.close();
        try { fs.unlinkSync(destPath); } catch (e) {}
        return reject(new Error(`Download failed with HTTP ${res.statusCode}`));
      }

      res.pipe(fileStream);
      fileStream.on('finish', () => {
        fileStream.close(() => resolve(destPath));
      });
      fileStream.on('error', err => {
        try { fs.unlinkSync(destPath); } catch (e) {}
        reject(err);
      });
    });

    req.on('error', err => {
      try { fs.unlinkSync(destPath); } catch (e) {}
      reject(err);
    });

    req.on('timeout', () => {
      req.destroy();
      try { fs.unlinkSync(destPath); } catch (e) {}
      reject(new Error('Download connection timed out'));
    });
  });
}

async function downloadFile(url, destPath, cookie = '', retries = 3) {
  let lastErr = null;
  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      return await downloadFileRaw(url, destPath, cookie);
    } catch (err) {
      lastErr = err;
      if (attempt < retries) {
        console.warn(`Download attempt ${attempt} failed (${err.message}), retrying in 2s...`);
        await new Promise(r => setTimeout(r, 2000));
      }
    }
  }
  throw lastErr;
}

const postFormatter = require('./post_formatter');

function checkDirectFileFormat(filePath) {
  try {
    const fd = fs.openSync(filePath, 'r');
    const buf = Buffer.alloc(16);
    fs.readSync(fd, buf, 0, 16, 0);
    fs.closeSync(fd);

    // PSD / PSB: '8BPS'
    if (buf[0] === 0x38 && buf[1] === 0x42 && buf[2] === 0x50 && buf[3] === 0x53) return 'psd';
    // TIFF: II*\0 or MM\0*
    if ((buf[0] === 0x49 && buf[1] === 0x49 && buf[2] === 0x2A && buf[3] === 0x00) ||
        (buf[0] === 0x4D && buf[1] === 0x4D && buf[2] === 0x00 && buf[3] === 0x2A)) return 'tif';
    // PNG: \x89PNG
    if (buf[0] === 0x89 && buf[1] === 0x50 && buf[2] === 0x4E && buf[3] === 0x47) return 'png';
    // JPEG: \xFF\xD8\xFF
    if (buf[0] === 0xFF && buf[1] === 0xD8 && buf[2] === 0xFF) return 'jpg';
  } catch (e) {}
  return null;
}

function extractArchive(archivePath, extractDir) {
  return new Promise((resolve, reject) => {
    if (!fs.existsSync(extractDir)) {
      fs.mkdirSync(extractDir, { recursive: true });
    }

    const sevenZip = config.PATHS.sevenZip;
    if (path.isAbsolute(sevenZip) && !fs.existsSync(sevenZip)) {
      return reject(new Error(`7-Zip not found at ${sevenZip}. Please verify installation.`));
    }

    // Command: 7z x "archive" -o"extractDir" -y
    execFile(sevenZip, ['x', archivePath, `-o${extractDir}`, '-y'], (error, stdout, stderr) => {
      if (error) {
        // If 7-zip says cannot open as archive, check if file itself is already a direct design file
        const directExt = checkDirectFileFormat(archivePath);
        if (directExt) {
          const destName = `design_${path.basename(archivePath, path.extname(archivePath))}.${directExt}`;
          const destPath = path.join(extractDir, destName);
          fs.copyFileSync(archivePath, destPath);
          console.log(`Direct uncompressed ${directExt.toUpperCase()} detected and extracted to ${destPath}`);
          return resolve(extractDir);
        }
        return reject(new Error(`7-Zip extraction error: ${stderr || error.message}`));
      }
      resolve(extractDir);
    });
  });
}

function findFilesRecursive(dir) {
  let results = [];
  const list = fs.readdirSync(dir);
  list.forEach(file => {
    const fullPath = path.join(dir, file);
    const stat = fs.statSync(fullPath);
    if (stat && stat.isDirectory()) {
      results = results.concat(findFilesRecursive(fullPath));
    } else {
      results.push(fullPath);
    }
  });
  return results;
}

async function processDownload(post, customTempDir = '') {
  const settings = config.getSettings();
  const tempBase = customTempDir || settings.tempWorkspace || config.DEFAULT_TEMP_DIR;

  if (!fs.existsSync(tempBase)) {
    fs.mkdirSync(tempBase, { recursive: true });
  }

  const postId = String(post.id).trim();
  const archivePath = path.join(tempBase, `${postId}.zip`);
  const extractDir = path.join(tempBase, `extract_${postId}`);

  // Check if archive is already downloaded locally (e.g., in Desktop / forpsd.com)
  const localDesktopZip = path.join('C:/Users/Guru/Desktop/New folder (2)/forpsd.com', `${postId}.zip`);
  let downloaded = false;

  if (fs.existsSync(localDesktopZip)) {
    console.log(`Using existing local copy from ${localDesktopZip}`);
    fs.copyFileSync(localDesktopZip, archivePath);
    downloaded = true;
  }

  if (!downloaded) {
    let dlUrl = post.downloadTokenUrl;
    // Check if dlUrl is empty or is an unencrypted URL like https://forpsd.com/download/1790
    if (!dlUrl || dlUrl.match(/\/download\/\d+$/i)) {
      console.log(`🔎 Download token not encrypted. Resolving real token from ForPSD for post #${postId}...`);
      const scraper = require('./scraper');
      const resolved = await scraper.getPostById(postId);
      if (resolved && resolved.downloadTokenUrl && !resolved.downloadTokenUrl.match(/\/download\/\d+$/i)) {
        dlUrl = resolved.downloadTokenUrl;
        post.downloadTokenUrl = dlUrl;
        if (resolved.fileName) post.fileName = resolved.fileName;
        if (resolved.title) post.title = resolved.title;
        console.log(`✅ Resolved live download token for #${postId}`);
      }
    }

    if (!dlUrl) {
      throw new Error(`No download token URL available for post #${postId}.`);
    }

    console.log(`Downloading from ${dlUrl}...`);
    try {
      await downloadFile(dlUrl, archivePath, settings.forpsdCookie);
    } catch (err) {
      // If failed with HTTP 500 or expired token, attempt to refresh token and retry
      console.warn(`Download failed (${err.message}). Attempting to refresh token from ForPSD...`);
      const scraper = require('./scraper');
      const fresh = await scraper.getPostById(postId);
      if (fresh && fresh.downloadTokenUrl && fresh.downloadTokenUrl !== dlUrl) {
        console.log(`Retrying download with fresh token: ${fresh.downloadTokenUrl}...`);
        await downloadFile(fresh.downloadTokenUrl, archivePath, settings.forpsdCookie);
      } else {
        throw err;
      }
    }
  }

  // Extract with 7-Zip (or direct format handler)
  console.log(`Extracting ${archivePath} with 7-Zip...`);
  await extractArchive(archivePath, extractDir);

  // Scan extracted files
  const allFiles = findFilesRecursive(extractDir);
  
  // Filter out junk/competitor advertising files
  const validFiles = allFiles.filter(f => {
    const base = path.basename(f).toLowerCase();
    return !base.endsWith('.url') &&
           !base.endsWith('.txt') &&
           !base.endsWith('.html') &&
           !base.endsWith('.htm') &&
           !base.endsWith('.ini') &&
           !base.endsWith('.nfo') &&
           !base.includes('__macosx');
  });

  // Categorize candidate design files
  const psdFiles = validFiles.filter(f => /\.(psd|psb)$/i.test(f));
  const tifFiles = validFiles.filter(f => /\.(tif|tiff)$/i.test(f));
  const cdrFiles = validFiles.filter(f => /\.(cdr|ai|eps)$/i.test(f));
  const pngFiles = validFiles.filter(f => /\.png$/i.test(f));
  const otherFiles = validFiles.filter(f => !/\.(webp|jpe?g)$/i.test(f));

  // Determine main design file & format hierarchy: PSD > TIF > CDR > PNG > Other
  let mainDesignFile = null;
  let format = 'PSD';

  const sortByDescSize = (list) => list.sort((a, b) => fs.statSync(b).size - fs.statSync(a).size);

  if (psdFiles.length > 0) {
    mainDesignFile = sortByDescSize(psdFiles)[0];
    format = 'PSD';
  } else if (tifFiles.length > 0) {
    mainDesignFile = sortByDescSize(tifFiles)[0];
    format = 'TIF';
  } else if (cdrFiles.length > 0) {
    mainDesignFile = sortByDescSize(cdrFiles)[0];
    format = 'CDR';
  } else if (pngFiles.length > 0) {
    mainDesignFile = sortByDescSize(pngFiles)[0];
    format = 'PNG';
  } else if (otherFiles.length > 0) {
    mainDesignFile = sortByDescSize(otherFiles)[0];
    format = path.extname(mainDesignFile).replace('.', '').toUpperCase();
  }

  if (!mainDesignFile) {
    throw new Error(`No supported design file (PSD, TIF, PNG, CDR) found in archive for post ${postId}. Files: ${allFiles.map(f => path.basename(f)).join(', ')}`);
  }

  // Scrub competitor branding from design filename if present
  const origBase = path.basename(mainDesignFile);
  const ext = path.extname(origBase);
  let cleanBaseName = postFormatter.scrubBranding(origBase.slice(0, -ext.length));
  if (!cleanBaseName || cleanBaseName.length < 2) {
    cleanBaseName = postFormatter.getFormattedDesignId(postId);
  }
  const cleanDesignPath = path.join(path.dirname(mainDesignFile), `${cleanBaseName}${ext}`);
  if (cleanDesignPath !== mainDesignFile) {
    try {
      fs.renameSync(mainDesignFile, cleanDesignPath);
      mainDesignFile = cleanDesignPath;
    } catch (e) {
      console.warn('Could not rename design file:', e.message);
    }
  }

  // Determine preview image
  let previewImage = null;
  if (format === 'PNG') {
    // For PNG design files, the PNG itself is high resolution preview
    previewImage = mainDesignFile;
  } else {
    // Find dedicated preview image file in archive
    previewImage = validFiles.find(f => /\.(webp|jpg|jpeg)$/i.test(f));
    if (!previewImage) {
      // Check if there is a PNG preview in non-PNG designs
      const previewPng = validFiles.find(f => /\.png$/i.test(f) && f !== mainDesignFile);
      if (previewPng) previewImage = previewPng;
    }
  }

  const stat = fs.statSync(mainDesignFile);
  const sizeMB = (stat.size / (1024 * 1024)).toFixed(2);

  return {
    archivePath,
    extractDir,
    designPath: mainDesignFile,
    psdPath: mainDesignFile,
    designName: path.basename(mainDesignFile),
    format,
    previewPath: previewImage || '',
    fileSizeBytes: stat.size,
    fileSizeFormatted: `${sizeMB} MB`
  };
}

module.exports = {
  downloadFile,
  extractArchive,
  processDownload
};

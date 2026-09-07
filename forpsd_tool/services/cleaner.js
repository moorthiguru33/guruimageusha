const fs = require('fs');
const path = require('path');

function removePathSafe(targetPath) {
  if (!targetPath || !fs.existsSync(targetPath)) return;
  try {
    const stat = fs.statSync(targetPath);
    if (stat.isDirectory()) {
      fs.rmSync(targetPath, { recursive: true, force: true });
      console.log(`Cleaned up directory: ${targetPath}`);
    } else {
      fs.unlinkSync(targetPath);
      console.log(`Cleaned up file: ${targetPath}`);
    }
  } catch (err) {
    console.warn(`Could not delete temp path ${targetPath}:`, err.message);
  }
}

function cleanupItemFiles(downloadResult, webpPath) {
  if (!downloadResult) return;

  // 1. Delete downloaded archive
  if (downloadResult.archivePath) {
    removePathSafe(downloadResult.archivePath);
  }

  // 2. Delete extracted folder
  if (downloadResult.extractDir) {
    removePathSafe(downloadResult.extractDir);
  }

  // 3. Delete generated zip of PSD (if created inside temp)
  if (downloadResult.zipPath) {
    removePathSafe(downloadResult.zipPath);
  }

  // 4. Delete local WebP preview once uploaded to R2
  if (webpPath) {
    removePathSafe(webpPath);
  }
}

module.exports = {
  removePathSafe,
  cleanupItemFiles
};

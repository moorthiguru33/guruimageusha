const fs = require('fs');
const path = require('path');
const downloader = require('./downloader');
const imageProcessor = require('./image_processor');
const r2Service = require('./r2');
const gdriveService = require('./gdrive');
const postFormatter = require('./post_formatter');
const excelGithub = require('./excel_github');
const cleaner = require('./cleaner');
const config = require('../config');

// In-memory progress tracking
let activeJob = null;
let eventListeners = [];

function broadcast(event, data) {
  eventListeners.forEach(listener => {
    try {
      listener(event, data);
    } catch (e) {}
  });
}

function addEventListener(fn) {
  eventListeners.push(fn);
  return () => {
    eventListeners = eventListeners.filter(l => l !== fn);
  };
}

function getActiveJob() {
  return activeJob;
}

async function startBatchProcess(selectedPosts, customTempDir = '', options = {}) {
  if (activeJob && activeJob.status === 'running') {
    throw new Error('A batch job is already running.');
  }

  // Ensure existing IDs are loaded
  await excelGithub.loadExistingIds();

  const skipExisting = options.skipExisting === true; // Default to false per user instructions: no need to skip existing files
  const forceReupload = !!options.forceReupload;

  activeJob = {
    id: 'job_' + Date.now(),
    status: 'running',
    total: selectedPosts.length,
    completed: 0,
    skipped: 0,
    failed: 0,
    currentIndex: 0,
    items: selectedPosts.map(p => ({
      ...p,
      status: 'queued',
      progress: 0,
      stage: 'Waiting in queue...',
      error: null,
      result: null
    })),
    startedAt: new Date().toISOString()
  };

  broadcast('job_started', activeJob);

  // Run in background
  (async () => {
    for (let i = 0; i < activeJob.items.length; i++) {
      activeJob.currentIndex = i;
      const item = activeJob.items[i];
      let downloadResult = null;
      let webpPath = null;

      // STEP 0: Pre-check if already uploaded to Excel
      if (skipExisting && !forceReupload && excelGithub.hasExistingId(item.id)) {
        console.log(`[SKIP] Post ${item.id} already exists in designs.xlsx. Skipping download & upload.`);
        item.status = 'skipped';
        item.progress = 100;
        item.stage = 'Skipped: Already recorded in designs.xlsx';
        item.result = { skipped: true, reason: 'Already in Excel' };
        activeJob.skipped++;
        broadcast('item_update', { index: i, item });
        continue;
      }

      try {
        // Step 1: Download & Extract
        item.status = 'downloading';
        item.progress = 15;
        item.stage = 'Downloading source file from ForPSD / Drive...';
        broadcast('item_update', { index: i, item });

        downloadResult = await downloader.processDownload(item, customTempDir);

        item.stage = `Extracting ${downloadResult.format} archive with 7-Zip...`;
        item.progress = 30;
        broadcast('item_update', { index: i, item });

        // Step 2: High-Quality WebP
        item.status = 'processing_image';
        item.stage = 'Generating High Quality WebP preview...';
        item.progress = 45;
        broadcast('item_update', { index: i, item });

        webpPath = await imageProcessor.prepareWebpPreview(item, downloadResult.designPath, downloadResult.extractDir);

        // Step 2.5: Extract technical metadata (dimensions, dpi, color mode)
        const meta = await imageProcessor.getImageMetadata(downloadResult.designPath || webpPath);

        // Step 3: Cloudflare R2 Upload
        item.status = 'uploading_r2';
        item.stage = 'Uploading HD preview to Cloudflare R2...';
        item.progress = 60;
        broadcast('item_update', { index: i, item });

        const r2PreviewUrl = await r2Service.uploadWebpToR2(webpPath, item.id);

        // Step 4: Google Drive Upload (Zip Design file)
        item.status = 'uploading_gdrive';
        item.stage = `Compressing & uploading ${downloadResult.format} to Google Drive...`;
        item.progress = 75;
        broadcast('item_update', { index: i, item });

        let lastBroadcast = 0;
        const driveResult = await gdriveService.uploadPsdZipToDrive(downloadResult.designPath, item.id, '', (uploaded, total) => {
          const now = Date.now();
          if (now - lastBroadcast > 600 || uploaded === total) {
            lastBroadcast = now;
            const pct = Math.round((uploaded / total) * 100);
            const upMB = (uploaded / (1024 * 1024)).toFixed(1);
            const totMB = (total / (1024 * 1024)).toFixed(1);
            item.stage = `Uploading to Google Drive: ${upMB} / ${totMB} MB (${pct}%)...`;
            item.progress = Math.min(89, 70 + Math.round(pct * 0.19));
            broadcast('item_update', { index: i, item });
          }
        });
        downloadResult.zipPath = driveResult.zipPath;

        // Step 5: Format Post & Add to designs.xlsx
        item.status = 'updating_excel';
        item.stage = `Adding to ${path.basename(config.PATHS.designsXlsx)}...`;
        item.progress = 90;
        broadcast('item_update', { index: i, item });

        const formatted = postFormatter.formatPostDetails(item, {
          downloadUrl: driveResult.downloadUrl,
          previewUrl: r2PreviewUrl,
          fileSizeFormatted: downloadResult.fileSizeFormatted,
          format: downloadResult.format,
          dimensions: meta.dimensions,
          dpi: meta.dpi,
          colorMode: meta.colorMode
        });

        await excelGithub.recordAndPush(formatted);

        // Step 6: Cleanup Temp Files
        item.stage = 'Cleaning temporary downloaded files...';
        cleaner.cleanupItemFiles(downloadResult, webpPath);

        // Done!
        item.status = 'completed';
        item.progress = 100;
        item.stage = 'Completed successfully!';
        item.result = {
          previewUrl: r2PreviewUrl,
          downloadUrl: driveResult.downloadUrl,
          title: formatted.title,
          category: formatted.category
        };
        activeJob.completed++;
        broadcast('item_update', { index: i, item });

      } catch (err) {
        console.error(`Pipeline error on post ${item.id}:`, err);
        item.status = 'error';
        item.stage = 'Failed: ' + err.message;
        item.error = err.message;
        activeJob.failed++;

        // Clean up even if errored
        cleaner.cleanupItemFiles(downloadResult, webpPath);
        broadcast('item_update', { index: i, item });
      }
    }

    activeJob.status = 'finished';
    activeJob.finishedAt = new Date().toISOString();
    broadcast('job_finished', activeJob);
  })();

  return activeJob;
}

module.exports = {
  getActiveJob,
  startBatchProcess,
  addEventListener
};

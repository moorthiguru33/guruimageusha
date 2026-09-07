#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const config = require('./config');
const scraper = require('./services/scraper');
const downloader = require('./services/downloader');
const imageProcessor = require('./services/image_processor');
const r2Service = require('./services/r2');
const gdriveService = require('./services/gdrive');
const postFormatter = require('./services/post_formatter');
const excelGithub = require('./services/excel_github');
const cleaner = require('./services/cleaner');

// Parse CLI Arguments
const args = process.argv.slice(2);
function getArg(flag, def = '') {
  const idx = args.indexOf(flag);
  if (idx !== -1 && idx + 1 < args.length) return args[idx + 1];
  const prefix = flag + '=';
  const found = args.find(a => a.startsWith(prefix));
  return found ? found.slice(prefix.length) : def;
}

const hasFlag = (flag) => args.includes(flag);

if (hasFlag('--help') || hasFlag('-h')) {
  console.log(`
Usage: node runner.js [options]

Options:
  --category, -c <name>    Category to process (e.g. Gods, Wedding, Puberty, Birthday, all) [default: all]
  --ids <id1,id2,...>      Specific comma-separated post IDs to process
  --count, -n <number>     Max number of new items to process [default: 10]
  --skip-existing          Skip items already in designs.xlsx [default: true]
  --no-skip                Do not skip items already in designs.xlsx
  --force                  Force re-download and re-upload even if in designs.xlsx
  --watermark <text>       Watermark text [default: www.tamilpsd.in]
  --help, -h               Show this help message
`);
  process.exit(0);
}

const category = getArg('--category', getArg('-c', process.env.RUN_CATEGORY || 'all'));
const idsInput = getArg('--ids', process.env.RUN_IDS || '');
const countLimit = parseInt(getArg('--count', getArg('-n', process.env.RUN_COUNT || '10')), 10);
const skipExisting = hasFlag('--skip-existing') || process.env.RUN_SKIP_EXISTING === 'true'; // Default to false
const forceReupload = hasFlag('--force');

async function main() {
  console.log('====================================================');
  console.log('🚀 TamilPSD CLI Runner (GitHub Actions / Headless)');
  console.log('====================================================');
  console.log(`📁 Excel Sheet: ${config.PATHS.designsXlsx}`);
  console.log(`☁️  R2 Bucket:  ${config.R2.bucket} (${config.R2.cdnBase})`);
  console.log(`📂 Drive Folder: ${config.GDRIVE.folderId}`);
  console.log(`🏷️  Category:    ${category}`);
  console.log(`🔢 Max Process: ${countLimit}`);
  console.log(`⏭️  Skip Existing: ${skipExisting}`);
  console.log('====================================================\n');

  // Step 1: Load existing IDs from Excel
  console.log('⏳ Loading existing IDs from Excel...');
  const existingIds = await excelGithub.loadExistingIds(true);
  console.log(`✅ Total existing designs in Excel: ${existingIds.size}\n`);

  // Step 2: Discover target posts
  let candidatePosts = [];

  if (idsInput.trim()) {
    const ids = idsInput.split(',').map(s => s.trim()).filter(Boolean);
    console.log(`🔍 Processing ${ids.length} specific IDs: ${ids.join(', ')}`);
    for (const id of ids) {
      const formattedName = postFormatter.getFormattedDesignId(id);
      candidatePosts.push({
        id,
        fileName: formattedName,
        title: formattedName,
        category: 'Design',
        downloadTokenUrl: `https://forpsd.com/download/${id}`,
        previewUrl: ''
      });
    }
  } else {
    const topic = category.toLowerCase() === 'all' ? '' : category;
    console.log(`🌐 Fetching posts from forpsd.com for topic: "${topic || 'All'}"...`);
    candidatePosts = await scraper.getPosts(topic, '', 1, true);
    console.log(`📦 Discovered ${candidatePosts.length} total posts from ForPSD.\n`);
  }

  // Step 3: Filter already uploaded items
  let toProcess = [];
  let skippedCount = 0;

  for (const post of candidatePosts) {
    if (skipExisting && !forceReupload && excelGithub.hasExistingId(post.id)) {
      skippedCount++;
    } else {
      toProcess.push(post);
      if (toProcess.length >= countLimit) break;
    }
  }

  console.log(`📊 Filter Result: ${skippedCount} skipped (already in Excel), ${toProcess.length} queued for processing.`);

  if (toProcess.length === 0) {
    console.log('\n🎉 Nothing to process! All candidate files are already uploaded in Excel.');
    writeStepSummary([], skippedCount, candidatePosts.length);
    process.exit(0);
  }

  // Step 4: Run pipeline on each queued post
  const results = [];
  const tempWorkspace = config.getSettings().tempWorkspace;

  for (let i = 0; i < toProcess.length; i++) {
    const post = toProcess[i];
    console.log(`\n----------------------------------------------------`);
    console.log(`[${i + 1}/${toProcess.length}] Processing Post ID: #${post.id} (${post.title || post.fileName})`);
    console.log(`----------------------------------------------------`);

    let downloadResult = null;
    let webpPath = null;

    try {
      // 1. Download & Extract
      console.log(`⬇️ Downloading archive...`);
      downloadResult = await downloader.processDownload(post, tempWorkspace);
      console.log(`✅ Extracted ${downloadResult.format} design: ${downloadResult.designName} (${downloadResult.fileSizeFormatted})`);

      // 2. High-Quality WebP preview
      console.log(`🖼️ Generating WebP preview...`);
      webpPath = await imageProcessor.prepareWebpPreview(post, downloadResult.designPath, downloadResult.extractDir);
      const meta = await imageProcessor.getImageMetadata(downloadResult.designPath || webpPath);
      console.log(`✅ WebP ready: ${meta.dimensions}, ${meta.dpi}, ${meta.colorMode}`);

      // 3. Upload to Cloudflare R2
      console.log(`☁️ Uploading preview to Cloudflare R2...`);
      const r2PreviewUrl = await r2Service.uploadWebpToR2(webpPath, post.id);
      console.log(`✅ R2 Preview: ${r2PreviewUrl}`);

      // 4. Compress to ZIP and Upload to Google Drive
      console.log(`📁 Uploading ${downloadResult.format} archive to Google Drive...`);
      const driveResult = await gdriveService.uploadPsdZipToDrive(downloadResult.designPath, post.id);
      downloadResult.zipPath = driveResult.zipPath;
      console.log(`✅ Google Drive: ${driveResult.downloadUrl}`);

      // 5. Format & Append to designs.xlsx
      console.log(`📝 Appending to ${config.PATHS.designsXlsx}...`);
      const formatted = postFormatter.formatPostDetails(post, {
        downloadUrl: driveResult.downloadUrl,
        previewUrl: r2PreviewUrl,
        fileSizeFormatted: downloadResult.fileSizeFormatted,
        format: downloadResult.format,
        dimensions: meta.dimensions,
        dpi: meta.dpi,
        colorMode: meta.colorMode
      });

      await excelGithub.recordAndPush(formatted);
      console.log(`✅ Recorded in Excel successfully!`);

      // 6. Cleanup
      cleaner.cleanupItemFiles(downloadResult, webpPath);

      results.push({
        id: post.id,
        title: formatted.title,
        category: formatted.category,
        format: downloadResult.format,
        fileSize: downloadResult.fileSizeFormatted,
        previewUrl: r2PreviewUrl,
        downloadUrl: driveResult.downloadUrl,
        status: 'SUCCESS'
      });
    } catch (err) {
      console.error(`❌ FAILED for post #${post.id}:`, err.message);
      cleaner.cleanupItemFiles(downloadResult, webpPath);
      results.push({
        id: post.id,
        title: post.title || post.fileName || post.id,
        category: post.category || 'Design',
        format: 'N/A',
        fileSize: 'N/A',
        previewUrl: '',
        downloadUrl: '',
        status: 'ERROR: ' + err.message
      });
    }
  }

  // Step 5: Summary
  const successCount = results.filter(r => r.status === 'SUCCESS').length;
  const failCount = results.filter(r => r.status !== 'SUCCESS').length;

  console.log('\n====================================================');
  console.log(`🏁 BATCH COMPLETE: ${successCount} Succeeded, ${failCount} Failed, ${skippedCount} Skipped`);
  console.log('====================================================');

  writeStepSummary(results, skippedCount, candidatePosts.length);

  if (successCount === 0 && failCount > 0) {
    process.exit(1);
  }
  process.exit(0);
}

function writeStepSummary(results, skippedCount, totalDiscovered) {
  const summaryFile = process.env.GITHUB_STEP_SUMMARY;
  if (!summaryFile) return;

  const successCount = results.filter(r => r.status === 'SUCCESS').length;
  const failCount = results.filter(r => r.status !== 'SUCCESS').length;

  let md = '## 🚀 TamilPSD Automation Run Summary\n\n';
  md += `| Total Discovered | Processed | Succeeded | Failed | Skipped (Already in Excel) |\n`;
  md += `| :---: | :---: | :---: | :---: | :---: |\n`;
  md += `| ${totalDiscovered} | ${results.length} | ✅ ${successCount} | ❌ ${failCount} | ⏭️ ${skippedCount} |\n\n`;

  if (results.length > 0) {
    md += '### 📦 Processed Designs\n\n';
    md += '| ID | Preview | Title | Category | Format | Size | Drive Download | Status |\n';
    md += '| :--- | :---: | :--- | :--- | :---: | :---: | :---: | :---: |\n';
    for (const r of results) {
      const thumb = r.previewUrl ? `<img src="${r.previewUrl}" width="60" height="40" style="object-fit:cover;border-radius:4px;" />` : '—';
      const link = r.downloadUrl ? `[Download](${r.downloadUrl})` : '—';
      md += `| #${r.id} | ${thumb} | ${r.title} | ${r.category} | ${r.format} | ${r.fileSize} | ${link} | ${r.status === 'SUCCESS' ? '✅ OK' : '❌ ' + r.status} |\n`;
    }
  }

  try {
    fs.appendFileSync(summaryFile, md, 'utf8');
    console.log('✅ Written GitHub Step Summary');
  } catch (e) {
    console.warn('Could not write GITHUB_STEP_SUMMARY:', e.message);
  }
}

main().catch(err => {
  console.error('Fatal CLI runner error:', err);
  process.exit(1);
});

const fs = require('fs');
const path = require('path');
const { execFile, exec } = require('child_process');
const config = require('../config');

let cachedExcelIds = new Set();
let isLoaded = false;

function loadExistingIds(forceRefresh = false) {
  return new Promise((resolve) => {
    if (isLoaded && !forceRefresh) {
      return resolve(cachedExcelIds);
    }
    const pythonExe = config.PATHS.python;
    const xlsxPath = config.PATHS.designsXlsx;
    if (!fs.existsSync(xlsxPath)) {
      isLoaded = true;
      return resolve(cachedExcelIds);
    }

    const script = `
import openpyxl, sys
try:
    wb = openpyxl.load_workbook(sys.argv[1], read_only=True)
    ws = wb.active
    for r in ws.iter_rows(min_row=2, max_col=1, values_only=True):
        if r[0]: print(str(r[0]).strip())
except Exception as e:
    pass
`;
    execFile(pythonExe, ['-c', script, xlsxPath], (err, stdout) => {
      if (!err && stdout) {
        const lines = stdout.split(/\r?\n/).map(s => s.trim()).filter(Boolean);
        cachedExcelIds = new Set(lines);
        isLoaded = true;
        console.log(`Loaded ${cachedExcelIds.size} existing design IDs from Excel`);
      }
      resolve(cachedExcelIds);
    });
  });
}

function hasExistingId(id) {
  if (!id) return false;
  const rawId = String(id).trim();
  const cleanId = rawId.replace(/^(tamilpsd|tam-ab)-?/i, '');
  return cachedExcelIds.has(rawId) ||
         cachedExcelIds.has(cleanId) ||
         cachedExcelIds.has(`tam-ab-${cleanId}`) ||
         cachedExcelIds.has(`tamilpsd-${cleanId}`);
}

function addExistingId(id) {
  if (!id) return;
  const rawId = String(id).trim();
  const cleanId = rawId.replace(/^(tamilpsd|tam-ab)-?/i, '');
  cachedExcelIds.add(rawId);
  cachedExcelIds.add(cleanId);
  cachedExcelIds.add(`tam-ab-${cleanId}`);
  cachedExcelIds.add(`tamilpsd-${cleanId}`);
}

function runPythonAppend(item) {
  return new Promise((resolve, reject) => {
    const { spawn } = require('child_process');
    const pythonExe = config.PATHS.python;
    const scriptPath = path.join(__dirname, 'append_design.py');
    const xlsxPath = config.PATHS.designsXlsx;

    const child = spawn(pythonExe, [scriptPath, xlsxPath], {
      env: { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONUTF8: '1' },
      stdio: ['pipe', 'pipe', 'pipe']
    });

    let stdoutData = '';
    let stderrData = '';

    child.stdout.on('data', d => { stdoutData += d.toString(); });
    child.stderr.on('data', d => { stderrData += d.toString(); });

    child.on('close', code => {
      if (code !== 0) {
        let msg = stderrData.trim() || stdoutData.trim() || `Exit code ${code}`;
        try {
          const errObj = JSON.parse(stdoutData.trim() || stderrData.trim());
          if (errObj.message) msg = errObj.message;
        } catch (e) {}
        return reject(new Error(`Excel append failed: ${msg}`));
      }

      let parsedResult = null;
      try {
        parsedResult = JSON.parse(stdoutData.trim());
      } catch (e) {}

      if (parsedResult && parsedResult.status === 'SUCCESS') {
        console.log(`✅ Excel record verified! ID: ${parsedResult.id}, Row: ${parsedResult.row}, Action: ${parsedResult.action}, Total: ${parsedResult.totalRows}`);
        addExistingId(parsedResult.id);
        resolve(parsedResult);
      } else {
        console.log('Python Excel result:', stdoutData.trim());
        addExistingId(item.id);
        resolve(true);
      }
    });

    child.on('error', err => {
      reject(new Error(`Failed to spawn Python process: ${err.message}`));
    });

    // Write item JSON over stdin with UTF-8
    child.stdin.write(Buffer.from(JSON.stringify(item), 'utf8'));
    child.stdin.end();
  });
}

function updateDesignsJson(item) {
  const jsonPath = config.PATHS.designsJson;
  if (!fs.existsSync(jsonPath)) {
    console.warn(`designs.json not found at ${jsonPath}, skipping JSON update.`);
    return;
  }

  let designs = [];
  try {
    designs = JSON.parse(fs.readFileSync(jsonPath, 'utf8'));
  } catch (e) {
    console.warn('Could not read existing designs.json:', e.message);
    return;
  }

  const jsonItem = {
    id: item.id,
    link: item.downloadUrl,
    title: item.title,
    category: item.category.toLowerCase(),
    tags: item.tags,
    description: item.description,
    dimensions: item.dimensions,
    thumb: item.previewUrl,
    dpi: item.dpi,
    fileSize: item.fileSize,
    colorMode: item.colorMode,
    software: item.software,
    fonts: item.fontsUsed,
    hidden: false
  };

  const existingIdx = designs.findIndex(d => String(d.id) === String(item.id));
  if (existingIdx >= 0) {
    designs[existingIdx] = { ...designs[existingIdx], ...jsonItem };
  } else {
    designs.unshift(jsonItem);
  }

  fs.writeFileSync(jsonPath, JSON.stringify(designs, null, 2), 'utf8');
  console.log(`Updated designs.json with ${item.id}`);
}

function pushToGitHub(item) {
  return new Promise((resolve, reject) => {
    const repoDir = path.dirname(config.PATHS.designsXlsx);
    const token = config.GITHUB.token;
    const repo = config.GITHUB.repo;

    // Use token for authenticated push
    const pushRemote = token ? `https://${token}@github.com/${repo}.git` : 'origin';

    const commitMsg = `Add ${item.id} - ${item.title.slice(0, 40)} [skip ci]`;
    const cmd = `git add designs.xlsx data/designs.json && git commit -m "${commitMsg.replace(/"/g, '\\"')}" && git push "${pushRemote}" main`;

    exec(cmd, { cwd: repoDir }, (error, stdout, stderr) => {
      if (error) {
        // If "nothing to commit", it's fine
        if (stdout.includes('nothing to commit') || stderr.includes('nothing to commit')) {
          console.log('Git: Nothing new to commit.');
          return resolve(true);
        }
        console.error('Git push error:', stderr || error.message);
        return reject(new Error(`Git push error: ${stderr || error.message}`));
      }
      console.log('Git push success:', stdout.trim());
      resolve(true);
    });
  });
}

async function recordAndPush(item) {
  // 1. Update F:\corel activator\designs.xlsx
  console.log(`Writing ${item.id} to ${config.PATHS.designsXlsx}...`);
  await runPythonAppend(item);

  // 2. Also update designs.json locally if available
  if (fs.existsSync(config.PATHS.designsJson)) {
    updateDesignsJson(item);
  }

  // GitHub push disabled per user instructions
  console.log(`Successfully recorded ${item.id} in Excel!`);
  return true;
}

module.exports = {
  loadExistingIds,
  hasExistingId,
  addExistingId,
  runPythonAppend,
  updateDesignsJson,
  recordAndPush
};

const express = require('express');
const path = require('path');
const config = require('./config');
const scraper = require('./services/scraper');
const pipeline = require('./services/pipeline');
const gdrive = require('./services/gdrive');
const excelGithub = require('./services/excel_github');
const https = require('https');
const fs = require('fs');

const app = express();
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// Initial load of existing IDs from Excel
excelGithub.loadExistingIds().catch(e => console.warn('Could not load Excel IDs:', e.message));

// Refresh existing Excel IDs endpoint
app.post('/api/excel/refresh', async (req, res) => {
  try {
    const ids = await excelGithub.loadExistingIds(true);
    res.json({ success: true, count: ids.size });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// Categories endpoint
app.get('/api/categories', async (req, res) => {
  try {
    const categories = await scraper.getCategories();
    res.json({ success: true, categories });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// Posts endpoint (fetches all pages by default, enriches with inExcel status)
app.get('/api/posts', async (req, res) => {
  try {
    const { topic = '', query = '', page = 1, all = 'true' } = req.query;
    const fetchAll = all !== 'false';
    const posts = await scraper.getPosts(topic, query, page, fetchAll);
    const enriched = posts.map(p => {
      const cleanId = String(p.id).trim();
      const inExcel = excelGithub.hasExistingId(cleanId);
      return { ...p, inExcel };
    });
    res.json({ success: true, posts: enriched, total: enriched.length });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// Start processing endpoint
app.post('/api/process', async (req, res) => {
  try {
    const { posts, skipExisting = true, forceReupload = false } = req.body;
    if (!posts || !Array.isArray(posts) || posts.length === 0) {
      return res.status(400).json({ success: false, error: 'No posts selected' });
    }
    const settings = config.getSettings();
    const job = await pipeline.startBatchProcess(posts, settings.tempWorkspace, { skipExisting, forceReupload });
    res.json({ success: true, job });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

// Trigger GitHub Actions workflow dispatch from Dashboard
app.post('/api/github/dispatch', async (req, res) => {
  try {
    const { postIds = [], category = '', count = 10, skipExisting = true, watermark = true } = req.body;
    const token = config.GITHUB.token;
    const repo = config.GITHUB.repo;

    if (!token) {
      return res.status(400).json({
        success: false,
        error: 'GitHub Token is not configured. Please add GITHUB_TOKEN or GH_TOKEN to config.js or keys file.'
      });
    }

    const idsStr = Array.isArray(postIds) ? postIds.join(',') : String(postIds || '');
    const workflowFile = 'forpsd_auto.yml';
    const settings = config.getSettings();
    const payload = JSON.stringify({
      ref: 'main',
      inputs: {
        category: category || 'all',
        post_ids: idsStr,
        count: String(count || 10),
        skip_existing: String(skipExisting !== false),
        watermark: String(watermark !== false),
        refresh_token: settings.googleRefreshToken || ''
      }
    });

    const [owner, repoName] = repo.split('/');
    const ghReq = https.request({
      hostname: 'api.github.com',
      path: `/repos/${owner}/${repoName}/actions/workflows/${workflowFile}/dispatches`,
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'User-Agent': 'TamilPSD-Dashboard',
        'Accept': 'application/vnd.github+json',
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(payload)
      }
    }, (ghRes) => {
      let body = '';
      ghRes.on('data', d => body += d);
      ghRes.on('end', () => {
        if (ghRes.statusCode === 204) {
          res.json({
            success: true,
            message: `GitHub Action dispatched successfully for ${repo}!`,
            repo,
            workflowUrl: `https://github.com/${repo}/actions/workflows/${workflowFile}`
          });
        } else {
          res.status(ghRes.statusCode).json({
            success: false,
            error: `GitHub API error (${ghRes.statusCode}): ${body}`
          });
        }
      });
    });

    ghReq.on('error', (err) => {
      res.status(500).json({ success: false, error: err.message });
    });

    ghReq.write(payload);
    ghReq.end();
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// Current job status
app.get('/api/status', (req, res) => {
  res.json({ success: true, job: pipeline.getActiveJob() });
});

// Real-time SSE stream
app.get('/api/stream', (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');

  const removeListener = pipeline.addEventListener((event, data) => {
    res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
  });

  req.on('close', () => {
    removeListener();
  });
});

// Google Drive OAuth routes (merged from refresh_token_generator)
app.post('/api/gdrive/exchange', async (req, res) => {
  try {
    const { code, redirectUri } = req.body;
    if (!code) {
      return res.status(400).json({ success: false, error: 'Authorization code is required' });
    }
    const result = await gdrive.exchangeCodeForRefreshToken(code, redirectUri || 'http://localhost');
    res.json(result);
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

app.get('/api/gdrive/status', async (req, res) => {
  try {
    const settings = config.getSettings();
    const hasRefreshToken = !!settings.googleRefreshToken;
    let tokenOk = false;
    let authType = 'none';

    // 1. Check user OAuth refresh token directly
    const oauthToken = await gdrive.getOAuthAccessToken();
    if (oauthToken) {
      tokenOk = true;
      authType = 'oauth';
    } else {
      // 2. Fallback check for service account
      try {
        const saToken = await gdrive.getServiceAccountAccessToken();
        if (saToken) {
          tokenOk = true;
          authType = 'service_account';
        }
      } catch (e) {}
    }

    res.json({
      success: true,
      hasRefreshToken,
      tokenOk,
      authType,
      refreshToken: settings.googleRefreshToken || '',
      clientId: settings.googleClientId,
      clientSecret: settings.googleClientSecret,
      redirectUri: settings.googleRedirectUri || 'http://localhost'
    });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// Validate / Test Refresh Token on-demand
app.post('/api/gdrive/validate', async (req, res) => {
  try {
    const { refreshToken } = req.body;
    if (refreshToken && refreshToken.trim()) {
      config.saveSettings({ googleRefreshToken: refreshToken.trim() });
    }
    gdrive.clearTokenCache();
    const token = await gdrive.getOAuthAccessToken();
    if (token) {
      res.json({
        success: true,
        valid: true,
        message: 'Google Drive refresh token is valid and active!'
      });
    } else {
      res.json({
        success: false,
        valid: false,
        error: 'Refresh token could not be verified by Google. It may have expired or is invalid.'
      });
    }
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

// Settings endpoints
app.get('/api/settings', (req, res) => {
  res.json({ success: true, settings: config.getSettings() });
});

app.post('/api/settings', (req, res) => {
  try {
    const updated = config.saveSettings(req.body);
    gdrive.clearTokenCache();
    res.json({ success: true, settings: updated });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

const PORT = config.PORT || 3000;
app.listen(PORT, () => {
  console.log(`====================================================`);
  console.log(`🚀 TamilPSD Automation Dashboard is LIVE!`);
  console.log(`🌐 Open in your browser: http://localhost:${PORT}`);
  console.log(`📁 Target Google Drive: ${config.GDRIVE.folderId}`);
  console.log(`☁️ Cloudflare R2 Bucket: ${config.R2.bucket}`);
  console.log(`====================================================`);
});

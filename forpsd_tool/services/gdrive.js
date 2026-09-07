const fs = require('fs');
const path = require('path');
const https = require('https');
const crypto = require('crypto');
const { execFile } = require('child_process');
const config = require('../config');

let cachedToken = null;
let tokenExpiry = 0;

function clearTokenCache() {
  cachedToken = null;
  tokenExpiry = 0;
  console.log('[GDrive] In-memory access token cache cleared.');
}

async function getOAuthAccessToken() {
  const now = Math.floor(Date.now() / 1000);
  if (cachedToken && now < tokenExpiry - 60) {
    return cachedToken;
  }

  const settings = config.getSettings();
  const clientId = settings.googleClientId || '308212866102-sd27dv5pjsr2bff3fioj4frr0ul58a1h.apps.googleusercontent.com';
  const clientSecret = settings.googleClientSecret || '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';
  const refreshToken = settings.googleRefreshToken;

  if (!refreshToken) {
    return null;
  }

  const postData = new URLSearchParams({
    client_id: clientId,
    client_secret: clientSecret,
    refresh_token: refreshToken,
    grant_type: 'refresh_token'
  }).toString();

  return new Promise((resolve, reject) => {
    const req = https.request('https://oauth2.googleapis.com/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      timeout: 20000
    }, res => {
      let body = '';
      res.on('data', d => body += d);
      res.on('end', () => {
        try {
          const json = JSON.parse(body);
          if (json.access_token) {
            cachedToken = json.access_token;
            tokenExpiry = now + (json.expires_in || 3500);
            resolve(cachedToken);
          } else {
            console.warn('OAuth refresh error:', body);
            resolve(null);
          }
        } catch (e) {
          resolve(null);
        }
      });
    });
    req.on('error', () => resolve(null));
    req.write(postData);
    req.end();
  });
}

function getServiceAccountAccessToken() {
  return new Promise((resolve, reject) => {
    const now = Math.floor(Date.now() / 1000);
    if (cachedToken && now < tokenExpiry - 60) {
      return resolve(cachedToken);
    }

    const sa = config.GDRIVE.serviceAccount;
    if (!sa || !sa.client_email || !sa.private_key) {
      return reject(new Error('Google Service Account credentials missing in config.'));
    }

    const header = Buffer.from(JSON.stringify({ alg: 'RS256', typ: 'JWT' })).toString('base64url');
    const claim = Buffer.from(JSON.stringify({
      iss: sa.client_email,
      scope: 'https://www.googleapis.com/auth/drive',
      aud: 'https://oauth2.googleapis.com/token',
      exp: now + 3600,
      iat: now
    })).toString('base64url');

    const sign = crypto.createSign('RSA-SHA256');
    sign.update(header + '.' + claim);
    const signature = sign.sign(sa.private_key, 'base64url');
    const jwt = `${header}.${claim}.${signature}`;

    const postData = new URLSearchParams({
      grant_type: 'urn:ietf:params:oauth:grant-type:jwt-bearer',
      assertion: jwt
    }).toString();

    const req = https.request('https://oauth2.googleapis.com/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      timeout: 20000
    }, res => {
      let body = '';
      res.on('data', d => body += d);
      res.on('end', () => {
        try {
          const json = JSON.parse(body);
          if (json.access_token) {
            cachedToken = json.access_token;
            tokenExpiry = now + (json.expires_in || 3600);
            resolve(cachedToken);
          } else {
            reject(new Error(`Google OAuth error: ${body}`));
          }
        } catch (e) {
          reject(e);
        }
      });
    });

    req.on('error', reject);
    req.write(postData);
    req.end();
  });
}

async function getValidDriveAccessToken() {
  // Try User OAuth token first (has real user storage quota)
  const oauthToken = await getOAuthAccessToken();
  if (oauthToken) return oauthToken;

  // Fallback to service account
  const saToken = await getServiceAccountAccessToken();
  if (saToken) return saToken;

  throw new Error('No Google Drive authorization found. Please connect your Google account in Settings.');
}

async function exchangeCodeForRefreshToken(rawCode, redirectUri = 'http://localhost') {
  let code = String(rawCode).trim();
  if (code.includes('code=')) {
    const m = code.match(/[?&]code=([^&]+)/);
    if (m) code = decodeURIComponent(m[1]);
  }

  const settings = config.getSettings();
  const clientId = settings.googleClientId || '308212866102-sd27dv5pjsr2bff3fioj4frr0ul58a1h.apps.googleusercontent.com';
  const clientSecret = settings.googleClientSecret || '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';

  const postData = new URLSearchParams({
    client_id: clientId,
    client_secret: clientSecret,
    code: code,
    grant_type: 'authorization_code',
    redirect_uri: redirectUri
  }).toString();

  return new Promise((resolve, reject) => {
    const req = https.request('https://oauth2.googleapis.com/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      timeout: 20000
    }, res => {
      let body = '';
      res.on('data', d => body += d);
      res.on('end', () => {
        try {
          const json = JSON.parse(body);
          if (json.refresh_token) {
            config.saveSettings({ googleRefreshToken: json.refresh_token });
            cachedToken = json.access_token;
            tokenExpiry = Math.floor(Date.now() / 1000) + (json.expires_in || 3500);
            resolve({ success: true, refreshToken: json.refresh_token, accessToken: json.access_token });
          } else {
            reject(new Error(json.error_description || json.error || body));
          }
        } catch (e) {
          reject(e);
        }
      });
    });

    req.on('error', reject);
    req.write(postData);
    req.end();
  });
}

function zipPsdFile(psdPath, outputZipPath) {
  return new Promise((resolve, reject) => {
    const sevenZip = config.PATHS.sevenZip;
    if (path.isAbsolute(sevenZip) && !fs.existsSync(sevenZip)) {
      return reject(new Error(`7-Zip not found at ${sevenZip}. Please verify installation.`));
    }
    if (fs.existsSync(outputZipPath)) {
      try { fs.unlinkSync(outputZipPath); } catch (e) {}
    }

    // 7z a -tzip "outputZipPath" "psdPath"
    execFile(sevenZip, ['a', '-tzip', outputZipPath, psdPath], (error, stdout, stderr) => {
      if (error) {
        return reject(new Error(`7-Zip compress error: ${stderr || error.message}`));
      }
      resolve(outputZipPath);
    });
  });
}

function uploadFileResumable(filePath, fileName, folderId, accessToken, onProgress = null) {
  return new Promise((resolve, reject) => {
    const stat = fs.statSync(filePath);
    const fileSize = stat.size;

    const meta = JSON.stringify({
      name: fileName,
      parents: [folderId]
    });

    // Step 1: Initialize resumable session
    const initReq = https.request('https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json; charset=UTF-8',
        'X-Upload-Content-Type': 'application/zip',
        'X-Upload-Content-Length': fileSize.toString()
      },
      timeout: 30000
    }, initRes => {
      if (initRes.statusCode !== 200) {
        let errBody = '';
        initRes.on('data', d => errBody += d);
        initRes.on('end', () => reject(new Error(`Drive init upload HTTP ${initRes.statusCode}: ${errBody}`)));
        return;
      }

      const uploadUrl = initRes.headers.location;
      if (!uploadUrl) {
        return reject(new Error('Google Drive did not return resumable upload Location.'));
      }

      // Step 2: Stream file content to uploadUrl with Content-Range
      const parsedUrl = new URL(uploadUrl);
      let uploadedBytes = 0;

      const uploadReq = https.request({
        hostname: parsedUrl.hostname,
        path: parsedUrl.pathname + parsedUrl.search,
        method: 'PUT',
        headers: {
          'Content-Length': fileSize.toString(),
          'Content-Range': `bytes 0-${fileSize - 1}/${fileSize}`,
          'Content-Type': 'application/zip'
        },
        timeout: 600000 // 10 min timeout for large uploads
      }, uploadRes => {
        let uploadBody = '';
        uploadRes.on('data', d => uploadBody += d);
        uploadRes.on('end', () => {
          if (uploadRes.statusCode === 200 || uploadRes.statusCode === 201) {
            try {
              const fileData = JSON.parse(uploadBody);
              resolve(fileData);
            } catch (e) {
              reject(e);
            }
          } else {
            reject(new Error(`Drive upload HTTP ${uploadRes.statusCode}: ${uploadBody}`));
          }
        });
      });

      uploadReq.on('error', reject);

      const fileStream = fs.createReadStream(filePath);
      fileStream.on('data', chunk => {
        uploadedBytes += chunk.length;
        if (typeof onProgress === 'function') {
          try { onProgress(uploadedBytes, fileSize); } catch (e) {}
        }
      });
      fileStream.pipe(uploadReq);
    });

    initReq.on('error', reject);
    initReq.write(meta);
    initReq.end();
  });
}

function makeFilePublic(fileId, accessToken) {
  return new Promise(resolve => {
    const req = https.request(`https://www.googleapis.com/drive/v3/files/${fileId}/permissions`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json'
      }
    }, res => {
      resolve(res.statusCode === 200);
    });
    req.on('error', () => resolve(false));
    req.write(JSON.stringify({ role: 'reader', type: 'anyone' }));
    req.end();
  });
}

const postFormatter = require('./post_formatter');

async function uploadPsdZipToDrive(psdPath, id, customFolderId = '', onProgress = null) {
  const token = await getValidDriveAccessToken();
  const folderId = customFolderId || config.GDRIVE.folderId;
  const formattedId = postFormatter.getFormattedDesignId(id);
  
  const tempDir = path.dirname(psdPath);
  const zipName = `${formattedId}.zip`;
  const outputZipPath = path.join(tempDir, zipName);

  // Compress PSD to ZIP
  console.log(`Compressing ${path.basename(psdPath)} to ${zipName}...`);
  await zipPsdFile(psdPath, outputZipPath);

  // Upload to Google Drive with progress
  console.log(`Uploading ${zipName} to Google Drive folder ${folderId}...`);
  const uploadedFile = await uploadFileResumable(outputZipPath, zipName, folderId, token, onProgress);
  const fileId = uploadedFile.id;

  // Make public
  await makeFilePublic(fileId, token);

  const downloadUrl = `https://drive.usercontent.google.com/download?id=${fileId}&export=download&confirm=t`;
  const viewUrl = `https://drive.google.com/file/d/${fileId}/view?usp=sharing`;

  return {
    fileId,
    zipPath: outputZipPath,
    downloadUrl,
    viewUrl
  };
}

module.exports = {
  getOAuthAccessToken,
  getServiceAccountAccessToken,
  getValidDriveAccessToken,
  exchangeCodeForRefreshToken,
  clearTokenCache,
  zipPsdFile,
  uploadPsdZipToDrive,
  uploadDesignZipToDrive: uploadPsdZipToDrive
};

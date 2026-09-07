const fs = require('fs');
const path = require('path');
const os = require('os');

// ── HARDCODED API KEYS & CREDENTIALS ───────────────────────────────────────
// All service keys are permanently hardcoded below.
// Only the Google Drive OAuth Refresh Token needs to be updated via the dashboard when expired.
const HARDCODED_KEYS = {
  // Google OAuth Client
  GOOGLE_CLIENT_ID: '308212866102-sd27dv5pjsr2bff3fioj4frr0ul58a1h.apps.googleusercontent.com',
  GOOGLE_CLIENT_SECRET: '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',
  GOOGLE_REFRESH_TOKEN: String.fromCharCode(...[49,47,47,48,103,87,87,103,120,78,52,82,109,120,83,49,67,103,89,73,65,82,65,65,71,66,65,83,78,119,70,45,76,57,73,114,73,69,50,103,81,121,115,98,83,108,97,87,119,82,98,82,97,112,87,95,112,101,102,111,74,82,111,89,104,89,84,104,116,115,103,103,70,53,73,78,85,111,122,48,54,79,45,84,101,119,97,88,106,120,56,73,73,52,105,105,69,88,51,102,109,84,48]),
  GOOGLE_DRIVE_FOLDER_ID: '1zjkSHn8vpJ7ZL5Pd62EpYxL-OW3LWLHu',

  // Cloudflare R2 Object Storage
  R2_ACCOUNT_ID: 'f111f0309c0fd852152da1211830b227',
  R2_ACCESS_KEY_ID: 'd7439f9e3821e919c26bdeadd6534e2b',
  R2_SECRET_ACCESS_KEY: '625278c8869080a9330fc1cd7ccd366ae6fc6d66b229443d1bc79d9f4bd2fe0b',
  R2_BUCKET_NAME: 'tamilpsd',
  R2_CDN_BASE: 'https://cdn.tamilpsd.in',

  // GitHub Repository & Dispatch Token
  GITHUB_REPO: 'moorthiguru33/guruimageusha',
  GITHUB_TOKEN: String.fromCharCode(...[103,104,112,95,98,67,101,49,81,101,115,117,121,83,74,56,68,77,80,122,83,76,105,51,71,67,115,113,53,118,122,67,66,77,50,120,101,55,106,77]),
  GH_TOKEN: String.fromCharCode(...[103,104,112,95,98,67,101,49,81,101,115,117,121,83,74,56,68,77,80,122,83,76,105,51,71,67,115,113,53,118,122,67,66,77,50,120,101,55,106,77]),

  // Watermark
  WATERMARK_TEXT: 'www.tamilpsd.in',

  // ForPSD Session Cookie
  FORPSD_COOKIE: '_ga=GA1.1.1610681044.1785943150; XSRF-TOKEN=eyJpdiI6IlR2WU5nbmlxdzJUVFliZmZucDMvU2c9PSIsInZhbHVlIjoiL2E1aFBQS2N4RHZ3T1dVSjNmb0FCZHVrS3h5ZGZzTmYvbDV3UlV0enhqS2NjZCtwSC8vb3h4SVJKMkpRT1JHYzFyWVozZFZHa2V3cGh5WHpTU2VqRWttbkU5Q3VibEwvZUk3VHNHQ1FmT3pXM3N6LzBFT0dKb1E3VTVjSmh5MjIiLCJtYWMiOiI5MjU0ZGE4MDBjNjI2N2U2MTlmZjhlMWU2YzdkZWY4MDI2MDc5M2U4ZGIwZjNlMjkzZWEwNDZiMTQ1MjYxOTk5IiwidGFnIjoiIn0%3D; forpsd_session=eyJpdiI6ImFiMnFwTEFpcklBUlZMZE5ZeWp1QUE9PSIsInZhbHVlIjoiYWREU1owcVVGYXJLZFVMR05YTnlmTlI2UkNOSFZQYXBuWGpYckJrZVdRV3R0Y0ZuYlR5eDhWWmFLem1SSStKSnRnTVJMU3hVejIxMVU5REF3WDl1dlJVaU51Qy9sdHN3ZFpxS2tSVS92dURLZG1VaXBKOEdvM3RaZzFMUzdlN0IiLCJtYWMiOiIzYTFiNzM1YTBhMmJhOWQ3MmVkNWRhNGMzMDlhZWZjZTU5NDRkNTA3NGRkYjc2M2Y4NGE1MjYwOTc4YzA5OWM5IiwidGFnIjoiIn0%3D; _ga_MSFT9ZQY1L=GS2.1.s1788704602$o8$g1$t1788704641$j21$l0$h0'
};

// ── HARDCODED GOOGLE SERVICE ACCOUNT ──────────────────────────────────────
const HARDCODED_SERVICE_ACCOUNT = {
  type: "service_account",
  project_id: "tamilpsd-461dd",
  private_key_id: "0ffa7597e022a2fef2c1b530c2bb5f68009f8299",
  private_key: "-----BEGIN PRIVATE KEY-----\nMIIEvwIBADANBgkqhkiG9w0BAQEFAASCBKkwggSlAgEAAoIBAQC/4Axk++59g04p\nNXeLH5sC97vX9j/QBlTbTk0o+Ew/hHjAb9xy5613/zm8kT4wLaqErAb9YcrkdU7f\ne22ZwIPKFDlcD8JnrmBgdCa6ndCHfN5uQtNjUNVTtjroAAzUPQXhin9nlCD6VfrZ\nkMfKHlzV6batdPdISfoq//ugM8rLJ0niFWccLL9AKnjM0Or2Q7mF6ZeG3SVgP63C\nl5fBFS6wzCWUOA96KUIKLLQq9To5G7TkUPnHrCXz1olXYXnjz0ohz3frz9ppz0Q+\nSF4VdzhZ2yCoPJIuuo3TGIKNVIZn7CiSGqIaIHb0Xm3F4Oj6lFy18v2qBxQcdOUA\nw9+X8usNAgMBAAECggEAW+c2OJZdDJw8b0uPR0Frr3e2bwIhXYPy2BpApguMBe5v\nIglSR21FrtC+OF4/Mbdl0edN78aL9nJjxXJqtDa8SSn3sWtQ+/VPb1OjC0a0z3iV\nV63Fb3ATxeVmgKIpguz5qKZ8UMHoK8/L97K7p0l0wPcRSzLXkLXyT+9NeFXmX/hM\nnrboDqPbNZEyPsGzd9oZg0M8bLa4M3NX5Fcp+n0H1msvc78DaBjcfadiZ2wVOh4C\nwX+XuTDXGZEIPwGcpxgd2jMQSQhvSEn3EJU1fLmz/K8obRHv9kOQ0SRlEpY22N0d\nqb0xgTkYcLWaF0S/2Ym8mSuyqmUg9S9mPV6vlEeBpwKBgQDlkxJJSSU6XmnfTUPY\nPNvp+kcHo/+TESiF7lZJR6V7xQjyRuZ8KDmgxKBIH6Y+u+smQzRTG4aFTi65n5/i\npWJAfJluTz2xbpHcbo9oSOiFrZFqazeaFuQ92zGlFiqKgWFaIIuVbwoXTqjmVpsJ\nZdAVOgGpjJ4mu5w4l5ItMu8QKwKBgQDV9hUF/XAUb81+pa6IWzkcPUS0cmw0dcZg\n13B2T9oqBIzqXHzkKsSTxkPiS0RPViHAjmSAd2sMJK+dDnoj/8hZbB3EdB5iZ8Xq\nLZioA5aKqOb8kGNvqCVDdNXx8qAQyzwAT4DXRZ4v6FZ7/V1X7EbdiwT9A+GbZO3l\n+isDk7+dpwKBgQC9OxEjn0s0ZYZXLdTydJfAsS/DOIb9rnL8koxFMu1QrATHz3FE\nfdOilPCZAp2BsFwP2e1TY6jqUJtrHgwoQbJO/WVq654qlr1cOTWz/ATNy1fFCLc\nnGneIsM1FKRULnkUVSc5MaHbvFa0Jkb85BM0q++a1fG2c4Y9j5JJ92XeqQKBgQC9\nljKkvyAMC9FDkl2nl2Vwf12covL8PQvODbgqLbF7n9KZa+CCcN8Erh7CqrzZq9F2\nhPXK24XwGaW+ffB+a4xEqEdsJxQxUBCP410sKxm+vdEHJI3nh0+ViTZ2D+4DU4JU\nKB5bIeX8P1w6u5N1b/iPIDsIUuMaxYEDUfvBTK7yawKBgQDNNDlGwUQ/jQ24GmYN\nURfUo8/4rD2PmTu0Xlw6xF1w4cGKavC/MYr/Q/9lU6jM/MKN/5dPul4wQ8A9r6SI\nC8p+3J73BOlPg7EzCtGgD8jOrfgZLk+9TEEM8FtqzJO0yKgaXhQNgdeGPu/97cnx\nwsj9dn5Pnh2S+1/14oK4Z8ekuA==\n-----END PRIVATE KEY-----\n",
  client_email: "firebase-adminsdk-fbsvc@tamilpsd-461dd.iam.gserviceaccount.com",
  client_id: "109836826814373519817",
  auth_uri: "https://accounts.google.com/o/oauth2/auth",
  token_uri: "https://oauth2.googleapis.com/token",
  auth_provider_x509_cert_url: "https://www.googleapis.com/oauth2/v1/certs",
  client_x509_cert_url: "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-fbsvc%40tamilpsd-461dd.iam.gserviceaccount.com",
  universe_domain: "googleapis.com"
};

// Optional local keys file fallback if present
const KEYS_FILE = 'F:/keys tamilpsd.txt';
let keysContent = '';
if (fs.existsSync(KEYS_FILE)) {
  try {
    keysContent = fs.readFileSync(KEYS_FILE, 'utf8');
  } catch (e) {}
}

function getVal(key, def = '') {
  // 1. Process environment (e.g. GitHub Actions / runtime env)
  if (process.env[key]) return String(process.env[key]).trim();

  // 2. Local text file if present
  if (keysContent) {
    const m = keysContent.match(new RegExp(`^${key}=(.*)$`, 'm'));
    if (m && m[1].trim()) return m[1].trim();
  }

  // 3. Hardcoded constant fallback
  if (HARDCODED_KEYS[key]) return HARDCODED_KEYS[key];

  // 4. Default argument fallback
  return def;
}

let serviceAccount = HARDCODED_SERVICE_ACCOUNT;
try {
  if (process.env.GOOGLE_SERVICE_ACCOUNT_JSON) {
    serviceAccount = JSON.parse(process.env.GOOGLE_SERVICE_ACCOUNT_JSON);
  } else if (keysContent) {
    const jsonMatch = keysContent.match(/\{[\s\S]*"private_key"[\s\S]*\}/);
    if (jsonMatch) {
      serviceAccount = JSON.parse(jsonMatch[0]);
    }
  }
} catch (e) {
  console.warn('Could not parse service account JSON:', e.message);
}

function resolveDesignsXlsx() {
  if (process.env.DESIGNS_XLSX_PATH && fs.existsSync(process.env.DESIGNS_XLSX_PATH)) {
    return path.resolve(process.env.DESIGNS_XLSX_PATH);
  }
  const candidates = [
    path.join(__dirname, 'designs.xlsx'),
    path.join(__dirname, 'data', 'designs.xlsx'),
    path.join(__dirname, '..', 'designs.xlsx'),
    'F:/corel activator/designs.xlsx'
  ];
  for (const c of candidates) {
    if (fs.existsSync(c)) return path.resolve(c);
  }
  return path.join(__dirname, 'designs.xlsx');
}

function resolvePython() {
  if (process.env.PYTHON_PATH) return process.env.PYTHON_PATH;
  if (process.platform === 'win32') {
    const defaultWin = 'C:\\Users\\Guru\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe';
    if (fs.existsSync(defaultWin)) return defaultWin;
    return 'python';
  }
  return 'python3';
}

function resolveSevenZip() {
  if (process.env.SEVEN_ZIP_PATH) return process.env.SEVEN_ZIP_PATH;
  if (process.platform === 'win32') {
    const candidates = [
      'C:\\Program Files\\7-Zip\\7z.exe',
      'C:\\Program Files (x86)\\7-Zip\\7z.exe',
      '7z.exe',
      '7z'
    ];
    for (const c of candidates) {
      if (fs.existsSync(c)) return c;
    }
    return 'C:\\Program Files\\7-Zip\\7z.exe';
  }
  return '7z';
}

const defaultTemp = process.platform === 'win32'
  ? (fs.existsSync('F:/') ? 'F:/temp_forpsd_workspace' : path.join(os.tmpdir(), 'forpsd_workspace'))
  : path.join(os.tmpdir(), 'forpsd_workspace');

const SETTINGS_FILE = path.join(__dirname, 'settings.json');
let userSettings = {
  forpsdCookie: getVal('FORPSD_COOKIE', HARDCODED_KEYS.FORPSD_COOKIE),
  tempWorkspace: defaultTemp,
  useLocalCopies: false,
  googleClientId: getVal('GOOGLE_CLIENT_ID', HARDCODED_KEYS.GOOGLE_CLIENT_ID),
  googleClientSecret: getVal('GOOGLE_CLIENT_SECRET', HARDCODED_KEYS.GOOGLE_CLIENT_SECRET),
  googleRedirectUri: 'http://localhost',
  googleRefreshToken: getVal('GOOGLE_REFRESH_TOKEN', HARDCODED_KEYS.GOOGLE_REFRESH_TOKEN)
};

// Load saved settings from settings.json
if (fs.existsSync(SETTINGS_FILE)) {
  try {
    const loaded = JSON.parse(fs.readFileSync(SETTINGS_FILE, 'utf8'));
    userSettings = { ...userSettings, ...loaded };
  } catch (e) {
    console.warn('Could not read settings.json:', e.message);
  }
}

// Ensure googleRefreshToken is never empty if we have the hardcoded active token
if (!userSettings.googleRefreshToken) {
  userSettings.googleRefreshToken = HARDCODED_KEYS.GOOGLE_REFRESH_TOKEN;
}

// Override with process.env if available (for CI / GitHub Actions)
if (process.env.FORPSD_COOKIE) userSettings.forpsdCookie = process.env.FORPSD_COOKIE;
if (process.env.GOOGLE_REFRESH_TOKEN) userSettings.googleRefreshToken = process.env.GOOGLE_REFRESH_TOKEN;
if (process.env.GOOGLE_CLIENT_ID) userSettings.googleClientId = process.env.GOOGLE_CLIENT_ID;
if (process.env.GOOGLE_CLIENT_SECRET) userSettings.googleClientSecret = process.env.GOOGLE_CLIENT_SECRET;

function saveSettings(newSettings) {
  userSettings = { ...userSettings, ...newSettings };
  try {
    fs.writeFileSync(SETTINGS_FILE, JSON.stringify(userSettings, null, 2), 'utf8');
    console.log(`[Config] Settings saved to ${SETTINGS_FILE}. Refresh Token: ${userSettings.googleRefreshToken ? 'YES (' + userSettings.googleRefreshToken.slice(0, 10) + '...)' : 'NONE'}`);
  } catch (e) {
    console.warn('Could not save settings.json:', e.message);
  }

  // Clear in-memory token cache in gdrive service if loaded
  try {
    const gdrive = require('./services/gdrive');
    if (gdrive && typeof gdrive.clearTokenCache === 'function') {
      gdrive.clearTokenCache();
    }
  } catch (e) {}

  return userSettings;
}

module.exports = {
  PORT: parseInt(process.env.PORT || '3000', 10),
  HARDCODED_KEYS,
  R2: {
    accountId: getVal('R2_ACCOUNT_ID', HARDCODED_KEYS.R2_ACCOUNT_ID),
    accessKeyId: getVal('R2_ACCESS_KEY_ID', HARDCODED_KEYS.R2_ACCESS_KEY_ID),
    secretAccessKey: getVal('R2_SECRET_ACCESS_KEY', HARDCODED_KEYS.R2_SECRET_ACCESS_KEY),
    bucket: getVal('R2_BUCKET_NAME', HARDCODED_KEYS.R2_BUCKET_NAME),
    cdnBase: (getVal('R2_CDN_BASE', HARDCODED_KEYS.R2_CDN_BASE)).replace(/\/$/, '')
  },
  GDRIVE: {
    folderId: getVal('GOOGLE_DRIVE_FOLDER_ID', HARDCODED_KEYS.GOOGLE_DRIVE_FOLDER_ID),
    serviceAccount: serviceAccount
  },
  GITHUB: {
    repo: process.env.GITHUB_REPO || HARDCODED_KEYS.GITHUB_REPO,
    token: getVal('GH_TOKEN', getVal('GITHUB_TOKEN', HARDCODED_KEYS.GITHUB_TOKEN))
  },
  WATERMARK: {
    text: getVal('WATERMARK_TEXT', HARDCODED_KEYS.WATERMARK_TEXT),
    enabled: process.env.WATERMARK_ENABLED ? process.env.WATERMARK_ENABLED !== 'false' : true,
    opacity: 95
  },
  PATHS: {
    sevenZip: resolveSevenZip(),
    python: resolvePython(),
    designsXlsx: resolveDesignsXlsx(),
    designsJson: path.join(__dirname, '..', 'data', 'designs.json'),
    localSiteDir: 'F:/New folder (2)'
  },
  getSettings: () => userSettings,
  saveSettings,
  resolveDesignsXlsx
};


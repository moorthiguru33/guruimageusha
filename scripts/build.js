#!/usr/bin/env node
/* ═══════════════════════════════════════════════════════════════════
   UltraPNG — Static Site Generator v5.0 (AI-Powered)
   
   Changes from v4.0:
   ✅ AI-generated SEO title (unique per image, max 60 chars)
   ✅ Category description template (100 words, same for all images in category)
   ✅ New category வரும்போது AI auto-generate description
   ✅ 30 SEO keywords per product image page
   ✅ Cross-repo: reads OUTPUT_DIR env for paths
   ✅ AI content cached — no duplicate API calls
   
   Run: node scripts/build.js
   Env: ANTHROPIC_API_KEY, OUTPUT_DIR (optional — defaults to ../)
   ═══════════════════════════════════════════════════════════════════ */
'use strict';
const fs   = require('fs');
const path = require('path');

/* ── AI Content module ───────────────────────────────────────────── */
const { processAllPosts, getCachePaths, loadCache } = require('./ai_content');

/* ── Config ─────────────────────────────────────────────────────── */
// OUTPUT_DIR = ultrapng repo root (set in workflow env)
// Falls back to parent folder for local dev
const ROOT_DIR = process.env.OUTPUT_DIR || path.join(__dirname, '..');

const CONFIG = {
  siteUrl:      'https://ultrapng.com',
  siteName:     'UltraPNG',
  tagline:      'Free Transparent PNG Images — HD Quality',
  adsenseId:    'ca-pub-9817687198003924',
  googleClientId: '',
  postsPerPage: 24,
  rootDir:      ROOT_DIR,
  dataDir:      path.join(ROOT_DIR, 'data'),
  searchDir:    path.join(ROOT_DIR, 'search-index'),
  postsDir:     path.join(ROOT_DIR, 'png'),
  catDir:       path.join(ROOT_DIR, 'category'),
  countdownSec: 15,
};

/* ── Category emoji map ─────────────────────────────────────────── */
const CAT_ICONS = {
  animals:'🐾', flowers:'🌸', food:'🍕', nature:'🌿', people:'👤',
  vehicles:'🚗', sports:'⚽', technology:'💻', business:'💼',
  education:'📚', fashion:'👗', travel:'✈️', architecture:'🏛️',
  medical:'⚕️', music:'🎵', art:'🎨',
  fish_seafood:'🐟', seafood:'🦐', birds:'🐦', insects:'🦋',
  fruits:'🍎', vegetables:'🥕', default:'📦'
};

/* ── Helpers ─────────────────────────────────────────────────────── */
const fmt        = n => Number(n).toLocaleString('en-IN');
const slug2title = s => s.replace(/-/g,' ').replace(/\b\w/g,c=>c.toUpperCase());
const escHtml    = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const mkdirp     = d => { if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true }); };

function formatCatName(name) {
  return name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

/* ─────────────────────────────────────────────────────────────────
   SEO TITLE — AI-generated, stored in ai_titles.json cache
   Fallback if AI unavailable: h1 + suffix
   ───────────────────────────────────────────────────────────────── */
function getPostTitle(post, titleCache) {
  // Use AI-cached title if available
  if (titleCache && titleCache[post.slug]) {
    return titleCache[post.slug];
  }
  // Fallback: use existing h1 with suffix (max 60 chars)
  const base   = post.h1 || post.title || slug2title(post.slug);
  const suffix = 'Free PNG | UltraPNG';
  const full   = `${base} | ${suffix}`;
  if (full.length <= 65) return full;
  return base.slice(0, 65 - suffix.length - 3) + '… | ' + suffix;
}

function md2html(md) {
  if (!md) return '';
  return md
    .replace(/^## (.+)$/gm,'<h2>$1</h2>')
    .replace(/^### (.+)$/gm,'<h3>$1</h3>')
    .replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g,'<a href="$2">$1</a>')
    .replace(/^- (.+)$/gm,'<li>$1</li>')
    .replace(/(<li>.*<\/li>\n?)+/g, l => `<ul>${l}</ul>`)
    .split('\n\n')
    .map(p => p.trim() && !p.startsWith('<') ? `<p>${p}</p>` : p)
    .join('\n');
}

function isToday(dateStr) {
  return dateStr === new Date().toISOString().slice(0,10);
}

/* ── HTML Head ──────────────────────────────────────────────────── */
function htmlHead({ title, desc, canonical, og_image, schema = '', keywords = '', type = 'website', datePublished = '', downloadPage = false }) {
  const metaDesc = escHtml(String(desc).slice(0, 160));
  const ogType   = type === 'article' ? 'article' : 'website';
  const adsenseScript = `<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${CONFIG.adsenseId}" crossorigin="anonymous"></script>`;
  const gsiScript = `<script src="https://accounts.google.com/gsi/client" async defer></script>`;

  // ── 30 SEO keywords meta tag (product pages only) ──
  const keywordsMeta = keywords
    ? `\n<meta name="keywords" content="${escHtml(keywords)}">`
    : '';

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${escHtml(title)}</title>
<meta name="description" content="${metaDesc}">${keywordsMeta}
<link rel="canonical" href="${CONFIG.siteUrl}${canonical}">
<!-- Open Graph -->
<meta property="og:type" content="${ogType}">
<meta property="og:title" content="${escHtml(title)}">
<meta property="og:description" content="${metaDesc}">
<meta property="og:url" content="${CONFIG.siteUrl}${canonical}">
<meta property="og:image" content="${og_image || CONFIG.siteUrl+'/assets/og-default.jpg'}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:site_name" content="${CONFIG.siteName}">
<meta property="og:locale" content="en_US">
${datePublished ? `<meta property="article:published_time" content="${datePublished}">` : ''}
<!-- Twitter -->
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:site" content="@ultrapng">
<meta name="twitter:title" content="${escHtml(title)}">
<meta name="twitter:description" content="${metaDesc}">
<meta name="twitter:image" content="${og_image || CONFIG.siteUrl+'/assets/og-default.jpg'}">
<!-- Robots -->
<meta name="robots" content="index, follow, max-image-preview:large">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/css/style.css">${downloadPage ? '\n<link rel="stylesheet" href="/css/download.css">' : ''}
<link rel="icon" type="image/svg+xml" href="/assets/favicon.svg">
${adsenseScript}
${gsiScript}
${schema}
</head>`;
}

/* ── HTML Header ────────────────────────────────────────────────── */
function htmlHeader(categories, totalCount) {
  const catLinks = [
    { href: '/', label: 'All', icon: '🏠' },
    ...categories.map(c => ({
      href: `/category/${c.name}/`,
      label: formatCatName(c.name),
      icon: CAT_ICONS[c.name] || CAT_ICONS.default
    }))
  ];
  const signInBtn = `<button class="btn-theme" id="btn-theme" title="Toggle dark mode" aria-label="Toggle dark mode"><svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/></svg></button>
      <button class="btn-signin" onclick="triggerGoogleSignIn()">
        <svg viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/><path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg>
        <span>Sign In</span>
      </button>`;

  return `
<header class="site-header">
  <div class="container">
    <a href="/" class="logo" aria-label="UltraPNG Home">
      <div class="logo-mark">UP</div>
      <span class="logo-text">Ultra<span>PNG</span></span>
    </a>
    <div class="header-search">
      <svg class="search-icon" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
      <input type="search" placeholder="Search ${fmt(totalCount)}+ free PNG images..." class="search-trigger-input" readonly>
    </div>
    <div class="header-actions" id="header-actions">
      ${signInBtn}
    </div>
  </div>
</header>
<nav class="cat-nav" aria-label="Categories">
  <div class="cat-nav-inner">
    ${catLinks.map(c => `<a href="${c.href}" class="cat-link"><span class="cat-icon">${c.icon}</span>${c.label}</a>`).join('')}
  </div>
</nav>`;
}

/* ── HTML Footer ─────────────────────────────────────────────────── */
function htmlFooter(categories, totalCount) {
  const year = new Date().getFullYear();
  const cats = categories.slice(0,8).map(c =>
    `<li><a href="/category/${c.name}/">${formatCatName(c.name)} PNG</a></li>`
  ).join('');
  const tagline = `Free transparent PNG images for designers, marketers &amp; creators worldwide. ${fmt(totalCount)}+ HD images updated daily.`;

  return `
<footer class="site-footer">
  <div class="container">
    <div class="footer-grid">
      <div class="footer-brand">
        <div class="logo">
          <div class="logo-mark">UP</div>
          <span class="logo-text">Ultra<span>PNG</span></span>
        </div>
        <p class="footer-tagline">${tagline}</p>
      </div>
      <div class="footer-links">
        <h4>Categories</h4>
        <ul>${cats}</ul>
      </div>
      <div class="footer-links">
        <h4>Legal</h4>
        <ul>
          <li><a href="/pages/about.html">About Us</a></li>
          <li><a href="/pages/contact.html">Contact</a></li>
          <li><a href="/pages/privacy.html">Privacy Policy</a></li>
          <li><a href="/pages/terms.html">Terms of Use</a></li>
          <li><a href="/pages/disclaimer.html">Disclaimer</a></li>
          <li><a href="/pages/dmca.html">DMCA</a></li>
        </ul>
      </div>
    </div>
    <div class="footer-bottom">
      <p>© ${year} UltraPNG. All rights reserved.</p>
    </div>
  </div>
</footer>`;
}

/* ─────────────────────────────────────────────────────────────────
   CATEGORY KEYWORD TAG CLOUD
   50 strong SEO keyword tags shown on:
   - Category page (top of page, full 50 tags)
   - Product page (bottom, same tags + image-specific 30 tags)
   ───────────────────────────────────────────────────────────────── */
function buildCategoryTagCloud(catData, catName, maxTags = 50) {
  if (!catData || !catData.keywords50 || !catData.keywords50.length) return '';
  const catDisplay = formatCatName(catName);
  const tags = catData.keywords50.slice(0, maxTags);
  return `
<div class="cat-keyword-cloud">
  <div class="container">
    <div class="kw-cloud-box">
      <h2 class="kw-cloud-heading">🔍 ${catDisplay} PNG — Popular Searches</h2>
      <div class="kw-cloud-tags">
        ${tags.map(kw =>
          `<a href="/category/${catName}/?q=${encodeURIComponent(kw)}" class="kw-tag">${escHtml(kw)}</a>`
        ).join('')}
      </div>
    </div>
  </div>
</div>`
}

/* ─────────────────────────────────────────────────────────────────
   PRODUCT PAGE — 30 IMAGE KEYWORDS + CATEGORY TAG CLOUD
   Two sections on each product page:
   1. Image-specific 30 keywords (as "Related Searches" chips)
   2. Category 50 keyword pool (as full tag cloud below)
   ───────────────────────────────────────────────────────────────── */
function buildKeywordsSection(keywords30, catData, cat) {
  let html = '';

  // ── Section 1: Image-specific 30 keywords ──
  if (keywords30 && keywords30.length) {
    html += `
<div class="dl-keywords-section">
  <h3 class="dl-kw-heading">🔍 Related Searches</h3>
  <div class="dl-tags dl-tags-keywords">
    ${keywords30.map(kw =>
      `<a href="/category/${cat}/?q=${encodeURIComponent(kw)}" class="tag-chip tag-chip-kw">${escHtml(kw)}</a>`
    ).join('')}
  </div>
</div>`;
  }

  // ── Section 2: Full category keyword tag cloud (50 tags) ──
  if (catData?.keywords50?.length) {
    html += `
<div class="dl-cat-keyword-cloud">
  <h3 class="dl-kw-heading">🏷️ Browse More ${formatCatName(cat)} PNG</h3>
  <div class="dl-tags dl-tags-keywords">
    ${catData.keywords50.map(kw =>
      `<a href="/category/${cat}/?q=${encodeURIComponent(kw)}" class="tag-chip tag-chip-cat">${escHtml(kw)}</a>`
    ).join('')}
  </div>
</div>`;
  }

  return html;
}

/* ── Pagination ─────────────────────────────────────────────────── */
function pagination(current, total, baseUrl) {
  if (total <= 1) return '';
  const pages = [];
  pages.push(current > 1
    ? `<a href="${baseUrl}${current > 2 ? 'page/'+(current-1)+'/' : ''}" class="page-btn prev-next">← Prev</a>`
    : `<button class="page-btn prev-next" disabled>← Prev</button>`);

  for (let p = 1; p <= total; p++) {
    if (p === 1 || p === total || (p >= current-2 && p <= current+2)) {
      const href = p === 1 ? baseUrl : `${baseUrl}page/${p}/`;
      pages.push(`<a href="${href}" class="page-btn${p===current?' active':''}">${p}</a>`);
    } else if (p === current-3 || p === current+3) {
      pages.push('<span class="page-ellipsis">…</span>');
    }
  }
  pages.push(current < total
    ? `<a href="${baseUrl}page/${current+1}/" class="page-btn prev-next">Next →</a>`
    : `<button class="page-btn prev-next" disabled>Next →</button>`);
  return `<div class="pagination">${pages.join('')}</div>`;
}

/* ── Card HTML ──────────────────────────────────────────────────── */
function pngCard(post) {
  const thumbUrl = post.preview_url_small || post.webp_preview_url || post.preview_url;
  const badge = isToday(post.date_added) ? '<span class="new-badge">NEW</span>' : '';
  return `
<a href="/png/${post.slug}/" class="png-card" data-subcat="${escHtml(post.subcategory)}" data-id="${escHtml(post.slug)}">
  <div class="card-img-wrap">
    ${badge}
    <img data-src="${escHtml(thumbUrl)}" src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1 1'%3E%3C/svg%3E" alt="${escHtml(post.alt_text || post.h1 || post.title)}" loading="lazy" width="200" height="200">
  </div>
  <p class="card-title">${escHtml(post.h1 || post.title)}</p>
</a>`;
}

/* ── Search Overlay ─────────────────────────────────────────────── */
function htmlSearchOverlay(totalCount) {
  return `
<div id="search-overlay" class="search-overlay" hidden>
  <div class="search-modal">
    <div class="search-modal-header">
      <input type="search" id="search-input" placeholder="Search ${fmt(totalCount)}+ PNG images..." autofocus>
      <button id="search-close" aria-label="Close search">✕</button>
    </div>
    <div id="search-results" class="search-results-grid"></div>
  </div>
</div>`;
}

function htmlMobileNav() {
  return `<nav class="mobile-nav" aria-label="Mobile navigation">
  <a href="/" class="mobile-nav-item"><svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg><span>Home</span></a>
  <a href="/category/" class="mobile-nav-item"><svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg><span>Categories</span></a>
  <button class="mobile-nav-item search-trigger"><svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg><span>Search</span></button>
</nav>`;
}

function htmlScripts() {
  return `<script src="/js/app.js" defer></script>`;
}

/* ── Read All Data ──────────────────────────────────────────────── */
function readAllData() {
  const dataFiles = fs.readdirSync(CONFIG.dataDir)
    .filter(f => f.endsWith('.json') && !f.startsWith('_') && !f.startsWith('.') && !f.startsWith('ai_') && !f.startsWith('category_'));

  if (dataFiles.length === 0) {
    console.error('❌ No data JSON files found in data/');
    process.exit(1);
  }

  const categoryMap = {};
  for (const file of dataFiles) {
    let posts;
    try {
      posts = JSON.parse(fs.readFileSync(path.join(CONFIG.dataDir, file), 'utf8'));
      if (!Array.isArray(posts)) posts = [posts];
    } catch (e) {
      console.warn(`  ⚠️  Skipping unreadable file: ${file} — ${e.message}`);
      continue;
    }
    for (const post of posts) {
      const cat = (post.category || '').trim() || file.replace('.json', '');
      post._category = cat;
      if (!categoryMap[cat]) categoryMap[cat] = [];
      categoryMap[cat].push(post);
    }
  }

  const categories = Object.entries(categoryMap)
    .map(([name, posts]) => ({ name, count: posts.length }))
    .sort((a, b) => b.count - a.count);

  const allPosts = Object.values(categoryMap).flat()
    .sort((a, b) => (b.date_added || '').localeCompare(a.date_added || ''));

  return { categories, allPosts };
}

/* ── Build Cache ─────────────────────────────────────────────────── */
const CACHE_FILE   = path.join(CONFIG.rootDir, '.build-cache.json');
const FORCE_REBUILD = process.argv.includes('--force');

function loadBuildCache() {
  if (FORCE_REBUILD) { console.log('⚡ --force: rebuilding all pages'); return {}; }
  try { return JSON.parse(fs.readFileSync(CACHE_FILE, 'utf8')); }
  catch { return {}; }
}
function saveBuildCache(cache) {
  try { fs.writeFileSync(CACHE_FILE, JSON.stringify(cache, null, 2)); }
  catch (e) { console.warn('Could not save build cache:', e.message); }
}

/* ─────────────────────────────────────────────────────────────────
   GENERATE: Home Page
   ───────────────────────────────────────────────────────────────── */
function generateHomePage(allPosts, categories, totalCount) {
  const PAGE = CONFIG.postsPerPage;
  const pageCount = Math.ceil(allPosts.length / PAGE);

  const websiteSchema = `
<script type="application/ld+json">${JSON.stringify({
  "@context":"https://schema.org",
  "@type":"WebSite",
  "name":"UltraPNG",
  "url":CONFIG.siteUrl,
  "description":`Download ${fmt(totalCount)}+ free transparent PNG images in HD. No watermarks, no signup.`,
  "potentialAction":{
    "@type":"SearchAction",
    "target":`${CONFIG.siteUrl}/?q={search_term_string}`,
    "query-input":"required name=search_term_string"
  }
})}</script>`;

  for (let pg = 1; pg <= pageCount; pg++) {
    const pagePosts = allPosts.slice((pg-1)*PAGE, pg*PAGE);
    const isFirst   = pg === 1;
    const outDir    = isFirst ? CONFIG.rootDir : path.join(CONFIG.rootDir, 'page', String(pg));
    mkdirp(outDir);

    const pageTitle = isFirst
      ? `Free Transparent PNG Images HD Download | UltraPNG`
      : `Free PNG Images — Page ${pg} | UltraPNG`;
    const pageDesc  = isFirst
      ? `Download ${fmt(totalCount)}+ free transparent PNG images in HD. No watermarks, no signup required.`
      : `Browse free transparent PNG images — Page ${pg} of ${pageCount}.`;
    const canonical = isFirst ? '/' : `/page/${pg}/`;

    const html = `${htmlHead({ title:pageTitle, desc:pageDesc, canonical, og_image:'', schema: isFirst ? websiteSchema : '' })}
<body>
${htmlHeader(categories, totalCount)}
${htmlSearchOverlay(totalCount)}
<div class="hero"><div class="container">
  <h1>Free <span>Transparent PNG</span> Images — HD Quality</h1>
  <div class="hero-stats">
    <div class="hero-stat"><strong>${fmt(totalCount)}+</strong><span>PNG Images</span></div>
    <div class="hero-stat"><strong>${categories.length}+</strong><span>Categories</span></div>
    <div class="hero-stat"><strong>Daily</strong><span>Updated</span></div>
  </div>
</div></div>
<div class="container">
  <div class="section-header"><h2 class="section-title">${isFirst ? 'Latest PNG Images' : `PNG Images — Page ${pg}`}</h2></div>
  <div class="png-grid">${pagePosts.map(pngCard).join('')}</div>
  ${pagination(pg, pageCount, '/')}
</div>
${htmlFooter(categories, totalCount)}${htmlMobileNav()}${htmlScripts()}
</body></html>`;

    fs.writeFileSync(path.join(outDir, 'index.html'), html);
  }
  console.log(`✓ Home: ${pageCount} page(s)`);
}

/* ─────────────────────────────────────────────────────────────────
   GENERATE: Category Pages
   Now includes: AI 100-word category description (template)
   ───────────────────────────────────────────────────────────────── */
function generateCategoryPages(categories, allPosts, totalCount, catCache) {
  mkdirp(path.join(CONFIG.rootDir, 'category'));
  let total = 0;

  const catListHtml = `${htmlHead({ title:`All PNG Categories | UltraPNG`, desc:`Browse ${categories.length}+ categories of free transparent PNG images.`, canonical:'/category/', og_image:'' })}
<body>
${htmlHeader(categories, totalCount)}
${htmlSearchOverlay(totalCount)}
<div class="cat-hero"><div class="container"><h1>All PNG Categories</h1><p>Browse ${categories.length}+ categories of free transparent PNG images</p></div></div>
<div class="container">
  <div class="section-header" style="padding-top:24px"><h2 class="section-title">All Categories</h2></div>
  <div class="cat-grid">
    ${categories.map(c => {
      const thumb = allPosts.find(p => (p.category||p._category)===c.name)?.preview_url || '';
      return `<a href="/category/${c.name}/" class="cat-card">
        ${thumb ? `<div class="cat-card-thumb"><img data-src="${escHtml(thumb)}" src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1 1'%3E%3C/svg%3E" alt="${formatCatName(c.name)} PNG" loading="lazy"></div>` : ''}
        <div class="cat-card-info">
          <span class="cat-icon-lg">${CAT_ICONS[c.name]||'📦'}</span>
          <strong>${formatCatName(c.name)}</strong>
          <span>${fmt(c.count)} images</span>
        </div>
      </a>`;
    }).join('')}
  </div>
</div>
${htmlFooter(categories, totalCount)}${htmlMobileNav()}${htmlScripts()}
</body></html>`;

  mkdirp(path.join(CONFIG.catDir));
  fs.writeFileSync(path.join(CONFIG.catDir, 'index.html'), catListHtml);

  for (const cat of categories) {
    const catPosts  = allPosts.filter(p => (p.category||p._category) === cat.name);
    const catTitle  = formatCatName(cat.name);
    const PAGE      = CONFIG.postsPerPage;
    const pageCount = Math.ceil(catPosts.length / PAGE);
    const catDir    = path.join(CONFIG.catDir, cat.name);
    mkdirp(catDir);

    // ── AI Category Keyword Tag Cloud (from cache) ──────────────
    const catData    = catCache ? catCache[cat.name] : null;
    const catTagCloud = buildCategoryTagCloud(catData, cat.name, 50);

    for (let pg = 1; pg <= pageCount; pg++) {
      const pagePosts = catPosts.slice((pg-1)*PAGE, pg*PAGE);
      const title = pg===1
        ? `${catTitle} PNG Images Free Download | UltraPNG`
        : `${catTitle} PNG Images — Page ${pg} | UltraPNG`;
      const desc  = pg===1
        ? (catData?.keywords50?.slice(0,5).join(', ') + ' — Free transparent PNG images in HD. No watermark, free download.' || `Download free ${catTitle} transparent PNG images in HD. No watermark required.`)
        : `${catTitle} PNG images — Page ${pg}. Free transparent background downloads.`;

      const outDir = pg===1 ? catDir : path.join(catDir,'page',String(pg));
      mkdirp(outDir);

      const html = `${htmlHead({ title, desc, canonical:`/category/${cat.name}/${pg>1?'page/'+pg+'/':''}`, og_image:catPosts[0]?.preview_url||'' })}
<body>
${htmlHeader(categories, totalCount)}
${htmlSearchOverlay(totalCount)}
<div class="cat-hero">
  <div class="container">
    <h1>${CAT_ICONS[cat.name]||'📦'} ${catTitle} PNG Images Free Download</h1>
    <p>${fmt(cat.count)}+ transparent ${catTitle} PNG images — HD quality, free download</p>
    <div class="cat-hero-stats">
      <span>${fmt(cat.count)} Images</span>
      <span>Updated <strong>Daily</strong></span>
      <span>No Watermark</span>
    </div>
  </div>
</div>

${catTagCloud}

<div class="container">
  <div class="section-header"><h2 class="section-title">${catTitle} PNG${pg>1?' — Page '+pg:''}</h2></div>
  <div class="png-grid">${pagePosts.map(pngCard).join('')}</div>
  ${pagination(pg, pageCount, `/category/${cat.name}/`)}
</div>
${htmlFooter(categories, totalCount)}${htmlMobileNav()}${htmlScripts()}
</body></html>`;

      fs.writeFileSync(path.join(outDir,'index.html'), html);
      total++;
    }
    console.log(`  ✓ /category/${cat.name}/ — ${pageCount} page(s)`);
  }
  console.log(`✓ Categories: ${total} page(s) total`);
}

/* ─────────────────────────────────────────────────────────────────
   GENERATE: Post (Product) Pages
   Changes:
   - title → from AI titleCache (unique per image)
   - description → category template (100 words, same for all in category)
   - 30 keywords → from kwCache, shown as tags + meta keywords
   ───────────────────────────────────────────────────────────────── */
function generatePostPages(allPosts, categories, totalCount, titleCache, catCache, kwCache) {
  mkdirp(CONFIG.postsDir);
  let count = 0, skipped = 0;
  const cache    = loadBuildCache();
  const newCache = { ...cache };

  const postsByCategory = {};
  allPosts.forEach(p => {
    const cat = p.category || p._category;
    if (!postsByCategory[cat]) postsByCategory[cat] = [];
    postsByCategory[cat].push(p);
  });

  for (const post of allPosts) {
    const cat      = post.category || post._category;
    const outDir   = path.join(CONFIG.postsDir, post.slug);
    const outFile  = path.join(outDir, 'index.html');
    const cached   = cache[post.slug];

    // Skip if already built AND AI content hasn't changed
    const hasTitleNow = titleCache && !!titleCache[post.slug];
    if (!FORCE_REBUILD && fs.existsSync(outFile) && cached &&
        cached.date_added === post.date_added && cached.has_ai_title === hasTitleNow) {
      skipped++;
      continue;
    }

    const catPosts  = postsByCategory[cat] || [];
    const sameSubcat = catPosts.filter(p => p.slug !== post.slug && p.subcategory === post.subcategory);
    const otherCat   = catPosts.filter(p => p.slug !== post.slug && p.subcategory !== post.subcategory);
    const related    = [...sameSubcat, ...otherCat].slice(0, 8);
    const catTitle   = formatCatName(cat);

    // ── 1. SEO TITLE (AI-generated) ──────────────────────────
    const pageTitle  = getPostTitle(post, titleCache);

    // ── 2. PAGE DESCRIPTION for meta tag ─────────────────────
    // Use top 5 category keywords as meta desc prefix
    const catData    = catCache ? catCache[cat] : null;
    const topKws     = catData?.keywords50?.slice(0, 5).join(', ') || '';
    const pageDesc   = topKws
      ? `${topKws} — ${post.alt_text || `Free ${formatCatName(cat)} transparent PNG download HD.`}`.slice(0, 160)
      : post.meta_desc || '';

    // ── 3. 30 KEYWORDS ───────────────────────────────────────
    const keywords30 = kwCache?.[post.slug] || [];
    // Also merge with original tags for display chips
    const origTags   = (post.tags || '').split(',').map(t => t.trim()).filter(Boolean);
    const allTagsDisplay = [...origTags]; // Original tags shown as tag-chips
    // keywords30 shown separately as "Related Searches"
    const keywordsMeta = keywords30.join(', ');

    // ── Schema.org ────────────────────────────────────────────
    const schema = `
<script type="application/ld+json">${JSON.stringify({
  "@context":"https://schema.org",
  "@type":"ImageObject",
  "name": post.h1 || post.title,
  "description": pageDesc,
  "contentUrl": post.preview_url,
  "thumbnailUrl": post.preview_url_small || post.preview_url || post.webp_preview_url,
  "url": `${CONFIG.siteUrl}/png/${post.slug}/`,
  "encodingFormat": "image/png",
  "keywords": keywords30.join(', ') || post.tags,
  "datePublished": post.date_added,
  "author": {"@type":"Organization","name":"UltraPNG","url":CONFIG.siteUrl},
  "license": `${CONFIG.siteUrl}/pages/terms.html`,
  "acquireLicensePage": `${CONFIG.siteUrl}/png/${post.slug}/`
})}</script>
<script type="application/ld+json">${JSON.stringify({
  "@context":"https://schema.org",
  "@type":"BreadcrumbList",
  "itemListElement":[
    {"@type":"ListItem","position":1,"name":"Home","item":CONFIG.siteUrl},
    {"@type":"ListItem","position":2,"name":catTitle+" PNG","item":`${CONFIG.siteUrl}/category/${cat}/`},
    {"@type":"ListItem","position":3,"name":post.h1||post.title,"item":`${CONFIG.siteUrl}/png/${post.slug}/`}
  ]
})}</script>`;

    // ── Related posts HTML ─────────────────────────────────────
    const relatedHtml = related.length ? `
<section class="dl-related">
  <h2>🖼️ Related ${catTitle} PNG Images</h2>
  <div class="dl-related-grid">
    ${related.map(r=>`
    <a href="/png/${r.slug}/" class="dl-related-card">
      <div class="dl-related-thumb">
        <img data-src="${escHtml(r.preview_url_small || r.preview_url || r.webp_preview_url)}" src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1 1'%3E%3C/svg%3E" alt="${escHtml(r.alt_text)}" loading="lazy">
      </div>
      <div class="dl-related-info">
        <p class="dl-related-title">${escHtml(r.h1||r.title)}</p>
        <span class="dl-related-cat">${escHtml(formatCatName(r.subcategory||r.category))}</span>
      </div>
    </a>`).join('')}
  </div>
</section>` : '';

    // ── Full page HTML ─────────────────────────────────────────
    const html = `${htmlHead({
  title:        pageTitle,
  desc:         pageDesc,
  keywords:     keywordsMeta,   // ← 30 keywords in meta
  canonical:    `/png/${post.slug}/`,
  og_image:     post.preview_url,
  schema,
  type:         'article',
  datePublished: post.date_added || '',
  downloadPage: true
})}
<body>
${htmlHeader(categories, totalCount)}
${htmlSearchOverlay(totalCount)}

<div class="dl-outer-wrap">

  <!-- LEFT AD -->
  <aside class="dl-col-ad dl-col-ad-left" aria-label="Advertisement" aria-hidden="true">
    <div class="dl-col-ad-inner">
      <ins class="adsbygoogle" style="display:block" data-ad-client="${CONFIG.adsenseId}" data-ad-slot="AUTO" data-ad-format="auto" data-full-width-responsive="false"></ins>
      <script>(adsbygoogle = window.adsbygoogle || []).push({});</script>
    </div>
  </aside>

  <!-- CENTER CONTENT -->
  <div class="dl-col-main">
    <div class="download-page">
      <div class="breadcrumb">
        <a href="/">Home</a><span class="breadcrumb-sep">›</span>
        <a href="/category/${cat}/">${catTitle}</a><span class="breadcrumb-sep">›</span>
        <span>${escHtml(post.h1||post.title)}</span>
      </div>

      <h1 class="post-title">${escHtml(post.h1||post.title)}</h1>

      <div class="download-hero">
        <div>
          <div class="dl-preview">
            <div class="dl-preview-img">
              <img src="${escHtml(post.preview_url)}" alt="${escHtml(post.alt_text)}" width="${post.preview_w||800}" height="${post.preview_h||800}" loading="eager">
            </div>
            <div class="dl-preview-meta">
              <div class="dl-meta-item"><div class="dl-meta-label">Format</div><div class="dl-meta-val">PNG</div></div>
              <div class="dl-meta-item"><div class="dl-meta-label">Background</div><div class="dl-meta-val">Transparent</div></div>
              <div class="dl-meta-item"><div class="dl-meta-label">Quality</div><div class="dl-meta-val">HD</div></div>
              <div class="dl-meta-item"><div class="dl-meta-label">Added</div><div class="dl-meta-val">${post.date_added||'Today'}</div></div>
            </div>
          </div>
          <div class="dl-leaderboard-ad">
            <ins class="adsbygoogle" style="display:block" data-ad-client="${CONFIG.adsenseId}" data-ad-slot="AUTO" data-ad-format="auto" data-full-width-responsive="true"></ins>
            <script>(adsbygoogle = window.adsbygoogle || []).push({});</script>
          </div>
        </div>

        <div class="dl-sidebar">
          <div class="dl-box">
            <div class="dl-box-top">
              <h2>📥 Free PNG Download</h2>
              <p>HD transparent background — no watermark</p>
            </div>
            <div class="dl-box-body">
              <div class="dl-countdown">
                <p class="dl-countdown-label">Click the button below to start</p>
                <div class="dl-countdown-ring">
                  <svg width="80" height="80" viewBox="0 0 88 88">
                    <circle class="track" cx="44" cy="44" r="38"/>
                    <circle class="progress" cx="44" cy="44" r="38"/>
                  </svg>
                  <span class="dl-countdown-num countdown-num">${CONFIG.countdownSec}</span>
                </div>
                <p class="dl-countdown-text">${CONFIG.countdownSec}s countdown starts on click</p>
              </div>

              <button id="download-btn" class="dl-btn dl-btn-ready" data-url="${escHtml(post.download_url)}" data-countdown="${CONFIG.countdownSec}">
                <svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                Download PNG Free
              </button>

              <div class="dl-formats">
                <p>Choose Format</p>
                <div class="dl-format-btns">
                  <button class="dl-format-btn format-btn active" data-url="${escHtml(post.download_url)}" data-format="PNG">PNG</button>
                  ${post.jpg_file_id ? `<button class="dl-format-btn format-btn" data-url="https://drive.usercontent.google.com/download?id=${escHtml(post.jpg_file_id)}&export=download&authuser=0" data-format="JPG">JPG</button>` : ''}
                  ${post.webp_file_id ? `<button class="dl-format-btn format-btn" data-url="https://drive.usercontent.google.com/download?id=${escHtml(post.webp_file_id)}&export=download&authuser=0" data-format="WebP">WebP</button>` : ''}
                </div>
              </div>

              <div class="dl-features">
                <div class="dl-feature"><svg fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>100% Transparent Background</div>
                <div class="dl-feature"><svg fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>No Watermark on Download</div>
                <div class="dl-feature"><svg fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>Free for Commercial Use</div>
                <div class="dl-feature"><svg fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>HD — Print &amp; Digital Ready</div>
              </div>

              <div class="dl-share">
                <span class="dl-share-label">Share:</span>
                <div class="dl-share-btns">
                  <button class="dl-share-btn share-btn share-wa" id="share-wa" title="Share on WhatsApp">📱</button>
                  <button class="dl-share-btn share-btn share-tw" id="share-tw" title="Share on Twitter">🐦</button>
                  <button class="dl-share-btn share-btn share-tg" id="share-tg" title="Share on Telegram">✈️</button>
                  <button class="dl-share-btn share-btn share-cp" id="share-cp" title="Copy link">🔗</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div><!-- /.download-page -->

    <div class="dl-content">
      <!-- ── Original keyword tag chips (from JSON tags field) ── -->
      <div class="dl-tags">
        ${allTagsDisplay.map(t => `<a href="/category/${cat}/?q=${encodeURIComponent(t)}" class="tag-chip">${escHtml(t)}</a>`).join('')}
      </div>

      <!-- ── 30 image-specific keywords + 50 category keyword cloud ── -->
      ${buildKeywordsSection(keywords30, catData, cat)}
    </div>

    ${relatedHtml}

  </div><!-- /.dl-col-main -->

  <!-- RIGHT AD -->
  <aside class="dl-col-ad dl-col-ad-right" aria-label="Advertisement" aria-hidden="true">
    <div class="dl-col-ad-inner">
      <ins class="adsbygoogle" style="display:block" data-ad-client="${CONFIG.adsenseId}" data-ad-slot="AUTO" data-ad-format="auto" data-full-width-responsive="false"></ins>
      <script>(adsbygoogle = window.adsbygoogle || []).push({});</script>
    </div>
  </aside>

</div><!-- /.dl-outer-wrap -->

${htmlFooter(categories, totalCount)}${htmlMobileNav()}${htmlScripts()}
</body></html>`;

    mkdirp(outDir);
    fs.writeFileSync(outFile, html);
    newCache[post.slug] = {
      date_added:   post.date_added,
      built_at:     new Date().toISOString().slice(0,10),
      has_ai_title: !!titleCache?.[post.slug],
    };
    count++;
    if (count % 100 === 0) console.log(`  … ${count} posts built`);
  }

  saveBuildCache(newCache);
  console.log(`✓ Posts: ${count} new, ${skipped} skipped`);
}

/* ── Cleanup, Search Index, Sitemap, Robots (unchanged from v4) ─── */
function cleanupStalePages(allPosts, categories) {
  let removed = 0;
  const validSlugs = new Set(allPosts.map(p => p.slug));
  if (fs.existsSync(CONFIG.postsDir)) {
    for (const dir of fs.readdirSync(CONFIG.postsDir)) {
      if (!validSlugs.has(dir)) {
        fs.rmSync(path.join(CONFIG.postsDir, dir), { recursive: true, force: true });
        removed++;
      }
    }
  }
  const validCats = new Set(categories.map(c => c.name));
  if (fs.existsSync(CONFIG.catDir)) {
    for (const dir of fs.readdirSync(CONFIG.catDir)) {
      const fullPath = path.join(CONFIG.catDir, dir);
      if (fs.statSync(fullPath).isDirectory() && !validCats.has(dir)) {
        fs.rmSync(fullPath, { recursive: true, force: true });
        removed++;
      }
    }
  }
  if (removed > 0) console.log(`✓ Cleanup: removed ${removed} stale page(s)`);
  else console.log('✓ Cleanup: no stale pages');
}

function generateSearchIndex(categories, allPosts) {
  mkdirp(CONFIG.searchDir);
  for (const cat of categories) {
    const catPosts = allPosts.filter(p => (p.category||p._category) === cat.name);
    const idx = catPosts.map(p => ({
      s: p.slug,
      t: p.h1 || p.title,
      c: p.category || p._category,
      k: (p.tags || '').slice(0, 100),
      i: p.preview_url_small || p.preview_url || p.webp_preview_url || ''
    }));
    fs.writeFileSync(path.join(CONFIG.searchDir, `${cat.name}.json`), JSON.stringify(idx));
  }
  const globalIdx = allPosts.slice(0, 5000).map(p => ({
    s: p.slug,
    t: p.h1 || p.title,
    c: p.category || p._category,
    k: (p.tags || '').slice(0, 80),
    i: p.preview_url_small || p.preview_url || p.webp_preview_url || ''
  }));
  fs.writeFileSync(path.join(CONFIG.searchDir, 'all.json'), JSON.stringify(globalIdx));
  console.log(`✓ Search index: ${categories.length} category + 1 global`);
}

function generateSitemap(allPosts, categories) {
  const today = new Date().toISOString().slice(0,10);
  const urls = [
    `<url><loc>${CONFIG.siteUrl}/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>`,
    `<url><loc>${CONFIG.siteUrl}/category/</loc><changefreq>daily</changefreq><priority>0.8</priority></url>`,
    ...categories.map(c => `<url><loc>${CONFIG.siteUrl}/category/${c.name}/</loc><changefreq>daily</changefreq><priority>0.8</priority></url>`),
    ...allPosts.map(p => `<url><loc>${CONFIG.siteUrl}/png/${p.slug}/</loc><lastmod>${p.date_added||today}</lastmod><changefreq>monthly</changefreq><priority>0.7</priority><image:image><image:loc>${escHtml(p.preview_url)}</image:loc><image:title>${escHtml((p.h1||p.title).slice(0,120))}</image:title></image:image></url>`)
  ];
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">
${urls.join('\n')}
</urlset>`;
  fs.writeFileSync(path.join(CONFIG.rootDir, 'sitemap.xml'), xml);
  console.log(`✓ Sitemap: ${urls.length} URLs`);
}

function generateRobots() {
  const txt = `User-agent: *\nAllow: /\nDisallow: /search-index/\nDisallow: /scripts/\nDisallow: /data/\n\nSitemap: ${CONFIG.siteUrl}/sitemap.xml`;
  fs.writeFileSync(path.join(CONFIG.rootDir, 'robots.txt'), txt);
  console.log('✓ robots.txt');
}

/* ─────────────────────────────────────────────────────────────────
   MAIN — Async (needs AI calls)
   ───────────────────────────────────────────────────────────────── */
async function main() {
  const startTime = Date.now();
  console.log('\n🚀 UltraPNG Build v5.0 (AI-Powered) Starting...\n');
  console.log(`📁 Output dir: ${CONFIG.rootDir}\n`);

  const { categories, allPosts } = readAllData();
  const totalCount = allPosts.length;
  console.log(`📊 Loaded: ${totalCount} posts across ${categories.length} categories\n`);

  /* ── STEP 1: AI Content Generation ─────────────────────────────
     - New categories → generate 100-word description + 30 keywords
     - New posts      → generate unique SEO title
     - All cached in data/ → no duplicate API calls
     ──────────────────────────────────────────────────────────── */
  let titleCache = {}, catCache = {}, kwCache = {};

  if (!process.env.GROQ_API_KEY) {
    console.log('⚠️  GROQ_API_KEY not set — skipping AI generation, using fallbacks\n');
  } else {
    console.log('🧠 Running AI content generation...');
    try {
      const result = await processAllPosts(allPosts, CONFIG.rootDir);
      titleCache = result.titleCache;
      catCache   = result.catCache;
      kwCache    = result.kwCache;
    } catch (e) {
      console.error('⚠️  AI generation error:', e.message);
      console.log('   Continuing with cached/fallback content...\n');
      // Load whatever is cached
      const cachePaths = getCachePaths(CONFIG.rootDir);
      titleCache = loadCache(cachePaths.titles);
      catCache   = loadCache(cachePaths.catDescs);
      kwCache    = loadCache(cachePaths.keywords);
    }
  }

  /* ── STEP 2: Build HTML Pages ─────────────────────────────── */
  console.log('\n🏗️  Building HTML pages...\n');
  generateHomePage(allPosts, categories, totalCount);
  generateCategoryPages(categories, allPosts, totalCount, catCache);
  generatePostPages(allPosts, categories, totalCount, titleCache, catCache, kwCache);
  cleanupStalePages(allPosts, categories);
  generateSearchIndex(categories, allPosts);
  generateSitemap(allPosts, categories);
  generateRobots();

  const elapsed = ((Date.now()-startTime)/1000).toFixed(1);
  console.log(`\n✅ Build complete in ${elapsed}s\n   ${totalCount} total posts | ${categories.length} categories\n`);
}

main().catch(err => { console.error('❌ Build failed:', err); process.exit(1); });

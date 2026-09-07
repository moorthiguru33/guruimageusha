const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');
const config = require('../config');
const postFormatter = require('./post_formatter');

function fetchHtml(url, cookie = '') {
  return new Promise((resolve, reject) => {
    const isHttps = url.startsWith('https:');
    const client = isHttps ? https : http;
    const req = client.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Cookie': cookie,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'
      },
      timeout: 15000
    }, res => {
      if ([301, 302, 307].includes(res.statusCode) && res.headers.location) {
        return fetchHtml(res.headers.location, cookie).then(resolve).catch(reject);
      }
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => resolve(body));
      res.on('error', reject);
    });
    req.on('error', reject);
    req.on('timeout', () => {
      req.destroy();
      reject(new Error('Request timeout'));
    });
  });
}

function parseCategoriesFromHtml(html) {
  const categories = [];
  const regex = /<a[^>]*href=["'][^"']*topic=([^&"']+)[^"']*["'][^>]*>([\s\S]*?)<\/a>/gi;
  let match;

  while ((match = regex.exec(html)) !== null) {
    const rawTopic = match[1];
    let topic = '';
    try {
      topic = decodeURIComponent(rawTopic.replace(/\+/g, ' ')).trim();
    } catch (e) {
      topic = rawTopic.trim();
    }
    const name = match[2].replace(/<[^>]+>/g, '').trim();
    if (topic && name && !categories.some(c => c.topic.toLowerCase() === topic.toLowerCase())) {
      categories.push({ topic, name });
    }
  }

  // Sort alphabetically for clean UI
  return categories.sort((a, b) => a.name.localeCompare(b.name));
}

function parsePostsFromHtml(html, activeTopic = '') {
  const posts = [];
  const boxParts = html.split(/<div class="[^"]*col-lg-3 box[^"]*">/i);
  
  for (let i = 1; i < boxParts.length; i++) {
    const part = boxParts[i];
    
    // File name
    const fnMatch = part.match(/<p class="file-name"[^>]*title="([^"]+)"/i) ||
                    part.match(/<p class="file-name"[^>]*>([\s\S]*?)<\/p>/i);
    const fileName = fnMatch ? fnMatch[1].trim() : '';
    if (!fileName) continue;

    // ID extracted from fileName (e.g. "6562 - hindu - gods..." -> "6562")
    const idMatch = fileName.match(/^([0-9A-Za-z_-]+)/);
    const id = idMatch ? idMatch[1] : `post-${i}`;

    // Preview Image URL
    let previewUrl = '';
    const imgMatch = part.match(/<img[^>]*class="[^"]*preview-img[^"]*"[^>]*src="([^"]+)"/i) ||
                     part.match(/<img[^>]*src="([^"]+)"[^>]*class="[^"]*preview-img[^"]*"/i) ||
                     part.match(/<img[^>]*src="([^"]+)"/i);
    if (imgMatch) {
      previewUrl = imgMatch[1].trim();
      if (previewUrl.startsWith('./')) {
        previewUrl = 'https://forpsd.com/' + previewUrl.slice(2);
      } else if (previewUrl.startsWith('/')) {
        previewUrl = 'https://forpsd.com' + previewUrl;
      }
    }

    // Download URL token
    const dlMatch = part.match(/_startDl\((?:'|"|&#39;|&quot;)(https:\/\/forpsd\.com\/download\/[^'"&;\s]+)/i) ||
                    part.match(/https:\/\/forpsd\.com\/download\/[a-zA-Z0-9+/=]+/i);
    const downloadTokenUrl = dlMatch ? (dlMatch[1] || dlMatch[0]) : '';

    // Upload Date
    const dateMatch = part.match(/File uploaded\s*:\s*([0-9.]+)/i);
    const uploadDate = dateMatch ? dateMatch[1] : '';

    // Assign SINGLE CANONICAL CATEGORY (e.g. 'Gods' for any god design, 'DMK' for stalin, etc.)
    const category = postFormatter.determineCanonicalCategory(fileName, activeTopic);

    posts.push({
      id,
      fileName,
      title: fileName,
      category,
      previewUrl,
      downloadTokenUrl,
      uploadDate
    });
  }

  return posts;
}

function getMaxPagesFromHtml(html) {
  const pageMatches = [...html.matchAll(/page=(\d+)/g)].map(m => parseInt(m[1], 10));
  return pageMatches.length > 0 ? Math.max(...pageMatches) : 1;
}

async function getCategories() {
  const settings = config.getSettings();
  let html = '';
  
  if (!settings.useLocalCopies) {
    try {
      html = await fetchHtml('https://forpsd.com/?iscategory=true', settings.forpsdCookie);
    } catch (e) {
      console.warn('Could not fetch live categories from forpsd.com, falling back to local copy:', e.message);
    }
  }

  if (!html || html.length < 500) {
    const localFile = path.join(config.PATHS.localSiteDir, 'FORPSD __ RAMARTS.html');
    if (fs.existsSync(localFile)) {
      html = fs.readFileSync(localFile, 'utf8');
    }
  }

  return parseCategoriesFromHtml(html);
}

async function getPosts(topic = '', query = '', page = 1, fetchAll = true) {
  const settings = config.getSettings();

  // If fetchAll is false, just fetch the requested single page
  if (!fetchAll) {
    let html = '';
    if (!settings.useLocalCopies && (topic || query)) {
      try {
        const url = `https://forpsd.com/search?topic=${encodeURIComponent(topic)}&query=${encodeURIComponent(query)}&page=${page}`;
        html = await fetchHtml(url, settings.forpsdCookie);
      } catch (e) {
        console.warn('Live fetch error:', e.message);
      }
    }
    if (!html || html.length < 500) {
      const localFile = path.join(config.PATHS.localSiteDir, 'FORPSD __ RAMARTS-.html');
      if (fs.existsSync(localFile)) html = fs.readFileSync(localFile, 'utf8');
    }
    return parsePostsFromHtml(html, topic);
  }

  // Fetch ALL pages for the category/query
  console.log(`Fetching ALL items for category="${topic || 'All'}", query="${query}"...`);
  let firstPageHtml = '';
  if (!settings.useLocalCopies && (topic || query)) {
    try {
      const url = `https://forpsd.com/search?topic=${encodeURIComponent(topic)}&query=${encodeURIComponent(query)}&page=1`;
      firstPageHtml = await fetchHtml(url, settings.forpsdCookie);
    } catch (e) {
      console.warn('Live fetch error for page 1:', e.message);
    }
  }

  if (!firstPageHtml || firstPageHtml.length < 500) {
    const localFile = path.join(config.PATHS.localSiteDir, 'FORPSD __ RAMARTS-.html');
    if (fs.existsSync(localFile)) firstPageHtml = fs.readFileSync(localFile, 'utf8');
  }

  const allPosts = [];
  const seenIds = new Set();

  function addPosts(posts) {
    for (const p of posts) {
      if (!seenIds.has(p.id)) {
        seenIds.add(p.id);
        allPosts.push(p);
      }
    }
  }

  // Add Page 1
  addPosts(parsePostsFromHtml(firstPageHtml, topic));

  // Determine total pages
  const maxPage = Math.min(getMaxPagesFromHtml(firstPageHtml), 50);
  console.log(`Category "${topic || query || 'All'}" has ${maxPage} pages`);

  if (maxPage > 1 && !settings.useLocalCopies) {
    // Fetch remaining pages in concurrent batches of 5
    for (let p = 2; p <= maxPage; p += 5) {
      const batchPages = [];
      for (let b = p; b < Math.min(p + 5, maxPage + 1); b++) {
        batchPages.push(b);
      }
      
      const promises = batchPages.map(async (pg) => {
        try {
          const url = `https://forpsd.com/search?topic=${encodeURIComponent(topic)}&query=${encodeURIComponent(query)}&page=${pg}`;
          const pageHtml = await fetchHtml(url, settings.forpsdCookie);
          return parsePostsFromHtml(pageHtml, topic);
        } catch (err) {
          console.warn(`Could not fetch page ${pg}:`, err.message);
          return [];
        }
      });

      const results = await Promise.all(promises);
      results.forEach(posts => addPosts(posts));
    }
  }

  console.log(`Total items collected for "${topic || query || 'All'}": ${allPosts.length}`);
  return allPosts;
}

module.exports = {
  getCategories,
  getPosts,
  parseCategoriesFromHtml,
  parsePostsFromHtml
};

#!/usr/bin/env node
/* ═══════════════════════════════════════════════════════════════════
   UltraPNG — AI Content Generator
   File: scripts/ai_content.js

   செய்வது:
   1. SEO Title → AI மூலம் unique title (60 chars max) per image
   2. Category Description → 100 words, per category (reuse for all images)
      New category வரும்போது மட்டும் AI generate செய்யும்
   3. 30 SEO Keywords → per image (category + subject based)

   Cache files (ultrapng/data/):
   - ai_titles.json            { slug → seoTitle }
   - category_descriptions.json { category → { desc, keywords30 } }
   - ai_keywords.json           { slug → [30 keywords] }
   ═══════════════════════════════════════════════════════════════════ */

'use strict';
const fs   = require('fs');
const path = require('path');

const API_KEY = process.env.GROQ_API_KEY;
const GROQ_URL = 'https://api.groq.com/openai/v1/chat/completions';
const MODEL   = 'llama-3.3-70b-versatile';  // Fast + smart Groq model

// Rate limiting — avoid hitting API limits
const DELAY_MS = 800;  // 800ms between API calls
const sleep = ms => new Promise(r => setTimeout(r, ms));

/* ── Cache paths (passed from build.js via OUTPUT_DIR env) ──────── */
function getCachePaths(rootDir) {
  return {
    titles:    path.join(rootDir, 'data', 'ai_titles.json'),
    catDescs:  path.join(rootDir, 'data', 'category_descriptions.json'),
    keywords:  path.join(rootDir, 'data', 'ai_keywords.json'),
  };
}

function loadCache(filePath) {
  try {
    if (fs.existsSync(filePath)) return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch (e) { /* ignore corrupt cache */ }
  return {};
}

function saveCache(filePath, data) {
  const dir = path.dirname(filePath);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf8');
}

/* ── Groq API call (OpenAI-compatible) ──────────────────────────── */
async function callGroq(prompt, maxTokens = 300) {
  if (!API_KEY) throw new Error('GROQ_API_KEY not set');

  const res = await fetch(GROQ_URL, {
    method: 'POST',
    headers: {
      'Content-Type':  'application/json',
      'Authorization': `Bearer ${API_KEY}`,
    },
    body: JSON.stringify({
      model:      MODEL,
      max_tokens: maxTokens,
      temperature: 0.4,
      messages:   [{ role: 'user', content: prompt }],
    }),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Groq API error ${res.status}: ${err}`);
  }

  const data = await res.json();
  return data.choices?.[0]?.message?.content?.trim() || '';
}

/* ══════════════════════════════════════════════════════════════════
   1. SEO TITLE GENERATOR
   Input: post object { slug, subject_name, subcategory, category }
   Output: SEO title string (max 60 chars)
   Format: "Keyword-rich Title | Free PNG"
   ══════════════════════════════════════════════════════════════════ */
async function generateSeoTitle(post) {
  const prompt = `Generate ONE SEO title for a transparent PNG image download page.

Image details:
- Subject: ${post.subject_name || post.subcategory}
- Category: ${post.category.replace(/_/g, ' ')}
- Subcategory: ${post.subcategory}
- Slug: ${post.slug}

Rules:
1. Maximum 55 characters (without "| UltraPNG" suffix)
2. Must include the subject name naturally
3. Use power words: Free, HD, Transparent, Download, PNG
4. Be descriptive and unique — avoid generic titles
5. NO quotes, NO punctuation at start/end
6. Return ONLY the title text, nothing else

Example format: "Fresh Crab Transparent PNG - HD Free Download"`;

  const raw = await callGroq(prompt, 100);
  // Clean up any quotes or extra text
  const title = raw.replace(/^["']|["']$/g, '').trim().slice(0, 55);
  return `${title} | UltraPNG`;
}

/* ══════════════════════════════════════════════════════════════════
   2. CATEGORY KEYWORD TAGS GENERATOR
   Input: category name, subcategories list
   Output: { keywords50: [...50 strong SEO tags] }

   NO description — only high-impact keyword tags.
   Same keyword set used for ALL images in that category.
   New category வரும்போது மட்டும் AI generate செய்யும்.
   Cached in data/category_descriptions.json
   ══════════════════════════════════════════════════════════════════ */
async function generateCategoryContent(categoryName, subcategories, samplePosts) {
  const catDisplay = categoryName.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  const subcatList = [...new Set(subcategories)].slice(0, 8).join(', ');

  const prompt = `You are an SEO expert for UltraPNG, a free transparent PNG image download website.

Generate exactly 50 strong SEO keyword tags for the "${catDisplay}" category.
Category types: ${subcatList}

Keyword rules:
- Mix short-tail (2 words) and long-tail (3-5 words) keywords
- Include download intent: "free download", "hd png", "transparent background"
- Include tool-specific: "for canva", "for photoshop", "for illustrator", "for powerpoint"
- Include use-case: "for menu design", "for logo", "for banner", "for social media"
- Include format variants: "png", "clipart", "vector png", "cutout"
- Include quality signals: "hd", "high resolution", "4k", "no watermark"
- All lowercase
- NO duplicates
- Each tag: 2-5 words max

Return ONLY a JSON array of exactly 50 strings. No explanation, no markdown:
["tag one", "tag two", ...]`;

  const raw = await callGroq(prompt, 900);

  try {
    const clean  = raw.replace(/```json|```/g, '').trim();
    const parsed = JSON.parse(clean);
    if (Array.isArray(parsed)) {
      return { keywords50: parsed.slice(0, 50) };
    }
    throw new Error('Not an array');
  } catch (e) {
    console.warn(`⚠️  JSON parse failed for category ${categoryName}, using fallback`);
    return { keywords50: generateFallbackKeywords(catDisplay) };
  }
}

/* ══════════════════════════════════════════════════════════════════
   3. IMAGE-LEVEL 30 KEYWORDS
   Per-image keywords combining category keywords + specific subject
   ══════════════════════════════════════════════════════════════════ */
async function generateImageKeywords(post, categoryKeywords) {
  const subject = post.subject_name || post.subcategory;
  const catKws  = categoryKeywords.slice(0, 15).join(', ');

  const prompt = `Generate exactly 30 SEO keywords for this specific PNG image download page.

Image: ${subject} transparent PNG
Category: ${post.category.replace(/_/g, ' ')}
Base category keywords available: ${catKws}

Rules:
1. First 10: Very specific to "${subject}" (e.g. "crab png transparent", "red crab clipart hd")
2. Next 10: Category + use-case keywords (e.g. "seafood png for menu design")
3. Last 10: From the provided base keywords (pick most relevant)
4. NO duplicates
5. Return ONLY a JSON array of exactly 30 strings, no explanation

Example: ["crab transparent png", "crab clipart hd", ...]`;

  const raw = await callGroq(prompt, 500);

  try {
    const clean = raw.replace(/```json|```/g, '').trim();
    const parsed = JSON.parse(clean);
    if (Array.isArray(parsed)) return parsed.slice(0, 30);
  } catch (e) { /* fallback */ }

  // Fallback: combine subject + category keywords
  const subject_kws = [
    `${subject} transparent png`,
    `${subject} png free download`,
    `${subject} clipart hd`,
    `${subject} png no background`,
    `${subject} transparent background`,
  ];
  return [...subject_kws, ...categoryKeywords].slice(0, 30);
}

/* ── Fallback keywords when API fails (50 tags) ─────────────────── */
function generateFallbackKeywords(catDisplay) {
  const base = catDisplay.toLowerCase();
  return [
    `${base} png`, `${base} transparent`, `${base} free download`,
    `${base} hd png`, `${base} clipart`, `${base} transparent background`,
    `${base} png image`, `${base} no background`, `free ${base} png`,
    `${base} graphic`, `${base} illustration png`, `${base} vector png`,
    `${base} png for canva`, `${base} for photoshop`, `${base} design element`,
    `transparent ${base}`, `${base} cutout png`, `hd ${base} download`,
    `${base} png file`, `${base} image transparent`,
    `download ${base} png`, `${base} png free`, `${base} high resolution png`,
    `${base} png background removed`, `${base} sticker png`,
    `${base} png printable`, `${base} icon png`, `${base} logo png`,
    `${base} element png`, `${base} resource png`,
    `${base} for illustrator`, `${base} for powerpoint`, `${base} for banner`,
    `${base} for social media`, `${base} for menu design`,
    `${base} 4k png`, `${base} no watermark`, `${base} hd quality`,
    `${base} png commercial use`, `${base} free commercial png`,
    `best ${base} png`, `${base} png collection`, `${base} clipart free`,
    `${base} png transparent hd`, `${base} vector free`,
    `${base} for presentation`, `${base} for website`, `${base} for blog`,
    `${base} png download free`, `${base} free clipart`,
  ];
}

/* ══════════════════════════════════════════════════════════════════
   MAIN EXPORT — processAllPosts()
   Called by build.js before HTML generation.

   Logic:
   1. Load all 3 caches
   2. Find posts needing new SEO titles
   3. Find new categories → generate description + 30 keywords
   4. Find posts needing image keywords
   5. Save all caches back
   ══════════════════════════════════════════════════════════════════ */
async function processAllPosts(allPosts, rootDir) {
  const cachePaths = getCachePaths(rootDir);
  const titleCache  = loadCache(cachePaths.titles);
  const catCache    = loadCache(cachePaths.catDescs);
  const kwCache     = loadCache(cachePaths.keywords);

  let newTitles = 0, newCats = 0, newKws = 0;

  // ── Pass 1: Process NEW categories first ────────────────────────
  // Group posts by category
  const byCategory = {};
  allPosts.forEach(p => {
    const cat = p.category || p._category;
    if (!byCategory[cat]) byCategory[cat] = [];
    byCategory[cat].push(p);
  });

  for (const [cat, posts] of Object.entries(byCategory)) {
    if (catCache[cat]) {
      console.log(`  📦 Category "${cat}" — cached ✓`);
      continue;
    }

    console.log(`  🆕 New category detected: "${cat}" — generating 50 SEO keyword tags...`);
    const subcats    = posts.map(p => p.subcategory).filter(Boolean);
    const catContent = await generateCategoryContent(cat, subcats, posts.slice(0, 3));
    catCache[cat] = {
      keywords50:   catContent.keywords50,
      generated_at: new Date().toISOString().slice(0, 10),
    };
    newCats++;
    saveCache(cachePaths.catDescs, catCache); // Save immediately after each new category
    await sleep(DELAY_MS);
  }

  // ── Pass 2: Process NEW post SEO titles ─────────────────────────
  const postsNeedingTitles = allPosts.filter(p => !titleCache[p.slug]);
  console.log(`\n  🤖 SEO Titles: ${postsNeedingTitles.length} new posts need AI titles`);

  for (const post of postsNeedingTitles) {
    try {
      const title = await generateSeoTitle(post);
      titleCache[post.slug] = title;
      newTitles++;
      process.stdout.write(`    ✓ ${post.slug}: "${title}"\n`);

      // Save every 10 titles (avoid losing progress)
      if (newTitles % 10 === 0) saveCache(cachePaths.titles, titleCache);
      await sleep(DELAY_MS);
    } catch (e) {
      console.warn(`    ⚠️  Title gen failed for ${post.slug}: ${e.message}`);
      // Fallback title from h1
      const subject = post.subject_name || post.subcategory || 'PNG';
      titleCache[post.slug] = `${subject} Transparent PNG Free Download | UltraPNG`.slice(0, 70);
    }
  }
  saveCache(cachePaths.titles, titleCache);

  // ── Pass 3: Process NEW image keywords ──────────────────────────
  const postsNeedingKws = allPosts.filter(p => !kwCache[p.slug]);
  console.log(`\n  🔑 Keywords: ${postsNeedingKws.length} new posts need 30 keywords`);

  for (const post of postsNeedingKws) {
    const cat = post.category || post._category;
    // Use category's 50 keyword pool as base for image-level 30 keywords
    const catKeywords = catCache[cat]?.keywords50 || generateFallbackKeywords(cat.replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase()));

    try {
      const kws = await generateImageKeywords(post, catKeywords);
      kwCache[post.slug] = kws;
      newKws++;
      if (newKws % 10 === 0) saveCache(cachePaths.keywords, kwCache);
      await sleep(DELAY_MS);
    } catch (e) {
      console.warn(`    ⚠️  Keywords failed for ${post.slug}: ${e.message}`);
      const subject = post.subject_name || post.subcategory || 'image';
      kwCache[post.slug] = [
        `${subject} transparent png`, `${subject} free download`,
        ...catKeywords.slice(0, 28),
      ].slice(0, 30);
    }
  }
  saveCache(cachePaths.keywords, kwCache);

  console.log(`\n  ✅ AI Content Summary:`);
  console.log(`     🆕 New categories (50 keyword tags each): ${newCats}`);
  console.log(`     🤖 New SEO titles generated: ${newTitles}`);
  console.log(`     🔑 New per-image keyword sets (30 each): ${newKws}`);

  return { titleCache, catCache, kwCache };
}

module.exports = { processAllPosts, getCachePaths, loadCache };

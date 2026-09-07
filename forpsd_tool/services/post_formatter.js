const config = require('../config');

// Forbidden competitor names to scrub completely from all outputs
const FORBIDDEN_REGEX = [
  /forpsd\.com/gi,
  /forpsd/gi,
  /for\s+psd/gi,
  /ramarts/gi,
  /ram\s+arts/gi,
  /ram-arts/gi
];

function scrubBranding(str) {
  if (!str) return '';
  let result = String(str);
  for (const regex of FORBIDDEN_REGEX) {
    result = result.replace(regex, '');
  }
  // Clean up duplicate hyphens, extra spaces, trailing/leading punctuation
  result = result
    .replace(/\s*-\s*-+\s*/g, ' - ')
    .replace(/\s{2,}/g, ' ')
    .replace(/^[\s\-_]+|[\s\-_]+$/g, '');
  return result;
}

// Category mapping from ForPSD topic/keyword to TamilPSD standard category
const CATEGORY_MAP = {
  'wedding flex': 'Wedding',
  'wedding banner': 'Wedding',
  'wedding': 'Wedding',
  'ear piercing flex': 'Ear Piercing',
  'ear piercing': 'Ear Piercing',
  'puberty flex': 'Puberty',
  'puberty': 'Puberty',
  'first birthday flex': 'Birthday',
  'birthday flex': 'Birthday',
  'birthday': 'Birthday',
  'temple flex': 'Temple',
  'temple': 'Temple',
  'death flex': 'Death',
  'memorial flex': 'Death',
  'death': 'Death',
  'condolence': 'Death',
  'madurai flex': 'Flex',
  'cinematic background': 'Background',
  'house warming flex': 'House Warming',
  'house warming': 'House Warming',
  'decoration flex': 'Decoration',
  'name board': 'Name Board',
  'visiting card': 'Visiting Card',
  'visiting cards': 'Visiting Card',
  'shop banner': 'Shop',
  'shop/business': 'Shop',
  'shop': 'Shop',
  'invitation': 'Invitation',
  'invitations': 'Invitation',
  'gods': 'Gods',
  'hindu': 'Gods',
  'christian': 'Gods',
  'muslim': 'Gods',
  'dmk': 'DMK',
  'admk': 'ADMK',
  'tvk': 'TVK',
  'vck': 'VCK',
  'pmk': 'PMK',
  'bjp': 'BJP',
  'congress': 'Congress',
  'dmdk': 'DMDK',
  'ntk': 'NTK',
  'png': 'PNG',
  'elements': 'Elements'
};

function determineCanonicalCategory(fileName = '', topic = '') {
  const text = `${fileName} ${topic}`.toLowerCase();

  // 1. Political Parties & Leaders
  if (/\b(dmk|stalin|m\.k\.stalin|kalaingar|karunanithi|udhayanithi)\b/i.test(text)) return 'DMK';
  if (/\b(admk|aiadmk|edapadi|palanisamy|eps|ops|jayalalitha|mgr)\b/i.test(text)) return 'ADMK';
  if (/\b(tvk|vijay\s*tvk)\b/i.test(text)) return 'TVK';
  if (/\b(vck|thirumavalavan)\b/i.test(text)) return 'VCK';
  if (/\b(pmk|anbumani|ramadoss)\b/i.test(text)) return 'PMK';
  if (/\b(bjp|modi|annamalai)\b/i.test(text)) return 'BJP';
  if (/\b(congress|rahul)\b/i.test(text)) return 'Congress';
  if (/\b(ntk|seeman)\b/i.test(text)) return 'NTK';
  if (/\b(dmdk|vijayakanth)\b/i.test(text)) return 'DMDK';
  if (/\b(ammk|dinakaran|ttv)\b/i.test(text)) return 'AMMK';
  if (/\b(ambedkar)\b/i.test(text)) return 'Ambedkar';

  // 2. Invitations
  if (/\b(invitation|pathirikai|patrikai|invitations)\b/i.test(text)) return 'Invitation';

  // 3. Photo Albums & Sheets
  if (/\b(album|albums|floral\s*album|vertical\s*album)\b/i.test(text)) return 'Album';

  // 4. Frames
  if (/\b(frame|frames|collage\s*frame)\b/i.test(text)) return 'Frame';

  // 5. Calendars
  if (/\b(calender|calendar)\b/i.test(text)) return 'Calendar';

  // 6. Gods & Spiritual (Deities, Hindu, Gods)
  if (/\b(god|gods|hindu|amman|murugar|murugan|ganesha|vinayagar|pillaiyar|sivan|shiva|perumal|krishna|krishnan|ayyappan|ayappan|karuppasamy|karuppar|muniswaran|hanuman|anjaneyar|lakshmi|saraswathi|meenakshi|deivam|saibaba|baba|jesus|allah|christian|christion|muslim|ramzan|eid|pongal|deepavali|diwali)\b/i.test(text)) return 'Gods';

  // 7. Life Events / Functions
  if (/\b(death|memorial|kanneer|kanneer\s*anjali|ninaivu\s*anjali|rip|condolence)\b/i.test(text)) return 'Death';
  if (/\b(puberty|manjal\s*neerattu|manjalneerattu|manjal)\b/i.test(text)) return 'Puberty';
  if (/\b(ear\s*piercing|earpiercing|kadhani|kaadukuthu)\b/i.test(text)) return 'Ear Piercing';
  if (/\b(first\s*birthday|1st\s*birthday|birthday)\b/i.test(text)) return 'Birthday';
  if (/\b(house\s*warming|housewarming|grahapravesam|kudimuzhukku)\b/i.test(text)) return 'House Warming';
  if (/\b(temple|kovil|thiruvizha|kumbabishekam)\b/i.test(text)) return 'Temple';
  if (/\b(wedding|marriage|manamalai|nitchayathartham|engagement)\b/i.test(text)) return 'Wedding';

  // 8. Commercial / Print formats
  if (/\b(visiting\s*card|visiting\s*cards|business\s*card)\b/i.test(text)) return 'Visiting Card';
  if (/\b(name\s*board|nameboard)\b/i.test(text)) return 'Name Board';
  if (/\b(shop|grand\s*opening|store|business\s*banner)\b/i.test(text)) return 'Shop';
  if (/\b(notice|temple\s*notice|bit\s*notice)\b/i.test(text)) return 'Notice';
  if (/\b(certificate)\b/i.test(text)) return 'Certificate';
  if (/\b(gift\s*shield|shield)\b/i.test(text)) return 'Gift Shield';
  if (/\b(3d\s*text|3dtext)\b/i.test(text)) return '3d Text';
  if (/\b(title|title\s*design)\b/i.test(text)) return 'Title';
  if (/\b(caricature)\b/i.test(text)) return 'Caricature';
  if (/\b(flyer|flyers|brochure|pamphlet)\b/i.test(text)) return 'Flyers';
  if (/\b(cinematic\s*background|ai\s*background|background|backgrounds)\b/i.test(text)) return 'Background';
  if (/\b(png|cutout|elements)\b/i.test(text)) return 'PNG';
  if (/\b(actor|rajini|ajith|vijay|kamal|suriya|dhanush|simbu|sivakarthikeyan)\b/i.test(text)) return 'Actor';
  if (/\b(madurai\s*flex|madurai)\b/i.test(text)) return 'Flex';

  // Fallback
  return normalizeCategory(topic) || 'Design';
}

function normalizeCategory(raw) {
  if (!raw) return 'Design';
  const scrubbed = scrubBranding(raw);
  const clean = scrubbed.trim().toLowerCase();
  
  if (CATEGORY_MAP[clean]) return CATEGORY_MAP[clean];
  
  // Try matching words inside topic
  for (const [key, val] of Object.entries(CATEGORY_MAP)) {
    if (clean.includes(key)) return val;
  }

  // Fallback: title case
  const res = clean.replace(/\b\w/g, l => l.toUpperCase());
  return scrubBranding(res) || 'Design';
}

function cleanTitle(rawFileName, format = 'PSD') {
  const fmt = (format || 'PSD').toUpperCase();
  if (!rawFileName) {
    if (fmt === 'PNG') return 'PNG HD Download';
    if (fmt === 'TIF' || fmt === 'TIFF') return 'TIF / PSD Flex Design Download';
    return 'PSD Template Download';
  }

  // Remove leading id like "6562 - " or "AA (100) - "
  let title = rawFileName.replace(/^[0-9A-Za-z_()-]+\s*-\s*/, '').trim();
  
  // Scrub competitor branding
  title = scrubBranding(title);

  // Replace hyphens and underscores with spaces
  title = title.replace(/[-_]+/g, ' ').replace(/\s+/g, ' ').trim();

  // Remove immediate duplicate words (e.g. "Banner Banner" -> "Banner")
  title = title.replace(/\b(\w+)\s+\1\b/gi, '$1');

  // Strip any existing format tokens to prevent duplicate suffixes
  title = title.replace(/\b(psd|tif|tiff|png|cdr|template|download)\b/gi, '').trim();
  title = title.replace(/\s+/g, ' ').trim();

  // Capitalize words
  title = title.replace(/\b\w/g, l => l.toUpperCase());

  // Clean trailing punctuation
  title = title.replace(/[-_,\s]+$/, '');

  // Add clean standard suffix based on format
  if (fmt === 'PNG') {
    title = `${title} PNG HD Download`;
  } else if (fmt === 'TIF' || fmt === 'TIFF') {
    title = `${title} TIF / PSD Flex Design Download`;
  } else if (fmt === 'CDR') {
    title = `${title} CorelDraw CDR Design Download`;
  } else {
    title = `${title} PSD Template Download`;
  }

  // Final scrub pass
  title = scrubBranding(title);
  return title;
}

function generateTags(title, category, format = 'PSD') {
  const fmt = (format || 'PSD').toUpperCase();
  const words = title.toLowerCase()
    .replace(/[^a-z0-9\s]/g, '')
    .split(/\s+/)
    .filter(w => w.length > 2 && !['and', 'the', 'for', 'with', 'psd', 'tif', 'png', 'template', 'download'].includes(w));
  
  const formatTag = fmt === 'PNG' ? 'transparent png' : (fmt.startsWith('TIF') ? 'tif flex design' : 'psd template');
  const tagsSet = new Set([
    category.toLowerCase(),
    formatTag,
    'tamilpsd',
    'flex banner',
    'hd design',
    fmt.toLowerCase(),
    ...words
  ]);

  // Filter out any forbidden words from tags
  const validTags = Array.from(tagsSet).filter(t => {
    return !FORBIDDEN_REGEX.some(r => r.test(t));
  });

  return validTags.slice(0, 15).join(', ');
}

function generateDescription(title, category, dimensions = '1800x1200 pixels', format = 'PSD', dpi = '300 DPI', colorMode = 'CMYK') {
  const fmt = (format || 'PSD').toUpperCase();
  const formatName = fmt === 'PNG' ? 'High-Resolution Transparent PNG' : (fmt.startsWith('TIF') ? 'Print-Ready TIFF / PSD Flex Design' : (fmt === 'CDR' ? 'CorelDraw Vector CDR' : 'Adobe Photoshop PSD'));
  const softwareName = fmt === 'PNG' ? 'Photoshop, Illustrator, Canva, CorelDRAW' : (fmt === 'CDR' ? 'CorelDRAW X7+ / Photoshop' : 'Photoshop CS6 and Above');

  const desc = `## Overview
This high-quality ${category} ${fmt} design is crafted for professional flex banners, posters, printing, and graphic design projects. It features modern typography, festive color harmony, and high-definition clarity.

## Design Concept
Crafted specifically for Tamil Nadu printing standards, this design delivers stunning print output. All elements and layers are organized for easy customization.

## Technical Specifications
| Specification | Details |
|---|---|
| File Format | ${formatName} |
| Resolution | ${dpi} |
| Color Mode | ${colorMode} |
| Compatible Software | ${softwareName} |
| Dimensions | ${dimensions} |
| Quality Standard | High Definition / Print Ready |

## How to Use
1. Extract the downloaded .zip file.
2. Open the file in ${fmt === 'PNG' ? 'Photoshop, Canva, or any design tool' : (fmt === 'CDR' ? 'CorelDRAW' : 'Adobe Photoshop')}.
3. Customize text, dates, photos, and background elements as needed.
4. Export as TIFF or CMYK JPEG at 300 DPI for high-definition flex printing.

## File Password
No password required / Free Download on tamilpsd.in.`;

  return scrubBranding(desc);
}

function getFormattedDesignId(rawId) {
  if (!rawId) {
    const randNum = Math.floor(1000 + Math.random() * 9000);
    return `tam-ab-${randNum}`;
  }
  let str = String(rawId).trim();
  str = str.replace(/^(tamilpsd|tam-ab)-?/i, '');
  const numMatch = str.match(/\d+/);
  const num = numMatch ? numMatch[0] : (str.replace(/[^0-9A-Za-z_-]/g, '') || String(Date.now()).slice(-4));
  return `tam-ab-${num}`;
}

function formatPostDetails(post, fileInfo = {}) {
  const id = getFormattedDesignId(post.id);
  const format = (fileInfo.format || (post.category && post.category.toLowerCase().includes('png') ? 'PNG' : 'PSD')).toUpperCase();
  const category = determineCanonicalCategory(post.fileName || post.title, post.category);
  const title = cleanTitle(post.fileName || post.title || `Design ${id}`, format);
  const tags = generateTags(title, category, format);
  const dimensions = fileInfo.dimensions || '1800x1200 pixels';
  const dpi = fileInfo.dpi || '300 DPI';
  const fileSize = fileInfo.fileSizeFormatted || '45.00 MB';
  const colorMode = fileInfo.colorMode || (format === 'PNG' ? 'RGB' : 'CMYK');
  const software = fileInfo.software || (format === 'PNG' ? 'Adobe Photoshop / PNG' : (format === 'CDR' ? 'CorelDRAW / Photoshop' : 'Adobe Photoshop CC'));
  const description = generateDescription(title, category, dimensions, format, dpi, colorMode);
  
  const previewUrl = fileInfo.previewUrl || `${config.R2.cdnBase}/previews/${id}.webp`;
  const downloadUrl = fileInfo.downloadUrl || '';

  return {
    id,
    downloadUrl,
    title,
    category,
    tags,
    description,
    dimensions,
    dpi,
    fileSize,
    colorMode,
    software,
    fontsUsed: 'None',
    previewUrl
  };
}

module.exports = {
  scrubBranding,
  normalizeCategory,
  determineCanonicalCategory,
  cleanTitle,
  generateTags,
  generateDescription,
  formatPostDetails,
  getFormattedDesignId
};

let currentPosts = [];
let selectedPosts = new Set();
let activeFilter = 'all'; // 'all', 'new', 'uploaded'
let eventSource = null;

// DOM Elements
const categorySelect = document.getElementById('categorySelect');
const searchInput = document.getElementById('searchInput');
const btnSearch = document.getElementById('btnSearch');
const btnSelectAllNew = document.getElementById('btnSelectAllNew');
const btnSelectAll = document.getElementById('btnSelectAll');
const btnDeselectAll = document.getElementById('btnDeselectAll');
const postsGrid = document.getElementById('postsGrid');
const loadingState = document.getElementById('loadingState');
const emptyState = document.getElementById('emptyState');
const currentTempFolder = document.getElementById('currentTempFolder');
const totalCategoryCount = document.getElementById('totalCategoryCount');
const btnSyncExcel = document.getElementById('btnSyncExcel');

// Filter Tab Elements & Counters
const tabFilterAll = document.getElementById('tabFilterAll');
const tabFilterNew = document.getElementById('tabFilterNew');
const tabFilterUploaded = document.getElementById('tabFilterUploaded');
const countAllEl = document.getElementById('countAll');
const countNewEl = document.getElementById('countNew');
const countUploadedEl = document.getElementById('countUploaded');

// Selection Counters & Action Buttons
const selectedCountEl = document.getElementById('selectedCount');
const selectedNewCountEl = document.getElementById('selectedNewCount');
const selectedInExcelCountEl = document.getElementById('selectedInExcelCount');
const btnStartPipelineLocal = document.getElementById('btnStartPipelineLocal');
const btnStartPipelineGithub = document.getElementById('btnStartPipelineGithub');
const btnSelectedCountEls = document.querySelectorAll('.btn-selected-count');

// Modals
const progressModal = document.getElementById('progressModal');
const progressBarFill = document.getElementById('progressBarFill');
const progressPercent = document.getElementById('progressPercent');
const progressSummary = document.getElementById('progressSummary');
const progressItemsList = document.getElementById('progressItemsList');
const jobOverallStatus = document.getElementById('jobOverallStatus');
const btnCloseProgress = document.getElementById('btnCloseProgress');

const settingsModal = document.getElementById('settingsModal');
const btnOpenSettings = document.getElementById('btnOpenSettings');
const btnCloseSettingsModal = document.getElementById('btnCloseSettingsModal');
const btnSaveSettings = document.getElementById('btnSaveSettings');
const settingCookie = document.getElementById('settingCookie');
const settingTempDir = document.getElementById('settingTempDir');
const settingLocalCopies = document.getElementById('settingLocalCopies');
const gdriveStatusBadge = document.getElementById('gdriveStatusBadge');
const btnOpenGoogleAuth = document.getElementById('btnOpenGoogleAuth');
const oauthAuthCode = document.getElementById('oauthAuthCode');
const btnExchangeOAuth = document.getElementById('btnExchangeOAuth');
const settingRefreshToken = document.getElementById('settingRefreshToken');
const btnSaveRefreshTokenDirect = document.getElementById('btnSaveRefreshTokenDirect');
const btnTestTokenDirect = document.getElementById('btnTestTokenDirect');
const tokenValidationMsg = document.getElementById('tokenValidationMsg');
const gdriveHeaderStatus = document.getElementById('gdriveHeaderStatus');
const gdriveHeaderChip = document.getElementById('gdriveHeaderChip');
const gdriveHeaderDot = document.getElementById('gdriveHeaderDot');

// Initialize
window.addEventListener('DOMContentLoaded', async () => {
  await loadSettings();
  await loadCategories();
  await fetchPosts();
  initEventStream();
  initFilterTabs();
});

// Load Settings
async function loadSettings() {
  try {
    const res = await fetch('/api/settings');
    const data = await res.json();
    if (data.success && data.settings) {
      settingCookie.value = data.settings.forpsdCookie || '';
      settingTempDir.value = data.settings.tempWorkspace || 'F:/temp_forpsd_workspace';
      settingLocalCopies.checked = !!data.settings.useLocalCopies;
      if (settingRefreshToken) {
        settingRefreshToken.value = data.settings.googleRefreshToken || '';
      }
      currentTempFolder.textContent = data.settings.tempWorkspace || 'F:/temp_forpsd_workspace';
    }
  } catch (e) {
    console.error('Settings load error:', e);
  }
  await checkGdriveStatus();
}

// Check Google Drive Status
async function checkGdriveStatus() {
  try {
    const res = await fetch('/api/gdrive/status');
    const data = await res.json();
    if (data.success && data.tokenOk && data.authType === 'oauth') {
      if (gdriveStatusBadge) {
        gdriveStatusBadge.className = 'status-badge completed';
        gdriveStatusBadge.textContent = '🟢 CONNECTED (PERSONAL DRIVE)';
      }
      if (gdriveHeaderStatus) gdriveHeaderStatus.textContent = 'Connected (Personal)';
      if (gdriveHeaderChip) gdriveHeaderChip.style.borderColor = 'rgba(16, 185, 129, 0.4)';
    } else if (data.success && data.tokenOk && data.authType === 'service_account') {
      if (gdriveStatusBadge) {
        gdriveStatusBadge.className = 'status-badge uploading_gdrive';
        gdriveStatusBadge.textContent = '🟡 SERVICE ACCOUNT (OAuth Expired/None)';
      }
      if (gdriveHeaderStatus) gdriveHeaderStatus.textContent = 'Service Account';
      if (gdriveHeaderChip) gdriveHeaderChip.style.borderColor = 'rgba(245, 158, 11, 0.4)';
    } else {
      if (gdriveStatusBadge) {
        gdriveStatusBadge.className = 'status-badge error';
        gdriveStatusBadge.textContent = '🔴 NOT CONNECTED / EXPIRED';
      }
      if (gdriveHeaderStatus) gdriveHeaderStatus.textContent = 'Token Expired';
      if (gdriveHeaderChip) gdriveHeaderChip.style.borderColor = 'rgba(239, 68, 68, 0.5)';
    }
    return data;
  } catch (e) {
    if (gdriveStatusBadge) {
      gdriveStatusBadge.className = 'status-badge error';
      gdriveStatusBadge.textContent = 'ERROR';
    }
    if (gdriveHeaderStatus) gdriveHeaderStatus.textContent = 'Error';
  }
}

// Direct Save Token button
if (btnSaveRefreshTokenDirect) {
  btnSaveRefreshTokenDirect.addEventListener('click', async () => {
    const token = settingRefreshToken.value.trim();
    if (!token) {
      alert('Please enter a Google Refresh Token first.');
      return;
    }
    btnSaveRefreshTokenDirect.disabled = true;
    btnSaveRefreshTokenDirect.textContent = '⏳ Saving...';
    if (tokenValidationMsg) {
      tokenValidationMsg.style.display = 'block';
      tokenValidationMsg.style.color = '#38bdf8';
      tokenValidationMsg.textContent = 'Verifying token with Google...';
    }

    try {
      const res = await fetch('/api/gdrive/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refreshToken: token })
      });
      const data = await res.json();
      if (data.valid) {
        if (tokenValidationMsg) {
          tokenValidationMsg.style.color = '#10b981';
          tokenValidationMsg.textContent = '✅ Token valid & saved to settings.json!';
        }
        await checkGdriveStatus();
        alert('🎉 Google Drive Refresh Token saved & connected successfully!');
      } else {
        if (tokenValidationMsg) {
          tokenValidationMsg.style.color = '#ef4444';
          tokenValidationMsg.textContent = '⚠️ Token saved, but verification failed: ' + (data.error || 'Check permissions or expiry.');
        }
        await checkGdriveStatus();
        alert('⚠️ Token saved to settings.json, but Google reported an authentication error.');
      }
    } catch (e) {
      if (tokenValidationMsg) {
        tokenValidationMsg.style.color = '#ef4444';
        tokenValidationMsg.textContent = 'Network error: ' + e.message;
      }
    } finally {
      btnSaveRefreshTokenDirect.disabled = false;
      btnSaveRefreshTokenDirect.textContent = '💾 Save Token';
    }
  });
}

// Direct Test Token button
if (btnTestTokenDirect) {
  btnTestTokenDirect.addEventListener('click', async () => {
    const token = settingRefreshToken.value.trim();
    btnTestTokenDirect.disabled = true;
    btnTestTokenDirect.textContent = '⏳ Testing...';
    if (tokenValidationMsg) {
      tokenValidationMsg.style.display = 'block';
      tokenValidationMsg.style.color = '#38bdf8';
      tokenValidationMsg.textContent = 'Checking connection with Google Drive...';
    }

    try {
      const res = await fetch('/api/gdrive/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refreshToken: token })
      });
      const data = await res.json();
      if (data.valid) {
        if (tokenValidationMsg) {
          tokenValidationMsg.style.color = '#10b981';
          tokenValidationMsg.textContent = '✅ Verified! Google Drive is fully authorized and ready.';
        }
        await checkGdriveStatus();
      } else {
        if (tokenValidationMsg) {
          tokenValidationMsg.style.color = '#ef4444';
          tokenValidationMsg.textContent = '❌ Invalid or Expired: ' + (data.error || 'Check permissions.');
        }
        await checkGdriveStatus();
      }
    } catch (e) {
      if (tokenValidationMsg) {
        tokenValidationMsg.style.color = '#ef4444';
        tokenValidationMsg.textContent = 'Network error: ' + e.message;
      }
    } finally {
      btnTestTokenDirect.disabled = false;
      btnTestTokenDirect.textContent = '⚡ Test';
    }
  });
}

// Save All Settings
btnSaveSettings.addEventListener('click', async () => {
  try {
    const payload = {
      forpsdCookie: settingCookie.value.trim(),
      tempWorkspace: settingTempDir.value.trim(),
      useLocalCopies: settingLocalCopies.checked,
      googleRefreshToken: settingRefreshToken ? settingRefreshToken.value.trim() : ''
    };
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success) {
      currentTempFolder.textContent = data.settings.tempWorkspace;
      settingsModal.classList.remove('open');
      alert('Settings saved successfully!');
      await checkGdriveStatus();
      fetchPosts();
    }
  } catch (e) {
    alert('Error saving settings: ' + e.message);
  }
});

// Google Drive Auth Buttons
if (btnOpenGoogleAuth) {
  btnOpenGoogleAuth.addEventListener('click', async () => {
    try {
      const res = await fetch('/api/gdrive/status');
      const data = await res.json();
      const clientId = data.clientId || '308212866102-sd27dv5pjsr2bff3fioj4frr0ul58a1h.apps.googleusercontent.com';
      const redirectUri = data.redirectUri || 'http://localhost';
      const authUrl = `https://accounts.google.com/o/oauth2/v2/auth?client_id=${clientId}&redirect_uri=${encodeURIComponent(redirectUri)}&response_type=code&scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fdrive&access_type=offline&prompt=consent`;
      window.open(authUrl, '_blank', 'width=600,height=700');
    } catch (e) {
      alert('Error initiating auth: ' + e.message);
    }
  });
}

if (btnExchangeOAuth) {
  btnExchangeOAuth.addEventListener('click', async () => {
    const rawCode = oauthAuthCode.value.trim();
    if (!rawCode) {
      alert('Please paste the authorization code or redirect URL first.');
      return;
    }

    btnExchangeOAuth.disabled = true;
    btnExchangeOAuth.textContent = '⏳ Exchanging...';

    try {
      const res = await fetch('/api/gdrive/exchange', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: rawCode })
      });
      const data = await res.json();
      if (data.success) {
        if (settingRefreshToken) {
          settingRefreshToken.value = data.refreshToken || '';
        }
        oauthAuthCode.value = '';
        await checkGdriveStatus();
        alert('🎉 Google Drive connected successfully! All PSD files will now upload without quota limits.');
      } else {
        alert('Exchange failed: ' + (data.error || 'Unknown error'));
      }
    } catch (e) {
      alert('Network error: ' + e.message);
    } finally {
      btnExchangeOAuth.disabled = false;
      btnExchangeOAuth.textContent = '⚡ Exchange & Connect Google Drive';
    }
  });
}

btnOpenSettings.addEventListener('click', () => {
  settingsModal.classList.add('open');
  checkGdriveStatus();
});
btnCloseSettingsModal.addEventListener('click', () => settingsModal.classList.remove('open'));

// Sync Excel IDs manually
if (btnSyncExcel) {
  btnSyncExcel.addEventListener('click', async () => {
    btnSyncExcel.disabled = true;
    btnSyncExcel.textContent = '⏳ Syncing...';
    try {
      const res = await fetch('/api/excel/refresh', { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        alert(`✅ Synced! Loaded ${data.count} existing designs from designs.xlsx.`);
        await fetchPosts();
      } else {
        alert('Could not sync Excel: ' + data.error);
      }
    } catch (e) {
      alert('Error syncing Excel: ' + e.message);
    } finally {
      btnSyncExcel.disabled = false;
      btnSyncExcel.textContent = '🔄 Sync Excel';
    }
  });
}

// Load Categories
async function loadCategories() {
  try {
    const res = await fetch('/api/categories');
    const data = await res.json();
    if (data.success && data.categories) {
      categorySelect.innerHTML = '<option value="">-- All Categories --</option>';
      data.categories.forEach(cat => {
        const opt = document.createElement('option');
        opt.value = cat.topic;
        opt.textContent = cat.name;
        categorySelect.appendChild(opt);
      });
    }
  } catch (e) {
    console.error('Error loading categories:', e);
  }
}

// Fetch Posts
async function fetchPosts() {
  const topic = categorySelect.value;
  const query = searchInput.value.trim();

  postsGrid.innerHTML = '';
  loadingState.style.display = 'block';
  emptyState.style.display = 'none';
  if (totalCategoryCount) totalCategoryCount.textContent = 'Loading designs...';

  try {
    const res = await fetch(`/api/posts?topic=${encodeURIComponent(topic)}&query=${encodeURIComponent(query)}`);
    const data = await res.json();
    loadingState.style.display = 'none';

    if (data.success && data.posts && data.posts.length > 0) {
      currentPosts = data.posts;
      updateFilterCounters();
      renderFilteredPosts();
    } else {
      currentPosts = [];
      updateFilterCounters();
      if (totalCategoryCount) totalCategoryCount.textContent = '0 Designs';
      emptyState.style.display = 'block';
    }
  } catch (e) {
    loadingState.style.display = 'none';
    emptyState.style.display = 'block';
    if (totalCategoryCount) totalCategoryCount.textContent = 'Error loading';
    console.error('Error fetching posts:', e);
  }
  updateSelectionUI();
}

function updateFilterCounters() {
  const total = currentPosts.length;
  const inExcelCount = currentPosts.filter(p => p.inExcel).length;
  const newCount = total - inExcelCount;

  if (countAllEl) countAllEl.textContent = total;
  if (countNewEl) countNewEl.textContent = newCount;
  if (countUploadedEl) countUploadedEl.textContent = inExcelCount;
  if (totalCategoryCount) totalCategoryCount.textContent = `${total} Designs (${newCount} New, ${inExcelCount} In Excel)`;
}

function initFilterTabs() {
  const tabs = [tabFilterAll, tabFilterNew, tabFilterUploaded];
  tabs.forEach(tab => {
    if (!tab) return;
    tab.addEventListener('click', () => {
      tabs.forEach(t => t && t.classList.remove('active'));
      tab.classList.add('active');
      activeFilter = tab.getAttribute('data-filter') || 'all';
      renderFilteredPosts();
    });
  });
}

function renderFilteredPosts() {
  let filtered = currentPosts;
  if (activeFilter === 'new') {
    filtered = currentPosts.filter(p => !p.inExcel);
  } else if (activeFilter === 'uploaded') {
    filtered = currentPosts.filter(p => p.inExcel);
  }

  if (filtered.length === 0) {
    postsGrid.innerHTML = '';
    emptyState.style.display = 'block';
  } else {
    emptyState.style.display = 'none';
    renderPosts(filtered);
  }
}

// Render Posts Grid
function renderPosts(posts) {
  postsGrid.innerHTML = '';
  posts.forEach(post => {
    const isSelected = selectedPosts.has(post.id);
    const card = document.createElement('div');
    card.className = `post-card ${isSelected ? 'selected' : ''} ${post.inExcel ? 'in-excel' : ''}`;
    card.dataset.id = post.id;

    const thumbSrc = post.previewUrl || 'https://via.placeholder.com/300x200?text=Preview+Image';

    card.innerHTML = `
      <div class="card-thumb-wrap">
        <img class="card-thumb" src="${thumbSrc}" alt="${post.title}" loading="lazy" onerror="this.src='https://via.placeholder.com/300x200?text=Image+Not+Found'">
        <input type="checkbox" class="card-checkbox" ${isSelected ? 'checked' : ''}>
        ${post.inExcel ? '<span class="badge-excel" style="position:absolute;bottom:6px;left:6px;background:#059669;color:#fff;font-size:0.7rem;font-weight:700;padding:2px 6px;border-radius:4px;box-shadow:0 2px 4px rgba(0,0,0,0.4);">✓ IN EXCEL</span>' : ''}
      </div>
      <div class="card-body">
        <h4 class="card-title" title="${post.title}">${post.title}</h4>
        <div class="card-meta">
          <span class="cat-pill">${post.category}</span>
          <span>ID: #${post.id}</span>
        </div>
      </div>
    `;

    // Click handler to toggle selection
    card.addEventListener('click', (e) => {
      toggleSelect(post.id);
      const cb = card.querySelector('.card-checkbox');
      if (cb) cb.checked = selectedPosts.has(post.id);
    });

    postsGrid.appendChild(card);
  });
}

function toggleSelect(id) {
  if (selectedPosts.has(id)) {
    selectedPosts.delete(id);
  } else {
    selectedPosts.add(id);
  }
  const card = document.querySelector(`.post-card[data-id="${id}"]`);
  if (card) {
    card.classList.toggle('selected', selectedPosts.has(id));
  }
  updateSelectionUI();
}

function updateSelectionUI() {
  const totalSel = selectedPosts.size;
  let newSel = 0;
  let inExcelSel = 0;

  selectedPosts.forEach(id => {
    const post = currentPosts.find(p => String(p.id) === String(id));
    if (post && post.inExcel) {
      inExcelSel++;
    } else {
      newSel++;
    }
  });

  if (selectedCountEl) selectedCountEl.textContent = totalSel;
  if (selectedNewCountEl) selectedNewCountEl.textContent = newSel;
  if (selectedInExcelCountEl) selectedInExcelCountEl.textContent = inExcelSel;

  btnSelectedCountEls.forEach(el => el.textContent = totalSel);

  const disabled = totalSel === 0;
  if (btnStartPipelineLocal) btnStartPipelineLocal.disabled = disabled;
  if (btnStartPipelineGithub) btnStartPipelineGithub.disabled = disabled;
}

// Category & Search Listeners
categorySelect.addEventListener('change', () => fetchPosts());
btnSearch.addEventListener('click', () => fetchPosts());
searchInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') fetchPosts();
});

// Select All New (Skips items already in Excel!)
if (btnSelectAllNew) {
  btnSelectAllNew.addEventListener('click', () => {
    currentPosts.forEach(p => {
      if (!p.inExcel) {
        selectedPosts.add(p.id);
      }
    });
    document.querySelectorAll('.post-card').forEach(card => {
      const id = card.dataset.id;
      const isSel = selectedPosts.has(id);
      card.classList.toggle('selected', isSel);
      const cb = card.querySelector('.card-checkbox');
      if (cb) cb.checked = isSel;
    });
    updateSelectionUI();
  });
}

// Select All visible
btnSelectAll.addEventListener('click', () => {
  let targetList = currentPosts;
  if (activeFilter === 'new') targetList = currentPosts.filter(p => !p.inExcel);
  else if (activeFilter === 'uploaded') targetList = currentPosts.filter(p => p.inExcel);

  targetList.forEach(p => selectedPosts.add(p.id));
  document.querySelectorAll('.post-card').forEach(card => {
    const id = card.dataset.id;
    const isSel = selectedPosts.has(id);
    card.classList.toggle('selected', isSel);
    const cb = card.querySelector('.card-checkbox');
    if (cb) cb.checked = isSel;
  });
  updateSelectionUI();
});

// Deselect All
btnDeselectAll.addEventListener('click', () => {
  selectedPosts.clear();
  document.querySelectorAll('.post-card').forEach(card => {
    card.classList.remove('selected');
    const cb = card.querySelector('.card-checkbox');
    if (cb) cb.checked = false;
  });
  updateSelectionUI();
});

// Start Pipeline Execution (Localhost)
if (btnStartPipelineLocal) {
  btnStartPipelineLocal.addEventListener('click', async () => {
    const selectedItems = currentPosts.filter(p => selectedPosts.has(p.id));
    if (selectedItems.length === 0) return;

    const confirmed = confirm(
      `Start Local Automation for ${selectedItems.length} selected designs?\n\n` +
      `This will download, extract with 7-Zip, create WebP (tam-ab-xxx), upload to Cloudflare R2, upload to Google Drive, and record in designs.xlsx.`
    );
    if (!confirmed) return;

    progressModal.classList.add('open');
    btnCloseProgress.style.display = 'none';
    jobOverallStatus.textContent = 'RUNNING';
    jobOverallStatus.className = 'status-badge downloading';
    progressBarFill.style.width = '0%';
    progressPercent.textContent = '0%';
    progressSummary.textContent = `Processing 0 of ${selectedItems.length}...`;

    renderProgressList(selectedItems.map(p => ({
      ...p,
      status: 'queued',
      stage: 'Queued for processing'
    })));

    try {
      const res = await fetch('/api/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ posts: selectedItems, skipExisting: false })
      });
      const data = await res.json();
      if (!data.success) {
        alert('Failed to start local pipeline: ' + data.error);
        progressModal.classList.remove('open');
      }
    } catch (err) {
      alert('Error starting pipeline: ' + err.message);
      progressModal.classList.remove('open');
    }
  });
}

// Start Pipeline Execution (GitHub Actions Cloud Runner)
if (btnStartPipelineGithub) {
  btnStartPipelineGithub.addEventListener('click', async () => {
    const selectedItems = currentPosts.filter(p => selectedPosts.has(p.id));
    if (selectedItems.length === 0) return;

    const ids = selectedItems.map(p => p.id);
    const confirmed = confirm(
      `⚡ Dispatch ${ids.length} selected designs to GITHUB ACTIONS?\n\n` +
      `✅ Benefits:\n` +
      `• Runs in GitHub Cloud (1 Gbps+ speed)\n` +
      `• Creates tam-ab-(numbers) WebP and ZIP files\n` +
      `• 0 bytes downloaded to your local PC\n` +
      `• Automatically updates & commits designs.xlsx to GitHub\n\n` +
      `Are you ready to dispatch?`
    );
    if (!confirmed) return;

    btnStartPipelineGithub.disabled = true;
    btnStartPipelineGithub.textContent = '⏳ Dispatching to GitHub...';

    try {
      const res = await fetch('/api/github/dispatch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          postIds: ids,
          category: categorySelect.value || 'all',
          count: ids.length,
          skipExisting: false
        })
      });
      const data = await res.json();

      if (data.success) {
        alert(
          `🎉 GitHub Action successfully triggered!\n\n` +
          `Repo: ${data.repo}\n\n` +
          `Your browser will now open the live GitHub Actions log page where you can see the designs being processed in the cloud.`
        );
        if (data.workflowUrl) {
          window.open(data.workflowUrl, '_blank');
        }
      } else {
        alert('Failed to trigger GitHub Action: ' + (data.error || 'Unknown error'));
      }
    } catch (err) {
      alert('Network error dispatching to GitHub: ' + err.message);
    } finally {
      updateSelectionUI();
    }
  });
}

btnCloseProgress.addEventListener('click', () => {
  progressModal.classList.remove('open');
  fetchPosts();
});

// Render Progress Items
function renderProgressList(items) {
  progressItemsList.innerHTML = '';
  items.forEach((item, idx) => {
    const div = document.createElement('div');
    div.className = 'status-item';
    div.id = `status-item-${idx}`;

    div.innerHTML = `
      <div>
        <strong style="font-size: 0.95rem; color: #fff;">#${item.id} - ${(item.title || item.fileName || '').slice(0, 45)}</strong>
        <div class="stage-text" style="font-size: 0.8rem; color: #94a3b8; margin-top: 4px;">${item.stage || 'Queued'}</div>
      </div>
      <span class="status-badge ${item.status || 'queued'}">${(item.status || 'queued').replace('_', ' ')}</span>
    `;
    progressItemsList.appendChild(div);
  });
}

function updateProgressItem(index, item) {
  const el = document.getElementById(`status-item-${index}`);
  if (el) {
    const stageEl = el.querySelector('.stage-text');
    const badgeEl = el.querySelector('.status-badge');
    if (stageEl) stageEl.textContent = item.stage;
    if (badgeEl) {
      badgeEl.className = `status-badge ${item.status}`;
      badgeEl.textContent = item.status.replace('_', ' ');
    }
  }

  if (item.progress !== undefined) {
    progressBarFill.style.width = `${item.progress}%`;
    progressPercent.textContent = `${item.progress}%`;
  }
  if (item.stage) {
    progressSummary.textContent = item.stage;
  }
}

// Server-Sent Events (SSE) stream for live progress updates
function initEventStream() {
  if (eventSource) eventSource.close();
  eventSource = new EventSource('/api/stream');

  eventSource.addEventListener('job_started', (e) => {
    const job = JSON.parse(e.data);
    renderProgressList(job.items);
  });

  eventSource.addEventListener('item_update', (e) => {
    const { index, item } = JSON.parse(e.data);
    updateProgressItem(index, item);
  });

  eventSource.addEventListener('job_finished', (e) => {
    const job = JSON.parse(e.data);
    progressBarFill.style.width = '100%';
    progressPercent.textContent = '100%';
    const skippedMsg = job.skipped ? `, ${job.skipped} skipped` : '';
    progressSummary.textContent = `Completed: ${job.completed} successful, ${job.failed} failed${skippedMsg}.`;
    jobOverallStatus.textContent = job.failed === 0 ? 'COMPLETED' : 'FINISHED WITH ERRORS';
    jobOverallStatus.className = `status-badge ${job.failed === 0 ? 'completed' : 'error'}`;
    btnCloseProgress.style.display = 'inline-block';
  });
}

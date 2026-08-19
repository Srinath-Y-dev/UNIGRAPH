/* ============================================================
   UniGraph IQ Enterprise 2.0 — Interactive Frontend Engine
   - Force-Directed Knowledge Graph Visualizer (Canvas Physics)
   - Side-by-Side Product Comparison Matrix
   - In-line Attribute Conflict Workbench & Steward Override
   - Multi-Format Syndication Hub Exporter
   - Faceted Catalog Multi-Filter Search
   - Visual SVG Analytics & Metrics
   - Active Connector Simulator
   ============================================================ */

/* ----- State ---------------------------------------------- */
let state = {
  products: [],
  dashboard: null,
  analytics: null,
  selectedCompareSkus: new Set(),
  activeSyndicationSku: null,
  currentProduct: null,
  graphData: null,
  graphAnimId: null,
};

/* ----- Utilities ------------------------------------------ */
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];

function esc(v) {
  return String(v ?? '').replace(/[&<>"']/g, m => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]
  ));
}

function formatMarkdown(text) {
  if (!text) return '';
  let safe = esc(text);
  // Code blocks: `code`
  safe = safe.replace(/`([^`]+)`/g, '<code style="background:rgba(255,255,255,0.08);padding:2px 5px;border-radius:4px;font-family:monospace;font-size:12px">$1</code>');
  // Bold: **text**
  safe = safe.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  // Italic: *text* or _text_
  safe = safe.replace(/\*([^*]+)\*/g, '<em>$1</em>');
  // Line items: • or - or *
  const lines = safe.split('\n');
  let inList = false;
  let result = [];
  for (let line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith('• ') || trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      if (!inList) {
        result.push('<ul style="margin:6px 0 6px 18px;padding:0">');
        inList = true;
      }
      result.push(`<li>${trimmed.replace(/^[•\-\*]\s*/, '')}</li>`);
    } else {
      if (inList) {
        result.push('</ul>');
        inList = false;
      }
      if (trimmed) {
        result.push(`<p style="margin:4px 0">${line}</p>`);
      } else {
        result.push('<div style="height:6px"></div>');
      }
    }
  }
  if (inList) result.push('</ul>');
  return result.join('');
}

function statusClass(s) {
  return s === 'READY_TO_PUBLISH' ? 'ready' : s === 'REVIEW_REQUIRED' ? 'review' : 'insufficient';
}

function statusText(s) {
  return String(s || '').replaceAll('_', ' ');
}

function toast(msg) {
  const t = $('#toast');
  if (!t) return;
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2800);
}

/* ---- Theme Management ------------------------------------ */
function initTheme() {
  const saved = localStorage.getItem('ugiq_theme') || 'dark';
  document.body.setAttribute('data-theme', saved);
}
function toggleTheme() {
  const current = document.body.getAttribute('data-theme') || 'dark';
  const next = current === 'dark' ? 'light' : 'dark';
  document.body.setAttribute('data-theme', next);
  localStorage.setItem('ugiq_theme', next);
  toast(`Theme switched to ${next} mode`);
  if (state.currentProduct) renderKnowledgeGraph();
}
initTheme();

/* ---- Mobile Nav ------------------------------------------ */
function toggleMobileNav() {
  const menu = $('#mobile-nav-menu');
  const btn = $('#burger-btn');
  if (!menu) return;
  const open = menu.style.display !== 'none';
  menu.style.display = open ? 'none' : 'flex';
  if (btn) btn.setAttribute('aria-expanded', String(!open));
}
function closeMobileNav() {
  const menu = $('#mobile-nav-menu');
  const btn = $('#burger-btn');
  if (menu) menu.style.display = 'none';
  if (btn) btn.setAttribute('aria-expanded', 'false');
}
document.addEventListener('click', e => {
  if (!e.target.closest('#mobile-nav-menu') && !e.target.closest('#burger-btn')) closeMobileNav();
});

/* ----- API Helper ----------------------------------------- */
async function api(url, opt = {}) {
  const token = localStorage.getItem('ugiq_token');
  opt.headers = new Headers(opt.headers || {});
  if (token) opt.headers.set('Authorization', 'Bearer ' + token);
  const r = await fetch(url, opt);
  if (r.status === 401) { openLogin(); throw new Error('Authentication required'); }
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

/* ============================================================
   COUNT-UP ANIMATION
   ============================================================ */
function animateCount(el, target, duration = 800) {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    el.textContent = target;
    return;
  }
  const isFloat = String(target).includes('.');
  const startTime = performance.now();
  const numTarget = parseFloat(target) || 0;
  function step(now) {
    const progress = Math.min((now - startTime) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    const current = numTarget * eased;
    el.textContent = isFloat ? current.toFixed(1) : Math.round(current);
    if (progress < 1) requestAnimationFrame(step);
    else el.textContent = isFloat ? numTarget.toFixed(1) : Math.round(numTarget);
  }
  requestAnimationFrame(step);
}

/* ============================================================
   NAVIGATION
   ============================================================ */
function showView(name) {
  $$('.view').forEach(v => v.classList.remove('active'));
  const view = $(`#view-${name}`);
  if (view) view.classList.add('active');

  $$('.nav').forEach(n => {
    const isActive = n.dataset.view === name;
    n.classList.toggle('active', isActive);
    n.setAttribute('aria-current', isActive ? 'page' : 'false');
  });

  const titles = {
    dashboard: 'Command Center',
    enrich: 'Enrich Product',
    catalog: 'Industrial Catalog',
    compare: 'Cross-Reference Matrix',
    review: 'Review & Governance Queue',
    copilot: 'Catalog Copilot',
    operations: 'Operations & Batch Jobs',
    enterprise: 'Enterprise Connectors & PIM',
    admin: 'Admin Panel',
  };
  const pt = $('#page-title');
  if (pt && name !== 'dashboard') pt.textContent = titles[name] || name;

  if (name === 'catalog') renderCatalog();
  if (name === 'compare') renderCompareView();
  if (name === 'review') renderReview();
  if (name === 'operations') loadOperations();
  if (name === 'enterprise') loadEnterprise();
  if (name === 'admin') loadAdmin();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

/* ============================================================
   COMMAND CENTER & ANALYTICS CHARTS
   ============================================================ */
function metric(label, val, sub) {
  return `<div class="metric">
    <div class="metric-label">${esc(label)}</div>
    <strong data-count="${val}">${val}</strong>
    <div class="metric-sub">${esc(sub)}</div>
  </div>`;
}

function renderHealthBars(m) {
  const bars = [
    { label: 'Intelligence Score', val: m.avg_iq || 0, color: 'var(--color-primary)' },
    { label: 'Commerce Readiness', val: m.avg_commerce || 0, color: 'var(--color-success)' },
    { label: 'Attribute Completeness', val: m.avg_completeness || 0, color: 'var(--color-info)' },
  ];
  $('#health-bars').innerHTML = bars.map(b => `
    <div style="margin-bottom:var(--sp-3)">
      <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:4px">
        <span>${b.label}</span>
        <strong>${Number(b.val).toFixed(1)}%</strong>
      </div>
      <div style="background:var(--color-surface-subtle);height:8px;border-radius:var(--radius-full);overflow:hidden;border:1px solid var(--color-border)">
        <div style="width:${Math.min(100, Math.max(0, b.val))}%;height:100%;background:${b.color};border-radius:var(--radius-full);transition:width 0.8s cubic-bezier(0.16,1,0.3,1)"></div>
      </div>
    </div>
  `).join('');
  $('#health-score').textContent = (m.avg_iq ? Number(m.avg_iq).toFixed(1) : '0') + '%';
}

function renderAnalyticsCharts(analytics) {
  if (!analytics) return;
  
  // 1. Category Breakdown Donut / Bar
  const cats = analytics.categories || [];
  const catTotal = cats.reduce((acc, c) => acc + c.count, 0) || 1;
  const colors = ['#0284c7', '#6366f1', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6', '#14b8a6', '#f97316'];
  
  const catSvg = `<svg class="chart-svg" viewBox="0 0 400 180">
    <g transform="translate(10, 20)">
      ${cats.slice(0, 5).map((c, i) => {
        const pct = (c.count / catTotal) * 100;
        const w = (pct / 100) * 220;
        const y = i * 30;
        return `
          <text x="0" y="${y + 14}" fill="var(--color-text-muted)" font-size="11" font-weight="600">${esc(c.category)}</text>
          <rect x="130" y="${y + 4}" width="220" height="12" rx="4" fill="var(--color-surface-subtle)" />
          <rect x="130" y="${y + 4}" width="${Math.max(6, w)}" height="12" rx="4" fill="${colors[i % colors.length]}" />
          <text x="${130 + w + 8}" y="${y + 14}" fill="var(--color-text)" font-size="11" font-weight="700">${c.count} (${pct.toFixed(0)}%)</text>
        `;
      }).join('')}
    </g>
  </svg>`;
  $('#chart-categories').innerHTML = catSvg;

  // 2. Completeness Brackets Chart
  const buckets = analytics.completeness_buckets || {};
  const bKeys = Object.keys(buckets);
  const bMax = Math.max(...Object.values(buckets), 1);
  
  const compSvg = `<svg class="chart-svg" viewBox="0 0 400 180">
    <g transform="translate(20, 20)">
      ${bKeys.map((k, i) => {
        const count = buckets[k] || 0;
        const barH = (count / bMax) * 110;
        const x = i * 85 + 20;
        const y = 120 - barH;
        return `
          <rect x="${x}" y="${y}" width="48" height="${barH}" rx="4" fill="${i === 0 ? 'var(--color-success)' : i === 1 ? 'var(--color-info)' : i === 2 ? 'var(--color-warning)' : 'var(--color-danger)'}" />
          <text x="${x + 24}" y="${y - 6}" text-anchor="middle" fill="var(--color-text)" font-size="12" font-weight="700">${count}</text>
          <text x="${x + 24}" y="142" text-anchor="middle" fill="var(--color-text-muted)" font-size="11">${k}</text>
        `;
      }).join('')}
      <line x1="10" y1="122" x2="360" y2="122" stroke="var(--color-border)" stroke-width="1"/>
    </g>
  </svg>`;
  $('#chart-completeness').innerHTML = compSvg;
}

function renderAttention(products, reviewQueue) {
  const conflicts = products.filter(p => p.conflict_count > 0);
  let html = '';
  if (conflicts.length) {
    html += `<div style="margin-bottom:var(--sp-3)">
      <div style="font-size:12px;color:var(--color-warning);font-weight:700;margin-bottom:6px">⚠️ ${conflicts.length} PRODUCTS WITH CONFLICTING DATA</div>
      ${conflicts.slice(0, 3).map(p => `
        <div class="review-item" style="padding:8px 0;border-bottom:1px solid var(--color-border)">
          <div><strong>${esc(p.sku)}</strong> <small class="muted">(${esc(p.category)})</small></div>
          <button class="button ghost sm" onclick="openProduct('${esc(p.sku)}')">Resolve Conflicts</button>
        </div>
      `).join('')}
    </div>`;
  }
  if (reviewQueue.length) {
    html += `<div>
      <div style="font-size:12px;color:var(--color-text-muted);font-weight:700;margin-bottom:6px">📋 ${reviewQueue.length} ITEMS IN REVIEW QUEUE</div>
      <button class="button ghost sm" onclick="showView('review')">Open Review Queue →</button>
    </div>`;
  }
  if (!conflicts.length && !reviewQueue.length) {
    html = '<p class="muted" style="text-align:center;padding:var(--sp-4)">All catalog products meet publish readiness standards.</p>';
  }
  $('#attention').innerHTML = html;
}

async function load() {
  try {
    const [d, a] = await Promise.all([
      api('/api/dashboard'),
      api('/api/catalog/analytics'),
    ]);
    state.dashboard = d;
    state.analytics = a;
    state.products = await api('/api/products');

    const m = d.metrics;
    $('#metrics').innerHTML =
      metric('Total Golden Records', m.total || 0, 'Catalog scale') +
      metric('Ready to Publish', m.ready || 0, 'Meets all gate policies') +
      metric('Requires Review', m.review || 0, 'Conflicts / low completeness') +
      metric('Avg. Intelligence IQ', Number(m.avg_iq || 0).toFixed(1) + '%', 'Portfolio confidence');

    setTimeout(() => {
      $$('#metrics .metric strong[data-count]').forEach(el => {
        const raw = el.dataset.count || '0';
        const num = parseFloat(raw.replace('%', ''));
        animateCount(el, raw.includes('%') ? num.toFixed(1) : num);
      });
    }, 100);

    renderHealthBars(m);
    renderAttention(state.products, d.review_queue || []);
    renderAnalyticsCharts(a);

    // Populate Category & Manufacturer Filter selects
    populateCatalogFilters();

    // Recent products
    $('#recent-products').innerHTML = (d.products || []).slice(0, 6).map(p => `
      <tr class="clickable" onclick="openProduct('${esc(p.sku)}')">
        <td><strong>${esc(p.sku)}</strong><div class="muted" style="font-size:12px">${esc(p.manufacturer || '')} · ${esc(p.mpn || '')}</div></td>
        <td>${esc(p.category)}</td>
        <td><span class="tag">${esc(p.taxonomy?.unspsc || 'UNSPSC')}</span></td>
        <td><strong style="color:var(--color-primary)">${p.intelligence_score}%</strong></td>
        <td>${p.commerce_score}%</td>
        <td><span class="status ${statusClass(p.status)}">${statusText(p.status)}</span></td>
        <td>
          <button class="text-btn" onclick="event.stopPropagation(); openProduct('${esc(p.sku)}')">Inspect →</button>
        </td>
      </tr>
    `).join('') || '<tr><td colspan="7" class="muted" style="text-align:center;padding:2rem">No products yet.</td></tr>';

  } catch (err) {
    console.error('Failed to load dashboard:', err);
  }
}

/* ============================================================
   CATALOG FACETED FILTERING & RENDERING
   ============================================================ */
function populateCatalogFilters() {
  const cats = [...new Set(state.products.map(p => p.category).filter(Boolean))].sort();
  const mfrs = [...new Set(state.products.map(p => p.manufacturer).filter(Boolean))].sort();

  const catSel = $('#filter-category');
  if (catSel) {
    catSel.innerHTML = '<option value="">All Categories</option>' + cats.map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join('');
  }
  const mfrSel = $('#filter-mfr');
  if (mfrSel) {
    mfrSel.innerHTML = '<option value="">All Manufacturers</option>' + mfrs.map(m => `<option value="${esc(m)}">${esc(m)}</option>`).join('');
  }
  const compAddSel = $('#compare-add-select');
  if (compAddSel) {
    compAddSel.innerHTML = '<option value="">+ Add product to comparison matrix...</option>' + state.products.map(p => `<option value="${esc(p.sku)}">${esc(p.sku)} — ${esc(p.manufacturer || '')} ${esc(p.category)}</option>`).join('');
  }
}

function resetCatalogFilters() {
  $('#catalog-search').value = '';
  $('#filter-category').value = '';
  $('#filter-status').value = '';
  $('#filter-mfr').value = '';
  $('#filter-completeness').value = '0';
  $('#completeness-val').textContent = '0%';
  $('#filter-conflicts-only').checked = false;
  renderCatalog();
}

function renderCatalog() {
  const q = ($('#catalog-search')?.value || '').toLowerCase().trim();
  const cat = $('#filter-category')?.value || '';
  const st = $('#filter-status')?.value || '';
  const mfr = $('#filter-mfr')?.value || '';
  const minComp = parseFloat($('#filter-completeness')?.value || '0');
  const conflictsOnly = $('#filter-conflicts-only')?.checked || false;

  const filtered = state.products.filter(p => {
    if (cat && p.category !== cat) return false;
    if (st && p.status !== st) return false;
    if (mfr && (p.manufacturer || '') !== mfr) return false;
    if (p.completeness < minComp) return false;
    if (conflictsOnly && p.conflict_count === 0) return false;
    if (q) {
      const haystack = [p.sku, p.manufacturer, p.mpn, p.category].join(' ').toLowerCase();
      if (!haystack.includes(q)) return false;
    }
    return true;
  });

  const countEl = $('#catalog-count');
  if (countEl) countEl.textContent = `Showing ${filtered.length} of ${state.products.length} Golden Records`;

  $('#catalog-body').innerHTML = filtered.map(p => {
    const isSelected = state.selectedCompareSkus.has(p.sku);
    return `
      <tr class="clickable" onclick="openProduct('${esc(p.sku)}')">
        <td onclick="event.stopPropagation()">
          <input type="checkbox" ${isSelected ? 'checked' : ''} onchange="toggleCompareSku('${esc(p.sku)}', this.checked)">
        </td>
        <td>
          <strong>${esc(p.sku)}</strong>
          <div class="muted" style="font-size:12px;margin-top:2px">${esc(p.manufacturer || 'OEM')} · ${esc(p.mpn || '')}</div>
        </td>
        <td>
          <div>${esc(p.category)}</div>
          <span class="tag" style="margin-top:2px;display:inline-block">${esc(p.taxonomy?.unspsc || 'UNSPSC')}</span>
        </td>
        <td>
          <div style="font-weight:700">${p.completeness}%</div>
          <div style="background:var(--color-surface-subtle);height:4px;width:60px;border-radius:2px;overflow:hidden;margin-top:4px">
            <div style="width:${p.completeness}%;height:100%;background:var(--color-primary)"></div>
          </div>
        </td>
        <td><strong style="color:var(--color-primary)">${p.intelligence_score}%</strong></td>
        <td>${p.commerce_score}%</td>
        <td>
          <span class="status ${statusClass(p.status)}">${statusText(p.status)}</span>
          ${p.conflict_count > 0 ? `<div style="color:var(--color-warning);font-size:11px;font-weight:700;margin-top:2px">⚠️ ${p.conflict_count} conflict(s)</div>` : ''}
        </td>
        <td onclick="event.stopPropagation()">
          <div style="display:flex;gap:4px">
            <button class="button ghost sm" onclick="openProduct('${esc(p.sku)}')">Inspect</button>
            <button class="button ghost sm" title="Export formats" onclick="openSyndicationModal('${esc(p.sku)}')">Syndicate</button>
          </div>
        </td>
      </tr>
    `;
  }).join('') || '<tr><td colspan="8" class="muted" style="padding:2.5rem;text-align:center">No matching products found.</td></tr>';
}

function exportCatalogCsv() {
  window.location.href = '/api/export/catalog.csv';
}

/* ============================================================
   MULTI-SKU COMPARISON MATRIX
   ============================================================ */
function toggleCompareSku(sku, checked) {
  if (checked) state.selectedCompareSkus.add(sku);
  else state.selectedCompareSkus.delete(sku);
  updateCompareBar();
}

function toggleSelectAllCompare(checked) {
  state.products.slice(0, 4).forEach(p => {
    if (checked) state.selectedCompareSkus.add(p.sku);
    else state.selectedCompareSkus.delete(p.sku);
  });
  renderCatalog();
  updateCompareBar();
}

function updateCompareBar() {
  const bar = $('#compare-bar');
  const count = $('#compare-selected-count');
  if (!bar || !count) return;
  const n = state.selectedCompareSkus.size;
  count.textContent = n;
  bar.style.display = n > 0 ? 'block' : 'none';
}

function clearCompareSelection() {
  state.selectedCompareSkus.clear();
  renderCatalog();
  updateCompareBar();
}

function launchCompareFromBar() {
  showView('compare');
}

function addCompareSku(sku) {
  if (!sku) return;
  state.selectedCompareSkus.add(sku);
  renderCompareView();
  updateCompareBar();
}

function removeCompareSku(sku) {
  state.selectedCompareSkus.delete(sku);
  renderCompareView();
  updateCompareBar();
}

async function renderCompareView() {
  // Ensure at least 2 SKUs are selected for demo if empty
  if (state.selectedCompareSkus.size < 2 && state.products.length >= 2) {
    state.products.slice(0, 2).forEach(p => state.selectedCompareSkus.add(p.sku));
  }

  const skus = Array.from(state.selectedCompareSkus);
  $('#compare-chips').innerHTML = skus.map(s => `
    <div class="compare-chip">
      <span>${esc(s)}</span>
      <button onclick="removeCompareSku('${esc(s)}')">×</button>
    </div>
  `).join('');

  if (skus.length < 2) {
    $('#compare-matrix-container').innerHTML = `
      <article class="card" style="text-align:center;padding:3rem">
        <h3>Select at least 2 products to build comparison matrix</h3>
        <p class="muted" style="margin-top:6px">Use the dropdown above or check products in the Catalog table.</p>
      </article>
    `;
    return;
  }

  try {
    const res = await api('/api/compare', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ skus }),
    });

    const { products, matrix } = res;

    let headersHtml = `<th>Technical Specification</th>` + products.map(p => `
      <th class="compare-header-cell">
        <strong>${esc(p.sku)}</strong>
        <div class="muted" style="font-size:12px">${esc(p.identity?.manufacturer || '')} · ${esc(p.category)}</div>
        <div style="margin-top:6px">
          <span class="status ${statusClass(p.scores?.status)}">${statusText(p.scores?.status)}</span>
        </div>
      </th>
    `).join('');

    let rowsHtml = matrix.map(row => {
      const cells = products.map(p => {
        const item = row.values[p.sku] || { value: null };
        if (item.value === null) return `<td style="color:var(--color-text-dim);text-align:center">—</td>`;
        return `<td>
          <div style="font-weight:600">${esc(item.value)}</div>
          <div class="muted" style="font-size:11px">${Math.round((item.confidence || 1) * 100)}% confidence</div>
        </td>`;
      }).join('');

      const badge = row.is_match
        ? `<span class="match-badge identical">MATCH</span>`
        : `<span class="match-badge variance">VARIANCE</span>`;

      return `
        <tr class="${row.is_match ? 'match-row' : 'diff-row'}">
          <td>
            <div style="font-weight:700">${esc(row.label)}</div>
            <div style="margin-top:2px">${badge}</div>
          </td>
          ${cells}
        </tr>
      `;
    }).join('');

    $('#compare-matrix-container').innerHTML = `
      <article class="card">
        <div class="section-head">
          <div>
            <span class="kicker">Cross-Reference Matrix</span>
            <h3>Specification Variance &amp; Matching Analysis (${matrix.length} Parameters)</h3>
          </div>
        </div>
        <div class="table-wrap">
          <table class="compare-matrix-table">
            <thead><tr>${headersHtml}</tr></thead>
            <tbody>${rowsHtml}</tbody>
          </table>
        </div>
      </article>
    `;
  } catch (err) {
    console.error('Failed to render comparison matrix:', err);
    toast('Error generating comparison matrix');
  }
}

/* ============================================================
   PRODUCT DETAIL & INTERACTIVE KNOWLEDGE GRAPH
   ============================================================ */
function attrHtml(name, a, sku) {
  const val = `${a.value} ${a.unit || ''}`.trim();
  const prov = a.provenance || [];
  const latest = prov[0] || {};
  return `
    <div class="attr-card">
      <div style="display:flex;justify-content:space-between;align-items:flex-start">
        <div class="attr-name">${esc(name.replace(/_/g, ' '))}</div>
        <button class="text-btn" style="font-size:11px" onclick="openAttrEditModal('${esc(sku)}', '${esc(name)}', '${esc(a.value)}', '${esc(a.unit || '')}')">Edit</button>
      </div>
      <div class="attr-val">${esc(val)}</div>
      <div class="attr-meta">
        <span>${Math.round((a.confidence || 1) * 100)}% conf.</span>
        <span class="tag">${esc(a.status || 'VERIFIED')}</span>
      </div>
      ${latest.source ? `<div class="muted" style="font-size:10px;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${esc(latest.source)}">Source: ${esc(latest.source)}</div>` : ''}
    </div>
  `;
}

async function openProduct(sku) {
  try {
    showView('catalog');
    const [p, g] = await Promise.all([
      api(`/api/products/${encodeURIComponent(sku)}`),
      api(`/api/products/${encodeURIComponent(sku)}/graph`),
    ]);

    state.currentProduct = p;
    state.graphData = g;

    const attrs = Object.entries(p.attributes || {});
    
    // Build conflicts resolution block
    let conflictsHtml = '';
    if (p.conflicts?.length) {
      conflictsHtml = `
        <h3 style="margin-top:var(--sp-4);color:var(--color-warning)">⚠️ QA Guardian Attribute Conflicts</h3>
        <p class="muted" style="font-size:12px;margin-bottom:8px">Multiple data sources disagree. Click a candidate chip to accept that source's value as authoritative.</p>
        ${p.conflicts.map(c => `
          <div class="conflict">
            <div style="display:flex;justify-content:space-between">
              <strong>${esc(c.attribute.replace(/_/g, ' ').toUpperCase())}</strong>
              <small class="muted">${esc(c.reason)}</small>
            </div>
            <div class="conflict-candidates">
              ${c.candidates.map(cand => {
                const cVal = `${cand.value} ${cand.unit || ''}`.trim();
                return `
                  <button class="candidate-chip" onclick="resolveCandidate('${esc(sku)}', '${esc(c.attribute)}', '${esc(cand.value)}', '${esc(cand.unit || '')}', '${esc(cand.source)}')">
                    ✓ Use: <strong>${esc(cVal)}</strong> <small>(${esc(cand.source)})</small>
                  </button>
                `;
              }).join('')}
              <button class="candidate-chip" style="border-style:dashed" onclick="openAttrEditModal('${esc(sku)}', '${esc(c.attribute)}')">
                ✎ Custom Override...
              </button>
            </div>
          </div>
        `).join('')}
      `;
    }

    $('#product-detail').innerHTML = `
      <div class="detail-grid">
        <!-- Left Column: Master Overview -->
        <article class="card">
          <div style="display:flex;justify-content:space-between;align-items:flex-start">
            <div>
              <span class="kicker">Golden Record Digital Twin</span>
              <h2 style="margin:2px 0 6px">${esc(p.sku)}</h2>
              <div class="muted" style="font-size:13px">${esc(p.identity?.manufacturer || 'OEM')} · MPN: ${esc(p.identity?.mpn || p.sku)}</div>
            </div>
            <button class="button sm" onclick="openSyndicationModal('${esc(p.sku)}')">Syndicate &amp; Export ↓</button>
          </div>

          <p style="margin:var(--sp-3) 0;font-size:13px;line-height:1.6">${esc(p.content?.long_description || '')}</p>

          <div class="score-box" style="background:var(--color-surface-subtle);border:1px solid var(--color-border);border-radius:var(--radius-md);padding:14px;margin:var(--sp-3) 0;display:flex;justify-content:space-around;text-align:center">
            <div>
              <strong style="font-size:22px;color:var(--color-primary)">${p.scores?.product_intelligence_score}%</strong>
              <span style="font-size:11px;color:var(--color-text-muted);display:block">PRODUCT IQ</span>
            </div>
            <div>
              <strong style="font-size:22px;color:var(--color-success)">${p.scores?.commerce_readiness}%</strong>
              <span style="font-size:11px;color:var(--color-text-muted);display:block">COMMERCE READINESS</span>
            </div>
            <div>
              <strong style="font-size:22px;color:var(--color-info)">${p.scores?.completeness}%</strong>
              <span style="font-size:11px;color:var(--color-text-muted);display:block">COMPLETENESS</span>
            </div>
          </div>

          <h3>Publish Gate Policy</h3>
          <div style="margin:var(--sp-2) 0">
            ${p.publish_gate?.allowed
              ? '<span class="status ready">✓ PUBLISH ALLOWED</span>'
              : '<span class="status review">✗ PUBLISH BLOCKED</span>'}
            <span class="muted" style="margin-left:8px;font-size:12px">${esc((p.publish_gate?.blockers || []).join(', ') || 'All gate requirements met.')}</span>
          </div>

          <h3 style="margin-top:var(--sp-3)">Taxonomy &amp; Compliance</h3>
          <div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap">
            <span class="tag">UNSPSC: ${esc(p.taxonomy?.unspsc || 'N/A')}</span>
            <span class="tag">ETIM: ${esc(p.taxonomy?.etim || 'N/A')}</span>
            ${(p.compliance?.found || []).map(c => `<span class="tag" style="background:var(--color-primary-light);color:var(--color-primary);font-weight:700">✓ ${esc(c)}</span>`).join('')}
          </div>

          <h3 style="margin-top:var(--sp-4)">Indexed Evidence Sources (${(p.sources || []).length})</h3>
          <div style="margin-top:6px;font-size:12px">
            ${(p.sources || []).map(s => `
              <div style="padding:4px 0;border-bottom:1px solid var(--color-border);display:flex;justify-content:space-between">
                <span>📄 ${esc(s.name)}</span>
                <span class="tag">${esc(s.type)}</span>
              </div>
            `).join('')}
          </div>
        </article>

        <!-- Right Column: Attributes & Workbench -->
        <article class="card">
          <div class="section-head">
            <div>
              <span class="kicker">Traceable Specifications</span>
              <h3>Verified Technical Attributes (${attrs.length})</h3>
            </div>
            <button class="button ghost sm" onclick="openAttrEditModal('${esc(p.sku)}')">+ Add Attribute</button>
          </div>

          <div class="attribute-grid">
            ${attrs.map(([k, v]) => attrHtml(k, v, p.sku)).join('') || '<p class="muted">No technical attributes extracted.</p>'}
          </div>

          ${conflictsHtml}
        </article>
      </div>

      <!-- Knowledge Graph Visualization Section -->
      <article class="card graph-card">
        <div class="section-head">
          <div>
            <span class="kicker">Connected Intelligence</span>
            <h3>Interactive Knowledge Graph Explorer</h3>
          </div>
          <div style="font-size:12px;color:var(--color-text-muted)">
            Drag nodes · Scroll to zoom · Click to inspect relationships
          </div>
        </div>

        <div class="graph-canvas-wrap">
          <canvas id="graph-canvas"></canvas>
          <div class="graph-controls">
            <button class="button ghost sm" onclick="resetGraphZoom()">Reset View</button>
          </div>
          <div class="graph-legend">
            <div class="legend-item"><div class="legend-dot" style="background:#0284c7"></div><span>SKU Root</span></div>
            <div class="legend-item"><div class="legend-dot" style="background:#10b981"></div><span>Manufacturer</span></div>
            <div class="legend-item"><div class="legend-dot" style="background:#8b5cf6"></div><span>Category</span></div>
            <div class="legend-item"><div class="legend-dot" style="background:#f59e0b"></div><span>Certification</span></div>
            <div class="legend-item"><div class="legend-dot" style="background:#64748b"></div><span>Attribute Spec</span></div>
          </div>
        </div>
      </article>
    `;

    $('#product-detail').scrollIntoView({ behavior: 'smooth', block: 'start' });

    // Initialize interactive force-directed canvas
    setTimeout(() => {
      initKnowledgeGraphCanvas(p, g);
    }, 100);

  } catch (err) {
    console.error('Failed to open product detail:', err);
    toast('Error loading product details');
  }
}

/* ============================================================
   INTERACTIVE FORCE-DIRECTED GRAPH PHYSICS ENGINE
   ============================================================ */
let graphState = {
  canvas: null,
  ctx: null,
  nodes: [],
  links: [],
  draggingNode: null,
  hoveredNode: null,
  zoom: 1,
  offsetX: 0,
  offsetY: 0,
};

function initKnowledgeGraphCanvas(product, edges) {
  const canvas = $('#graph-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  
  // Set real canvas dimensions based on CSS display size
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * window.devicePixelRatio;
  canvas.height = rect.height * window.devicePixelRatio;
  ctx.scale(window.devicePixelRatio, window.devicePixelRatio);

  const W = rect.width;
  const H = rect.height;

  // Build nodes & links
  const nodeMap = new Map();

  function getOrCreateNode(id, label, type, color, radius) {
    if (!nodeMap.has(id)) {
      nodeMap.set(id, {
        id,
        label,
        type,
        color,
        radius,
        x: W / 2 + (Math.random() - 0.5) * 200,
        y: H / 2 + (Math.random() - 0.5) * 200,
        vx: 0,
        vy: 0,
      });
    }
    return nodeMap.get(id);
  }

  // Root SKU Node
  const root = getOrCreateNode(product.sku, product.sku, 'root', '#0284c7', 22);
  root.x = W / 2;
  root.y = H / 2;

  // Edges
  const links = [];
  edges.slice(0, 30).forEach(e => {
    let color = '#64748b';
    let radius = 12;
    if (e.relation === 'MANUFACTURED_BY') { color = '#10b981'; radius = 16; }
    else if (e.relation === 'CLASSIFIED_AS') { color = '#8b5cf6'; radius = 16; }
    else if (e.relation === 'CERTIFIED_WITH') { color = '#f59e0b'; radius = 14; }
    else if (e.relation === 'SAME_PRODUCT_FAMILY' || e.relation === 'SIMILAR_PRODUCT') { color = '#ec4899'; radius = 14; }

    const targetNode = getOrCreateNode(e.target, e.target, e.relation, color, radius);
    links.push({
      source: root,
      target: targetNode,
      relation: e.relation.replace('HAS_', '').replace(/_/g, ' '),
      confidence: e.confidence || 1.0,
    });
  });

  graphState = {
    canvas,
    ctx,
    nodes: Array.from(nodeMap.values()),
    links,
    draggingNode: null,
    hoveredNode: null,
    zoom: 1,
    offsetX: 0,
    offsetY: 0,
    width: W,
    height: H,
  };

  // Event Listeners for Interaction
  canvas.onmousedown = onCanvasMouseDown;
  canvas.onmousemove = onCanvasMouseMove;
  window.onmouseup = onCanvasMouseUp;
  canvas.onwheel = onCanvasWheel;

  // Start Animation Loop
  if (state.graphAnimId) cancelAnimationFrame(state.graphAnimId);
  animateGraph();
}

function animateGraph() {
  const { ctx, nodes, links, width, height, zoom, offsetX, offsetY } = graphState;
  if (!ctx) return;

  // Physics Simulation Step
  const k = 0.05; // spring constant
  const repulse = 1800; // charge repulsion

  // Node-Node Repulsion
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const dx = nodes[j].x - nodes[i].x;
      const dy = nodes[j].y - nodes[i].y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      if (dist < 300) {
        const force = repulse / (dist * dist);
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        nodes[i].vx -= fx;
        nodes[i].vy -= fy;
        nodes[j].vx += fx;
        nodes[j].vy += fy;
      }
    }
  }

  // Link Springs
  links.forEach(l => {
    const dx = l.target.x - l.source.x;
    const dy = l.target.y - l.source.y;
    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
    const targetDist = 120;
    const force = (dist - targetDist) * k;
    const fx = (dx / dist) * force;
    const fy = (dy / dist) * force;
    if (l.source !== graphState.draggingNode) {
      l.source.vx += fx;
      l.source.vy += fy;
    }
    if (l.target !== graphState.draggingNode) {
      l.target.vx -= fx;
      l.target.vy -= fy;
    }
  });

  // Center Gravity & Damping
  nodes.forEach(n => {
    if (n === graphState.draggingNode) return;
    n.vx += (width / 2 - n.x) * 0.005;
    n.vy += (height / 2 - n.y) * 0.005;
    n.vx *= 0.85;
    n.vy *= 0.85;
    n.x += n.vx;
    n.y += n.vy;
  });

  // Render Frame
  ctx.clearRect(0, 0, width, height);
  ctx.save();
  ctx.translate(offsetX, offsetY);
  ctx.scale(zoom, zoom);

  // Draw Edges
  links.forEach(l => {
    ctx.beginPath();
    ctx.moveTo(l.source.x, l.source.y);
    ctx.lineTo(l.target.x, l.target.y);
    ctx.strokeStyle = document.body.getAttribute('data-theme') === 'light' ? 'rgba(0,0,0,0.15)' : 'rgba(255,255,255,0.12)';
    ctx.lineWidth = Math.max(1, (l.confidence || 1) * 2);
    ctx.stroke();

    // Edge Label
    const mx = (l.source.x + l.target.x) / 2;
    const my = (l.source.y + l.target.y) / 2;
    ctx.font = '9px sans-serif';
    ctx.fillStyle = document.body.getAttribute('data-theme') === 'light' ? '#64748b' : '#94a3b8';
    ctx.fillText(l.relation, mx + 4, my - 2);
  });

  // Draw Nodes
  nodes.forEach(n => {
    ctx.beginPath();
    ctx.arc(n.x, n.y, n.radius, 0, Math.PI * 2);
    ctx.fillStyle = n.color;
    ctx.shadowColor = n.color;
    ctx.shadowBlur = n.type === 'root' ? 15 : 6;
    ctx.fill();
    ctx.shadowBlur = 0;

    // Node Border
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // Node Label
    ctx.font = n.type === 'root' ? 'bold 11px sans-serif' : '10px sans-serif';
    ctx.fillStyle = document.body.getAttribute('data-theme') === 'light' ? '#0f172a' : '#f8fafc';
    ctx.textAlign = 'center';
    ctx.fillText(n.label.length > 20 ? n.label.slice(0, 18) + '…' : n.label, n.x, n.y + n.radius + 12);
  });

  ctx.restore();
  state.graphAnimId = requestAnimationFrame(animateGraph);
}

function onCanvasMouseDown(e) {
  const rect = graphState.canvas.getBoundingClientRect();
  const mouseX = (e.clientX - rect.left - graphState.offsetX) / graphState.zoom;
  const mouseY = (e.clientY - rect.top - graphState.offsetY) / graphState.zoom;

  for (let n of graphState.nodes) {
    const dx = n.x - mouseX;
    const dy = n.y - mouseY;
    if (Math.sqrt(dx * dx + dy * dy) <= n.radius + 4) {
      graphState.draggingNode = n;
      break;
    }
  }
}

function onCanvasMouseMove(e) {
  const rect = graphState.canvas.getBoundingClientRect();
  const mouseX = (e.clientX - rect.left - graphState.offsetX) / graphState.zoom;
  const mouseY = (e.clientY - rect.top - graphState.offsetY) / graphState.zoom;

  if (graphState.draggingNode) {
    graphState.draggingNode.x = mouseX;
    graphState.draggingNode.y = mouseY;
    graphState.draggingNode.vx = 0;
    graphState.draggingNode.vy = 0;
  }
}

function onCanvasMouseUp() {
  graphState.draggingNode = null;
}

function onCanvasWheel(e) {
  e.preventDefault();
  const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
  graphState.zoom = Math.max(0.4, Math.min(2.5, graphState.zoom * zoomFactor));
}

function resetGraphZoom() {
  graphState.zoom = 1;
  graphState.offsetX = 0;
  graphState.offsetY = 0;
}

/* ============================================================
   IN-LINE ATTRIBUTE WORKBENCH & OVERRIDE
   ============================================================ */
function openAttrEditModal(sku, name = '', value = '', unit = '') {
  $('#attr-edit-sku').value = sku;
  $('#attr-edit-name').value = name;
  $('#attr-edit-display-name').value = name.replace(/_/g, ' ').toUpperCase();
  $('#attr-edit-value').value = value;
  $('#attr-edit-unit').value = unit;
  $('#attr-edit-comment').value = '';
  $('#attr-edit-modal').style.display = 'flex';
  $('#attr-edit-value').focus();
}

function closeAttrEditModal() {
  $('#attr-edit-modal').style.display = 'none';
}

$('#attr-edit-form')?.addEventListener('submit', async e => {
  e.preventDefault();
  const sku = $('#attr-edit-sku').value;
  const name = $('#attr-edit-name').value || prompt('Enter attribute key (e.g. voltage_rating):');
  if (!name) return;
  const value = $('#attr-edit-value').value.trim();
  const unit = $('#attr-edit-unit').value.trim();
  const comment = $('#attr-edit-comment').value.trim() || 'Steward manual override';

  const btn = e.submitter;
  btn.disabled = true;
  btn.textContent = 'Saving & Recalculating…';

  try {
    const updated = await api(`/api/products/${encodeURIComponent(sku)}/attribute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, value, unit, comment }),
    });

    closeAttrEditModal();
    toast(`Attribute "${name}" updated & Golden Record recalculated.`);
    await load();
    await openProduct(sku);
  } catch (err) {
    console.error(err);
    toast('Failed to save attribute override');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Save & Recalculate Golden Record';
  }
});

async function resolveCandidate(sku, name, value, unit, source) {
  try {
    await api(`/api/products/${encodeURIComponent(sku)}/attribute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name,
        value,
        unit,
        comment: `Accepted candidate value from ${source}`,
      }),
    });
    toast(`Conflict resolved: Accepted ${value} from ${source}`);
    await load();
    await openProduct(sku);
  } catch (err) {
    console.error(err);
    toast('Failed to resolve candidate');
  }
}

/* ============================================================
   SYNDICATION HUB MODAL
   ============================================================ */
function openSyndicationModal(sku) {
  state.activeSyndicationSku = sku;
  $('#syndication-sku-title').textContent = `Target SKU: ${sku}`;
  $('#syndication-modal').style.display = 'flex';
}

function closeSyndicationModal() {
  $('#syndication-modal').style.display = 'none';
}

function downloadSyndication(format) {
  const sku = state.activeSyndicationSku;
  if (!sku) return;

  if (format === 'json') {
    window.open(`/api/export/${encodeURIComponent(sku)}.json`, '_blank');
  } else if (format === 'factsheet') {
    window.open(`/api/export/${encodeURIComponent(sku)}/syndication/factsheet`, '_blank');
  } else {
    window.open(`/api/export/${encodeURIComponent(sku)}/syndication/${format}`, '_blank');
  }
}

/* ============================================================
   ENRICH FORM SUBMISSION
   ============================================================ */
$('#enrich-form')?.addEventListener('submit', async e => {
  e.preventDefault();
  const btn = e.submitter;
  btn.disabled = true;
  btn.textContent = 'Running Agents…';

  try {
    const p = await api('/api/enrich', {
      method: 'POST',
      body: new FormData(e.target),
    });

    toast(`Golden Record generated for ${p.sku}`);
    await load();
    await openProduct(p.sku);
  } catch (err) {
    console.error(err);
    toast('Enrichment execution failed');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Run Autonomous Intelligence Pipeline';
  }
});

/* ============================================================
   REVIEW QUEUE
   ============================================================ */
function renderReview() {
  const q = state.dashboard?.review_queue || [];
  $('#review-list').innerHTML = q.map(p => `
    <div class="review-item" style="display:flex;justify-content:space-between;align-items:center;padding:12px;border-bottom:1px solid var(--color-border)">
      <div>
        <strong>${esc(p.sku)}</strong>
        <div class="muted" style="font-size:12px">${esc(p.category)} · ${esc(p.manufacturer || '')}</div>
      </div>
      <div>
        <span class="status ${statusClass(p.status)}">${statusText(p.status)}</span>
        ${p.conflict_count > 0 ? `<span style="color:var(--color-warning);font-size:12px;margin-left:8px;font-weight:700">⚠️ ${p.conflict_count} conflict(s)</span>` : ''}
      </div>
      <div class="review-actions" style="display:flex;gap:6px">
        <button class="button ghost sm" onclick="openProduct('${esc(p.sku)}')">Inspect</button>
        <button class="button sm" style="background:var(--color-success)" onclick="openReviewModal('${esc(p.sku)}', 'APPROVE')">Approve</button>
        <button class="button sm" style="background:var(--color-danger)" onclick="openReviewModal('${esc(p.sku)}', 'REJECT')">Reject</button>
      </div>
    </div>
  `).join('') || '<p class="muted" style="padding:var(--sp-6);text-align:center">No products currently require review.</p>';
}

function openReviewModal(sku, decision = 'APPROVE') {
  $('#review-modal-sku').value = sku;
  $('#review-decision').value = decision;
  $('#review-attribute').value = '';
  $('#review-comment').value = '';
  $('#review-modal').style.display = 'flex';
}

function closeReviewModal() {
  $('#review-modal').style.display = 'none';
}

$('#review-modal-form')?.addEventListener('submit', async e => {
  e.preventDefault();
  const sku = $('#review-modal-sku').value;
  const decision = $('#review-decision').value;
  const attribute = $('#review-attribute').value.trim() || null;
  const comment = $('#review-comment').value.trim();

  try {
    await api(`/api/reviews/${encodeURIComponent(sku)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision, attribute, comment }),
    });

    closeReviewModal();
    toast(`Decision "${decision}" applied to ${sku}`);
    await load();
    renderReview();
  } catch (err) {
    console.error(err);
    toast('Failed to submit review decision');
  }
});

/* ============================================================
   AI CATALOG COPILOT
   ============================================================ */
$('#copilot-form')?.addEventListener('submit', e => {
  e.preventDefault();
  const input = $('#copilot-input');
  if (input?.value.trim()) {
    askCopilot(input.value.trim());
    input.value = '';
  }
});

async function askCopilot(q) {
  const chat = $('#chat');
  chat.innerHTML += `<div class="bubble user">${esc(q)}</div>`;
  
  // Thinking indicator
  const loadId = 'copilot-load-' + Date.now();
  chat.innerHTML += `<div id="${loadId}" class="bubble ai muted" style="font-style:italic">🤖 Analyzing query & consulting Golden Catalog…</div>`;
  chat.scrollTop = chat.scrollHeight;

  try {
    const r = await api('/api/copilot', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: q }),
    });

    const loadEl = document.getElementById(loadId);
    if (loadEl) loadEl.remove();

    let linksHtml = '';
    if (r.products?.length) {
      linksHtml = `<div style="margin-top:10px;display:flex;flex-wrap:wrap;gap:6px">` +
        r.products.slice(0, 6).map(p => `
          <button class="button ghost sm" onclick="openProduct('${esc(p.sku)}')">🔎 ${esc(p.sku)} →</button>
        `).join('') + `</div>`;
    }

    if (r.evidence?.length) {
      linksHtml += `<div style="margin-top:10px;font-size:12px">` +
        `<strong style="font-size:11px;text-transform:uppercase;color:var(--color-primary)">Verified Source Evidence</strong>` +
        r.evidence.slice(0, 3).map(e => `
          <div style="background:var(--color-surface);padding:8px 10px;border-radius:6px;margin-top:4px;border:1px solid var(--color-border)">
            <strong style="color:var(--color-text)">${esc(e.sku)} · ${esc(e.source_name)}</strong>
            <p class="muted" style="margin:2px 0 0;font-family:monospace;font-size:11px">${esc(e.snippet)}</p>
          </div>
        `).join('') + `</div>`;
    }

    chat.innerHTML += `
      <div class="bubble ai">
        <div>${formatMarkdown(r.answer)}</div>
        ${linksHtml}
      </div>
    `;
    chat.scrollTop = chat.scrollHeight;
  } catch (err) {
    const loadEl = document.getElementById(loadId);
    if (loadEl) loadEl.remove();
    chat.innerHTML += `<div class="bubble ai" style="color:var(--color-danger)">Copilot query error. Please check your connection or environment settings.</div>`;
  }
}


/* ============================================================
   OPERATIONS & BULK JOBS
   ============================================================ */
async function loadOperations() {
  try {
    const jobs = await api('/api/jobs');
    $('#jobs-list').innerHTML = jobs.map(j => `
      <div class="review-item" style="padding:10px 0;border-bottom:1px solid var(--color-border);display:flex;justify-content:space-between">
        <div>
          <strong>${esc(j.id)}</strong>
          <div class="muted" style="font-size:12px">${esc(j.type)} · By ${esc(j.created_by || 'system')}</div>
        </div>
        <div style="text-align:right">
          <span class="tag">${esc(j.status)}</span>
          <div class="muted" style="font-size:12px;margin-top:2px">${j.success}/${j.total} processed · ${j.failed} errors</div>
        </div>
      </div>
    `).join('') || '<p class="muted" style="text-align:center;padding:var(--sp-4)">No bulk jobs executed yet.</p>';
  } catch (e) {
    console.error(e);
  }
}

$('#bulk-form')?.addEventListener('submit', async e => {
  e.preventDefault();
  const btn = e.submitter;
  btn.disabled = true;
  btn.textContent = 'Processing Catalog CSV…';

  try {
    const res = await api('/api/bulk', {
      method: 'POST',
      body: new FormData(e.target),
    });

    toast(`Bulk job complete: ${res.success}/${res.total} SKUs enriched`);
    await load();
    await loadOperations();
  } catch (err) {
    console.error(err);
    toast('Bulk ingestion failed');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Run Bulk Catalog Enrichment';
  }
});

$('#rag-form')?.addEventListener('submit', async e => {
  e.preventDefault();
  const q = $('#rag-input').value;
  const res = await api('/api/rag/search?q=' + encodeURIComponent(q));
  $('#rag-results').innerHTML = res.results.map(r => `
    <div class="review-item" style="padding:10px 0;border-bottom:1px solid var(--color-border)">
      <div>
        <strong>${esc(r.sku)} · ${esc(r.source_name)}</strong>
        <span class="tag" style="margin-left:6px">${esc(r.source_type)}</span>
      </div>
      <div style="font-size:13px;margin-top:4px;line-height:1.5">${esc(r.snippet)}</div>
    </div>
  `).join('') || '<p class="muted" style="text-align:center;padding:var(--sp-4)">No matching evidence chunks found.</p>';
});

/* ============================================================
   ENTERPRISE CONNECTORS & ACTIVE SIMULATOR
   ============================================================ */
async function loadEnterprise() {
  try {
    const [d, c, a] = await Promise.all([
      api('/api/dashboard'),
      api('/api/connectors'),
      api('/api/audit'),
    ]);

    const m = d.metrics;
    $('#enterprise-metrics').innerHTML =
      metric('Evidence Chunks', m.evidence_chunks || 0, 'Indexed in RAG store') +
      metric('Catalog Jobs', m.jobs || 0, 'Governed batch runs') +
      metric('Active Connectors', (c || []).length, 'PIM & ERP targets') +
      metric('Avg. IQ Quality', Number(m.avg_iq || 0).toFixed(1) + '%', 'Portfolio readiness');

    renderConnectors(c);

    $('#audit-list').innerHTML = a.slice(0, 20).map(x => `
      <div class="review-item" style="padding:8px 0;border-bottom:1px solid var(--color-border);font-size:13px">
        <div style="display:flex;justify-content:space-between">
          <strong>${esc(x.action)}</strong>
          <small class="muted">${esc(x.created_at)}</small>
        </div>
        <div class="muted" style="font-size:12px">${esc(x.actor || 'system')} · SKU: ${esc(x.sku || 'Platform')}</div>
        <div style="margin-top:2px">${esc(x.detail || '')}</div>
      </div>
    `).join('') || '<p class="muted">No audit events recorded.</p>';
  } catch (err) {
    console.error(err);
  }
}

function renderConnectors(connectors) {
  const el = $('#connector-list');
  if (!el) return;
  el.innerHTML = connectors.map(x => `
    <div class="review-item" style="padding:10px 0;border-bottom:1px solid var(--color-border);display:flex;justify-content:space-between;align-items:center">
      <div>
        <strong>${esc(x.name)}</strong>
        <div class="muted" style="font-size:12px">${esc(x.type)} · ${esc(x.base_url || 'Internal endpoint')}</div>
      </div>
      <div style="display:flex;gap:6px;align-items:center">
        <span class="status ready">${esc(x.status)}</span>
        <button class="button ghost sm" onclick="testConnector('${esc(x.name)}')">Ping Test</button>
      </div>
    </div>
  `).join('') || '<p class="muted">No connectors configured.</p>';
}

function toggleConnectorForm() {
  const f = $('#connector-form');
  if (!f) return;
  const show = f.style.display === 'none';
  f.style.display = show ? 'block' : 'none';
}

$('#connector-form')?.addEventListener('submit', async e => {
  e.preventDefault();
  try {
    await api('/api/connectors', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: $('#conn-name').value.trim(),
        type: $('#conn-type').value,
        base_url: $('#conn-url').value.trim(),
        status: $('#conn-status').value,
      }),
    });
    toast('Connector registered successfully');
    toggleConnectorForm();
    e.target.reset();
    const c = await api('/api/connectors');
    renderConnectors(c);
  } catch (err) {
    toast('Failed to save connector');
  }
});

async function testConnector(name) {
  try {
    const res = await api(`/api/connectors/${encodeURIComponent(name)}/test`, { method: 'POST' });
    toast(`[${res.connector}] ${res.status} (${res.latency_ms}ms) — ${res.message}`);
  } catch (err) {
    toast(`Connector ${name} ping failed`);
  }
}

/* ============================================================
   ADMIN USERS & API KEYS
   ============================================================ */
async function loadAdmin() {
  try {
    const [users, keys] = await Promise.all([
      api('/api/admin/users'),
      api('/api/admin/api-keys'),
    ]);
    renderAdminUsers(users);
    renderAdminKeys(keys);
  } catch (err) {
    toast('Admin views require admin role privileges');
  }
}

function renderAdminUsers(users) {
  $('#admin-users-body').innerHTML = users.map(u => `
    <tr>
      <td><strong>${esc(u.name || '—')}</strong><div class="muted" style="font-size:12px">${esc(u.email)}</div></td>
      <td><span class="tag">${esc(u.role)}</span></td>
      <td><span class="status ${u.active ? 'ready' : 'insufficient'}">${u.active ? 'Active' : 'Inactive'}</span></td>
      <td class="muted" style="font-size:12px">${u.last_login ? u.last_login.slice(0, 16).replace('T', ' ') : 'Never'}</td>
      <td>${u.active && u.email !== 'admin@unigraph.local' ? `<button class="button ghost sm" style="color:var(--color-danger)" onclick="deactivateUser(${u.id})">Deactivate</button>` : '—'}</td>
    </tr>
  `).join('');
}

function renderAdminKeys(keys) {
  $('#admin-keys-body').innerHTML = keys.map(k => `
    <tr>
      <td><strong>${esc(k.name)}</strong></td>
      <td><code>${esc(k.key_prefix)}…</code></td>
      <td><span class="tag">${esc(k.role)}</span></td>
      <td><span class="status ${k.active ? 'ready' : 'insufficient'}">${k.active ? 'Active' : 'Revoked'}</span></td>
      <td class="muted" style="font-size:12px">${k.last_used ? k.last_used.slice(0, 16).replace('T', ' ') : 'Never'}</td>
      <td class="muted" style="font-size:12px">${(k.created_at || '').slice(0, 10)}</td>
    </tr>
  `).join('') || '<tr><td colspan="6" class="muted" style="text-align:center;padding:2rem">No API keys yet.</td></tr>';
}

function openAddUser() { $('#add-user-modal').style.display = 'flex'; }
function closeAddUser() { $('#add-user-modal').style.display = 'none'; }
function openGenerateKey() { $('#gen-key-modal').style.display = 'flex'; }
function closeGenerateKey() { $('#gen-key-modal').style.display = 'none'; }
function openLogin() { $('#login-modal').style.display = 'flex'; }
function closeLogin() { $('#login-modal').style.display = 'none'; }

$('#add-user-form')?.addEventListener('submit', async e => {
  e.preventDefault();
  try {
    await api('/api/admin/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: $('#new-user-email').value.trim(),
        name: $('#new-user-name').value.trim(),
        role: $('#new-user-role').value,
        password: $('#new-user-password').value,
      }),
    });
    toast('User created successfully');
    closeAddUser();
    e.target.reset();
    loadAdmin();
  } catch (err) {
    toast('Failed to create user');
  }
});

$('#gen-key-form')?.addEventListener('submit', async e => {
  e.preventDefault();
  try {
    const res = await api('/api/admin/api-keys', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: $('#key-name').value.trim(),
        role: $('#key-role').value,
      }),
    });
    closeGenerateKey();
    e.target.reset();
    $('#key-reveal-value').textContent = res.api_key;
    $('#key-reveal').style.display = 'flex';
    toast('API Key generated — save it now');
    loadAdmin();
  } catch (err) {
    toast('Key generation failed');
  }
});

function copyKey() {
  const val = $('#key-reveal-value')?.textContent;
  if (val) {
    navigator.clipboard.writeText(val).then(() => {
      $('#copy-key-btn').textContent = 'Copied!';
      setTimeout(() => $('#copy-key-btn').textContent = 'Copy', 2000);
    });
  }
}

async function deactivateUser(id) {
  if (!confirm('Deactivate this user account?')) return;
  try {
    await api(`/api/admin/users/${id}`, { method: 'DELETE' });
    toast('User deactivated');
    loadAdmin();
  } catch (e) {
    toast('Deactivation failed');
  }
}

/* ============================================================
   AUTH IDENTITY
   ============================================================ */
$('#login-form')?.addEventListener('submit', async e => {
  e.preventDefault();
  const f = new FormData(e.target);
  try {
    const r = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: f.get('email'), password: f.get('password') }),
    });
    if (!r.ok) throw new Error('Invalid credentials');
    const x = await r.json();
    localStorage.setItem('ugiq_token', x.token);
    $('#auth-button').textContent = x.user.name || x.user.email;
    closeLogin();
    toast('Welcome, signed in');
    await load();
  } catch (err) {
    toast('Sign in failed');
  }
});

async function loadIdentity() {
  try {
    const u = await api('/api/auth/me');
    if (u && $('#auth-button')) $('#auth-button').textContent = u.name || u.email;
    if (u && u.role === 'admin') $$('.admin-nav').forEach(el => el.style.display = '');
  } catch (e) {}
}

/* ============================================================
   INITIALIZATION
   ============================================================ */
load().catch(console.error);
loadIdentity();

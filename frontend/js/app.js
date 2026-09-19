/** Dashboard: SQL list + Meilisearch full-text search + detail enrich */
import {
  API_BASE,
  clearToken,
  enrichListing,
  fetchListings,
  getToken,
  me,
  searchListings,
} from "./api.js";

function money(n) {
  if (n == null || Number.isNaN(Number(n))) return '—';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(Number(n));
}

function ratioLabel(r) {
  if (r == null) return '—';
  return `${Number(r).toFixed(1)}x`;
}

function requireAuth() {
  if (!getToken()) {
    window.location.href = 'login.html';
    return false;
  }
  return true;
}

async function loadUser() {
  try {
    const user = await me();
    const el = document.getElementById('navUser');
    if (el) el.textContent = user.email;
  } catch {
    clearToken();
    window.location.href = 'login.html';
  }
}

function cardHtml(listing) {
  return `
    <button type="button" class="listing-card" data-lien-id="${listing.lien_id}">
      <div class="listing-card__top">
        <div>
          <p class="listing-card__addr">${escapeHtml(listing.address || listing.parcel_id)}</p>
          <p class="listing-card__loc">${escapeHtml([listing.city, listing.state].filter(Boolean).join(', '))}${listing.county ? ' · ' + escapeHtml(listing.county) : ''}</p>
        </div>
        <span class="listing-card__ratio">${ratioLabel(listing.value_to_lien_ratio)}</span>
      </div>
      <div class="listing-card__figures">
        <div>
          <p class="listing-card__figure-label">Assessed value</p>
          <p class="listing-card__figure-value">${money(listing.assessed_value)}</p>
        </div>
        <div>
          <p class="listing-card__figure-label">Lien amount</p>
          <p class="listing-card__figure-value">${money(listing.lien_amount)}</p>
        </div>
      </div>
    </button>
  `;
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

let currentListings = [];

async function loadListings() {
  const minRatio = Number(document.getElementById('minRatio').value || 0);
  const state = (document.getElementById('stateFilter').value || '').trim();
  const q = (document.getElementById('searchQuery').value || '').trim();
  const status = document.getElementById('statusBar');
  const grid = document.getElementById('listingGrid');
  const mode = document.getElementById('searchMode');

  status.textContent = 'Loading…';
  grid.innerHTML = '';

  try {
    let data;
    if (q) {
      data = await searchListings({ q, minRatio, state, limit: 100 });
      if (mode) mode.textContent = 'Meilisearch';
      status.textContent = `${data.count} result${data.count === 1 ? '' : 's'} for “${q}” · ratio ≥ ${minRatio || 0}`;
      currentListings = data.listings || [];
    } else {
      data = await fetchListings({ minRatio, state, limit: 100 });
      if (mode) mode.textContent = 'SQL';
      status.textContent = `${data.count} listing${data.count === 1 ? '' : 's'} · ratio ≥ ${minRatio || 0}`;
      currentListings = data.listings || [];
    }

    if (!currentListings.length) {
      grid.innerHTML = `<div class="empty-state">No listings match.<br>Seed demo data and run <code>reindex_meili.py</code> if searching.</div>`;
      return;
    }

    grid.innerHTML = currentListings.map(cardHtml).join('');
    grid.querySelectorAll('.listing-card').forEach((btn) => {
      btn.addEventListener('click', () => openDetail(btn.dataset.lienId));
    });
  } catch (err) {
    status.textContent = '';
    grid.innerHTML = `<div class="empty-state">Could not load listings.<br>${escapeHtml(err.message)}<br><span style="font-size:12px">API: ${escapeHtml(API_BASE || '(same origin)')}</span></div>`;
  }
}

function openDetail(lienId) {
  const listing = currentListings.find((l) => String(l.lien_id) === String(lienId));
  if (!listing) return;

  const backdrop = document.getElementById('modalBackdrop');
  document.getElementById('modalAddr').textContent = listing.address || listing.parcel_id;
  document.getElementById('modalLoc').textContent = [listing.city, listing.state, listing.county]
    .filter(Boolean)
    .join(' · ');
  document.getElementById('modalRatio').textContent = ratioLabel(listing.value_to_lien_ratio);
  document.getElementById('modalAssessed').textContent = money(listing.assessed_value);
  document.getElementById('modalLien').textContent = money(listing.lien_amount);
  document.getElementById('modalInterest').textContent =
    listing.interest_rate != null ? `${listing.interest_rate}%` : '—';
  document.getElementById('modalSummary').textContent = 'Click “Generate AI summary” for a plain-language note.';
  document.getElementById('modalSummary').dataset.lienId = lienId;

  const link = document.getElementById('modalSource');
  if (listing.source_county_url) {
    link.href = listing.source_county_url;
    link.style.display = '';
  } else {
    link.style.display = 'none';
  }

  backdrop.classList.add('is-open');
}

function closeDetail() {
  document.getElementById('modalBackdrop').classList.remove('is-open');
}

async function runEnrich() {
  const summaryEl = document.getElementById('modalSummary');
  const lienId = summaryEl.dataset.lienId;
  const btn = document.getElementById('enrichBtn');
  if (!lienId) return;

  btn.disabled = true;
  btn.textContent = 'Generating…';
  summaryEl.textContent = 'Asking Gemini…';

  try {
    const data = await enrichListing(lienId);
    summaryEl.textContent =
      data.ai_summary ||
      'No summary returned (set GEMINI_API_KEY on the server, or the model call failed).';
  } catch (err) {
    summaryEl.textContent = err.message || 'Enrichment failed.';
  } finally {
    btn.disabled = false;
    btn.textContent = 'Generate AI summary';
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  if (!requireAuth()) return;
  await loadUser();

  document.getElementById('logoutBtn')?.addEventListener('click', () => {
    clearToken();
    window.location.href = 'index.html';
  });

  document.getElementById('applyFilters')?.addEventListener('click', loadListings);
  ['minRatio', 'stateFilter', 'searchQuery'].forEach((id) => {
    document.getElementById(id)?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') loadListings();
    });
  });

  document.getElementById('modalClose')?.addEventListener('click', closeDetail);
  document.getElementById('modalBackdrop')?.addEventListener('click', (e) => {
    if (e.target.id === 'modalBackdrop') closeDetail();
  });
  document.getElementById('enrichBtn')?.addEventListener('click', runEnrich);

  await loadListings();
});

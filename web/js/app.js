/**
 * InternPulse — Main Application Controller
 */

import { apiClient } from './api.js';
import { renderSkillsChart } from './charts.js';

// Application State
const state = {
    term: 'Summer 2027', // Default focus
    company: '',
    keyword: '',
    is_remote: null,
    page: 1,
    page_size: 15,
    sort_by: 'posted_at',
    sort_order: 'desc',
    skill_category: '',
    totalPages: 1,
    totalItems: 0,
};

// DOM Element Selectors
const elements = {
    termTabs: document.getElementById('term-tabs'),
    searchInput: document.getElementById('search-input'),
    clearSearchBtn: document.getElementById('clear-search'),
    companySelect: document.getElementById('company-select'),
    remoteToggle: document.getElementById('remote-toggle'),
    sortSelect: document.getElementById('sort-select'),
    postingsGrid: document.getElementById('postings-grid'),
    currentCountDisplay: document.getElementById('current-count-display'),
    termContextLabel: document.getElementById('term-context-label'),
    prevPageBtn: document.getElementById('prev-page-btn'),
    nextPageBtn: document.getElementById('next-page-btn'),
    pageIndicator: document.getElementById('page-indicator'),
    activeTagsRow: document.getElementById('active-tags-row'),
    tagsContainer: document.getElementById('tags-container'),
    resetFiltersBtn: document.getElementById('reset-filters-btn'),
    skillCatPills: document.getElementById('skill-cat-pills'),
    skillsChartList: document.getElementById('skills-chart-list'),
    val2027Count: document.getElementById('val-2027-count'),
    valActiveCount: document.getElementById('val-active-count'),
    valCompaniesCount: document.getElementById('val-companies-count'),
    badge2027: document.getElementById('badge-2027'),
};

// Initialize Application
document.addEventListener('DOMContentLoaded', async () => {
    setupEventListeners();
    await loadInitialStats();
    await loadPostings();
    await loadSkills();
});

/**
 * Setup UI Event Listeners
 */
function setupEventListeners() {
    // 1. Term Switcher Tabs
    elements.termTabs.addEventListener('click', (e) => {
        const tab = e.target.closest('.term-tab');
        if (!tab) return;

        elements.termTabs.querySelectorAll('.term-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');

        state.term = tab.dataset.term;
        state.page = 1;
        updateTermContext();
        loadPostings();
        loadSkills();
    });

    // 2. Debounced Keyword Search
    let debounceTimer;
    elements.searchInput.addEventListener('input', (e) => {
        const val = e.target.value.trim();
        elements.clearSearchBtn.style.display = val ? 'block' : 'none';

        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            state.keyword = val;
            state.page = 1;
            renderActiveFilterTags();
            loadPostings();
        }, 300);
    });

    elements.clearSearchBtn.addEventListener('click', () => {
        elements.searchInput.value = '';
        elements.clearSearchBtn.style.display = 'none';
        state.keyword = '';
        state.page = 1;
        renderActiveFilterTags();
        loadPostings();
    });

    // 3. Company Selector
    elements.companySelect.addEventListener('change', (e) => {
        state.company = e.target.value;
        state.page = 1;
        renderActiveFilterTags();
        loadPostings();
    });

    // 4. Remote Only Toggle
    elements.remoteToggle.addEventListener('click', () => {
        const isActive = state.is_remote === true;
        state.is_remote = isActive ? null : true;
        elements.remoteToggle.classList.toggle('active', !isActive);
        state.page = 1;
        renderActiveFilterTags();
        loadPostings();
    });

    // 5. Sort Selector
    elements.sortSelect.addEventListener('change', (e) => {
        const [field, order] = e.target.value.split(':');
        state.sort_by = field;
        state.sort_order = order;
        state.page = 1;
        loadPostings();
    });

    // 6. Pagination Controls
    elements.prevPageBtn.addEventListener('click', () => {
        if (state.page > 1) {
            state.page--;
            loadPostings();
            window.scrollTo({ top: 400, behavior: 'smooth' });
        }
    });

    elements.nextPageBtn.addEventListener('click', () => {
        if (state.page < state.totalPages) {
            state.page++;
            loadPostings();
            window.scrollTo({ top: 400, behavior: 'smooth' });
        }
    });

    // 7. Reset Filters Button
    elements.resetFiltersBtn.addEventListener('click', () => {
        resetAllFilters();
    });

    // 8. Skill Category Pills
    elements.skillCatPills.addEventListener('click', (e) => {
        const pill = e.target.closest('.cat-pill');
        if (!pill) return;

        elements.skillCatPills.querySelectorAll('.cat-pill').forEach(p => p.classList.remove('active'));
        pill.classList.add('active');

        state.skill_category = pill.dataset.cat;
        loadSkills();
    });
}

/**
 * Load Initial Aggregate Stats & Fill Company Dropdown
 */
async function loadInitialStats() {
    try {
        const stats = await apiClient.getStats();

        // Update hero metrics
        if (elements.valActiveCount) {
            elements.valActiveCount.textContent = stats.active_postings.toLocaleString();
        }

        // Check 2027 count in terms breakdown
        const term2027 = stats.postings_by_term.find(t => t.term.includes('2027'));
        if (term2027) {
            if (elements.val2027Count) elements.val2027Count.textContent = `${term2027.count}+`;
            if (elements.badge2027) elements.badge2027.textContent = term2027.count;
        }

        // Tracked companies
        const companyCount = stats.top_companies ? stats.top_companies.length : 0;
        if (elements.valCompaniesCount) {
            elements.valCompaniesCount.textContent = `${stats.total_postings > 1000 ? '500+' : companyCount}`;
        }

        // Populate company select dropdown
        if (stats.top_companies && stats.top_companies.length > 0) {
            const options = stats.top_companies.map(c => `
                <option value="${escapeHtml(c.company)}">${escapeHtml(c.company)} (${c.count})</option>
            `).join('');
            elements.companySelect.innerHTML = '<option value="">All Companies</option>' + options;
        }
    } catch (err) {
        console.error('Failed to load initial stats:', err);
    }
}

/**
 * Load & Render Postings Grid
 */
async function loadPostings() {
    elements.postingsGrid.innerHTML = `
        <div class="loading-spinner-container">
            <div class="spinner"></div>
            <p>Fetching verified live postings...</p>
        </div>
    `;

    try {
        const data = await apiClient.getPostings({
            term: state.term,
            company: state.company,
            keyword: state.keyword,
            is_remote: state.is_remote,
            page: state.page,
            page_size: state.page_size,
            sort_by: state.sort_by,
            sort_order: state.sort_order,
        });

        state.totalPages = data.total_pages || 1;
        state.totalItems = data.total || 0;

        // Update Count Display
        elements.currentCountDisplay.textContent = (data.total || 0).toLocaleString();

        // Update Pagination
        elements.pageIndicator.textContent = `Page ${data.page} of ${data.total_pages || 1}`;
        elements.prevPageBtn.disabled = data.page <= 1;
        elements.nextPageBtn.disabled = data.page >= data.total_pages;

        if (data.items.length === 0) {
            renderEmptyState();
            return;
        }

        renderPostingsList(data.items);
    } catch (err) {
        elements.postingsGrid.innerHTML = `
            <div class="empty-state-container">
                <div class="empty-icon">⚠️</div>
                <h3>Unable to load job postings</h3>
                <p>${escapeHtml(err.message)}</p>
            </div>
        `;
    }
}

/**
 * Render List of Job Cards
 */
function renderPostingsList(items) {
    const html = items.map(p => {
        const companyInitial = p.company ? p.company.charAt(0).toUpperCase() : '💼';
        const isSummer2027 = p.terms && p.terms.includes('2027');
        const termBadgeClass = isSummer2027 ? 'term-badge-2027' : 'term-badge-other';
        const ageText = formatRelativeTime(p.posted_at || p.first_seen_at);

        return `
            <article class="job-card" id="job-card-${p.id}">
                <div class="job-main">
                    <div class="job-company-row">
                        <div class="company-avatar">${companyInitial}</div>
                        <span class="company-name">${escapeHtml(p.company)}</span>
                        <span class="source-pill">${escapeHtml(p.source)}</span>
                    </div>

                    <h3 class="job-title">${escapeHtml(p.title)}</h3>

                    <div class="job-meta-row">
                        ${p.terms ? `<span class="${termBadgeClass}">🗓️ ${escapeHtml(p.terms)}</span>` : ''}
                        ${p.location ? `<span class="meta-pill">📍 ${escapeHtml(p.location)}</span>` : ''}
                        ${p.is_remote ? `<span class="remote-pill">🏠 Remote</span>` : ''}
                        <span class="age-indicator">🕒 ${ageText}</span>
                    </div>
                </div>

                <div class="job-action">
                    <a href="${escapeHtml(p.url || '#')}" target="_blank" rel="noopener noreferrer" class="btn-apply" id="apply-btn-${p.id}">
                        Apply Now <span>↗</span>
                    </a>
                </div>
            </article>
        `;
    }).join('');

    elements.postingsGrid.innerHTML = html;
}

/**
 * Render Empty State
 */
function renderEmptyState() {
    elements.postingsGrid.innerHTML = `
        <div class="empty-state-container">
            <div class="empty-icon">🔍</div>
            <h3>No postings found matching your filters</h3>
            <p>Try resetting filters or searching with different keywords.</p>
            <button class="btn btn-apply" style="margin-top: 1rem;" onclick="window.resetAllFilters()">Reset Filters</button>
        </div>
    `;
}

/**
 * Load Top Skills & Render Interactive Chart
 */
async function loadSkills() {
    try {
        const skills = await apiClient.getTopSkills(state.term, state.skill_category, 10);
        renderSkillsChart(elements.skillsChartList, skills, (selectedSkill) => {
            // Filter board when clicking a skill bar
            state.keyword = selectedSkill;
            elements.searchInput.value = selectedSkill;
            elements.clearSearchBtn.style.display = 'block';
            state.page = 1;
            renderActiveFilterTags();
            loadPostings();
        });
    } catch (err) {
        console.error('Failed to load skills:', err);
    }
}

/**
 * Update Term Context Display
 */
function updateTermContext() {
    if (!state.term) {
        elements.termContextLabel.textContent = 'across all active roles';
    } else {
        elements.termContextLabel.textContent = `for ${state.term}`;
    }
}

/**
 * Render Active Filter Tag Badges
 */
function renderActiveFilterTags() {
    const tags = [];

    if (state.keyword) {
        tags.push({ label: `Keyword: "${state.keyword}"`, remove: () => {
            state.keyword = '';
            elements.searchInput.value = '';
            elements.clearSearchBtn.style.display = 'none';
        }});
    }

    if (state.company) {
        tags.push({ label: `Company: ${state.company}`, remove: () => {
            state.company = '';
            elements.companySelect.value = '';
        }});
    }

    if (state.is_remote) {
        tags.push({ label: 'Remote Only', remove: () => {
            state.is_remote = null;
            elements.remoteToggle.classList.remove('active');
        }});
    }

    if (tags.length > 0) {
        elements.activeTagsRow.style.display = 'flex';
        elements.tagsContainer.innerHTML = tags.map((t, idx) => `
            <span class="filter-tag">
                ${escapeHtml(t.label)}
                <button class="filter-tag-remove" data-idx="${idx}">×</button>
            </span>
        `).join('');

        elements.tagsContainer.querySelectorAll('.filter-tag-remove').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const idx = parseInt(e.target.dataset.idx, 10);
                tags[idx].remove();
                renderActiveFilterTags();
                state.page = 1;
                loadPostings();
            });
        });
    } else {
        elements.activeTagsRow.style.display = 'none';
    }
}

/**
 * Reset All Active Filters
 */
window.resetAllFilters = function() {
    state.keyword = '';
    state.company = '';
    state.is_remote = null;
    elements.searchInput.value = '';
    elements.clearSearchBtn.style.display = 'none';
    elements.companySelect.value = '';
    elements.remoteToggle.classList.remove('active');
    state.page = 1;
    renderActiveFilterTags();
    loadPostings();
};

/**
 * Format Relative Timestamps
 */
function formatRelativeTime(dateString) {
    if (!dateString) return 'recently';
    const date = new Date(dateString);
    const now = new Date();
    const diffSec = Math.floor((now - date) / 1000);

    if (diffSec < 60) return 'just now';
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
    const days = Math.floor(diffSec / 86400);
    if (days === 1) return '1d ago';
    if (days < 30) return `${days}d ago`;
    return `${Math.floor(days / 30)}mo ago`;
}

function escapeHtml(str) {
    if (!str) return '';
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

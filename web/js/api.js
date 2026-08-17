/**
 * InternPulse — API Client for FastAPI backend endpoints
 */

const API_BASE = '/api/v1';

export const apiClient = {
    /**
     * Fetch paginated and filtered job postings
     */
    async getPostings(params = {}) {
        const query = new URLSearchParams();
        
        if (params.term) query.set('term', params.term);
        if (params.company) query.set('company', params.company);
        if (params.keyword) query.set('keyword', params.keyword);
        if (params.is_remote !== undefined && params.is_remote !== null) {
            query.set('is_remote', params.is_remote);
        }
        if (params.page) query.set('page', params.page);
        if (params.page_size) query.set('page_size', params.page_size);
        if (params.sort_by) query.set('sort_by', params.sort_by);
        if (params.sort_order) query.set('sort_order', params.sort_order);

        // Always request active postings for the UI
        query.set('is_active', 'true');

        const res = await fetch(`${API_BASE}/postings?${query.toString()}`);
        if (!res.ok) throw new Error(`Failed to fetch postings: ${res.statusText}`);
        return res.json();
    },

    /**
     * Fetch aggregated metrics and stats
     */
    async getStats() {
        const res = await fetch(`${API_BASE}/stats`);
        if (!res.ok) throw new Error(`Failed to fetch stats: ${res.statusText}`);
        return res.json();
    },

    /**
     * Fetch top in-demand skills
     */
    async getTopSkills(term = null, category = null, limit = 10) {
        const query = new URLSearchParams();
        if (term) query.set('term', term);
        if (category) query.set('category', category);
        if (limit) query.set('limit', limit);

        const res = await fetch(`${API_BASE}/skills/top?${query.toString()}`);
        if (!res.ok) throw new Error(`Failed to fetch top skills: ${res.statusText}`);
        return res.json();
    },

    /**
     * Fetch skills breakdown by category
     */
    async getSkillsByCategory() {
        const res = await fetch(`${API_BASE}/skills/by-category`);
        if (!res.ok) throw new Error(`Failed to fetch skills by category: ${res.statusText}`);
        return res.json();
    }
};

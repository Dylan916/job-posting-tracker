/**
 * InternPulse — Interactive Skill Demand Charts Component
 */

export function renderSkillsChart(container, skills, onSkillClick) {
    if (!container) return;

    if (!skills || skills.length === 0) {
        container.innerHTML = `
            <div style="padding: 1.5rem 0; text-align: center; color: var(--text-muted); font-size: 0.85rem;">
                No skills detected for this category filter.
            </div>
        `;
        return;
    }

    // Find max count for relative bar scaling
    const maxCount = Math.max(...skills.map(s => s.count), 1);

    const html = skills.map(s => {
        const barWidth = Math.max(Math.round((s.count / maxCount) * 100), 8);
        return `
            <div class="skill-bar-row" data-skill="${escapeHtml(s.skill)}" title="Click to filter jobs requiring ${escapeHtml(s.skill)}">
                <div class="skill-label-row">
                    <span class="skill-name">
                        ${getSkillIcon(s.skill)} ${escapeHtml(s.skill)}
                    </span>
                    <span class="skill-stats">
                        <strong>${s.count}</strong> jobs (${s.percentage_of_skills}%)
                    </span>
                </div>
                <div class="skill-bar-track">
                    <div class="skill-bar-fill" style="width: ${barWidth}%;"></div>
                </div>
            </div>
        `;
    }).join('');

    container.innerHTML = html;

    // Attach click listeners to filter job board
    container.querySelectorAll('.skill-bar-row').forEach(row => {
        row.addEventListener('click', () => {
            const skillName = row.getAttribute('data-skill');
            if (onSkillClick) onSkillClick(skillName);
        });
    });
}

function getSkillIcon(skill) {
    const s = skill.toLowerCase();
    if (s.includes('python')) return '🐍';
    if (s.includes('java') && !s.includes('script')) return '☕';
    if (s.includes('script') || s === 'js' || s === 'ts') return '🟨';
    if (s.includes('go') || s.includes('golang')) return '🐹';
    if (s.includes('rust')) return '🦀';
    if (s.includes('c++') || s.includes('cpp') || s.includes('c#')) return '⚡';
    if (s.includes('sql') || s.includes('postgres') || s.includes('db')) return '🗄️';
    if (s.includes('linux')) return '🐧';
    if (s.includes('aws') || s.includes('gcp') || s.includes('azure') || s.includes('cloud')) return '☁️';
    if (s.includes('docker') || s.includes('k8s') || s.includes('kubernetes')) return '🐳';
    if (s.includes('ai') || s.includes('llm') || s.includes('vision') || s.includes('nlp')) return '🤖';
    if (s.includes('react') || s.includes('vue') || s.includes('node')) return '⚛️';
    return '🔹';
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

// Coach's notebook page logic
let currentCategory = 'all';

document.addEventListener('DOMContentLoaded', async () => {
    document.querySelectorAll('[data-cat]').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('[data-cat]').forEach(b => {
                b.className = `btn btn-sm ${b.dataset.cat === btn.dataset.cat ? 'btn-primary' : 'btn-secondary'}`;
            });
            currentCategory = btn.dataset.cat;
            loadEntries();
        });
    });
    await loadEntries();
});

async function loadEntries() {
    const container = document.getElementById('notebook-entries');
    try {
        const entries = await Coach.get('/notebook?active_only=true');
        const filtered = currentCategory === 'all'
            ? entries
            : entries.filter(e => e.category === currentCategory);

        if (filtered.length === 0) {
            container.innerHTML = '<div class="card text-muted">No entries yet. Your coach will add observations as you train and chat.</div>';
            return;
        }

        let html = '';
        for (const entry of filtered) {
            const catColors = {
                pattern: 'blue', observation: 'muted', risk: 'red',
                strength: 'green', preference: 'yellow',
            };
            const color = catColors[entry.category] || 'muted';

            html += `<div class="card">
                <div class="flex-between">
                    <div>
                        <span class="badge badge-${color}">${entry.category}</span>
                        ${entry.confidence !== 'medium' ? `<span class="badge badge-muted">${entry.confidence}</span>` : ''}
                    </div>
                    <div class="flex gap-sm">
                        <button class="btn btn-sm btn-secondary" onclick="toggleEntry(${entry.id}, ${entry.active ? 0 : 1})">${entry.active ? 'Dismiss' : 'Reactivate'}</button>
                    </div>
                </div>
                <p class="mt-sm">${entry.content}</p>
                ${entry.evidence ? `<p class="text-sm text-muted mt-sm">Evidence: ${entry.evidence}</p>` : ''}
                <p class="text-sm text-muted">${Coach.formatDate(entry.created_at)}</p>
            </div>`;
        }
        container.innerHTML = html;
    } catch (e) {
        container.innerHTML = '<div class="text-muted">Failed to load notebook</div>';
    }
}

async function toggleEntry(id, active) {
    try {
        await Coach.put(`/notebook/${id}`, { active });
        await loadEntries();
    } catch (e) {
        alert('Failed to update: ' + e.message);
    }
}

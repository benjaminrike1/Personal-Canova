// Injury log page logic
document.addEventListener('DOMContentLoaded', async () => {
    Coach.initRangeInputs();

    document.getElementById('add-injury').addEventListener('click', () => showInjuryForm());
    document.getElementById('cancel-injury').addEventListener('click', hideInjuryForm);
    document.getElementById('injury-form').addEventListener('submit', saveInjury);

    await loadInjuries();
});

function showInjuryForm(editData) {
    const form = document.getElementById('injury-form');
    form.reset();
    if (editData && editData.id) {
        form.querySelector('[name="id"]').value = editData.id;
        form.querySelector('[name="body_part"]').value = editData.body_part || '';
        form.querySelector('[name="onset_date"]').value = editData.onset_date || '';
        form.querySelector('[name="severity"]').value = editData.severity || 5;
        form.querySelector('[name="status"]').value = editData.status || 'active';
        form.querySelector('[name="description"]').value = editData.description || '';
        document.getElementById('severity-val').textContent = editData.severity || 5;
    } else {
        // Default onset date to today
        form.querySelector('[name="onset_date"]').value = new Date().toISOString().slice(0, 10);
    }
    document.getElementById('injury-form-card').classList.remove('hidden');
    Coach.initRangeInputs();
}

function hideInjuryForm() {
    document.getElementById('injury-form-card').classList.add('hidden');
}

async function saveInjury(e) {
    e.preventDefault();
    const form = e.target;
    const id = form.querySelector('[name="id"]').value;
    const data = {
        body_part: form.querySelector('[name="body_part"]').value,
        onset_date: form.querySelector('[name="onset_date"]').value,
        severity: parseInt(form.querySelector('[name="severity"]').value),
        status: form.querySelector('[name="status"]').value,
        description: form.querySelector('[name="description"]').value,
    };

    try {
        if (id) {
            await Coach.put(`/injuries/${id}`, data);
        } else {
            await Coach.post('/injuries', data);
        }
        hideInjuryForm();
        await loadInjuries();
    } catch (e) {
        alert('Failed to save injury: ' + e.message);
    }
}

async function loadInjuries() {
    const container = document.getElementById('injury-list');
    try {
        const injuries = await Coach.get('/injuries');
        if (injuries.length === 0) {
            container.innerHTML = '<div class="card text-muted">No injuries logged. Hopefully it stays that way.</div>';
            return;
        }

        let html = '';
        for (const inj of injuries) {
            const days = Coach.daysUntil(inj.onset_date);
            const daysAgo = days ? Math.abs(days) : '?';
            const sevClass = inj.severity >= 7 ? 'red' : inj.severity >= 4 ? 'yellow' : 'green';
            const statusClass = inj.status === 'active' ? 'red' : inj.status === 'monitoring' ? 'yellow' : 'green';

            html += `<div class="card">
                <div class="flex-between">
                    <div>
                        <strong>${inj.body_part}</strong>
                        <span class="badge badge-${statusClass} ml-sm">${inj.status}</span>
                        <span class="badge badge-${sevClass}">${inj.severity}/10</span>
                    </div>
                    <div class="flex gap-sm">
                        <button class="btn btn-sm btn-secondary" onclick='showInjuryForm(${JSON.stringify(inj)})'>Edit</button>
                        <button class="btn btn-sm btn-secondary" onclick='showUpdateForm(${inj.id})'>Update</button>
                    </div>
                </div>
                <div class="text-sm text-muted mt-sm">${inj.description}</div>
                <div class="text-sm text-muted">Onset: ${Coach.formatDate(inj.onset_date)} (${daysAgo} days ago)</div>
                <div id="history-${inj.id}" class="mt-sm"></div>
            </div>`;
        }
        container.innerHTML = html;

        // Load history for active injuries
        for (const inj of injuries.filter(i => i.status !== 'resolved')) {
            loadInjuryHistory(inj.id);
        }
    } catch (e) {
        container.innerHTML = '<div class="text-muted">Failed to load injuries</div>';
    }
}

async function loadInjuryHistory(injuryId) {
    const container = document.getElementById(`history-${injuryId}`);
    if (!container) return;

    try {
        const history = await Coach.get(`/injuries/${injuryId}/history`);
        if (history.length === 0) return;

        let html = '<div class="text-sm"><strong>Severity history:</strong> ';
        html += history.slice(-7).map(h => {
            const color = h.severity >= 7 ? 'var(--red)' : h.severity >= 4 ? 'var(--yellow)' : 'var(--green)';
            return `<span style="color:${color}" title="${h.date}: ${h.notes || ''}">${h.severity}</span>`;
        }).join(' → ');
        html += '</div>';
        container.innerHTML = html;
    } catch (e) { /* ignore */ }
}

async function showUpdateForm(injuryId) {
    const severity = prompt('Current severity (1-10):');
    if (!severity) return;
    const notes = prompt('Notes (optional):') || '';

    try {
        await Coach.post(`/injuries/${injuryId}/update`, {
            severity: parseInt(severity),
            notes,
        });
        await loadInjuries();
    } catch (e) {
        alert('Failed to update: ' + e.message);
    }
}

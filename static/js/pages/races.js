// Race calendar page logic
document.addEventListener('DOMContentLoaded', async () => {
    document.getElementById('add-race').addEventListener('click', showRaceForm);
    document.getElementById('cancel-race').addEventListener('click', hideRaceForm);
    document.getElementById('race-form').addEventListener('submit', saveRace);
    await loadRaces();
});

function showRaceForm(editData) {
    const form = document.getElementById('race-form');
    form.reset();
    if (editData && typeof editData === 'object' && editData.id) {
        form.querySelector('[name="id"]').value = editData.id;
        form.querySelector('[name="name"]').value = editData.name || '';
        form.querySelector('[name="date"]').value = editData.date || '';
        form.querySelector('[name="distance_label"]').value = editData.distance_label || '10k';
        form.querySelector('[name="priority"]').value = editData.priority || 'B';
        form.querySelector('[name="goal_notes"]').value = editData.goal_notes || '';
        form.querySelector('[name="discipline"]').value = editData.discipline || 'running';
    }
    document.getElementById('race-form-card').classList.remove('hidden');
}

function hideRaceForm() {
    document.getElementById('race-form-card').classList.add('hidden');
}

async function saveRace(e) {
    e.preventDefault();
    const form = e.target;
    const id = form.querySelector('[name="id"]').value;
    const data = {
        name: form.querySelector('[name="name"]').value,
        date: form.querySelector('[name="date"]').value,
        distance_label: form.querySelector('[name="distance_label"]').value,
        priority: form.querySelector('[name="priority"]').value,
        goal_notes: form.querySelector('[name="goal_notes"]').value,
        discipline: form.querySelector('[name="discipline"]').value,
    };

    try {
        if (id) {
            await Coach.put(`/races/${id}`, data);
        } else {
            await Coach.post('/races', data);
        }
        hideRaceForm();
        await loadRaces();
    } catch (e) {
        alert('Failed to save race: ' + e.message);
    }
}

async function loadRaces() {
    const container = document.getElementById('race-list');
    try {
        const races = await Coach.get('/races');
        if (races.length === 0) {
            container.innerHTML = '<div class="card text-muted">No races yet. Add your first race above.</div>';
            return;
        }

        let html = '<table class="table"><thead><tr><th>Priority</th><th>Race</th><th>Date</th><th>Distance</th><th>Goal</th><th>Status</th><th>Weeks</th><th></th></tr></thead><tbody>';
        for (const r of races) {
            const weeks = Coach.weeksUntil(r.date);
            const weeksLabel = weeks !== null && weeks >= 0 ? `${weeks}w` : '-';
            const priorityClass = r.priority === 'A' ? 'red' : r.priority === 'B' ? 'yellow' : 'muted';
            const statusClass = r.status === 'completed' ? 'green' : r.status === 'upcoming' ? 'blue' : 'muted';

            html += `<tr>
                <td><span class="badge badge-${priorityClass}">${r.priority}</span></td>
                <td><strong>${r.name}</strong></td>
                <td>${Coach.formatDate(r.date)}</td>
                <td>${r.distance_label || '-'}</td>
                <td class="text-sm">${r.goal_notes || '-'}</td>
                <td><span class="badge badge-${statusClass}">${r.status}</span></td>
                <td class="font-bold">${weeksLabel}</td>
                <td>
                    <button class="btn btn-sm btn-secondary" onclick='showRaceForm(${JSON.stringify(r)})'>Edit</button>
                    <button class="btn btn-sm btn-danger" onclick='deleteRace(${r.id})'>Del</button>
                </td>
            </tr>`;
        }
        html += '</tbody></table>';
        container.innerHTML = html;
    } catch (e) {
        container.innerHTML = '<div class="text-muted">Failed to load races</div>';
    }
}

async function deleteRace(id) {
    if (!confirm('Delete this race?')) return;
    try {
        await Coach.del(`/races/${id}`);
        await loadRaces();
    } catch (e) {
        alert('Failed to delete: ' + e.message);
    }
}

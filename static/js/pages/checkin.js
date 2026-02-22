// Check-in form logic
document.addEventListener('DOMContentLoaded', async () => {
    Coach.initRangeInputs();

    const form = document.getElementById('checkin-form');
    const type = form.querySelector('input[name="type"]').value;

    // Pre-fill injury updates for morning check-ins
    if (type === 'morning') {
        await prefillInjuries();
    }

    // Load today's sessions for evening/weekend RPE
    if (type === 'evening' || type === 'weekend') {
        await loadTodaySessions();
    }

    // Handle form submission
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        await submitCheckin(form, type);
    });
});

async function prefillInjuries() {
    try {
        const injuries = await Coach.get('/injuries/active');
        const textarea = document.getElementById('injury-update');
        if (textarea && injuries.length > 0) {
            const lines = injuries.map(inj =>
                `${inj.body_part} (${inj.severity}/10): `
            );
            textarea.value = lines.join('\n');
            textarea.placeholder = 'Update each injury status...';
        }
    } catch (e) {
        console.error('Failed to load injuries:', e);
    }
}

async function loadTodaySessions() {
    const container = document.getElementById('session-rpe-list');
    if (!container) return;

    try {
        const activities = await Coach.get('/activities?days=1');
        if (activities.length === 0) {
            container.innerHTML = '<p class="text-muted text-sm">No sessions recorded today</p>';
            return;
        }

        let html = '';
        for (const a of activities) {
            const dist = a.distance_m ? (a.distance_m / 1000).toFixed(1) + 'km' : '';
            const dur = Coach.formatDuration(a.duration_s || a.elapsed_s);
            html += `
                <div class="card" style="padding: 8px 12px; margin-bottom: 8px;">
                    <div class="flex-between">
                        <span><strong>${a.sport}</strong> ${a.name || ''} — ${dist} ${dur}</span>
                    </div>
                    <div class="range-group mt-sm">
                        <label class="text-sm">RPE:</label>
                        <input type="range" name="session_rpe_${a.id}" min="1" max="10" value="5" class="session-rpe" data-activity-id="${a.id}">
                        <span class="range-value" id="session_rpe_${a.id}-val">5</span>
                    </div>
                    <input type="text" class="form-input mt-sm" name="session_notes_${a.id}" placeholder="Session notes (optional)" style="font-size: 13px;">
                </div>
            `;
        }
        container.innerHTML = html;
        Coach.initRangeInputs();
    } catch (e) {
        container.innerHTML = '<p class="text-muted text-sm">Could not load sessions</p>';
    }
}

async function submitCheckin(form, type) {
    const formData = new FormData(form);
    const data = { type };

    // Collect standard fields
    for (const [key, value] of formData.entries()) {
        if (key === 'type') continue;
        if (key.startsWith('session_rpe_') || key.startsWith('session_notes_')) continue;
        if (value !== '') {
            // Convert numeric fields
            if (['sleep_quality', 'work_stress', 'energy_level', 'motivation', 'alcohol'].includes(key)) {
                data[key] = parseInt(value);
            } else if (['hours_slept', 'body_weight_kg', 'hours_worked'].includes(key)) {
                data[key] = parseFloat(value);
            } else {
                data[key] = value;
            }
        }
    }

    // Collect session RPEs
    const sessionRpes = [];
    form.querySelectorAll('.session-rpe').forEach(input => {
        const activityId = input.dataset.activityId;
        const rpe = parseInt(input.value);
        const notes = form.querySelector(`input[name="session_notes_${activityId}"]`)?.value || '';
        sessionRpes.push({ activity_id: parseInt(activityId), rpe, notes });
    });
    if (sessionRpes.length > 0) {
        data.session_rpes = sessionRpes;
    }

    try {
        const result = await Coach.post('/checkins', data);
        // Show success and redirect to dashboard
        const btn = form.querySelector('button[type="submit"]');
        btn.textContent = 'Saved!';
        btn.classList.remove('btn-primary');
        btn.classList.add('btn-secondary');
        btn.disabled = true;
        setTimeout(() => window.location.href = '/', 1000);
    } catch (e) {
        alert('Failed to save check-in: ' + e.message);
    }
}

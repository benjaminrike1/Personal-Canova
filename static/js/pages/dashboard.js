// Dashboard page logic
document.addEventListener('DOMContentLoaded', async () => {
    // Check onboarding status first
    try {
        const status = await Coach.get('/athlete/onboarding-status');
        if (!status.complete) {
            window.location.href = '/onboarding';
            return;
        }
    } catch (e) {
        // No profile yet — go to onboarding
        window.location.href = '/onboarding';
        return;
    }

    // Load all dashboard data in parallel
    await Promise.allSettled([
        loadCheckinStatus(),
        loadNextRace(),
        loadFitness(),
        loadActiveInjuries(),
        loadWeekPlan(),
        loadRecentActivities(),
        loadSleepTrend(),
        loadStressTrend(),
    ]);
});

async function loadCheckinStatus() {
    try {
        const status = await Coach.get('/checkins/today');
        renderCheckinCard('morning-status', status.morning, 'morning');
        renderCheckinCard('evening-status', status.evening, 'evening');
    } catch (e) {
        document.getElementById('morning-status').textContent = '-';
        document.getElementById('evening-status').textContent = '-';
    }
}

function renderCheckinCard(elementId, checkin, type) {
    const el = document.getElementById(elementId);
    if (!el) return;
    if (checkin && checkin.completed) {
        el.innerHTML = '<span class="badge badge-green">Done</span>';
    } else if (checkin) {
        el.innerHTML = `<span class="badge badge-yellow">${Math.round(checkin.completion_pct || 0)}%</span> <a href="/checkin/${type}" class="btn btn-sm btn-secondary">Continue</a>`;
    } else {
        el.innerHTML = `<a href="/checkin/${type}" class="btn btn-sm btn-primary">Start</a>`;
    }
}

async function loadNextRace() {
    const el = document.getElementById('next-race');
    try {
        const race = await Coach.get('/races/next');
        if (race) {
            const weeks = Coach.weeksUntil(race.date);
            const days = Coach.daysUntil(race.date);
            el.innerHTML = `
                <div class="card-value">${weeks}w</div>
                <div class="text-muted text-sm">${race.name} — ${Coach.formatDate(race.date)}</div>
                <div class="text-sm">${race.distance_label || ''} ${race.goal_notes ? '| ' + race.goal_notes : ''}</div>
            `;
        } else {
            el.innerHTML = '<span class="text-muted">No upcoming races</span>';
        }
    } catch (e) {
        el.textContent = '-';
    }
}

async function loadFitness() {
    const el = document.getElementById('fitness');
    try {
        const data = await Coach.get('/analytics/training-load?weeks=1');
        if (data && data.length > 0) {
            const latest = data[data.length - 1];
            const tsb = (latest.ctl || 0) - (latest.atl || 0);
            const tsbClass = tsb > 10 ? 'text-green' : tsb < -20 ? 'text-red' : 'text-yellow';
            el.innerHTML = `
                <div class="card-value">${(latest.ctl || 0).toFixed(0)} / ${(latest.atl || 0).toFixed(0)} / <span class="${tsbClass}">${tsb >= 0 ? '+' : ''}${tsb.toFixed(0)}</span></div>
                <div class="text-muted text-sm">Ramp: ${(latest.ramp_rate || 0) >= 0 ? '+' : ''}${(latest.ramp_rate || 0).toFixed(1)}</div>
            `;
        } else {
            el.innerHTML = '<span class="text-muted">No fitness data yet — sync activities first</span>';
        }
    } catch (e) {
        el.textContent = '-';
    }
}

async function loadActiveInjuries() {
    const el = document.getElementById('active-injuries');
    try {
        const injuries = await Coach.get('/injuries/active');
        if (injuries.length === 0) {
            el.innerHTML = '<span class="badge badge-green">None</span>';
        } else {
            el.innerHTML = injuries.map(inj =>
                `<div class="text-sm"><span class="badge badge-${inj.severity >= 7 ? 'red' : inj.severity >= 4 ? 'yellow' : 'muted'}">${inj.severity}/10</span> ${inj.body_part}</div>`
            ).join('');
        }
    } catch (e) {
        el.textContent = '-';
    }
}

async function loadWeekPlan() {
    const container = document.getElementById('week-plan');
    try {
        const plan = await Coach.get('/plan/current');
        const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
        const today = new Date().getDay(); // 0=Sun
        const todayMon = today === 0 ? 6 : today - 1; // Convert to 0=Mon

        let html = '';
        for (let i = 0; i < 7; i++) {
            const daySessions = plan.filter(s => s.day_of_week === i);
            const isToday = i === todayMon;
            html += `<div class="plan-day${isToday ? ' style="border-color: var(--accent)"' : ''}">`;
            html += `<div class="plan-day-header">${days[i]}${isToday ? ' (today)' : ''}</div>`;

            if (daySessions.length === 0) {
                html += '<div class="plan-session rest">Rest</div>';
            } else {
                for (const s of daySessions) {
                    if (s.is_rest_day) {
                        html += '<div class="plan-session rest">Rest</div>';
                    } else {
                        const cls = s.is_key_session ? 'key' : '';
                        const dur = Coach.formatDuration(s.target_duration_s);
                        const done = s.completed ? ' ✓' : '';
                        html += `<div class="plan-session ${cls}">${s.session_type} ${dur}${done}</div>`;
                    }
                }
            }
            html += '</div>';
        }
        container.innerHTML = html;
    } catch (e) {
        container.innerHTML = '<span class="text-muted">No plan for this week</span>';
    }
}

async function loadRecentActivities() {
    const container = document.getElementById('recent-activities');
    try {
        const activities = await Coach.get('/activities?days=7&limit=10');
        if (activities.length === 0) {
            container.innerHTML = '<span class="text-muted">No recent activities — <button class="btn btn-sm btn-secondary" onclick="syncActivities()">Sync now</button></span>';
            return;
        }

        let html = '<table class="table"><thead><tr><th>Date</th><th>Sport</th><th>Name</th><th>Dist</th><th>Time</th><th>HR</th><th>Load</th></tr></thead><tbody>';
        for (const a of activities) {
            const dist = a.distance_m ? (a.distance_m / 1000).toFixed(1) + 'km' : '-';
            const time = Coach.formatDuration(a.duration_s || a.elapsed_s);
            const hr = a.avg_hr ? Math.round(a.avg_hr) : '-';
            const load = a.training_load ? Math.round(a.training_load) : '-';
            html += `<tr>
                <td class="text-sm">${Coach.formatDateShort(a.start_time)}</td>
                <td><span class="badge badge-blue">${a.sport}</span></td>
                <td>${a.name || '-'}</td>
                <td>${dist}</td>
                <td>${time}</td>
                <td>${hr}</td>
                <td>${load}</td>
            </tr>`;
        }
        html += '</tbody></table>';
        container.innerHTML = html;
    } catch (e) {
        container.innerHTML = '<span class="text-muted">-</span>';
    }
}

async function loadSleepTrend() {
    const el = document.getElementById('sleep-trend');
    try {
        const data = await Coach.get('/analytics/training-load?weeks=1');
        if (!data || data.length === 0) {
            el.innerHTML = '<span class="text-muted">No data</span>';
            return;
        }
        // Simple sparkline from wellness sleep data
        const checkins = await Coach.get('/checkins?days=7');
        const sleepData = checkins
            .filter(c => c.type === 'morning' && c.hours_slept)
            .map(c => ({ date: c.date, hours: c.hours_slept, quality: c.sleep_quality }));

        if (sleepData.length === 0) {
            el.innerHTML = '<span class="text-muted">No check-in data yet</span>';
            return;
        }

        let html = '';
        for (const s of sleepData.reverse()) {
            const bar = Math.max(10, (s.hours / 10) * 100);
            const color = s.quality >= 7 ? 'var(--green)' : s.quality >= 5 ? 'var(--yellow)' : 'var(--red)';
            html += `<div style="display:inline-block; width:${100/7}%; text-align:center;">
                <div style="height:${bar}px; background:${color}; border-radius:3px; margin: 0 2px;"></div>
                <div class="text-sm text-muted">${s.hours}h</div>
            </div>`;
        }
        el.innerHTML = html;
    } catch (e) {
        el.innerHTML = '<span class="text-muted">-</span>';
    }
}

async function loadStressTrend() {
    const el = document.getElementById('stress-trend');
    try {
        const checkins = await Coach.get('/checkins?days=7');
        const stressData = checkins
            .filter(c => c.type === 'morning' && c.work_stress)
            .map(c => ({ date: c.date, stress: c.work_stress, finish: c.work_finish_time }));

        if (stressData.length === 0) {
            el.innerHTML = '<span class="text-muted">No check-in data yet</span>';
            return;
        }

        let html = '';
        for (const s of stressData.reverse()) {
            const bar = Math.max(10, (s.stress / 10) * 60);
            const color = s.stress >= 8 ? 'var(--red)' : s.stress >= 5 ? 'var(--yellow)' : 'var(--green)';
            html += `<div style="display:inline-block; width:${100/7}%; text-align:center;">
                <div style="height:${bar}px; background:${color}; border-radius:3px; margin: 0 2px;"></div>
                <div class="text-sm text-muted">${s.stress}/10</div>
            </div>`;
        }
        el.innerHTML = html;
    } catch (e) {
        el.innerHTML = '<span class="text-muted">-</span>';
    }
}

async function syncActivities() {
    try {
        await Coach.post('/activities/sync', { days: 30 });
        window.location.reload();
    } catch (e) {
        alert('Sync failed: ' + e.message);
    }
}

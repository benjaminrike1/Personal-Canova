// Training plan page logic
let currentMonday = null;

document.addEventListener('DOMContentLoaded', async () => {
    // Start with current week
    const today = new Date();
    const dayOfWeek = today.getDay() === 0 ? 6 : today.getDay() - 1;
    currentMonday = new Date(today);
    currentMonday.setDate(today.getDate() - dayOfWeek);

    document.getElementById('prev-week').addEventListener('click', () => shiftWeek(-7));
    document.getElementById('next-week').addEventListener('click', () => shiftWeek(7));

    await loadWeek();
});

function shiftWeek(days) {
    currentMonday.setDate(currentMonday.getDate() + days);
    loadWeek();
}

function getWeekStart() {
    return currentMonday.toISOString().slice(0, 10);
}

async function loadWeek() {
    const weekStart = getWeekStart();
    const weekEnd = new Date(currentMonday);
    weekEnd.setDate(weekEnd.getDate() + 6);
    document.getElementById('week-label').textContent =
        `${Coach.formatDateShort(weekStart)} — ${Coach.formatDateShort(weekEnd.toISOString())}`;

    const container = document.getElementById('plan-grid');
    const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

    try {
        const plan = await Coach.get(`/plan/week/${weekStart}`);
        const todayIdx = (() => {
            const t = new Date();
            const d = t.getDay() === 0 ? 6 : t.getDay() - 1;
            const isSameWeek = t.toISOString().slice(0, 10) >= weekStart &&
                               t.toISOString().slice(0, 10) <= weekEnd.toISOString().slice(0, 10);
            return isSameWeek ? d : -1;
        })();

        let html = '';
        let totalPlanned = 0;
        let totalActual = 0;
        let keyCount = 0;

        for (let i = 0; i < 7; i++) {
            const daySessions = plan.filter(s => s.day_of_week === i);
            const isToday = i === todayIdx;
            const borderStyle = isToday ? 'border-color: var(--accent); border-width: 2px;' : '';

            html += `<div class="plan-day" style="${borderStyle}">`;
            html += `<div class="plan-day-header">${days[i]}${isToday ? ' ●' : ''}</div>`;

            if (daySessions.length === 0) {
                html += '<div class="plan-session rest">-</div>';
            } else {
                for (const s of daySessions) {
                    if (s.is_rest_day) {
                        html += '<div class="plan-session rest">Rest</div>';
                    } else {
                        const cls = s.is_key_session ? 'key' : '';
                        const dur = Coach.formatDuration(s.target_duration_s);
                        totalPlanned += (s.target_duration_s || 0);
                        if (s.is_key_session) keyCount++;

                        let status = '';
                        if (s.completed) {
                            status = ' <span class="badge badge-green">Done</span>';
                            totalActual += (s.target_duration_s || 0); // Use actual if available
                        }

                        html += `<div class="plan-session ${cls}">
                            <div>${s.session_type}${status}</div>
                            <div class="text-muted text-sm">${dur}${s.target_intensity ? ' @ ' + s.target_intensity : ''}</div>
                            ${s.key_objective ? '<div class="text-sm">' + s.key_objective + '</div>' : ''}
                        </div>`;
                    }
                }
            }
            html += '</div>';
        }
        container.innerHTML = html;

        document.getElementById('planned-hours').textContent = (totalPlanned / 3600).toFixed(1) + 'h';
        document.getElementById('actual-hours').textContent = (totalActual / 3600).toFixed(1) + 'h';
        document.getElementById('key-sessions-count').textContent = keyCount;
    } catch (e) {
        container.innerHTML = '<span class="text-muted">No plan for this week</span>';
    }
}

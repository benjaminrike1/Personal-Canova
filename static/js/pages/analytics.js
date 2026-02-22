// Analytics page logic (Chart.js)
let currentWeeks = 4;
let currentSport = 'Run';
const charts = {};

const CHART_COLORS = {
    ctl: '#58a6ff',
    atl: '#f85149',
    tsb: '#3fb950',
    hr: '#f85149',
    pace: '#58a6ff',
    power: '#d29922',
    planned: 'rgba(88, 166, 255, 0.5)',
    actual: '#58a6ff',
};

const CHART_DEFAULTS = {
    responsive: true,
    maintainAspectRatio: true,
    plugins: {
        legend: { labels: { color: '#8b949e', font: { size: 11 } } },
    },
    scales: {
        x: { ticks: { color: '#8b949e' }, grid: { color: '#21262d' } },
        y: { ticks: { color: '#8b949e' }, grid: { color: '#21262d' } },
    },
};

document.addEventListener('DOMContentLoaded', async () => {
    // Period toggle
    document.querySelectorAll('#period-toggle button').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#period-toggle button').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentWeeks = parseInt(btn.dataset.weeks);
            loadAllCharts();
        });
    });

    // Sport toggle
    document.getElementById('sport-run').addEventListener('click', () => setSport('Run'));
    document.getElementById('sport-ride').addEventListener('click', () => setSport('Ride'));

    await loadAllCharts();
});

function setSport(sport) {
    currentSport = sport;
    document.getElementById('sport-run').className = `btn btn-sm ${sport === 'Run' ? 'btn-primary' : 'btn-secondary'}`;
    document.getElementById('sport-ride').className = `btn btn-sm ${sport === 'Ride' ? 'btn-primary' : 'btn-secondary'}`;
    loadAllCharts();
}

async function loadAllCharts() {
    await Promise.allSettled([
        loadAerobicChart(),
        loadTrainingLoad(),
        loadKeySessionChart(),
        loadZoneChart(),
        loadPlannedActual(),
    ]);
}

async function loadTrainingLoad() {
    try {
        const data = await Coach.get(`/analytics/training-load?weeks=${currentWeeks}`);
        if (!data || data.length === 0) return;

        const labels = data.map(d => d.date);
        const ctl = data.map(d => d.ctl || 0);
        const atl = data.map(d => d.atl || 0);
        const tsb = data.map(d => (d.ctl || 0) - (d.atl || 0));

        if (charts.load) charts.load.destroy();
        charts.load = new Chart(document.getElementById('chart-load'), {
            type: 'line',
            data: {
                labels,
                datasets: [
                    { label: 'CTL (Fitness)', data: ctl, borderColor: CHART_COLORS.ctl, tension: 0.3, pointRadius: 0 },
                    { label: 'ATL (Fatigue)', data: atl, borderColor: CHART_COLORS.atl, tension: 0.3, pointRadius: 0 },
                    { label: 'TSB (Form)', data: tsb, borderColor: CHART_COLORS.tsb, tension: 0.3, pointRadius: 0, fill: { target: 'origin', above: 'rgba(63,185,80,0.1)', below: 'rgba(248,81,73,0.1)' } },
                ],
            },
            options: { ...CHART_DEFAULTS },
        });
    } catch (e) { console.error('Training load chart error:', e); }
}

async function loadAerobicChart() {
    try {
        const data = await Coach.get(`/analytics/aerobic-efficiency?sport=${currentSport}&weeks=${currentWeeks}`);
        if (!data || data.length === 0) return;

        const labels = data.map(d => d.date);

        if (charts.aerobic) charts.aerobic.destroy();
        charts.aerobic = new Chart(document.getElementById('chart-aerobic'), {
            type: 'scatter',
            data: {
                datasets: [
                    {
                        label: 'HR',
                        data: data.map(d => ({ x: d.date, y: d.avg_hr })),
                        backgroundColor: CHART_COLORS.hr,
                        yAxisID: 'y',
                    },
                    {
                        label: currentSport === 'Run' ? 'Pace (s/km)' : 'Power (W)',
                        data: data.map(d => ({
                            x: d.date,
                            y: currentSport === 'Run' ? d.pace_s_km : d.avg_power,
                        })),
                        backgroundColor: CHART_COLORS.pace,
                        yAxisID: 'y1',
                    },
                ],
            },
            options: {
                ...CHART_DEFAULTS,
                scales: {
                    ...CHART_DEFAULTS.scales,
                    y: { ...CHART_DEFAULTS.scales.y, position: 'left', title: { display: true, text: 'HR (bpm)', color: '#8b949e' } },
                    y1: { ...CHART_DEFAULTS.scales.y, position: 'right', title: { display: true, text: currentSport === 'Run' ? 'Pace (s/km)' : 'Power (W)', color: '#8b949e' }, grid: { drawOnChartArea: false } },
                },
            },
        });
    } catch (e) { console.error('Aerobic chart error:', e); }
}

async function loadKeySessionChart() {
    try {
        const data = await Coach.get(`/analytics/key-sessions?weeks=${currentWeeks}`);
        if (!data || data.length === 0) return;

        if (charts.keySessions) charts.keySessions.destroy();
        charts.keySessions = new Chart(document.getElementById('chart-key-sessions'), {
            type: 'scatter',
            data: {
                datasets: [{
                    label: 'Key Sessions',
                    data: data.map(d => ({ x: d.date, y: d.training_load || 0 })),
                    backgroundColor: CHART_COLORS.ctl,
                    pointRadius: 6,
                }],
            },
            options: { ...CHART_DEFAULTS },
        });
    } catch (e) { console.error('Key sessions chart error:', e); }
}

async function loadZoneChart() {
    try {
        const data = await Coach.get(`/analytics/zone-distribution?sport=${currentSport}&weeks=${currentWeeks}`);
        if (!data || data.length === 0) return;

        const zoneColors = ['#3fb950', '#58a6ff', '#d29922', '#f85149', '#db6d28'];
        const labels = data.map(d => d.week_start);
        const datasets = [];

        // Up to 5 zones
        const maxZones = Math.max(...data.map(d => (d.zones || []).length));
        for (let z = 0; z < maxZones; z++) {
            datasets.push({
                label: `Zone ${z + 1}`,
                data: data.map(d => ((d.zones || [])[z] || 0) / 60),
                backgroundColor: zoneColors[z % zoneColors.length],
            });
        }

        if (charts.zones) charts.zones.destroy();
        charts.zones = new Chart(document.getElementById('chart-zones'), {
            type: 'bar',
            data: { labels, datasets },
            options: {
                ...CHART_DEFAULTS,
                scales: {
                    ...CHART_DEFAULTS.scales,
                    x: { ...CHART_DEFAULTS.scales.x, stacked: true },
                    y: { ...CHART_DEFAULTS.scales.y, stacked: true, title: { display: true, text: 'Minutes', color: '#8b949e' } },
                },
            },
        });
    } catch (e) { console.error('Zone chart error:', e); }
}

async function loadPlannedActual() {
    try {
        const data = await Coach.get(`/analytics/planned-vs-actual?weeks=${currentWeeks}`);
        if (!data || data.length === 0) return;

        const labels = data.map(d => d.week_start);

        if (charts.plannedActual) charts.plannedActual.destroy();
        charts.plannedActual = new Chart(document.getElementById('chart-planned-actual'), {
            type: 'bar',
            data: {
                labels,
                datasets: [
                    { label: 'Planned', data: data.map(d => d.planned_hours), backgroundColor: CHART_COLORS.planned },
                    { label: 'Actual', data: data.map(d => d.actual_hours), backgroundColor: CHART_COLORS.actual },
                ],
            },
            options: { ...CHART_DEFAULTS },
        });
    } catch (e) { console.error('Planned vs actual chart error:', e); }
}

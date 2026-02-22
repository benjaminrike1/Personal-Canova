// Coach — Core JS utilities

const Coach = {
    // API helper
    async api(method, path, body = null) {
        const opts = {
            method,
            headers: { 'Content-Type': 'application/json' },
        };
        if (body) opts.body = JSON.stringify(body);
        const res = await fetch(`/api${path}`, opts);
        if (!res.ok) {
            const err = await res.text();
            throw new Error(`API error ${res.status}: ${err}`);
        }
        return res.json();
    },

    get(path) { return this.api('GET', path); },
    post(path, body) { return this.api('POST', path, body); },
    put(path, body) { return this.api('PUT', path, body); },
    del(path) { return this.api('DELETE', path); },

    // Format helpers
    formatDuration(seconds) {
        if (!seconds) return '-';
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        if (h > 0) return `${h}h ${m}m`;
        return `${m}m`;
    },

    formatPace(secondsPerKm) {
        if (!secondsPerKm) return '-';
        const m = Math.floor(secondsPerKm / 60);
        const s = Math.floor(secondsPerKm % 60);
        return `${m}:${s.toString().padStart(2, '0')}/km`;
    },

    formatDate(isoDate) {
        if (!isoDate) return '-';
        return new Date(isoDate).toLocaleDateString('en-GB', {
            day: 'numeric', month: 'short', year: 'numeric'
        });
    },

    formatDateShort(isoDate) {
        if (!isoDate) return '-';
        return new Date(isoDate).toLocaleDateString('en-GB', {
            day: 'numeric', month: 'short'
        });
    },

    daysUntil(isoDate) {
        if (!isoDate) return null;
        const now = new Date();
        now.setHours(0, 0, 0, 0);
        const target = new Date(isoDate);
        return Math.ceil((target - now) / (1000 * 60 * 60 * 24));
    },

    weeksUntil(isoDate) {
        const days = this.daysUntil(isoDate);
        if (days === null) return null;
        return Math.ceil(days / 7);
    },

    // DOM helpers
    $(sel) { return document.querySelector(sel); },
    $$(sel) { return document.querySelectorAll(sel); },

    // Simple range input handler
    initRangeInputs() {
        document.querySelectorAll('input[type="range"]').forEach(input => {
            const display = document.getElementById(input.id + '-val');
            if (display) {
                display.textContent = input.value;
                input.addEventListener('input', () => {
                    display.textContent = input.value;
                });
            }
        });
    },
};

// Mobile nav toggle
document.addEventListener('DOMContentLoaded', () => {
    const toggle = document.querySelector('.nav-toggle');
    const links = document.querySelector('.nav-links');
    if (toggle && links) {
        toggle.addEventListener('click', () => links.classList.toggle('open'));
    }

    // Mark active nav link
    const path = window.location.pathname;
    document.querySelectorAll('.nav-link').forEach(link => {
        if (link.getAttribute('href') === path) {
            link.classList.add('active');
        }
    });

    Coach.initRangeInputs();
});

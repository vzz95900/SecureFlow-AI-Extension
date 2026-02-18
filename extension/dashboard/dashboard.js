/**
 * SecureFlow AI — Dashboard Logic with Chart.js.
 * Renders overview stats, risk/trend/entity charts, tables, and CSV export.
 */

(() => {
    'use strict';

    // ── DOM refs ──────────────────────────────────────────────
    const $ = (sel) => document.querySelector(sel);
    const navItems = document.querySelectorAll('.nav-item');
    const sections = {
        overview: $('#section-overview'),
        history: $('#section-history'),
        entities: $('#section-entities'),
    };

    // ── Charts (lazy-created) ─────────────────────────────────
    let riskChart = null;
    let trendChart = null;
    let entityChart = null;

    // Chart.js dark theme defaults
    const chartColors = {
        high: '#ef4444',
        medium: '#f59e0b',
        low: '#10b981',
        grid: 'rgba(148, 163, 184, 0.08)',
        tick: '#94a3b8',
    };

    const entityPalette = [
        '#6366f1', '#06b6d4', '#818cf8', '#22d3ee',
        '#f472b6', '#a78bfa', '#34d399', '#fbbf24',
        '#fb923c', '#f87171',
    ];

    // ── Navigation ────────────────────────────────────────────
    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const target = item.dataset.section;

            navItems.forEach(n => n.classList.remove('active'));
            item.classList.add('active');

            Object.entries(sections).forEach(([key, el]) => {
                el.classList.toggle('hidden', key !== target);
            });

            $('#page-title').textContent = {
                overview: 'Overview',
                history: 'Session History',
                entities: 'Entity Breakdown',
            }[target] || 'Overview';
        });
    });

    // ── Load data ─────────────────────────────────────────────
    function loadDashboard() {
        if (typeof chrome === 'undefined' || !chrome.storage) {
            renderDemoData();
            return;
        }

        chrome.storage.local.get(['stats', 'sessions'], (data) => {
            const stats = data.stats || { totalPrompts: 0, totalEntities: 0, highRiskCount: 0 };
            const sessions = data.sessions || [];
            render(stats, sessions);
        });
    }

    function renderDemoData() {
        // Show demo data when running outside the extension
        const stats = { totalPrompts: 42, totalEntities: 187, highRiskCount: 23 };
        const sessions = [
            { timestamp: Date.now() - 60000 * 5, sessionId: 'a1b2c3d4', entities: 8, riskLevel: 'HIGH', entitySummary: [{ type: 'PERSON', count: 3, risk: 'MEDIUM' }, { type: 'SSN', count: 2, risk: 'HIGH' }, { type: 'EMAIL', count: 3, risk: 'MEDIUM' }] },
            { timestamp: Date.now() - 60000 * 15, sessionId: 'e5f6g7h8', entities: 3, riskLevel: 'MEDIUM', entitySummary: [{ type: 'PHONE', count: 2, risk: 'MEDIUM' }, { type: 'PERSON', count: 1, risk: 'MEDIUM' }] },
            { timestamp: Date.now() - 60000 * 45, sessionId: 'i9j0k1l2', entities: 12, riskLevel: 'HIGH', entitySummary: [{ type: 'CREDIT_CARD', count: 1, risk: 'HIGH' }, { type: 'SSN', count: 4, risk: 'HIGH' }, { type: 'PERSON', count: 5, risk: 'MEDIUM' }, { type: 'EMAIL', count: 2, risk: 'MEDIUM' }] },
            { timestamp: Date.now() - 60000 * 90, sessionId: 'm3n4o5p6', entities: 1, riskLevel: 'LOW', entitySummary: [{ type: 'DATE', count: 1, risk: 'LOW' }] },
            { timestamp: Date.now() - 60000 * 120, sessionId: 'q7r8s9t0', entities: 5, riskLevel: 'MEDIUM', entitySummary: [{ type: 'PERSON', count: 2, risk: 'MEDIUM' }, { type: 'LOCATION', count: 3, risk: 'LOW' }] },
        ];
        render(stats, sessions);
    }

    // ── Render everything ─────────────────────────────────────
    function render(stats, sessions) {
        renderSummaryCards(stats);
        renderRecentTable(sessions.slice(0, 10));
        renderHistoryTable(sessions);
        renderEntityBars(sessions);
        renderRiskChart(sessions);
        renderTrendChart(sessions);
        renderEntityChart(sessions);
    }

    // ── Summary cards ─────────────────────────────────────────
    function renderSummaryCards(stats) {
        animateCount($('#total-prompts'), stats.totalPrompts || 0);
        animateCount($('#total-entities'), stats.totalEntities || 0);
        animateCount($('#high-risk-count'), stats.highRiskCount || 0);

        const rate = stats.totalPrompts > 0 ? '100%' : '—';
        $('#protection-rate').textContent = rate;
    }

    function animateCount(el, target) {
        const duration = 600;
        const start = performance.now();
        const initial = parseInt(el.textContent) || 0;

        function step(now) {
            const t = Math.min((now - start) / duration, 1);
            const ease = 1 - Math.pow(1 - t, 3);
            el.textContent = Math.round(initial + (target - initial) * ease);
            if (t < 1) requestAnimationFrame(step);
        }
        requestAnimationFrame(step);
    }

    // ── Recent Activity table ─────────────────────────────────
    function renderRecentTable(sessions) {
        const tbody = $('#recent-tbody');
        if (!sessions.length) return;

        tbody.innerHTML = sessions.map(s => `
            <tr>
                <td>${formatTime(s.timestamp)}</td>
                <td><code>${s.sessionId}</code></td>
                <td>${s.entities}</td>
                <td><span class="risk-badge ${s.riskLevel.toLowerCase()}">${s.riskLevel}</span></td>
            </tr>
        `).join('');
    }

    // ── Full History table ────────────────────────────────────
    function renderHistoryTable(sessions) {
        const tbody = $('#history-tbody');
        if (!sessions.length) {
            tbody.innerHTML = '<tr class="empty-row"><td colspan="5">No sessions recorded yet.</td></tr>';
            return;
        }

        tbody.innerHTML = sessions.map(s => {
            const types = (s.entitySummary || []).map(e => e.type).join(', ') || '—';
            return `
                <tr>
                    <td>${formatDateTime(s.timestamp)}</td>
                    <td><code>${s.sessionId}</code></td>
                    <td>${s.entities}</td>
                    <td><span class="risk-badge ${s.riskLevel.toLowerCase()}">${s.riskLevel}</span></td>
                    <td>${types}</td>
                </tr>
            `;
        }).join('');
    }

    // ── Entity bars ───────────────────────────────────────────
    function renderEntityBars(sessions) {
        const container = $('#entity-bars');
        const counts = aggregateEntities(sessions);
        const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);

        if (!entries.length) return;

        const max = entries[0][1];
        container.innerHTML = entries.map(([type, count]) => {
            const pct = Math.round((count / max) * 100);
            return `
                <div class="entity-bar-row">
                    <span class="entity-bar-label">${type}</span>
                    <div class="entity-bar-track">
                        <div class="entity-bar-fill" style="width: ${pct}%"></div>
                    </div>
                    <span class="entity-bar-count">${count}</span>
                </div>
            `;
        }).join('');
    }

    // ── Risk Distribution chart (doughnut) ────────────────────
    function renderRiskChart(sessions) {
        const counts = { HIGH: 0, MEDIUM: 0, LOW: 0 };
        sessions.forEach(s => {
            const r = (s.riskLevel || 'LOW').toUpperCase();
            counts[r] = (counts[r] || 0) + 1;
        });

        const ctx = document.getElementById('risk-chart');
        if (!ctx) return;

        if (riskChart) riskChart.destroy();

        riskChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['High', 'Medium', 'Low'],
                datasets: [{
                    data: [counts.HIGH, counts.MEDIUM, counts.LOW],
                    backgroundColor: [chartColors.high, chartColors.medium, chartColors.low],
                    borderColor: 'transparent',
                    borderWidth: 0,
                    hoverOffset: 6,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '65%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: chartColors.tick, font: { size: 12, family: 'Inter' }, padding: 16 },
                    },
                },
            },
        });
    }

    // ── Activity Trend chart (line) ───────────────────────────
    function renderTrendChart(sessions) {
        const ctx = document.getElementById('trend-chart');
        if (!ctx) return;

        // Group sessions by hour for last 24h
        const buckets = {};
        const now = Date.now();
        for (let h = 23; h >= 0; h--) {
            const label = `${h}h ago`;
            buckets[label] = 0;
        }

        sessions.forEach(s => {
            const hoursAgo = Math.floor((now - s.timestamp) / (60 * 60 * 1000));
            if (hoursAgo >= 0 && hoursAgo < 24) {
                const label = `${hoursAgo}h ago`;
                buckets[label] = (buckets[label] || 0) + s.entities;
            }
        });

        const labels = Object.keys(buckets).reverse();
        const data = labels.map(l => buckets[l]);

        if (trendChart) trendChart.destroy();

        trendChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    label: 'Entities Detected',
                    data,
                    borderColor: '#6366f1',
                    backgroundColor: 'rgba(99, 102, 241, 0.08)',
                    fill: true,
                    tension: 0.4,
                    pointRadius: 2,
                    pointHoverRadius: 5,
                    borderWidth: 2,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { ticks: { color: chartColors.tick, font: { size: 10 }, maxTicksLimit: 8 }, grid: { color: chartColors.grid } },
                    y: { beginAtZero: true, ticks: { color: chartColors.tick, font: { size: 10 } }, grid: { color: chartColors.grid } },
                },
                plugins: { legend: { display: false } },
            },
        });
    }

    // ── Entity Breakdown chart (horizontal bar) ───────────────
    function renderEntityChart(sessions) {
        const ctx = document.getElementById('entity-chart');
        if (!ctx) return;

        const counts = aggregateEntities(sessions);
        const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);

        if (entityChart) entityChart.destroy();

        entityChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: entries.map(e => e[0]),
                datasets: [{
                    label: 'Count',
                    data: entries.map(e => e[1]),
                    backgroundColor: entries.map((_, i) => entityPalette[i % entityPalette.length]),
                    borderRadius: 6,
                    borderSkipped: false,
                    maxBarThickness: 36,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y',
                scales: {
                    x: { beginAtZero: true, ticks: { color: chartColors.tick, font: { size: 11 } }, grid: { color: chartColors.grid } },
                    y: { ticks: { color: chartColors.tick, font: { size: 12, weight: '600' } }, grid: { display: false } },
                },
                plugins: { legend: { display: false } },
            },
        });
    }

    // ── Helpers ────────────────────────────────────────────────
    function aggregateEntities(sessions) {
        const counts = {};
        sessions.forEach(s => {
            (s.entitySummary || []).forEach(e => {
                counts[e.type] = (counts[e.type] || 0) + e.count;
            });
        });
        return counts;
    }

    function formatTime(ts) {
        return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    function formatDateTime(ts) {
        return new Date(ts).toLocaleString([], {
            month: 'short', day: 'numeric',
            hour: '2-digit', minute: '2-digit',
        });
    }

    // ── CSV Export ─────────────────────────────────────────────
    $('#btn-export')?.addEventListener('click', () => {
        if (typeof chrome === 'undefined' || !chrome.storage) {
            alert('CSV export is available when running as a Chrome extension.');
            return;
        }

        chrome.storage.local.get(['sessions'], (data) => {
            const sessions = data.sessions || [];
            const header = 'Timestamp,Session ID,Entities Found,Risk Level,Entity Types\n';
            const rows = sessions.map(s => {
                const types = (s.entitySummary || []).map(e => e.type).join('; ');
                return `${new Date(s.timestamp).toISOString()},${s.sessionId},${s.entities},${s.riskLevel},"${types}"`;
            }).join('\n');

            const blob = new Blob([header + rows], { type: 'text/csv' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `secureflow_sessions_${Date.now()}.csv`;
            a.click();
            URL.revokeObjectURL(url);
        });
    });

    // ── Refresh ───────────────────────────────────────────────
    $('#btn-refresh')?.addEventListener('click', loadDashboard);

    // ── Init ──────────────────────────────────────────────────
    loadDashboard();
})();

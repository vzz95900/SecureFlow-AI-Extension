/**
 * SecureFlow AI — Popup Logic
 */
'use strict';

document.addEventListener('DOMContentLoaded', async () => {
    // ── Elements ─────────────────────────────────────────────────
    const toggleSwitch = document.getElementById('toggle-switch');
    const statusCard = document.getElementById('status-card');
    const statusLabel = document.getElementById('status-label');
    const statusSite = document.getElementById('status-site');
    const pulseDot = document.getElementById('pulse-dot');
    const pulseRing = document.getElementById('pulse-ring');
    const statPrompts = document.getElementById('stat-prompts');
    const statEntities = document.getElementById('stat-entities');
    const statRisk = document.getElementById('stat-risk');
    const riskCard = document.getElementById('risk-card');
    const pills = document.querySelectorAll('.pill');
    const btnDashboard = document.getElementById('btn-dashboard');
    const btnOptions = document.getElementById('btn-options');

    // ── Load State ───────────────────────────────────────────────
    const stored = await chrome.storage.local.get([
        'secureflow_enabled',
        'secureflow_config',
        'secureflow_stats',
    ]);

    const isEnabled = stored.secureflow_enabled !== false;
    const config = stored.secureflow_config || {};
    const stats = stored.secureflow_stats || { totalPrompts: 0, totalEntities: 0, sessions: [] };

    // Toggle
    toggleSwitch.checked = isEnabled;
    updateStatusUI(isEnabled);

    // Stats
    statPrompts.textContent = stats.totalPrompts;
    statEntities.textContent = stats.totalEntities;

    // Risk level from most recent session
    if (stats.sessions.length > 0) {
        const lastRisk = stats.sessions[0].riskLevel || '—';
        statRisk.textContent = lastRisk;
        riskCard.setAttribute('data-risk', lastRisk);
    }

    // Sensitivity pills
    const currentSensitivity = config.sensitivity || 'high';
    pills.forEach((pill) => {
        pill.classList.toggle('active', pill.dataset.level === currentSensitivity);
    });

    // ── Event Listeners ──────────────────────────────────────────

    toggleSwitch.addEventListener('change', async () => {
        const enabled = toggleSwitch.checked;
        await chrome.storage.local.set({ secureflow_enabled: enabled });
        updateStatusUI(enabled);
    });

    pills.forEach((pill) => {
        pill.addEventListener('click', async () => {
            pills.forEach((p) => p.classList.remove('active'));
            pill.classList.add('active');

            const updatedConfig = { ...config, sensitivity: pill.dataset.level };
            await chrome.storage.local.set({ secureflow_config: updatedConfig });

            // Notify service worker
            chrome.runtime.sendMessage({
                action: 'setConfig',
                config: updatedConfig,
            });
        });
    });

    btnDashboard.addEventListener('click', () => {
        chrome.tabs.create({ url: chrome.runtime.getURL('dashboard/dashboard.html') });
    });

    btnOptions.addEventListener('click', () => {
        chrome.runtime.openOptionsPage();
    });

    // ── Helpers ──────────────────────────────────────────────────

    function updateStatusUI(enabled) {
        if (enabled) {
            statusCard.classList.add('active');
            statusCard.classList.remove('disabled');
            statusLabel.textContent = 'Protection Active';
            statusSite.textContent = 'Monitoring LLM interactions';
            pulseDot.style.background = 'var(--accent-green)';
            pulseRing.style.borderColor = 'var(--accent-green)';
            pulseRing.style.animationPlayState = 'running';
        } else {
            statusCard.classList.remove('active');
            statusCard.classList.add('disabled');
            statusLabel.textContent = 'Protection Disabled';
            statusSite.textContent = 'Click toggle to enable';
            pulseDot.style.background = 'var(--text-muted)';
            pulseRing.style.borderColor = 'var(--text-muted)';
            pulseRing.style.animationPlayState = 'paused';
        }
    }
});

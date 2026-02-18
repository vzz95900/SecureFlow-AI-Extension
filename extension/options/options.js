/**
 * SecureFlow AI — Options Page Logic
 */
'use strict';

document.addEventListener('DOMContentLoaded', async () => {
    const backendUrl = document.getElementById('backend-url');
    const apiKey = document.getElementById('api-key');
    const toggleKeyBtn = document.getElementById('toggle-key-visibility');
    const sensitivity = document.getElementById('sensitivity');
    const autoMode = document.getElementById('auto-mode');
    const auditLog = document.getElementById('audit-log');
    const form = document.getElementById('settings-form');
    const saveStatus = document.getElementById('save-status');
    const btnTest = document.getElementById('btn-test-connection');
    const connStatus = document.getElementById('connection-status');
    const btnClear = document.getElementById('btn-clear-data');

    // ── Load existing config ─────────────────────────────────────
    const stored = await chrome.storage.local.get(['secureflow_config', 'secureflow_options']);
    const config = stored.secureflow_config || {};
    const options = stored.secureflow_options || {};

    backendUrl.value = config.backendUrl || 'http://localhost:8000';
    apiKey.value = config.apiKey || '';
    sensitivity.value = config.sensitivity || 'high';
    autoMode.checked = options.autoMode !== false;
    auditLog.checked = options.auditLog !== false;

    // Site toggles
    const siteToggles = document.querySelectorAll('[data-site]');
    const enabledSites = options.enabledSites || { chatgpt: true, claude: true, gemini: true };
    siteToggles.forEach((toggle) => {
        toggle.checked = enabledSites[toggle.dataset.site] !== false;
    });

    // ── Toggle API key visibility ────────────────────────────────
    toggleKeyBtn.addEventListener('click', () => {
        apiKey.type = apiKey.type === 'password' ? 'text' : 'password';
    });

    // ── Test Connection ──────────────────────────────────────────
    btnTest.addEventListener('click', async () => {
        connStatus.textContent = 'Testing…';
        connStatus.className = 'connection-status';

        try {
            const url = backendUrl.value.replace(/\/+$/, '');
            const res = await fetch(`${url}/api/v1/health`, {
                method: 'GET',
                headers: config.apiKey ? { 'X-API-Key': apiKey.value } : {},
            });

            if (res.ok) {
                connStatus.textContent = '✅ Connected';
                connStatus.className = 'connection-status success';
            } else {
                connStatus.textContent = `❌ Error ${res.status}`;
                connStatus.className = 'connection-status error';
            }
        } catch (err) {
            connStatus.textContent = '❌ Cannot reach server';
            connStatus.className = 'connection-status error';
        }
    });

    // ── Save ─────────────────────────────────────────────────────
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const updatedConfig = {
            backendUrl: backendUrl.value.replace(/\/+$/, ''),
            apiKey: apiKey.value,
            sensitivity: sensitivity.value,
        };

        const sites = {};
        siteToggles.forEach((toggle) => {
            sites[toggle.dataset.site] = toggle.checked;
        });

        const updatedOptions = {
            autoMode: autoMode.checked,
            auditLog: auditLog.checked,
            enabledSites: sites,
        };

        await chrome.storage.local.set({
            secureflow_config: updatedConfig,
            secureflow_options: updatedOptions,
        });

        // Notify service worker
        chrome.runtime.sendMessage({ action: 'setConfig', config: updatedConfig });

        saveStatus.textContent = '✅ Saved';
        setTimeout(() => { saveStatus.textContent = ''; }, 2000);
    });

    // ── Clear Data ───────────────────────────────────────────────
    btnClear.addEventListener('click', async () => {
        if (!confirm('This will permanently delete all stored sessions and statistics. Continue?')) return;

        await chrome.storage.local.remove(['secureflow_stats']);
        alert('All data cleared.');
    });
});

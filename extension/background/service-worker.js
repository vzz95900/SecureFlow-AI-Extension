/**
 * SecureFlow AI — Service Worker (Background Script)
 * Handles communication between content scripts and the backend API.
 * Routes sanitization and restoration requests.
 */

'use strict';

// ── Configuration ────────────────────────────────────────────────
const DEFAULT_CONFIG = {
    backendUrl: 'http://localhost:8000',
    apiKey: '',
    sensitivity: 'high',
};

let config = { ...DEFAULT_CONFIG };

// ── Load config from storage on startup ──────────────────────────
chrome.storage.local.get(['secureflow_config'], (result) => {
    if (result.secureflow_config) {
        config = { ...DEFAULT_CONFIG, ...result.secureflow_config };
    }
});

// Watch for config changes
chrome.storage.onChanged.addListener((changes) => {
    if (changes.secureflow_config) {
        config = { ...DEFAULT_CONFIG, ...changes.secureflow_config.newValue };
    }
});

// ── Message Handler ──────────────────────────────────────────────
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    const { action } = message;

    switch (action) {
        case 'sanitize':
            handleSanitize(message).then(sendResponse).catch((err) => {
                sendResponse({ success: false, error: err.message });
            });
            return true; // async response

        case 'sanitizeFile':
            handleSanitizeFile(message).then(sendResponse).catch((err) => {
                sendResponse({ success: false, error: err.message });
            });
            return true;

        case 'restore':
            handleRestore(message).then(sendResponse).catch((err) => {
                sendResponse({ success: false, error: err.message });
            });
            return true;

        case 'updateBadge':
            updateBadge(message.count);
            sendResponse({ success: true });
            return false;

        case 'getStats':
            getSessionStats().then(sendResponse);
            return true;

        case 'getConfig':
            sendResponse({ success: true, config });
            return false;

        case 'setConfig':
            config = { ...DEFAULT_CONFIG, ...message.config };
            chrome.storage.local.set({ secureflow_config: config });
            sendResponse({ success: true });
            return false;

        default:
            sendResponse({ success: false, error: `Unknown action: ${action}` });
            return false;
    }
});

// ── API Calls ────────────────────────────────────────────────────

async function handleSanitize({ text, sessionId, redactionMode }) {
    try {
        const response = await fetch(`${config.backendUrl}/api/v1/sanitize`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(config.apiKey ? { 'X-API-Key': config.apiKey } : {}),
            },
            body: JSON.stringify({
                text,
                session_id: sessionId || undefined,
                sensitivity: config.sensitivity,
                redaction_mode: redactionMode || 'xxx',
            }),
        });

        if (!response.ok) {
            const error = await response.text();
            throw new Error(`Backend error (${response.status}): ${error}`);
        }

        const data = await response.json();

        // Store stats
        await updateSessionStats(data);

        return {
            success: true,
            sanitizedText: data.sanitized_text,
            sessionId: data.session_id,
            entitiesFound: data.entities_found,
            riskLevel: data.risk_level,
            entitySummary: data.entity_summary || [],
        };
    } catch (err) {
        console.error('[SecureFlow SW] Sanitize error:', err);
        return { success: false, error: err.message };
    }
}

async function handleSanitizeFile({ fileBase64, fileName, fileType, sessionId }) {
    try {
        // Convert base64 back to binary
        const binaryString = atob(fileBase64);
        const bytes = new Uint8Array(binaryString.length);
        for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }
        const blob = new Blob([bytes], { type: fileType });

        // Build multipart form data
        const formData = new FormData();
        formData.append('file', blob, fileName);
        formData.append('sensitivity', config.sensitivity);
        formData.append('redaction_mode', 'xxx');
        if (sessionId) {
            formData.append('session_id', sessionId);
        }

        const headers = {};
        if (config.apiKey) {
            headers['X-API-Key'] = config.apiKey;
        }

        const response = await fetch(`${config.backendUrl}/api/v1/sanitize-file`, {
            method: 'POST',
            headers,
            body: formData,
        });

        if (!response.ok) {
            const error = await response.text();
            throw new Error(`Backend error (${response.status}): ${error}`);
        }

        const data = await response.json();

        await updateSessionStats(data);

        return {
            success: true,
            sanitizedText: data.sanitized_text,
            sessionId: data.session_id,
            entitiesFound: data.entities_found,
            riskLevel: data.risk_level,
            entitySummary: data.entity_summary || [],
            entityDetails: data.entity_details || [],
            fileType: data.file_type,
            originalText: data.original_text,
        };
    } catch (err) {
        console.error('[SecureFlow SW] File sanitize error:', err);
        return { success: false, error: err.message };
    }
}

async function handleRestore({ text, sessionId }) {
    try {
        const response = await fetch(`${config.backendUrl}/api/v1/restore`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(config.apiKey ? { 'X-API-Key': config.apiKey } : {}),
            },
            body: JSON.stringify({
                text,
                session_id: sessionId,
            }),
        });

        if (!response.ok) {
            const error = await response.text();
            throw new Error(`Backend error (${response.status}): ${error}`);
        }

        const data = await response.json();

        return {
            success: true,
            restoredText: data.restored_text,
        };
    } catch (err) {
        console.error('[SecureFlow SW] Restore error:', err);
        return { success: false, error: err.message };
    }
}

// ── Badge ────────────────────────────────────────────────────────

function updateBadge(count) {
    const text = count > 0 ? String(count) : '';
    chrome.action.setBadgeText({ text });
    chrome.action.setBadgeBackgroundColor({
        color: count > 0 ? '#ef4444' : '#6b7280',
    });
}

// ── Session Stats ────────────────────────────────────────────────

async function updateSessionStats(sanitizeResult) {
    const stored = await chrome.storage.local.get(['secureflow_stats']);
    const stats = stored.secureflow_stats || {
        totalPrompts: 0,
        totalEntities: 0,
        sessions: [],
    };

    stats.totalPrompts += 1;
    stats.totalEntities += sanitizeResult.entities_found || 0;

    // Keep last 100 session records
    stats.sessions.unshift({
        timestamp: new Date().toISOString(),
        sessionId: sanitizeResult.session_id,
        entitiesFound: sanitizeResult.entities_found,
        riskLevel: sanitizeResult.risk_level,
        entitySummary: sanitizeResult.entity_summary,
    });
    if (stats.sessions.length > 100) {
        stats.sessions = stats.sessions.slice(0, 100);
    }

    await chrome.storage.local.set({ secureflow_stats: stats });
}

async function getSessionStats() {
    const stored = await chrome.storage.local.get(['secureflow_stats']);
    return {
        success: true,
        stats: stored.secureflow_stats || {
            totalPrompts: 0,
            totalEntities: 0,
            sessions: [],
        },
    };
}

// ── Install / Update ─────────────────────────────────────────────

chrome.runtime.onInstalled.addListener((details) => {
    if (details.reason === 'install') {
        // Set defaults
        chrome.storage.local.set({
            secureflow_enabled: true,
            secureflow_config: DEFAULT_CONFIG,
            secureflow_stats: {
                totalPrompts: 0,
                totalEntities: 0,
                sessions: [],
            },
        });

        console.log('[SecureFlow] Extension installed successfully.');
    }
});

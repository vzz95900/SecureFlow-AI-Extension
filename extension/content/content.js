/**
 * SecureFlow AI — Content Script
 * Injected into supported LLM pages (ChatGPT, Claude, Gemini, Copilot,
 * Perplexity, DeepSeek, HuggingChat).
 *
 * ▸ Intercepts user prompts before submission
 * ▸ Intercepts file uploads (drag-drop / file input)
 * ▸ Sends data to the service worker for sanitization (XXX masking)
 * ▸ Warns the user when PII is detected
 */

(() => {
    'use strict';

    // ── State ──────────────────────────────────────────────────────
    let isEnabled = true;
    let sessionStats = { entitiesRedacted: 0, promptsProcessed: 0 };
    let currentSessionId = null;

    // ── Site Configurations ────────────────────────────────────────
    const SITE_CONFIG = {
        'chat.openai.com': {
            inputSelector: '#prompt-textarea, textarea[data-id="root"]',
            submitSelector: 'button[data-testid="send-button"], form button[class*="bottom"]',
            responseSelector: '[data-message-author-role="assistant"]',
            fileInputSelector: 'input[type="file"]',
            dropZoneSelector: '#prompt-textarea, main',
            name: 'ChatGPT',
        },
        'chatgpt.com': {
            inputSelector: '#prompt-textarea, textarea[data-id="root"]',
            submitSelector: 'button[data-testid="send-button"], form button[class*="bottom"]',
            responseSelector: '[data-message-author-role="assistant"]',
            fileInputSelector: 'input[type="file"]',
            dropZoneSelector: '#prompt-textarea, main',
            name: 'ChatGPT',
        },
        'claude.ai': {
            inputSelector: '[contenteditable="true"].ProseMirror, div[contenteditable="true"]',
            submitSelector: 'button[aria-label="Send Message"], button[class*="send"]',
            responseSelector: '[data-is-streaming], .font-claude-message',
            fileInputSelector: 'input[type="file"]',
            dropZoneSelector: '[contenteditable="true"], main',
            name: 'Claude',
        },
        'gemini.google.com': {
            inputSelector: '.ql-editor, rich-textarea .textarea, div[contenteditable="true"]',
            submitSelector: 'button[aria-label="Send message"], .send-button',
            responseSelector: '.model-response-text, .response-content',
            fileInputSelector: 'input[type="file"]',
            dropZoneSelector: '.ql-editor, main',
            name: 'Gemini',
        },
        'copilot.microsoft.com': {
            inputSelector: 'textarea#searchbox, textarea[name="searchbox"], #userInput',
            submitSelector: 'button[aria-label="Submit"], button[type="submit"]',
            responseSelector: '.ac-container, [data-content="ai-message"]',
            fileInputSelector: 'input[type="file"]',
            dropZoneSelector: 'textarea, main',
            name: 'Copilot',
        },
        'www.perplexity.ai': {
            inputSelector: 'textarea[placeholder*="Ask"], textarea',
            submitSelector: 'button[aria-label="Submit"], button[type="submit"]',
            responseSelector: '.prose, [data-testid="answer-content"]',
            fileInputSelector: 'input[type="file"]',
            dropZoneSelector: 'textarea, main',
            name: 'Perplexity',
        },
        'chat.deepseek.com': {
            inputSelector: 'textarea#chat-input, textarea',
            submitSelector: 'button[class*="send"], button[aria-label*="send"]',
            responseSelector: '.markdown-body, [class*="message-content"]',
            fileInputSelector: 'input[type="file"]',
            dropZoneSelector: 'textarea, main',
            name: 'DeepSeek',
        },
        'huggingface.co': {
            inputSelector: 'textarea[placeholder*="message"], textarea',
            submitSelector: 'button[type="submit"], button[class*="send"]',
            responseSelector: '.prose, [class*="assistant"]',
            fileInputSelector: 'input[type="file"]',
            dropZoneSelector: 'textarea, main',
            name: 'HuggingChat',
        },
    };

    // ── Helpers ────────────────────────────────────────────────────

    function getSiteConfig() {
        const host = window.location.hostname;
        return SITE_CONFIG[host] || null;
    }

    function getInputText(inputEl) {
        if (!inputEl) return '';
        if (inputEl.tagName === 'TEXTAREA' || inputEl.tagName === 'INPUT') {
            return inputEl.value;
        }
        return inputEl.innerText || inputEl.textContent || '';
    }

    function setInputText(inputEl, text) {
        if (!inputEl) return;
        if (inputEl.tagName === 'TEXTAREA' || inputEl.tagName === 'INPUT') {
            const nativeSetter = Object.getOwnPropertyDescriptor(
                window.HTMLTextAreaElement.prototype, 'value'
            )?.set || Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value'
            )?.set;
            if (nativeSetter) {
                nativeSetter.call(inputEl, text);
            } else {
                inputEl.value = text;
            }
            inputEl.dispatchEvent(new Event('input', { bubbles: true }));
        } else {
            // contenteditable
            inputEl.innerText = text;
            inputEl.dispatchEvent(new Event('input', { bubbles: true }));
        }
    }

    // ── Communication with Service Worker ──────────────────────────

    async function sendToServiceWorker(action, data) {
        return new Promise((resolve, reject) => {
            chrome.runtime.sendMessage({ action, ...data }, (response) => {
                if (chrome.runtime.lastError) {
                    reject(new Error(chrome.runtime.lastError.message));
                    return;
                }
                resolve(response);
            });
        });
    }

    async function sanitizeText(text) {
        try {
            const response = await sendToServiceWorker('sanitize', {
                text,
                sessionId: currentSessionId,
                redactionMode: 'xxx',
            });
            if (response && response.success) {
                currentSessionId = response.sessionId;
                sessionStats.entitiesRedacted += response.entitiesFound || 0;
                sessionStats.promptsProcessed += 1;
                updateBadge();
                return response;
            }
            console.warn('[SecureFlow] Sanitization failed, sending original text.');
            return null;
        } catch (err) {
            console.error('[SecureFlow] Error during sanitization:', err);
            return null;
        }
    }

    async function sanitizeFile(file) {
        try {
            const base64 = await fileToBase64(file);
            const response = await sendToServiceWorker('sanitizeFile', {
                fileBase64: base64,
                fileName: file.name,
                fileType: file.type,
                sessionId: currentSessionId,
            });
            if (response && response.success) {
                currentSessionId = response.sessionId;
                return response;
            }
            console.warn('[SecureFlow] File sanitization failed.');
            return null;
        } catch (err) {
            console.error('[SecureFlow] Error during file sanitization:', err);
            return null;
        }
    }

    function fileToBase64(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => {
                // result is "data:<mime>;base64,<data>" — extract only the data
                const base64 = reader.result.split(',')[1];
                resolve(base64);
            };
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
    }

    async function restoreText(text, sessionId) {
        try {
            const response = await sendToServiceWorker('restore', {
                text,
                sessionId,
            });
            return response?.success ? response.restoredText : text;
        } catch (err) {
            console.error('[SecureFlow] Error during restoration:', err);
            return text;
        }
    }

    function updateBadge() {
        sendToServiceWorker('updateBadge', {
            count: sessionStats.entitiesRedacted,
        }).catch(() => { });
    }

    // ── Prompt Interception ────────────────────────────────────────

    let _isSanitizing = false;  // bypass flag to prevent re-interception

    function interceptSubmit(config) {
        // Use a MutationObserver to detect dynamically loaded submit buttons
        const observer = new MutationObserver(() => {
            const submitBtn = document.querySelector(config.submitSelector);
            if (submitBtn && !submitBtn.__secureflow_hooked) {
                submitBtn.__secureflow_hooked = true;
                submitBtn.addEventListener('click', handleSubmit, true);
            }
        });

        observer.observe(document.body, { childList: true, subtree: true });

        // Also hook into Enter key on the input
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
                const inputEl = document.querySelector(config.inputSelector);
                if (inputEl && document.activeElement === inputEl) {
                    handleSubmit(event);
                }
            }
        }, true);

        async function handleSubmit(event) {
            // Skip if disabled or if this is the re-triggered submit after sanitization
            if (!isEnabled || _isSanitizing) return;

            const inputEl = document.querySelector(config.inputSelector);
            const rawText = getInputText(inputEl);

            if (!rawText || rawText.trim().length === 0) return;

            // Prevent the original submit
            event.preventDefault();
            event.stopImmediatePropagation();

            // Show sanitizing indicator
            showNotification('🔒 Scanning for sensitive data…', 'info');

            const result = await sanitizeText(rawText);

            if (result && result.sanitizedText) {
                setInputText(inputEl, result.sanitizedText);

                if (result.entitiesFound > 0) {
                    showNotification(
                        `🛡️ ${result.entitiesFound} sensitive item(s) replaced with XXX — Risk: ${result.riskLevel}`,
                        'warning'
                    );
                } else {
                    showNotification('✅ No sensitive data detected — safe to send', 'success');
                }
            }

            // Set bypass flag so the re-triggered submit passes through
            _isSanitizing = true;

            // Re-trigger the submit after a short delay
            setTimeout(() => {
                const submitBtn = document.querySelector(config.submitSelector);
                if (submitBtn) {
                    submitBtn.click();
                } else {
                    // Simulate Enter key
                    inputEl?.dispatchEvent(
                        new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })
                    );
                }
                // Reset bypass flag after submission completes
                setTimeout(() => { _isSanitizing = false; }, 200);
            }, 100);
        }
    }

    // ── File Upload Interception ──────────────────────────────────

    function interceptFileUploads(config) {
        // 1. Hook <input type="file"> clicks
        const fileInputObserver = new MutationObserver(() => {
            const fileInputs = document.querySelectorAll(
                config.fileInputSelector || 'input[type="file"]'
            );
            fileInputs.forEach((input) => {
                if (input.__secureflow_file_hooked) return;
                input.__secureflow_file_hooked = true;

                input.addEventListener('change', async (event) => {
                    if (!isEnabled) return;
                    const files = event.target.files;
                    if (!files || files.length === 0) return;

                    for (const file of files) {
                        await scanAndWarnFile(file);
                    }
                });
            });
        });

        fileInputObserver.observe(document.body, { childList: true, subtree: true });

        // 2. Hook drag-and-drop on the chat area
        const dropZones = config.dropZoneSelector || 'main';

        document.addEventListener('drop', async (event) => {
            if (!isEnabled) return;
            const target = event.target;
            if (!target.closest?.(dropZones)) return;

            const files = event.dataTransfer?.files;
            if (!files || files.length === 0) return;

            for (const file of files) {
                await scanAndWarnFile(file);
            }
        }, true);

        // 3. Also intercept paste events (users paste images / files)
        document.addEventListener('paste', async (event) => {
            if (!isEnabled) return;

            const items = event.clipboardData?.items;
            if (!items) return;

            for (const item of items) {
                if (item.kind === 'file') {
                    const file = item.getAsFile();
                    if (file) {
                        await scanAndWarnFile(file);
                    }
                }
            }
        }, true);
    }

    async function scanAndWarnFile(file) {
        // ── Expanded supported types ────────────────────────────────
        const supportedMimeTypes = [
            'application/pdf',
            'image/png', 'image/jpeg', 'image/jpg',
            'image/webp', 'image/bmp', 'image/tiff',
            'text/plain', 'text/csv', 'text/markdown', 'text/rtf',
            'text/html', 'text/xml',
            'application/json', 'application/xml', 'application/rtf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        ];
        const supportedExtensions = [
            '.txt', '.csv', '.md', '.rtf', '.log', '.json', '.xml',
            '.html', '.htm', '.yaml', '.yml', '.ini', '.cfg', '.conf',
            '.pdf', '.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff',
            '.docx',
        ];

        const ext = (file.name || '').toLowerCase().split('.').pop();
        const matchesMime = supportedMimeTypes.includes(file.type);
        const matchesExt = supportedExtensions.includes('.' + ext);

        if (!matchesMime && !matchesExt) {
            // Not a scannable file type — skip silently
            return;
        }

        showNotification(`🔍 Scanning "${file.name}" for sensitive data…`, 'info');

        const result = await sanitizeFile(file);

        if (!result) {
            showNotification(`⚠️ Could not scan "${file.name}" — backend unavailable`, 'error');
            return;
        }

        if (result.entitiesFound > 0) {
            // Show detailed warning modal with all detected PII
            showPIIWarningModal(file.name, result);
        } else {
            showNotification(
                `✅ "${file.name}" scanned — no sensitive data found`,
                'success',
            );
        }
    }

    // ── PII Warning Modal ─────────────────────────────────────────

    function showPIIWarningModal(fileName, result) {
        // Remove any existing modal
        const existing = document.getElementById('secureflow-pii-modal');
        if (existing) existing.remove();

        // Group entities by type
        const entityGroups = {};
        const details = result.entityDetails || [];
        for (const entity of details) {
            const type = entity.type || 'UNKNOWN';
            if (!entityGroups[type]) {
                entityGroups[type] = [];
            }
            entityGroups[type].push(entity.text || '***');
        }

        // Build the entity list HTML
        let entityListHTML = '';
        const typeLabels = {
            PERSON: '👤 Person Name',
            EMAIL: '📧 Email Address',
            PHONE: '📱 Phone Number',
            SSN: '🔐 SSN / ID Number',
            AADHAAR: '🆔 Aadhaar Number',
            PAN: '🆔 PAN Card',
            PASSPORT: '🛂 Passport Number',
            CREDIT_CARD: '💳 Credit Card',
            ADDRESS: '📍 Address',
            DATE_OF_BIRTH: '🎂 Date of Birth',
            IP_ADDRESS: '🌐 IP Address',
            BANK_ACCOUNT: '🏦 Bank Account',
            ORGANIZATION: '🏢 Organization',
            GPE: '📍 Location',
            DATE: '📅 Date',
            IFSC: '🏦 IFSC Code',
            UPI_ID: '💸 UPI ID',
            VEHICLE_REG: '🚗 Vehicle Registration',
        };

        for (const [type, values] of Object.entries(entityGroups)) {
            const label = typeLabels[type] || `🔒 ${type}`;
            const maskedValues = values.map(v => {
                // Partially mask the value for display
                if (v.length <= 4) return '***';
                return v.substring(0, 2) + '•'.repeat(Math.min(v.length - 4, 8)) + v.substring(v.length - 2);
            });

            entityListHTML += `
                <div style="margin-bottom:10px;">
                    <div style="font-weight:600;color:#f59e0b;margin-bottom:4px;font-size:13px;">
                        ${label} <span style="color:#94a3b8;font-weight:400;">(${values.length} found)</span>
                    </div>
                    <div style="padding-left:12px;color:#cbd5e1;font-size:12px;line-height:1.6;">
                        ${maskedValues.map(v => `<code style="background:#1e293b;padding:2px 6px;border-radius:4px;font-family:'Courier New',monospace;">${v}</code>`).join(' ')}
                    </div>
                </div>
            `;
        }

        // Create modal overlay
        const overlay = document.createElement('div');
        overlay.id = 'secureflow-pii-modal';
        Object.assign(overlay.style, {
            position: 'fixed',
            top: '0',
            left: '0',
            width: '100vw',
            height: '100vh',
            zIndex: '2147483647',
            background: 'rgba(0,0,0,0.6)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontFamily: "'Inter','Segoe UI',system-ui,sans-serif",
        });

        const riskColors = {
            high: '#ef4444',
            medium: '#f59e0b',
            low: '#10b981',
        };
        const riskColor = riskColors[result.riskLevel] || '#f59e0b';

        overlay.innerHTML = `
            <div style="
                background: #0f172a;
                border: 1px solid #334155;
                border-radius: 16px;
                padding: 28px 32px;
                max-width: 480px;
                width: 90%;
                max-height: 80vh;
                overflow-y: auto;
                box-shadow: 0 24px 48px rgba(0,0,0,0.5);
                color: #f1f5f9;
            ">
                <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;">
                    <div style="
                        width:44px;height:44px;border-radius:12px;
                        background:linear-gradient(135deg,#f59e0b,#ef4444);
                        display:flex;align-items:center;justify-content:center;
                        font-size:22px;flex-shrink:0;
                    ">⚠️</div>
                    <div>
                        <div style="font-size:17px;font-weight:700;">Sensitive Data Detected</div>
                        <div style="font-size:12px;color:#94a3b8;margin-top:2px;">
                            File: <strong style="color:#e2e8f0;">${fileName}</strong>
                        </div>
                    </div>
                </div>

                <div style="
                    background:#1e293b;border-radius:10px;padding:14px 16px;
                    margin-bottom:16px;display:flex;gap:16px;
                ">
                    <div style="text-align:center;flex:1;">
                        <div style="font-size:22px;font-weight:700;color:${riskColor};">${result.entitiesFound}</div>
                        <div style="font-size:11px;color:#94a3b8;">Items Found</div>
                    </div>
                    <div style="width:1px;background:#334155;"></div>
                    <div style="text-align:center;flex:1;">
                        <div style="font-size:22px;font-weight:700;color:${riskColor};">${result.riskLevel?.toUpperCase() || 'UNKNOWN'}</div>
                        <div style="font-size:11px;color:#94a3b8;">Risk Level</div>
                    </div>
                </div>

                <div style="margin-bottom:16px;font-size:13px;color:#e2e8f0;line-height:1.5;">
                    Your document contains the following sensitive information.<br>
                    <strong style="color:#f59e0b;">Please remove them before sharing with AI.</strong>
                </div>

                <div style="
                    background:#1e293b;border-radius:10px;padding:14px 16px;
                    margin-bottom:20px;max-height:250px;overflow-y:auto;
                    border:1px solid #334155;
                ">
                    ${entityListHTML}
                </div>

                <div style="display:flex;gap:10px;">
                    <button id="secureflow-modal-dismiss" style="
                        flex:1;padding:10px;border:1px solid #334155;
                        background:#1e293b;color:#e2e8f0;border-radius:8px;
                        font-weight:600;cursor:pointer;font-size:13px;
                        transition:background 0.2s;
                    ">I Understand the Risk</button>
                    <button id="secureflow-modal-close" style="
                        flex:1;padding:10px;border:none;
                        background:linear-gradient(135deg,#f59e0b,#ef4444);
                        color:#fff;border-radius:8px;
                        font-weight:600;cursor:pointer;font-size:13px;
                        transition:opacity 0.2s;
                    ">Remove & Re-upload</button>
                </div>
            </div>
        `;

        document.body.appendChild(overlay);

        // Close on "I Understand the Risk" — just dismiss the modal
        document.getElementById('secureflow-modal-dismiss')?.addEventListener('click', () => {
            overlay.style.opacity = '0';
            setTimeout(() => overlay.remove(), 200);
        });

        // Close on "Remove & Re-upload" — dismiss and show info toast
        document.getElementById('secureflow-modal-close')?.addEventListener('click', () => {
            overlay.style.opacity = '0';
            setTimeout(() => overlay.remove(), 200);
            showNotification(
                '📝 Please edit your file to remove the sensitive data listed above, then re-upload.',
                'info',
                5000,
            );
        });

        // Also close on overlay background click
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                overlay.style.opacity = '0';
                setTimeout(() => overlay.remove(), 200);
            }
        });
    }

    // ── Response Monitoring & Restoration ──────────────────────────

    function watchResponses(config) {
        if (!config.responseSelector) return;

        const observer = new MutationObserver(async (mutations) => {
            if (!isEnabled || !currentSessionId) return;

            for (const mutation of mutations) {
                for (const node of mutation.addedNodes) {
                    if (node.nodeType !== Node.ELEMENT_NODE) continue;

                    const responseEls = node.matches?.(config.responseSelector)
                        ? [node]
                        : Array.from(node.querySelectorAll?.(config.responseSelector) || []);

                    for (const el of responseEls) {
                        // Wait for streaming to finish
                        await waitForStable(el);

                        const responseText = el.innerText || el.textContent;
                        if (responseText && responseText.includes('[REDACTED_')) {
                            const restored = await restoreText(responseText, currentSessionId);
                            if (restored !== responseText) {
                                el.innerText = restored;
                            }
                        }
                    }
                }
            }
        });

        observer.observe(document.body, { childList: true, subtree: true });
    }

    function waitForStable(element, timeout = 5000) {
        return new Promise((resolve) => {
            let timer;
            let lastText = element.innerText;

            const check = () => {
                const currentText = element.innerText;
                if (currentText === lastText) {
                    resolve();
                    return;
                }
                lastText = currentText;
                timer = setTimeout(check, 500);
            };

            timer = setTimeout(check, 500);
            setTimeout(() => {
                clearTimeout(timer);
                resolve();
            }, timeout);
        });
    }

    // ── UI Notification Toast ──────────────────────────────────────

    function showNotification(message, type = 'info', duration = 3000) {
        // Remove existing notification
        const existing = document.getElementById('secureflow-toast');
        if (existing) existing.remove();

        const toast = document.createElement('div');
        toast.id = 'secureflow-toast';
        toast.textContent = message;

        const colors = {
            info: { bg: '#1e293b', border: '#3b82f6' },
            success: { bg: '#022c22', border: '#10b981' },
            warning: { bg: '#431407', border: '#f59e0b' },
            error: { bg: '#450a0a', border: '#ef4444' },
        };
        const c = colors[type] || colors.info;

        Object.assign(toast.style, {
            position: 'fixed',
            bottom: '20px',
            right: '20px',
            zIndex: '2147483647',
            padding: '12px 20px',
            borderRadius: '10px',
            background: c.bg,
            border: `1px solid ${c.border}`,
            color: '#f1f5f9',
            fontFamily: "'Inter', 'Segoe UI', system-ui, sans-serif",
            fontSize: '13px',
            fontWeight: '500',
            boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
            backdropFilter: 'blur(8px)',
            transition: 'opacity 0.3s ease, transform 0.3s ease',
            opacity: '0',
            transform: 'translateY(10px)',
            maxWidth: '380px',
            lineHeight: '1.4',
        });

        document.body.appendChild(toast);

        // Animate in
        requestAnimationFrame(() => {
            toast.style.opacity = '1';
            toast.style.transform = 'translateY(0)';
        });

        // Auto-remove
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(10px)';
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }

    // ── Initialization ─────────────────────────────────────────────

    async function init() {
        const config = getSiteConfig();
        if (!config) {
            console.log('[SecureFlow] Unsupported site, content script inactive.');
            return;
        }

        // Load enabled state from storage
        const stored = await chrome.storage.local.get(['secureflow_enabled']);
        isEnabled = stored.secureflow_enabled !== false; // default to true

        // Listen for toggle changes
        chrome.storage.onChanged.addListener((changes) => {
            if (changes.secureflow_enabled) {
                isEnabled = changes.secureflow_enabled.newValue;
                showNotification(
                    isEnabled ? '🛡️ SecureFlow AI enabled' : '⚠️ SecureFlow AI disabled',
                    isEnabled ? 'success' : 'warning'
                );
            }
        });

        console.log(`[SecureFlow] Active on ${config.name} — protection ${isEnabled ? 'ON' : 'OFF'}`);
        showNotification(`🛡️ SecureFlow AI active on ${config.name}`, 'success');

        interceptSubmit(config);
        interceptFileUploads(config);
        watchResponses(config);
    }

    // Wait for page to be ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();

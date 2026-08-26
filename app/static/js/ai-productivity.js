/**
 * Society SaaS - AI Automation & Quick Productivity Suite (v2.0)
 * Integrates:
 * 1. Duplicate Submission Guard (frontend double-click guard + idempotency token)
 * 2. Keyboard Productivity & Navigation Shortcuts (Ctrl+K, G+D, G+R, G+N, G+B, G+C, ?, /)
 * 3. Smart Table Experience (Persistent filters, column visibility, compact mode)
 * 4. Smart Contextual Help Modal & AI Page Assistant
 * 5. 'What Changed?' History Diff Viewer
 * 6. Safe Bulk Action Guard Modal
 * 7. Record Change Preview (Before vs. After Diff)
 * 8. Smart Navigation & Aggregate Feature Telemetry
 */

'use strict';

// --------------------------------------------------------------------------
// 1. Duplicate Submission Guard
// --------------------------------------------------------------------------
(function initDuplicateSubmissionGuard() {
    document.addEventListener('submit', function (e) {
        const form = e.target;
        if (!form || form.getAttribute('data-no-guard')) return;

        const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
        if (submitBtn && !submitBtn.disabled) {
            // Check if already submitting
            if (form.getAttribute('data-submitting') === 'true') {
                e.preventDefault();
                return;
            }

            form.setAttribute('data-submitting', 'true');
            const originalHTML = submitBtn.innerHTML || submitBtn.value;
            submitBtn.setAttribute('data-orig-text', originalHTML);
            submitBtn.disabled = true;

            if (submitBtn.tagName === 'BUTTON') {
                submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Processing...';
            }

            // Generate unique submission token
            const submissionToken = 'sub_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            let tokenInput = form.querySelector('input[name="_submission_id"]');
            if (!tokenInput) {
                tokenInput = document.createElement('input');
                tokenInput.type = 'hidden';
                tokenInput.name = '_submission_id';
                form.appendChild(tokenInput);
            }
            tokenInput.value = submissionToken;

            // Re-enable safety timeout after 5 seconds in case submission was aborted
            setTimeout(() => {
                form.removeAttribute('data-submitting');
                if (submitBtn) {
                    submitBtn.disabled = false;
                    const orig = submitBtn.getAttribute('data-orig-text');
                    if (orig) submitBtn.innerHTML = orig;
                }
            }, 5000);
        }
    }, true);
})();


// --------------------------------------------------------------------------
// 2. Keyboard Productivity & Navigation Shortcuts
// --------------------------------------------------------------------------
(function initKeyboardShortcuts() {
    let pendingGKey = false;
    let gKeyTimeout = null;

    document.addEventListener('keydown', function (e) {
        const activeTag = document.activeElement ? document.activeElement.tagName : '';
        const isEditing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(activeTag) || (document.activeElement && document.activeElement.isContentEditable);

        // Escape: close open productivity modals
        if (e.key === 'Escape') {
            closeContextualHelpModal();
            closeWhatChangedModal();
            closeShortcutsModal();
            return;
        }

        // If user is typing in an input, do not trigger single-key navigation shortcuts
        if (isEditing) return;

        // / : Focus global search
        if (e.key === '/' && !e.ctrlKey && !e.metaKey) {
            e.preventDefault();
            const searchTrigger = document.getElementById('global-search-trigger');
            if (searchTrigger) searchTrigger.click();
            return;
        }

        // ? : Show keyboard shortcuts cheat sheet
        if (e.key === '?' || (e.shiftKey && e.key === '/')) {
            e.preventDefault();
            window.showKeyboardShortcutsHelp();
            return;
        }

        // Two-key chord navigation: G then <Key>
        if (e.key.toLowerCase() === 'g' && !pendingGKey) {
            pendingGKey = true;
            clearTimeout(gKeyTimeout);
            gKeyTimeout = setTimeout(() => { pendingGKey = false; }, 1200);
            return;
        }

        if (pendingGKey) {
            pendingGKey = false;
            clearTimeout(gKeyTimeout);
            const key = e.key.toLowerCase();

            const routes = {
                'd': '/dashboard',
                'r': '/admin/residents',
                'n': '/resident/notifications',
                'b': '/payments/bills',
                'c': '/complaints/',
                'q': '/admin/data-quality',
                'h': '/admin/app-health',
                'w': '/admin/work-queue',
                'p': '/resident/profile',
            };

            if (routes[key]) {
                e.preventDefault();
                window.location.href = routes[key];
            }
        }
    });
})();

// --------------------------------------------------------------------------
// 3. Smart Table Experience
// --------------------------------------------------------------------------
class SmartTableManager {
    static init() {
        document.querySelectorAll('table.data-table').forEach((table, idx) => {
            const tableId = table.id || `smart_table_${idx}`;
            this.restoreFilters(table, tableId);
            this.attachFilterListeners(table, tableId);
            this.addCompactModeToggle(table);
        });
    }

    static attachFilterListeners(table, tableId) {
        const container = table.closest('.card') || table.parentElement;
        if (!container) return;

        container.querySelectorAll('input[type="search"], select').forEach(input => {
            input.addEventListener('change', () => {
                const state = JSON.parse(localStorage.getItem(`table_filters_${tableId}`) || '{}');
                state[input.name || input.id] = input.value;
                localStorage.setItem(`table_filters_${tableId}`, JSON.stringify(state));
            });
        });
    }

    static restoreFilters(table, tableId) {
        const saved = JSON.parse(localStorage.getItem(`table_filters_${tableId}`) || '{}');
        const container = table.closest('.card') || table.parentElement;
        if (!container) return;

        Object.entries(saved).forEach(([k, v]) => {
            const input = container.querySelector(`[name="${k}"], #${k}`);
            if (input && v && !input.value) {
                input.value = v;
                input.dispatchEvent(new Event('change'));
            }
        });
    }

    static addCompactModeToggle(table) {
        const header = table.closest('.card')?.querySelector('h2, .card-header');
        if (!header || header.querySelector('.btn-compact-toggle')) return;

        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'btn btn-xs btn-outline btn-compact-toggle';
        btn.style.marginLeft = 'auto';
        btn.style.fontSize = '11px';
        btn.innerHTML = '<i class="fa-solid fa-table-cells"></i> Compact';

        const isCompact = localStorage.getItem('table_compact_mode') === 'true';
        if (isCompact) table.classList.add('table-compact');

        btn.addEventListener('click', () => {
            table.classList.toggle('table-compact');
            const nowCompact = table.classList.contains('table-compact');
            localStorage.setItem('table_compact_mode', nowCompact);
            btn.innerHTML = nowCompact ? '<i class="fa-solid fa-table-list"></i> Normal' : '<i class="fa-solid fa-table-cells"></i> Compact';
        });

        header.style.display = 'flex';
        header.style.alignItems = 'center';
        header.appendChild(btn);
    }
}


// --------------------------------------------------------------------------
// 4. Smart Contextual Help Modal
// --------------------------------------------------------------------------
window.openContextualHelp = async function (pageKey = 'admin_dashboard') {
    let modal = document.getElementById('contextual-help-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'contextual-help-modal';
        modal.className = 'confirm-modal-backdrop';
        modal.setAttribute('role', 'dialog');
        modal.setAttribute('aria-modal', 'true');
        modal.innerHTML = `
            <div class="confirm-modal-box" style="max-width: 620px; width: 90%;">
                <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-color); padding-bottom: 14px; margin-bottom: 16px;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <i class="fa-solid fa-circle-question" style="color: var(--primary); font-size: 20px;"></i>
                        <h3 id="help-modal-title" style="margin: 0; font-size: 18px; font-weight: 800;">Page Guide</h3>
                    </div>
                    <button type="button" class="toast-close" onclick="closeContextualHelpModal()"><i class="fa-solid fa-xmark"></i></button>
                </div>
                <div id="help-modal-content" style="max-height: 400px; overflow-y: auto; font-size: 14px; line-height: 1.6;">
                    <div style="text-align: center; padding: 20px;"><i class="fa-solid fa-spinner fa-spin"></i> Loading page guide...</div>
                </div>
                <div style="margin-top: 16px; padding-top: 14px; border-top: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center;">
                    <div style="display: flex; gap: 6px; flex: 1; margin-right: 10px;">
                        <input type="text" id="help-ask-input" class="form-control" placeholder="Ask a question about this page..." style="font-size: 13px;">
                        <button type="button" class="btn btn-sm btn-primary" id="help-ask-btn">Ask</button>
                    </div>
                    <button type="button" class="btn btn-secondary btn-sm" onclick="closeContextualHelpModal()">Close</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);

        document.getElementById('help-ask-btn').addEventListener('click', askContextualHelp);
        document.getElementById('help-ask-input').addEventListener('keydown', (e) => {
            if (e.key === 'Enter') askContextualHelp();
        });
    }

    modal.classList.add('open');
    modal.setAttribute('data-page-key', pageKey);

    try {
        const res = await fetch(`/api/v1/ai/contextual-help?page=${encodeURIComponent(pageKey)}`);
        const data = await res.json();
        renderHelpContent(data);
    } catch (err) {
        document.getElementById('help-modal-content').innerHTML = `
            <div style="color: var(--text-secondary); text-align: center; padding: 20px;">
                AI contextual suggestions are temporarily unavailable. The page remains fully operational.
            </div>
        `;
    }
};

function renderHelpContent(data) {
    document.getElementById('help-modal-title').textContent = data.title || 'Page Guidance';
    const content = document.getElementById('help-modal-content');

    let actionsHTML = (data.common_actions || []).map(a => `
        <a href="${a.url}" class="btn btn-xs btn-outline" style="font-size: 12px;">
            <i class="fa-solid ${a.icon || 'fa-arrow-right'}"></i> ${a.label}
        </a>
    `).join(' ');

    let bulletsHTML = (data.what_you_can_do_here || []).map(b => `<li>${b}</li>`).join('');
    let warningsHTML = (data.important_warnings || []).map(w => `<li style="color: #b91c1c;">${w}</li>`).join('');

    content.innerHTML = `
        <div style="margin-bottom: 14px;">
            <strong style="font-size: 13px; text-transform: uppercase; color: var(--text-secondary);">What this page does:</strong>
            <p style="margin: 4px 0 12px 0;">${data.what_this_page_does}</p>
        </div>

        <div style="margin-bottom: 14px;">
            <strong style="font-size: 13px; text-transform: uppercase; color: var(--text-secondary);">What you can do here:</strong>
            <ul style="margin: 4px 0 12px 20px; padding: 0;">${bulletsHTML}</ul>
        </div>

        ${warningsHTML ? `
        <div style="margin-bottom: 14px; background: rgba(239, 68, 68, 0.08); border-left: 3px solid var(--danger); padding: 8px 12px; border-radius: 4px;">
            <strong style="font-size: 12px; text-transform: uppercase; color: var(--danger);">Important Notices:</strong>
            <ul style="margin: 4px 0 0 16px; padding: 0; font-size: 13px;">${warningsHTML}</ul>
        </div>` : ''}

        ${actionsHTML ? `
        <div>
            <strong style="font-size: 13px; text-transform: uppercase; color: var(--text-secondary);">Common Actions:</strong>
            <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-top: 6px;">${actionsHTML}</div>
        </div>` : ''}
    `;
}

async function askContextualHelp() {
    const input = document.getElementById('help-ask-input');
    const q = input.value.trim();
    if (!q) return;

    const modal = document.getElementById('contextual-help-modal');
    const pageKey = modal.getAttribute('data-page-key') || 'admin_dashboard';
    const content = document.getElementById('help-modal-content');

    const originalHTML = content.innerHTML;
    content.innerHTML += `
        <div style="margin-top: 14px; padding: 12px; background: var(--bg-hover); border-radius: 6px; border-left: 3px solid var(--primary);">
            <div style="font-weight: 700; font-size: 13px; color: var(--primary);">Q: ${escapeHTML(q)}</div>
            <div id="help-ai-ans" style="margin-top: 4px; font-size: 13px;"><i class="fa-solid fa-spinner fa-spin"></i> Thinking...</div>
        </div>
    `;
    input.value = '';

    try {
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
        const res = await fetch('/api/v1/ai/contextual-help/ask', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({ page: pageKey, question: q })
        });
        const data = await res.json();
        const ansEl = document.getElementById('help-ai-ans');
        if (ansEl) ansEl.textContent = data.answer || 'No guidance found.';
    } catch (e) {
        const ansEl = document.getElementById('help-ai-ans');
        if (ansEl) ansEl.textContent = 'AI assistance temporarily unavailable.';
    }
}

function closeContextualHelpModal() {
    const m = document.getElementById('contextual-help-modal');
    if (m) m.classList.remove('open');
}

// --------------------------------------------------------------------------
// 5. 'What Changed?' History Diff Viewer
// --------------------------------------------------------------------------
window.showWhatChanged = async function (entityType = 'Resident', entityId = null) {
    let modal = document.getElementById('what-changed-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'what-changed-modal';
        modal.className = 'confirm-modal-backdrop';
        modal.setAttribute('role', 'dialog');
        modal.innerHTML = `
            <div class="confirm-modal-box" style="max-width: 540px; width: 90%;">
                <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-color); padding-bottom: 12px; margin-bottom: 14px;">
                    <h3 style="margin: 0; font-size: 17px; font-weight: 800; display: flex; align-items: center; gap: 8px;">
                        <i class="fa-solid fa-clock-rotate-left" style="color: var(--primary);"></i>
                        What Changed?
                    </h3>
                    <button type="button" class="toast-close" onclick="closeWhatChangedModal()"><i class="fa-solid fa-xmark"></i></button>
                </div>
                <div id="what-changed-content" style="max-height: 350px; overflow-y: auto; font-size: 13px;">
                    <div style="text-align: center; padding: 20px;"><i class="fa-solid fa-spinner fa-spin"></i> Checking recent history...</div>
                </div>
                <div style="margin-top: 14px; text-align: right;">
                    <button type="button" class="btn btn-secondary btn-sm" onclick="closeWhatChangedModal()">Close</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }

    modal.classList.add('open');
    try {
        const url = `/api/v1/ai/what-changed?entity_type=${encodeURIComponent(entityType)}` + (entityId ? `&entity_id=${entityId}` : '');
        const res = await fetch(url);
        const data = await res.json();

        const content = document.getElementById('what-changed-content');
        if (data.total_changes === 0) {
            content.innerHTML = `<div style="padding: 20px; text-align: center; color: var(--text-secondary);">No recent changes recorded for this record.</div>`;
        } else {
            let listHTML = (data.changes_list || []).map((c, i) => `
                <div style="padding: 10px; border-bottom: 1px solid var(--border-color); line-height: 1.4;">
                    <div style="font-weight: 700; color: var(--text-primary);">${i + 1}. ${escapeHTML(c.action)}</div>
                    <div style="color: var(--text-secondary); margin-top: 2px;">${escapeHTML(c.description)}</div>
                    <div style="font-size: 11px; color: var(--text-secondary); margin-top: 4px;">By ${escapeHTML(c.actor)} • ${c.timestamp}</div>
                </div>
            `).join('');
            content.innerHTML = `<div><strong style="color: var(--primary);">${data.summary}</strong><div style="margin-top: 10px;">${listHTML}</div></div>`;
        }
    } catch (e) {
        document.getElementById('what-changed-content').innerHTML = `<div style="color: var(--danger); text-align: center; padding: 20px;">Could not load history.</div>`;
    }
};

function closeWhatChangedModal() {
    const m = document.getElementById('what-changed-modal');
    if (m) m.classList.remove('open');
}

// --------------------------------------------------------------------------
// 6. Keyboard Shortcuts Help Modal
// --------------------------------------------------------------------------
window.showKeyboardShortcutsHelp = function () {
    let modal = document.getElementById('shortcuts-help-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'shortcuts-help-modal';
        modal.className = 'confirm-modal-backdrop';
        modal.setAttribute('role', 'dialog');
        modal.innerHTML = `
            <div class="confirm-modal-box" style="max-width: 520px; width: 90%;">
                <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-color); padding-bottom: 12px; margin-bottom: 14px;">
                    <h3 style="margin: 0; font-size: 17px; font-weight: 800; display: flex; align-items: center; gap: 8px;">
                        <i class="fa-solid fa-keyboard" style="color: var(--primary);"></i>
                        Keyboard Shortcuts
                    </h3>
                    <button type="button" class="toast-close" onclick="closeShortcutsModal()"><i class="fa-solid fa-xmark"></i></button>
                </div>
                <div style="font-size: 13px; line-height: 1.8;">
                    <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid var(--border-color);">
                        <span>Open Command Palette</span>
                        <kbd style="padding: 2px 6px; background: var(--bg-hover); border-radius: 4px; font-weight: 700;">Ctrl + K</kbd>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid var(--border-color);">
                        <span>Focus Search</span>
                        <kbd style="padding: 2px 6px; background: var(--bg-hover); border-radius: 4px; font-weight: 700;">/</kbd>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid var(--border-color);">
                        <span>Go to Dashboard</span>
                        <kbd style="padding: 2px 6px; background: var(--bg-hover); border-radius: 4px; font-weight: 700;">G then D</kbd>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid var(--border-color);">
                        <span>Go to Residents</span>
                        <kbd style="padding: 2px 6px; background: var(--bg-hover); border-radius: 4px; font-weight: 700;">G then R</kbd>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid var(--border-color);">
                        <span>Go to Notifications</span>
                        <kbd style="padding: 2px 6px; background: var(--bg-hover); border-radius: 4px; font-weight: 700;">G then N</kbd>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid var(--border-color);">
                        <span>Go to Work Queue</span>
                        <kbd style="padding: 2px 6px; background: var(--bg-hover); border-radius: 4px; font-weight: 700;">G then W</kbd>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 4px 0;">
                        <span>Close dialog / modal</span>
                        <kbd style="padding: 2px 6px; background: var(--bg-hover); border-radius: 4px; font-weight: 700;">Esc</kbd>
                    </div>
                </div>
                <div style="margin-top: 14px; text-align: right;">
                    <button type="button" class="btn btn-secondary btn-sm" onclick="closeShortcutsModal()">Got It</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }
    modal.classList.add('open');
};

function closeShortcutsModal() {
    const m = document.getElementById('shortcuts-help-modal');
    if (m) m.classList.remove('open');
}

// --------------------------------------------------------------------------
// 7. Auto-init on page load & aggregate telemetry
// --------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
    SmartTableManager.init();

    // Telemetry: record page interaction
    const path = window.location.pathname;
    try {
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
        fetch('/api/v1/ai/analytics/record-usage', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({ feature_name: document.title.split('-')[0].trim(), action: 'view' })
        });
    } catch (e) { }
});

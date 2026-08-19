/**
 * Society SaaS - UI Components & Interactive Widgets (v2.0)
 * Reusable components for toasts, command palette, drawer, bulk actions, and keyboard shortcuts.
 */

'use strict';

// --------------------------------------------------------------------------
// 1. Toast Notification System
// --------------------------------------------------------------------------
window.toast = function (message, type = 'info', title = null) {
    let container = document.getElementById('global-toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'global-toast-container';
        container.className = 'toast-container';
        container.setAttribute('aria-live', 'polite');
        document.body.appendChild(container);
    }

    const toastItem = document.createElement('div');
    toastItem.className = `toast-item toast-${type}`;
    toastItem.setAttribute('role', 'alert');

    let iconClass = 'fa-circle-info';
    if (type === 'success') iconClass = 'fa-circle-check';
    else if (type === 'danger' || type === 'error') iconClass = 'fa-circle-exclamation';
    else if (type === 'warning') iconClass = 'fa-triangle-exclamation';

    const defaultTitle = type.charAt(0).toUpperCase() + type.slice(1);

    toastItem.innerHTML = `
        <i class="fa-solid ${iconClass} toast-icon" aria-hidden="true"></i>
        <div class="toast-content">
            <div class="toast-title">${escapeHTML(title || defaultTitle)}</div>
            <div class="toast-message">${escapeHTML(message)}</div>
        </div>
        <button type="button" class="toast-close" aria-label="Close notification"><i class="fa-solid fa-xmark"></i></button>
    `;

    const closeBtn = toastItem.querySelector('.toast-close');
    const dismiss = () => {
        toastItem.classList.add('toast-hiding');
        setTimeout(() => toastItem.remove(), 250);
    };

    closeBtn.addEventListener('click', dismiss);
    container.appendChild(toastItem);

    setTimeout(dismiss, 4500);
};

function escapeHTML(str) {
    if (!str) return '';
    return String(str).replace(/[&<>"']/g, m => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
    })[m]);
}

function escapeRegex(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// --------------------------------------------------------------------------
// 2. Unified Global Search + Command Center (Single Component & State)
// --------------------------------------------------------------------------
class GlobalSearchCommandCenter {
    constructor() {
        this.backdrop = document.getElementById('cmd-palette-backdrop');
        this.modal = document.getElementById('global-search-command-center') || document.querySelector('.cmd-palette-modal');
        this.input = document.getElementById('cmd-palette-input');
        this.resultsContainer = document.getElementById('cmd-palette-results');
        this.clearBtn = document.getElementById('cmd-palette-clear-btn');
        this.backBtn = document.getElementById('cmd-palette-mobile-back');
        this.resultCountEl = document.getElementById('cmd-result-count');
        this.isOpen = false;
        this.selectedIndex = -1;
        this.items = [];
        this.debounceTimer = null;
        this.lastTriggerElement = null;
        this.role = document.body ? (document.body.dataset.role || 'Resident') : 'Resident';
        this.searchHistory = this.loadHistory();

        this.initRegistry();
        if (this.backdrop && this.input) {
            this.initEvents();
        }
    }

    loadHistory() {
        try {
            return JSON.parse(localStorage.getItem('cmd_search_history') || '[]');
        } catch (e) {
            return [];
        }
    }

    saveHistoryItem(query) {
        if (!query || query.trim().length < 2) return;
        query = query.trim();
        this.searchHistory = this.searchHistory.filter(h => h.toLowerCase() !== query.toLowerCase());
        this.searchHistory.unshift(query);
        this.searchHistory = this.searchHistory.slice(0, 8);
        try {
            localStorage.setItem('cmd_search_history', JSON.stringify(this.searchHistory));
        } catch (e) { }
    }

    removeHistoryItem(query, event) {
        if (event) event.stopPropagation();
        this.searchHistory = this.searchHistory.filter(h => h !== query);
        try {
            localStorage.setItem('cmd_search_history', JSON.stringify(this.searchHistory));
        } catch (e) { }
        this.renderDefault();
    }

    clearHistory(event) {
        if (event) event.stopPropagation();
        this.searchHistory = [];
        try {
            localStorage.removeItem('cmd_search_history');
        } catch (e) { }
        this.renderDefault();
    }
    initRegistry() {
        const isAdmin = ['Super Admin', 'Society Admin', 'Accounting Staff', 'Security Staff', 'Maintenance Staff'].includes(this.role);

        if (isAdmin) {
            this.commandRegistry = [
                // Quick Actions
                { id: 'add-resident', title: 'Add Resident', subtitle: 'Register owner or tenant in society', category: 'Quick Actions', type: 'Action', icon: 'fa-user-plus', url: '/admin/residents', keywords: ['add resident', 'new resident', 'create resident', 'member', 'new member', 'register resident', 'tenant', 'owner'] },
                { id: 'gen-bills', title: 'Generate Maintenance Bills', subtitle: 'Issue monthly billing for all flats', category: 'Quick Actions', type: 'Action', icon: 'fa-file-invoice-dollar', url: '/payments/bills', keywords: ['create bill', 'generate bill', 'issue bill', 'monthly billing', 'billing', 'bill', 'invoice'] },
                { id: 'record-pay', title: 'Record Payment', subtitle: 'Record cash, cheque or offline dues', category: 'Quick Actions', type: 'Action', icon: 'fa-hand-holding-dollar', url: '/payments/bills', keywords: ['record payment', 'collect payment', 'payment', 'pay', 'dues', 'collect', 'cash', 'cheque', 'offline payment'] },
                { id: 'page-complaints-action', title: 'Complaints Desk', subtitle: 'Assign and resolve resident tickets', category: 'Quick Actions', type: 'Action', icon: 'fa-headset', url: '/complaints/', keywords: ['complaints', 'tickets', 'issues', 'view complaints', 'support', 'problem', 'grievance'] },
                { id: 'add-visitor', title: 'Visitor Security Desk', subtitle: 'Log visitor entry at security gate', category: 'Quick Actions', type: 'Action', icon: 'fa-id-badge', url: '/visitors/', keywords: ['add visitor', 'new visitor', 'visitor pass', 'gate pass', 'guest', 'visitor', 'visitors', 'visitor security desk'] },

                // Recent
                { id: 'page-dashboard', title: 'Dashboard', subtitle: 'Executive overview & statistics', category: 'Recent', type: 'Page', icon: 'fa-chart-line', url: '/dashboard', keywords: ['dashboard', 'home', 'overview', 'analytics'] },
                { id: 'page-payment-history', title: 'Payment History', subtitle: 'Payment center & reconciliation', category: 'Recent', type: 'Page', icon: 'fa-credit-card', url: '/payments/admin_dashboard', keywords: ['payment history', 'payments', 'reconciliation', 'cash verification'] },

                // Pages & Navigation
                { id: 'page-residents', title: 'Residents Management', subtitle: 'Directory of owners and tenants', category: 'Pages', type: 'Page', icon: 'fa-users', url: '/admin/residents', keywords: ['residents', 'members', 'directory', 'owners', 'tenants', 'view resident', 'edit resident'] },
                { id: 'page-flats', title: 'Flats & Wings', subtitle: 'Wing, block and flat inventory', category: 'Pages', type: 'Page', icon: 'fa-city', url: '/admin/flats', keywords: ['flats', 'wings', 'blocks', 'units', 'buildings', 'inventory', 'floors'] },
                { id: 'page-billing', title: 'Payments & Billing', subtitle: 'Bill generation, configs & receipts', category: 'Pages', type: 'Page', icon: 'fa-file-invoice', url: '/payments/bills', keywords: ['payments', 'billing', 'maintenance', 'invoices', 'bills', 'view payments', 'generate receipt', 'download receipt', 'receipts', 'receipt'] },
                { id: 'page-defaulters', title: 'Pending Payments & Defaulters', subtitle: 'Defaulter list and outstanding dues', category: 'Pages', type: 'Page', icon: 'fa-circle-exclamation', url: '/reports/defaulters', keywords: ['pending payments', 'view pending payments', 'defaulters', 'dues', 'outstanding', 'unpaid', 'overdue'] },
                { id: 'page-vendors', title: 'Vendors & Operations', subtitle: 'Contractors, AMC and staff', category: 'Pages', type: 'Page', icon: 'fa-handshake', url: '/operations/vendors', keywords: ['vendors', 'contractors', 'amc', 'staff', 'suppliers', 'operations'] },
                { id: 'page-accounting', title: 'Expenses & Vouchers', subtitle: 'Expense vouchers and ledger', category: 'Pages', type: 'Page', icon: 'fa-file-invoice-dollar', url: '/accounting/vouchers', keywords: ['expenses', 'accounting', 'ledger', 'vouchers', 'spending', 'payments'] },
                { id: 'page-reports', title: 'Financial Reports', subtitle: 'Income vs expense & collections', category: 'Pages', type: 'Page', icon: 'fa-chart-pie', url: '/reports/financial', keywords: ['reports', 'financial reports', 'balance sheet', 'collection report'] },
                { id: 'page-vault', title: 'Document Vault', subtitle: 'Bylaws, contracts and files', category: 'Pages', type: 'Page', icon: 'fa-vault', url: '/documents/vault', keywords: ['documents', 'vault', 'bylaws', 'contracts', 'files', 'records'] },
                { id: 'page-system', title: 'Audit Logs & System Health', subtitle: 'Database backups & activity logs', category: 'Pages', type: 'Page', icon: 'fa-heart-pulse', url: '/system/backups', keywords: ['audit logs', 'system health', 'backups', 'security logs', 'audit'] },
                { id: 'page-notices', title: 'Notice Management', subtitle: 'Society circulars & announcements', category: 'Pages', type: 'Page', icon: 'fa-bullhorn', url: '/resident/announcements', keywords: ['notices', 'announcements', 'circulars', 'view notices', 'notice'] },

                // Settings & Preferences
                { id: 'theme-toggle', title: 'Toggle Theme', subtitle: 'Switch between light and dark theme', category: 'Settings', type: 'Setting', icon: 'fa-moon', action: () => { const btn = document.getElementById('theme-toggle-btn'); if (btn) btn.click(); }, keywords: ['theme', 'dark mode', 'light mode', 'switch theme', 'settings'] },
                { id: 'profile', title: 'Admin Profile', subtitle: 'Manage account credentials & security', category: 'Settings', type: 'Page', icon: 'fa-user-gear', url: '/resident/profile', keywords: ['profile', 'settings', 'admin profile', 'account'] },
                { id: 'logout', title: 'Logout Account', subtitle: 'End current administrator session', category: 'Settings', type: 'Action', icon: 'fa-right-from-bracket', url: '/auth/logout', keywords: ['logout', 'sign out', 'exit'] }
            ];
        } else {
            // Resident Registry
            this.commandRegistry = [
                // Quick Actions
                { id: 'pay-dues', title: 'Pay Maintenance', subtitle: 'Pay dues online via Razorpay or QR', category: 'Quick Actions', type: 'Action', icon: 'fa-credit-card', url: '/resident/bills', keywords: ['record payment', 'pay maintenance', 'payment', 'pay', 'dues', 'maintenance', 'outstanding', 'unpaid', 'pay now', 'bills', 'fees'] },
                { id: 'page-bills', title: 'My Bills', subtitle: 'Monthly invoices & breakdown', category: 'Quick Actions', type: 'Action', icon: 'fa-file-invoice', url: '/resident/bills', keywords: ['bills', 'my bills', 'invoices', 'charges', 'maintenance bill', 'dues', 'view bills'] },
                { id: 'page-receipts', title: 'Receipts', subtitle: 'Download official payment receipts', category: 'Quick Actions', type: 'Action', icon: 'fa-receipt', url: '/resident/receipts', keywords: ['receipts', 'receipt', 'payment receipt', 'invoices', 'download', 'view receipts'] },
                { id: 'raise-complaint', title: 'Complaint Desk', subtitle: 'Submit ticket for maintenance/repair', category: 'Quick Actions', type: 'Action', icon: 'fa-headset', url: '/resident/complaints', keywords: ['create complaint', 'raise complaint', 'complaint', 'complaints', 'issue', 'problem', 'broken', 'repair', 'ticket', 'support', 'help', 'grievance', 'new complaint', 'complaint desk'] },
                { id: 'invite-visitor', title: 'Visitor Security Desk', subtitle: 'Generate QR gate pass for guests', category: 'Quick Actions', type: 'Action', icon: 'fa-id-badge', url: '/resident/visitors', keywords: ['add visitor', 'invite visitor', 'pre-approve visitor', 'visitor', 'visitors', 'guest', 'pass', 'gate pass', 'delivery', 'cab', 'security', 'visitor security desk'] },

                // Recent
                { id: 'page-dashboard', title: 'Dashboard', subtitle: 'Overview of bills, dues & notices', category: 'Recent', type: 'Page', icon: 'fa-house', url: '/dashboard', keywords: ['dashboard', 'home', 'overview'] },
                { id: 'page-payment-history', title: 'Payment History', subtitle: 'Transaction history and status', category: 'Recent', type: 'Page', icon: 'fa-clock-rotate-left', url: '/payments/payment_history', keywords: ['payment history', 'payments', 'transactions', 'paid', 'history', 'view payments', 'view payment history'] },

                // Pages
                { id: 'page-profile', title: 'My Profile & Flat Details', subtitle: 'Flat ownership & member details', category: 'Pages', type: 'Page', icon: 'fa-user', url: '/resident/profile', keywords: ['profile', 'my profile', 'flat details', 'personal info', 'account', 'user'] },
                { id: 'page-yearly-summary', title: 'Yearly Summary', subtitle: 'Annual dues and collection breakdown', category: 'Pages', type: 'Page', icon: 'fa-chart-bar', url: '/resident/yearly_summary', keywords: ['yearly summary', 'annual statement', 'summary', 'ledger'] },
                { id: 'page-facilities', title: 'Facility Booking', subtitle: 'Reserve clubhouse, gym, or pool', category: 'Pages', type: 'Page', icon: 'fa-swimming-pool', url: '/facilities/', keywords: ['facilities', 'facility', 'clubhouse', 'book facility', 'gym', 'pool', 'hall', 'book', 'amenity', 'reservation', 'facility booking'] },
                { id: 'page-announcements', title: 'Announcements & Notices', subtitle: 'Society circulars & broadcasts', category: 'Pages', type: 'Page', icon: 'fa-bullhorn', url: '/resident/announcements', keywords: ['notices', 'announcements', 'circulars', 'updates', 'broadcast', 'view notices'] },
                { id: 'page-notifications', title: 'Notifications Center', subtitle: 'Alerts and billing reminders', category: 'Pages', type: 'Page', icon: 'fa-bell', url: '/resident/notifications', keywords: ['notifications', 'alerts', 'reminders', 'bell'] },
                { id: 'page-household', title: 'Household Members', subtitle: 'Family members & emergency contacts', category: 'Pages', type: 'Page', icon: 'fa-people-roof', url: '/resident/household', keywords: ['household', 'family', 'members', 'dependents', 'contacts'] },
                { id: 'page-documents', title: 'Society Documents', subtitle: 'Bylaws, guidelines and rulebooks', category: 'Pages', type: 'Page', icon: 'fa-folder-open', url: '/resident/documents', keywords: ['documents', 'bylaws', 'society docs', 'rules', 'vault', 'files'] },
                { id: 'page-security', title: 'Account Security', subtitle: 'Password, 2FA and sessions', category: 'Pages', type: 'Page', icon: 'fa-shield-halved', url: '/resident/security', keywords: ['security', 'password', '2fa', 'settings', 'account security'] },
                { id: 'page-preferences', title: 'Notification Preferences', subtitle: 'Configure alert channels', category: 'Pages', type: 'Page', icon: 'fa-sliders', url: '/resident/notification_preferences', keywords: ['preferences', 'notification settings', 'settings', 'alerts'] },
                { id: 'page-help', title: 'Help & Support Center', subtitle: 'FAQs and support tickets', category: 'Pages', type: 'Page', icon: 'fa-circle-question', url: '/resident/help_center', keywords: ['help', 'help & support', 'support', 'faq', 'contact', 'guide'] },
                { id: 'page-activity', title: 'My Activity Log', subtitle: 'Recent resident actions & logs', category: 'Pages', type: 'Page', icon: 'fa-clock-rotate-left', url: '/resident/activity', keywords: ['activity', 'log', 'history', 'logs'] },

                // Settings & Preferences
                { id: 'theme-toggle', title: 'Toggle Theme', subtitle: 'Switch between light and dark theme', category: 'Settings', type: 'Setting', icon: 'fa-moon', action: () => { const btn = document.getElementById('theme-toggle-btn'); if (btn) btn.click(); }, keywords: ['theme', 'dark mode', 'light mode', 'switch theme', 'settings'] },
                { id: 'logout', title: 'Logout Account', subtitle: 'Sign out of resident portal', category: 'Settings', type: 'Action', icon: 'fa-right-from-bracket', url: '/auth/logout', keywords: ['logout', 'sign out', 'exit'] }
            ];
        }
    }

    initEvents() {
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isOpen) {
                e.preventDefault();
                this.close();
            } else if (this.isOpen) {
                if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    this.navigate(1);
                } else if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    this.navigate(-1);
                } else if (e.key === 'Enter') {
                    e.preventDefault();
                    this.triggerSelected();
                }
            }
        });

        this.backdrop.addEventListener('click', (e) => {
            if (e.target === this.backdrop) this.close();
        });

        if (this.backBtn) {
            this.backBtn.addEventListener('click', () => this.close());
        }

        const modalCloseBtn = document.getElementById('cmd-palette-close-btn');
        if (modalCloseBtn) {
            modalCloseBtn.addEventListener('click', () => this.close());
        }

        if (this.clearBtn) {
            this.clearBtn.addEventListener('click', () => {
                this.input.value = '';
                this.clearBtn.style.display = 'none';
                this.renderDefault();
                this.input.focus();
            });
        }

        this.input.addEventListener('input', () => {
            const val = this.input.value;
            if (this.clearBtn) {
                this.clearBtn.style.display = val.length > 0 ? 'inline-flex' : 'none';
            }
            clearTimeout(this.debounceTimer);
            this.debounceTimer = setTimeout(() => {
                this.search(val.trim());
            }, 120);
        });

        const globalTrigger = document.getElementById('global-search-trigger');
        if (globalTrigger) {
            globalTrigger.addEventListener('click', (e) => {
                e.preventDefault();
                this.open();
            });
        }
    }

    open(initialQuery = '') {
        this.isOpen = true;
        this.lastTriggerElement = document.activeElement;
        this.backdrop.classList.add('open');
        this.input.value = initialQuery;
        if (this.clearBtn) this.clearBtn.style.display = initialQuery ? 'inline-flex' : 'none';

        if (initialQuery) {
            this.search(initialQuery);
        } else {
            this.renderDefault();
        }
        setTimeout(() => {
            if (this.input) {
                this.input.focus();
                if (initialQuery) this.input.select();
            }
        }, 50);
    }

    close() {
        this.isOpen = false;
        this.backdrop.classList.remove('open');
        this.selectedIndex = -1;
        if (this.lastTriggerElement && typeof this.lastTriggerElement.focus === 'function') {
            this.lastTriggerElement.focus();
        } else {
            const globalTrigger = document.getElementById('global-search-trigger');
            if (globalTrigger && typeof globalTrigger.focus === 'function') {
                globalTrigger.focus();
            }
        }
    }

    toggle() {
        if (this.isOpen) this.close();
        else this.open();
    }

    renderDefault() {
        this.items = [];
        this.resultsContainer.innerHTML = '';
        if (this.resultCountEl) this.resultCountEl.textContent = '';

        // 1. QUICK ACTIONS
        const quickActions = this.commandRegistry.filter(c => c.category === 'Quick Actions');
        if (quickActions.length > 0) {
            const groupDiv = document.createElement('div');
            groupDiv.className = 'cmd-group-label';
            groupDiv.textContent = 'QUICK ACTIONS';
            this.resultsContainer.appendChild(groupDiv);

            quickActions.forEach(c => {
                this.items.push(c);
                this.appendItemDOM(c, this.items.length - 1);
            });
        }

        // 2. RECENT
        const recentGroupDiv = document.createElement('div');
        recentGroupDiv.className = 'cmd-group-label';
        recentGroupDiv.style.display = 'flex';
        recentGroupDiv.style.justifyContent = 'space-between';
        recentGroupDiv.style.alignItems = 'center';
        recentGroupDiv.innerHTML = `
            <span>RECENT</span>
            ${this.searchHistory.length > 0 ? '<button type="button" class="filter-clear-all" style="font-size:11px; text-decoration:none;" id="cmd-clear-history">Clear History</button>' : ''}
        `;
        this.resultsContainer.appendChild(recentGroupDiv);

        if (this.searchHistory.length > 0) {
            const clearBtn = recentGroupDiv.querySelector('#cmd-clear-history');
            if (clearBtn) clearBtn.addEventListener('click', (e) => this.clearHistory(e));
        }

        // Core recent items (Dashboard, Payment History)
        const recentCore = this.commandRegistry.filter(c => c.category === 'Recent');
        recentCore.forEach(c => {
            this.items.push(c);
            this.appendItemDOM(c, this.items.length - 1);
        });

        // Search history if any
        if (this.searchHistory.length > 0) {
            this.searchHistory.slice(0, 4).forEach(hist => {
                const item = {
                    title: hist,
                    subtitle: 'Recent Search',
                    icon: 'fa-clock-rotate-left',
                    type: 'Recent',
                    action: () => {
                        this.input.value = hist;
                        if (this.clearBtn) this.clearBtn.style.display = 'inline-flex';
                        this.search(hist);
                    }
                };
                this.items.push(item);
                this.appendItemDOM(item, this.items.length - 1, true, hist);
            });
        }

        this.selectedIndex = this.items.length > 0 ? 0 : -1;
        this.updateSelectionDOM();
    }

    async search(query) {
        if (!query) {
            this.renderDefault();
            return;
        }

        const qLower = query.toLowerCase();
        this.resultsContainer.innerHTML = '<div style="padding: 24px; text-align: center; color: var(--text-secondary);"><i class="fa-solid fa-spinner fa-spin"></i> Searching...</div>';

        // 1. Match local registry with fuzzy matching & scoring
        const matchedLocal = [];
        this.commandRegistry.forEach(c => {
            let score = 0;
            const tLower = c.title.toLowerCase();
            const sLower = c.subtitle.toLowerCase();

            if (tLower === qLower) score = 100;
            else if (tLower.startsWith(qLower)) score = 80;
            else if (tLower.includes(qLower)) score = 60;
            else if (sLower.includes(qLower)) score = 40;
            else if (c.keywords && c.keywords.some(k => k.toLowerCase().includes(qLower) || qLower.includes(k.toLowerCase()))) score = 50;

            if (score > 0) {
                matchedLocal.push({ item: c, score });
            }
        });
        matchedLocal.sort((a, b) => b.score - a.score);

        // 2. Fetch server records from /api/v1/search
        let serverCategories = [];
        let searchError = false;
        try {
            const res = await fetch('/api/v1/search?q=' + encodeURIComponent(query));
            if (res.ok) {
                const data = await res.json();
                if (data && data.categories) {
                    serverCategories = data.categories;
                }
            } else {
                searchError = true;
            }
        } catch (err) {
            console.error('API search failed', err);
            searchError = true;
        }

        this.renderSearchResults(query, matchedLocal.map(m => m.item), serverCategories, searchError);
    }

    renderSearchResults(query, localItems, serverCategories, searchError = false) {
        this.items = [];
        this.resultsContainer.innerHTML = '';

        let totalCount = 0;

        if (searchError) {
            const errDiv = document.createElement('div');
            errDiv.style.padding = '8px 16px';
            errDiv.style.margin = '8px 16px';
            errDiv.style.borderRadius = 'var(--radius-sm, 6px)';
            errDiv.style.background = 'rgba(239, 68, 68, 0.1)';
            errDiv.style.color = 'var(--danger, #ef4444)';
            errDiv.style.fontSize = '12px';
            errDiv.style.display = 'flex';
            errDiv.style.alignItems = 'center';
            errDiv.style.justifyContent = 'space-between';
            errDiv.innerHTML = `
                <span><i class="fa-solid fa-triangle-exclamation"></i> Search unavailable</span>
                <button type="button" class="btn btn-xs btn-outline" style="font-size:11px; padding:2px 8px;" id="cmd-try-again">Try Again</button>
            `;
            this.resultsContainer.appendChild(errDiv);
            const tryBtn = errDiv.querySelector('#cmd-try-again');
            if (tryBtn) {
                tryBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.search(query);
                });
            }
        }

        // Render Local Actions/Pages if any
        if (localItems.length > 0) {
            const groupDiv = document.createElement('div');
            groupDiv.className = 'cmd-group-label';
            groupDiv.textContent = 'Actions & Commands';
            this.resultsContainer.appendChild(groupDiv);

            localItems.forEach(item => {
                this.items.push(item);
                totalCount++;
                this.appendItemDOM(item, this.items.length - 1, false, null, query);
            });
        }

        // Render Server Categories
        const catMap = {
            category_residents: { label: 'Residents & Members', type: 'Resident', icon: 'fa-user' },
            category_flats: { label: 'Flats & Wings', type: 'Flat', icon: 'fa-building' },
            category_bills: { label: 'Maintenance Bills', type: 'Bill', icon: 'fa-file-invoice-dollar' },
            category_payments: { label: 'Payments & Transactions', type: 'Payment', icon: 'fa-receipt' },
            category_receipts: { label: 'Receipts', type: 'Receipt', icon: 'fa-receipt' },
            category_complaints: { label: 'Complaints', type: 'Complaint', icon: 'fa-headset' },
            category_visitors: { label: 'Visitors', type: 'Visitor', icon: 'fa-id-badge' },
            category_vehicles: { label: 'Vehicles', type: 'Vehicle', icon: 'fa-car' },
            category_vendors: { label: 'Vendors', type: 'Vendor', icon: 'fa-handshake' },
            category_staff: { label: 'Staff Members', type: 'Staff', icon: 'fa-user-gear' },
            category_expenses: { label: 'Expenses & Vouchers', type: 'Expense', icon: 'fa-file-invoice-dollar' },
            category_documents: { label: 'Documents', type: 'Document', icon: 'fa-folder-open' },
            category_notices: { label: 'Notices & Announcements', type: 'Notice', icon: 'fa-bullhorn' },
            category_audit: { label: 'Audit Logs', type: 'Audit', icon: 'fa-clock-rotate-left' }
        };

        serverCategories.forEach(cat => {
            if (cat.items && cat.items.length > 0) {
                const catMeta = catMap[cat.key] || { label: cat.key.replace('category_', '').toUpperCase(), type: 'Record', icon: 'fa-magnifying-glass' };
                const groupDiv = document.createElement('div');
                groupDiv.className = 'cmd-group-label';
                groupDiv.textContent = catMeta.label;
                this.resultsContainer.appendChild(groupDiv);

                cat.items.forEach(srvItem => {
                    const item = {
                        title: srvItem.title,
                        subtitle: srvItem.subtitle || '',
                        icon: srvItem.icon || catMeta.icon,
                        url: srvItem.url,
                        type: catMeta.type,
                        actions: srvItem.actions || []
                    };
                    this.items.push(item);
                    totalCount++;
                    this.appendItemDOM(item, this.items.length - 1, false, null, query);
                });
            }
        });

        if (this.resultCountEl) {
            this.resultCountEl.textContent = totalCount > 0 ? (totalCount + ' result' + (totalCount > 1 ? 's' : '')) : '';
        }

        if (this.items.length === 0) {
            const emptyDiv = document.createElement('div');
            emptyDiv.className = 'empty-state-card';
            emptyDiv.style.cssText = 'margin: 20px 16px; border: none; background: transparent; text-align: center;';
            emptyDiv.innerHTML = `
                <div class="empty-state-icon" style="font-size: 26px; color: var(--text-secondary); margin-bottom: 6px;"><i class="fa-solid fa-magnifying-glass"></i></div>
                <div class="empty-state-title" style="font-size: 14.5px; font-weight: 600;">No results found for "${escapeHTML(query)}"</div>
                <div class="empty-state-desc" style="font-size: 12.5px; color: var(--text-secondary); margin-top: 4px;">
                    Try searching: resident name, flat number, payment, bill, complaint, action name
                </div>
            `;
            this.resultsContainer.appendChild(emptyDiv);

            // Render Quick Actions fallback
            const quickActions = this.commandRegistry.filter(c => c.category === 'Quick Actions').slice(0, 4);
            if (quickActions.length > 0) {
                const suggGroup = document.createElement('div');
                suggGroup.className = 'cmd-group-label';
                suggGroup.textContent = 'Suggested Actions';
                this.resultsContainer.appendChild(suggGroup);

                quickActions.forEach(c => {
                    this.items.push(c);
                    this.appendItemDOM(c, this.items.length - 1);
                });
                this.selectedIndex = 0;
                this.updateSelectionDOM();
            } else {
                this.selectedIndex = -1;
            }
        } else {
            this.selectedIndex = 0;
            this.updateSelectionDOM();
        }
    }

    appendItemDOM(item, index, isHistory = false, historyQuery = null, highlightQuery = '') {
        const el = document.createElement('div');
        el.className = `cmd-item ${index === this.selectedIndex ? 'selected' : ''}`;

        let titleDisplay = escapeHTML(item.title);
        if (highlightQuery && highlightQuery.trim().length > 0) {
            const regex = new RegExp('(' + escapeRegex(highlightQuery.trim()) + ')', 'gi');
            titleDisplay = titleDisplay.replace(regex, '<span class="cmd-item-highlight">$1</span>');
        }

        let typeClass = 'badge-action';
        if (item.type === 'Page') typeClass = 'badge-page';
        else if (item.type === 'Resident') typeClass = 'badge-resident';
        else if (item.type === 'Bill') typeClass = 'badge-bill';
        else if (item.type === 'Payment' || item.type === 'Receipt') typeClass = 'badge-payment';

        let contextualActionsHtml = '';
        if (item.actions && item.actions.length > 0) {
            contextualActionsHtml = '<div class="cmd-item-actions" style="display:flex; gap:6px; margin-left:auto;">';
            item.actions.forEach(act => {
                contextualActionsHtml += `<button type="button" class="btn btn-xs btn-outline" style="padding:2px 8px; font-size:11px;" onclick="event.stopPropagation(); window.location.href='${act.url}'">${escapeHTML(act.label)}</button>`;
            });
            contextualActionsHtml += '</div>';
        }

        el.innerHTML = `
            <div class="cmd-item-icon"><i class="fa-solid ${item.icon}"></i></div>
            <div class="cmd-item-text" style="flex:1;">
                <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
                    <span style="font-weight:600;">${titleDisplay}</span>
                    <span class="cmd-type-badge ${typeClass}">${item.type || 'Action'}</span>
                </div>
                <div style="font-size:12px; color:var(--text-secondary); margin-top:2px;">${escapeHTML(item.subtitle || '')}</div>
            </div>
            ${contextualActionsHtml}
            ${isHistory ? `<button type="button" class="toast-close" style="font-size:12px; opacity:0.6; padding:4px;" aria-label="Remove search" title="Remove"><i class="fa-solid fa-xmark"></i></button>` : ''}
        `;

        if (isHistory) {
            const removeBtn = el.querySelector('.toast-close');
            if (removeBtn) {
                removeBtn.addEventListener('click', (e) => this.removeHistoryItem(historyQuery, e));
            }
        }

        el.addEventListener('click', () => this.executeItem(item));
        this.resultsContainer.appendChild(el);
    }

    navigate(dir) {
        if (this.items.length === 0) return;
        this.selectedIndex = (this.selectedIndex + dir + this.items.length) % this.items.length;
        this.updateSelectionDOM();
    }

    updateSelectionDOM() {
        const domItems = this.resultsContainer.querySelectorAll('.cmd-item');
        domItems.forEach((el, i) => {
            el.classList.toggle('selected', i === this.selectedIndex);
            if (i === this.selectedIndex) el.scrollIntoView({ block: 'nearest' });
        });
    }

    triggerSelected() {
        if (this.selectedIndex >= 0 && this.selectedIndex < this.items.length) {
            this.executeItem(this.items[this.selectedIndex]);
        }
    }

    executeItem(item) {
        const currentQuery = this.input.value.trim();
        if (currentQuery) {
            this.saveHistoryItem(currentQuery);
        }
        this.close();
        if (item.action) {
            item.action();
        } else if (item.url) {
            window.location.href = item.url;
        }
    }
}
// --------------------------------------------------------------------------
// 3. Universal Confirmation Modal System
// --------------------------------------------------------------------------
window.confirmAction = function({
    title = 'Confirm Action',
    message = 'Are you sure you want to proceed?',
    details = null,
    confirmText = 'Confirm',
    confirmClass = 'btn-danger',
    icon = 'fa-triangle-exclamation',
    onConfirm = null
} = {}) {
    return new Promise((resolve) => {
        const modal = document.getElementById('universal-confirm-modal');
        if (!modal) {
            const confirmed = window.confirm(message);
            if (confirmed && onConfirm) onConfirm();
            resolve(confirmed);
            return;
        }

        const titleEl = document.getElementById('confirm-modal-title');
        const messageEl = document.getElementById('confirm-modal-message');
        const detailsEl = document.getElementById('confirm-modal-details');
        const iconEl = document.getElementById('confirm-modal-icon');
        const cancelBtn = document.getElementById('confirm-modal-cancel');
        const okBtn = document.getElementById('confirm-modal-ok');

        if (titleEl) titleEl.textContent = title;
        if (messageEl) messageEl.textContent = message;
        if (detailsEl) {
            if (details) {
                detailsEl.innerHTML = details;
                detailsEl.style.display = 'block';
            } else {
                detailsEl.style.display = 'none';
            }
        }
        if (iconEl) {
            iconEl.innerHTML = `<i class="fa-solid ${icon}"></i>`;
        }
        if (okBtn) {
            okBtn.textContent = confirmText;
            okBtn.className = `btn ${confirmClass}`;
        }

        modal.classList.add('open');

        const cleanup = () => {
            modal.classList.remove('open');
            cancelBtn.removeEventListener('click', handleCancel);
            okBtn.removeEventListener('click', handleOk);
            document.removeEventListener('keydown', handleKey);
        };

        const handleCancel = () => {
            cleanup();
            resolve(false);
        };

        const handleOk = () => {
            if (okBtn) {
                okBtn.disabled = true;
                okBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Processing...`;
            }
            setTimeout(() => {
                cleanup();
                if (okBtn) {
                    okBtn.disabled = false;
                    okBtn.textContent = confirmText;
                }
                if (onConfirm) onConfirm();
                resolve(true);
            }, 150);
        };

        const handleKey = (e) => {
            if (e.key === 'Escape') handleCancel();
            else if (e.key === 'Enter') handleOk();
        };

        cancelBtn.addEventListener('click', handleCancel);
        okBtn.addEventListener('click', handleOk);
        document.addEventListener('keydown', handleKey);
    });
};

function initUniversalConfirmListener() {
    document.addEventListener('click', (e) => {
        const target = e.target.closest('[data-confirm]');
        if (target) {
            e.preventDefault();
            const message = target.getAttribute('data-confirm') || 'Are you sure you want to proceed?';
            const title = target.getAttribute('data-confirm-title') || 'Confirm Action';
            const details = target.getAttribute('data-confirm-details') || null;
            const btnClass = target.getAttribute('data-confirm-class') || 'btn-danger';

            window.confirmAction({
                title,
                message,
                details,
                confirmClass: btnClass,
                onConfirm: () => {
                    if (target.tagName === 'FORM') {
                        target.submit();
                    } else if (target.form) {
                        target.form.submit();
                    } else if (target.href) {
                        window.location.href = target.href;
                    }
                }
            });
        }
    });
}
// --------------------------------------------------------------------------
// 4. Interactive Table Sorting & Pagination Helpers
// --------------------------------------------------------------------------
function initTableSorting() {
    document.querySelectorAll('th.sortable, table.sortable th').forEach(th => {
        if (!th.classList.contains('no-sort')) {
            th.style.cursor = 'pointer';
            th.addEventListener('click', () => {
                const table = th.closest('table');
                if (!table) return;
                const tbody = table.querySelector('tbody');
                if (!tbody) return;

                const colIndex = Array.from(th.parentNode.children).indexOf(th);
                const isAsc = !th.classList.contains('sorted-asc');

                th.parentNode.querySelectorAll('th').forEach(h => h.classList.remove('sorted-asc', 'sorted-desc'));
                th.classList.toggle('sorted-asc', isAsc);
                th.classList.toggle('sorted-desc', !isAsc);

                const rows = Array.from(tbody.querySelectorAll('tr'));
                rows.sort((a, b) => {
                    const aCell = a.children[colIndex] ? a.children[colIndex].textContent.trim() : '';
                    const bCell = b.children[colIndex] ? b.children[colIndex].textContent.trim() : '';

                    const aNum = parseFloat(aCell.replace(/[^0-9.-]+/g, ''));
                    const bNum = parseFloat(bCell.replace(/[^0-9.-]+/g, ''));

                    if (!isNaN(aNum) && !isNaN(bNum)) {
                        return isAsc ? aNum - bNum : bNum - aNum;
                    }
                    return isAsc ? aCell.localeCompare(bCell) : bCell.localeCompare(aCell);
                });

                rows.forEach(r => tbody.appendChild(r));
            });
        }
    });
}

function initPaginationControls() {
    document.querySelectorAll('.page-size-select').forEach(sel => {
        sel.addEventListener('change', () => {
            const url = new URL(window.location.href);
            url.searchParams.set('page_size', sel.value);
            url.searchParams.set('page', '1');
            window.location.href = url.toString();
        });
    });

    document.addEventListener('keydown', (e) => {
        const activeTag = document.activeElement ? document.activeElement.tagName : '';
        if (['INPUT', 'TEXTAREA', 'SELECT'].includes(activeTag) || (document.activeElement && document.activeElement.isContentEditable)) {
            return;
        }
        if (e.key === 'ArrowLeft' && e.altKey) {
            const prevLink = document.querySelector('.pagination-link-prev, a[rel="prev"]');
            if (prevLink) prevLink.click();
        } else if (e.key === 'ArrowRight' && e.altKey) {
            const nextLink = document.querySelector('.pagination-link-next, a[rel="next"]');
            if (nextLink) nextLink.click();
        }
    });
}

// --------------------------------------------------------------------------
// 5. Sidebar Collapsible & Mobile Drawer Controls
// --------------------------------------------------------------------------
function initSidebarControls() {
    const sidebar = document.querySelector('.sidebar');
    const mainContent = document.querySelector('.main-content');
    const toggleBtn = document.getElementById('sidebar-toggle-btn');
    const mobileMenuBtn = document.getElementById('mobile-menu-btn');
    const overlay = document.getElementById('sidebar-mobile-overlay');

    if (sidebar) {
        sidebar.querySelectorAll('.nav-item').forEach(item => {
            const span = item.querySelector('span');
            if (span && !item.getAttribute('data-tooltip')) {
                item.setAttribute('data-tooltip', span.textContent.trim());
            }
        });
    }

    // Restore desktop collapsed state
    const isCollapsed = localStorage.getItem('sidebar_collapsed') === 'true';
    if (isCollapsed && sidebar && mainContent && window.innerWidth > 768) {
        sidebar.classList.add('sidebar-collapsed');
        mainContent.classList.add('sidebar-collapsed-active');
    }

    if (toggleBtn && sidebar && mainContent) {
        toggleBtn.addEventListener('click', (e) => {
            e.preventDefault();
            const collapsed = sidebar.classList.toggle('sidebar-collapsed');
            mainContent.classList.toggle('sidebar-collapsed-active', collapsed);
            localStorage.setItem('sidebar_collapsed', collapsed ? 'true' : 'false');
        });
    }

    // Authoritative Single Source of Truth for Mobile Menu State
    let isMenuOpen = false;

    function setMobileMenuOpen(open) {
        isMenuOpen = Boolean(open);
        if (sidebar) {
            sidebar.classList.toggle('mobile-open', isMenuOpen);
        }
        if (overlay) {
            overlay.classList.toggle('active', isMenuOpen);
        }
        document.body.classList.toggle('drawer-open', isMenuOpen);
        if (mobileMenuBtn) {
            mobileMenuBtn.setAttribute('aria-expanded', isMenuOpen ? 'true' : 'false');
            mobileMenuBtn.setAttribute('aria-label', isMenuOpen ? 'Close menu' : 'Open menu');
            mobileMenuBtn.setAttribute('title', isMenuOpen ? 'Close menu' : 'Open menu');
        }
    }

    function toggleMobileMenu() {
        setMobileMenuOpen(!isMenuOpen);
    }

    function closeMobileMenu() {
        if (isMenuOpen) {
            setMobileMenuOpen(false);
        }
    }

    function openMobileMenu() {
        if (!isMenuOpen) {
            setMobileMenuOpen(true);
        }
    }

    // Expose state and controller globally
    window.isMobileMenuOpen = () => isMenuOpen;
    window.isMenuOpen = () => isMenuOpen;
    window.toggleMobileMenu = toggleMobileMenu;
    window.openMobileMenu = openMobileMenu;
    window.closeMobileMenu = closeMobileMenu;
    window.setMobileMenuOpen = setMobileMenuOpen;

    // Single click handler on hamburger button
    if (mobileMenuBtn) {
        mobileMenuBtn.addEventListener('click', (e) => {
            e.preventDefault();
            toggleMobileMenu();
        });
    }

    // Click on backdrop overlay closes menu
    if (overlay) {
        overlay.addEventListener('click', (e) => {
            e.preventDefault();
            closeMobileMenu();
        });
    }

    // Document click listener: closes menu when clicked outside menu boundary
    document.addEventListener('click', (e) => {
        if (!isMenuOpen) return;
        // If click is on the hamburger button or inside the sidebar, keep menu open
        if (mobileMenuBtn && mobileMenuBtn.contains(e.target)) {
            return;
        }
        if (sidebar && sidebar.contains(e.target)) {
            return;
        }
        // Click was outside menu -> close
        closeMobileMenu();
    });

    // Escape key closes menu
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && isMenuOpen) {
            closeMobileMenu();
        }
    });

    // Viewport resize cleanup
    window.addEventListener('resize', () => {
        if (window.innerWidth > 768 && isMenuOpen) {
            closeMobileMenu();
        }
    });

    // Active navigation is managed centrally
    updateActiveNavigation();
}

// --------------------------------------------------------------------------
// Route-Aware Active Navigation Manager (Sidebar & Mobile Bottom Navigation)
// --------------------------------------------------------------------------
function updateActiveNavigation() {
    const currentPath = window.location.pathname.replace(/\/+$/, '') || '/';

    // 1. Sidebar Nav Items
    const sidebarItems = document.querySelectorAll('.sidebar-nav .nav-item');
    if (sidebarItems.length > 0) {
        let bestSidebarItem = null;
        let highestSidebarScore = -1;

        sidebarItems.forEach(item => {
            const rawHref = item.getAttribute('href');
            if (!rawHref || rawHref === '#' || rawHref.startsWith('javascript:')) return;

            const hrefPath = rawHref.split('?')[0].split('#')[0].replace(/\/+$/, '') || '/';
            let score = 0;

            if (currentPath === hrefPath) {
                score = 1000 + hrefPath.length;
            } else if ((currentPath === '/' || currentPath === '/dashboard') && (hrefPath === '/' || hrefPath === '/dashboard')) {
                score = 900;
            } else if (hrefPath !== '/' && hrefPath !== '/dashboard') {
                if (currentPath.startsWith(hrefPath + '/') || currentPath === hrefPath) {
                    score = 500 + hrefPath.length;
                }
            }

            if (score > highestSidebarScore && score > 0) {
                highestSidebarScore = score;
                bestSidebarItem = item;
            }
        });

        sidebarItems.forEach(item => {
            if (item === bestSidebarItem) {
                item.classList.add('active');
                item.classList.remove('inactive');
                item.setAttribute('aria-current', 'page');
            } else {
                item.classList.remove('active');
                item.classList.add('inactive');
                item.removeAttribute('aria-current');
            }
        });
    }

    // 2. Mobile Bottom Nav Items
    const mobileNavItems = document.querySelectorAll('.mobile-nav a, .mobile-nav .mobile-nav-item');
    if (mobileNavItems.length > 0) {
        let bestMobileItem = null;
        let highestMobileScore = -1;

        mobileNavItems.forEach(item => {
            const rawHref = item.getAttribute('href');
            const target = (item.getAttribute('data-nav-target') || '').toLowerCase();
            const text = (item.textContent || '').trim().toLowerCase();
            const hrefPath = rawHref ? rawHref.split('?')[0].split('#')[0].replace(/\/+$/, '') || '/' : '';
            let score = 0;

            if (target === 'home' || text.includes('home')) {
                if (currentPath === '/' || currentPath === '/dashboard') {
                    score = 950;
                }
            } else if (target === 'bills' || text.includes('bill')) {
                if (currentPath === '/resident/bills' || currentPath.startsWith('/resident/bills') || currentPath === '/payments/bills') {
                    score = 900;
                }
            } else if (target === 'pay' || text.includes('pay')) {
                if (currentPath.startsWith('/payments/pay') ||
                    currentPath.startsWith('/payments/multi-month') ||
                    currentPath.startsWith('/payments/retry') ||
                    currentPath.startsWith('/payments/success') ||
                    currentPath.startsWith('/payments/failed') ||
                    currentPath.startsWith('/payments/cancelled')) {
                    score = 920;
                }
            } else if (target === 'receipts' || text.includes('receipt')) {
                if (currentPath === '/resident/receipts' || currentPath.startsWith('/resident/receipts') || currentPath.startsWith('/payments/receipt')) {
                    score = 900;
                }
            } else if (target === 'more' || text.includes('more') || text.includes('profile')) {
                if (currentPath.startsWith('/resident/profile') ||
                    currentPath.startsWith('/resident/household') ||
                    currentPath.startsWith('/resident/documents') ||
                    currentPath.startsWith('/resident/security') ||
                    currentPath.startsWith('/resident/support') ||
                    currentPath.startsWith('/resident/activity') ||
                    currentPath.startsWith('/resident/preferences') ||
                    currentPath.startsWith('/resident/notification_preferences') ||
                    currentPath.startsWith('/resident/help') ||
                    currentPath.startsWith('/resident/yearly_summary') ||
                    currentPath.startsWith('/resident/announcements') ||
                    currentPath.startsWith('/resident/notifications') ||
                    currentPath.startsWith('/resident/visitors') ||
                    currentPath.startsWith('/resident/complaints') ||
                    currentPath.startsWith('/facilities')) {
                    score = 800;
                }
            }

            // Fallback to exact / prefix matching on href if score not yet set
            if (score === 0 && hrefPath && rawHref !== '#' && !rawHref.startsWith('javascript:')) {
                if (currentPath === hrefPath) {
                    score = 600 + hrefPath.length;
                } else if (hrefPath !== '/' && hrefPath !== '/dashboard' && (currentPath.startsWith(hrefPath + '/') || currentPath === hrefPath)) {
                    score = 400 + hrefPath.length;
                }
            }

            if (score > highestMobileScore && score > 0) {
                highestMobileScore = score;
                bestMobileItem = item;
            }
        });

        mobileNavItems.forEach(item => {
            if (item === bestMobileItem) {
                item.classList.add('active');
                item.classList.remove('inactive');
                item.setAttribute('aria-current', 'page');
            } else {
                item.classList.remove('active');
                item.classList.add('inactive');
                item.removeAttribute('aria-current');
            }
        });
    }
}

function initActiveNavigation() {
    updateActiveNavigation();

    // Bind navigation click listeners for immediate active feedback
    document.querySelectorAll('.sidebar-nav .nav-item, .mobile-nav a, .mobile-nav .mobile-nav-item').forEach(link => {
        link.addEventListener('click', function() {
            const href = this.getAttribute('href');
            if (href && href !== '#' && !href.startsWith('javascript:')) {
                const parentNav = this.closest('.sidebar-nav') || this.closest('.mobile-nav');
                if (parentNav) {
                    parentNav.querySelectorAll('.nav-item, a, .mobile-nav-item').forEach(el => {
                        if (el === this) {
                            el.classList.add('active');
                            el.classList.remove('inactive');
                            el.setAttribute('aria-current', 'page');
                        } else {
                            el.classList.remove('active');
                            el.classList.add('inactive');
                            el.removeAttribute('aria-current');
                        }
                    });
                }
            }
        });
    });

    // Browser navigation listeners (Back/Forward buttons, history push/pop)
    window.addEventListener('popstate', updateActiveNavigation);
    window.addEventListener('pageshow', updateActiveNavigation);
    window.addEventListener('hashchange', updateActiveNavigation);
}

window.updateActiveNavigation = updateActiveNavigation;
window.initActiveNavigation = initActiveNavigation;

// --------------------------------------------------------------------------
// 6. Back To Top Button & Page Progress
// --------------------------------------------------------------------------
function initBackToTop() {
    const btn = document.getElementById('back-to-top-btn');
    if (!btn) return;

    window.addEventListener('scroll', () => {
        if (window.scrollY > 300) {
            btn.classList.add('visible');
        } else {
            btn.classList.remove('visible');
        }
    });

    btn.addEventListener('click', () => {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });
}

function initPageProgressBar() {
    const progressBar = document.getElementById('page-progress-bar');
    if (!progressBar) return;

    window.addEventListener('beforeunload', () => {
        progressBar.style.opacity = '1';
        progressBar.style.width = '70%';
    });
}

// --------------------------------------------------------------------------
// 7. Global Recently Visited Tracker
// --------------------------------------------------------------------------
function trackRecentlyVisited() {
    try {
        const title = document.title.replace('· Society SaaS', '').replace('- Society SaaS', '').trim();
        const path = window.location.pathname;
        if (path === '/login' || path === '/register' || path === '/logout' || path === '/auth/login') return;

        let recent = JSON.parse(localStorage.getItem('recently_visited') || '[]');
        recent = recent.filter(r => r.path !== path);
        recent.unshift({ title, path, time: Date.now() });
        recent = recent.slice(0, 8);
        localStorage.setItem('recently_visited', JSON.stringify(recent));
    } catch (e) {}
}

// --------------------------------------------------------------------------
// 8. Global Keyboard Shortcuts (P=Pay, B=Bills, R=Receipts, /=Search)
// --------------------------------------------------------------------------
function initKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        const activeTag = document.activeElement ? document.activeElement.tagName : '';
        if (['INPUT', 'TEXTAREA', 'SELECT'].includes(activeTag) || (document.activeElement && document.activeElement.isContentEditable)) {
            return;
        }

        if (e.key === 'b' || e.key === 'B') {
            const billLink = document.querySelector('a[href*="/resident/bills"]');
            if (billLink) window.location.href = billLink.href;
        } else if (e.key === 'r' || e.key === 'R') {
            const recLink = document.querySelector('a[href*="/resident/receipts"]');
            if (recLink) window.location.href = recLink.href;
        }
    });
}

// --------------------------------------------------------------------------
// 9. Prevent Accidental Double Submission & Button Loading States
// --------------------------------------------------------------------------
function initFormLoadingStates() {
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', function(e) {
            const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
            if (submitBtn && !submitBtn.disabled) {
                if (!form.checkValidity()) return;

                setTimeout(() => {
                    submitBtn.disabled = true;
                    if (submitBtn.tagName === 'BUTTON') {
                        const originalHtml = submitBtn.innerHTML;
                        submitBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Processing...`;
                        setTimeout(() => {
                            submitBtn.disabled = false;
                            submitBtn.innerHTML = originalHtml;
                        }, 10000);
                    }
                }, 10);
            }
        });
    });
}

// --------------------------------------------------------------------------
// 10. Dashboard Customizable & Draggable Widgets
// --------------------------------------------------------------------------
function initDashboardWidgetManager() {
    const grid = document.querySelector('.dashboard-grid, .dash-widget-grid');
    if (!grid) return;

    const savedOrder = JSON.parse(localStorage.getItem('dashboard_widget_order') || '[]');
    if (savedOrder.length > 0) {
        savedOrder.forEach(id => {
            const el = grid.querySelector(`[data-widget-id="${id}"]`);
            if (el) grid.appendChild(el);
        });
    }

    let dragSrcEl = null;
    grid.querySelectorAll('[data-widget-id]').forEach(widget => {
        widget.setAttribute('draggable', 'true');
        widget.addEventListener('dragstart', (e) => {
            dragSrcEl = widget;
            e.dataTransfer.effectAllowed = 'move';
            widget.classList.add('widget-dragging');
        });
        widget.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
        });
        widget.addEventListener('drop', (e) => {
            e.preventDefault();
            if (dragSrcEl !== widget) {
                const widgets = Array.from(grid.querySelectorAll('[data-widget-id]'));
                const srcIdx = widgets.indexOf(dragSrcEl);
                const tgtIdx = widgets.indexOf(widget);
                if (srcIdx < tgtIdx) {
                    grid.insertBefore(dragSrcEl, widget.nextSibling);
                } else {
                    grid.insertBefore(dragSrcEl, widget);
                }
                const newOrder = Array.from(grid.querySelectorAll('[data-widget-id]')).map(w => w.getAttribute('data-widget-id'));
                localStorage.setItem('dashboard_widget_order', JSON.stringify(newOrder));
            }
        });
        widget.addEventListener('dragend', () => {
            widget.classList.remove('widget-dragging');
        });
    });

    window.resetDashboardLayout = function() {
        localStorage.removeItem('dashboard_widget_order');
        localStorage.removeItem('dashboard_hidden_widgets');
        window.location.reload();
    };
}

// --------------------------------------------------------------------------
// 11. Saved Filter Presets & Active Filters Summary
// --------------------------------------------------------------------------
function initSavedFilterPresets() {
    const filterContainer = document.querySelector('.filter-bar, .filter-drawer');
    if (!filterContainer) return;

    const key = 'filter_presets_' + window.location.pathname;
    window.saveCurrentFilterPreset = function(name) {
        if (!name) return;
        const currentParams = window.location.search;
        let presets = JSON.parse(localStorage.getItem(key) || '{}');
        presets[name] = currentParams;
        localStorage.setItem(key, JSON.stringify(presets));
        if (window.toast) window.toast(`Filter preset "${name}" saved!`, 'success');
    };

    window.loadFilterPreset = function(name) {
        let presets = JSON.parse(localStorage.getItem(key) || '{}');
        if (presets[name]) {
            window.location.search = presets[name];
        }
    };
}

// Expose Unified Global Search Functions and Aliases
window.GlobalSearchCommandCenter = GlobalSearchCommandCenter;
window.CommandPalette = GlobalSearchCommandCenter;

window.openGlobalSearch = function(query) {
    if (window.globalSearchCommandCenter) {
        window.globalSearchCommandCenter.open(query);
    }
};

window.closeGlobalSearch = function() {
    if (window.globalSearchCommandCenter) {
        window.globalSearchCommandCenter.close();
    }
};

window.toggleGlobalSearch = function() {
    if (window.globalSearchCommandCenter) {
        window.globalSearchCommandCenter.toggle();
    }
};

window.setIsGlobalSearchOpen = function(isOpen) {
    if (window.globalSearchCommandCenter) {
        if (isOpen) window.globalSearchCommandCenter.open();
        else window.globalSearchCommandCenter.close();
    }
};

try {
    Object.defineProperty(window, 'isGlobalSearchOpen', {
        get() {
            return window.globalSearchCommandCenter ? window.globalSearchCommandCenter.isOpen : false;
        },
        set(val) {
            window.setIsGlobalSearchOpen(val);
        },
        configurable: true
    });
} catch (e) { }

// Auto-run on DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
    window.globalSearchCommandCenter = new GlobalSearchCommandCenter();
    window.cmdPalette = window.globalSearchCommandCenter;
    initUniversalConfirmListener();
    initTableSorting();
    initPaginationControls();
    initActiveNavigation();
    initSidebarControls();
    initBackToTop();
    initPageProgressBar();
    trackRecentlyVisited();
    initKeyboardShortcuts();
    initFormLoadingStates();
    initDashboardWidgetManager();
    initSavedFilterPresets();
});

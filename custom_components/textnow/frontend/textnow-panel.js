/**
 * TextNow Panel for Home Assistant
 * A sidebar panel for managing TextNow contacts and messages
 */

class TextNowPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = null;
    this._entries = [];  // All TextNow accounts/hubs
    this._contactsByEntry = {};  // Contacts grouped by entry_id
    this._activeTab = "contacts";
    this._loading = false;
  }

  set hass(hass) {
    this._hass = hass;
    if (this._entries.length === 0) {
      this._loadEntries();
    }
  }

  set panel(panel) {
    this._config = panel.config;
  }

  async _loadEntries() {
    if (!this._hass) return;
    
    this._loading = true;
    this._render();
    
    try {
      const entries = await this._hass.callWS({
        type: "textnow/get_entries",
      });
      
      this._entries = entries || [];
      
      // Load contacts for each entry
      for (const entry of this._entries) {
        await this._loadContactsForEntry(entry.entry_id);
      }
    } catch (e) {
      console.error("Failed to load TextNow entries:", e);
      this._entries = [];
    }
    
    this._loading = false;
    this._render();
  }

  async _loadContactsForEntry(entryId) {
    if (!this._hass) return;
    
    try {
      const result = await this._hass.callWS({
        type: "textnow/contacts_list",
        entry_id: entryId,
      });
      this._contactsByEntry[entryId] = result || [];
    } catch (e) {
      console.error(`Failed to load contacts for entry ${entryId}:`, e);
      this._contactsByEntry[entryId] = [];
    }
  }

  async _addContact(entryId, name, phone) {
    if (!this._hass || !entryId) return;
    
    try {
      await this._hass.callWS({
        type: "textnow/contacts_add",
        entry_id: entryId,
        name: name,
        phone: phone,
      });
      await this._loadContactsForEntry(entryId);
      this._render();
      this._showToast("Contact added successfully!");
    } catch (e) {
      console.error("Failed to add contact:", e);
      this._showToast("Failed to add contact: " + e.message, true);
    }
  }

  async _deleteContact(entryId, contactId) {
    if (!this._hass || !entryId) return;
    
    if (!confirm("Are you sure you want to delete this contact?")) return;
    
    try {
      await this._hass.callWS({
        type: "textnow/contacts_delete",
        entry_id: entryId,
        id: contactId,
      });
      await this._loadContactsForEntry(entryId);
      this._render();
      this._showToast("Contact deleted!");
    } catch (e) {
      console.error("Failed to delete contact:", e);
      this._showToast("Failed to delete contact: " + e.message, true);
    }
  }

  _addNewAccount() {
    // Navigate to add integration flow
    window.location.href = "/config/integrations/dashboard/add?domain=textnow";
  }

  _showToast(message, isError = false) {
    const toast = this.shadowRoot.querySelector(".toast");
    if (toast) {
      toast.textContent = message;
      toast.className = `toast ${isError ? "error" : "success"} show`;
      setTimeout(() => {
        toast.className = "toast";
      }, 3000);
    }
  }

  _maskPhone(phone) {
    if (!phone) return "•••••••••";
    // Remove any non-digit characters for consistent masking
    const digits = phone.replace(/\D/g, "");
    if (digits.length <= 4) {
      return phone; // Too short to mask meaningfully
    }
    // Show only last 4 digits, mask the rest with bullet characters
    const visiblePart = digits.slice(-4);
    const maskedLength = digits.length - 4;
    return "•".repeat(maskedLength) + visiblePart;
  }

  connectedCallback() {
    this._render();
  }

  _render() {
    const styles = `
      <style>
        :host {
          display: block;
          height: 100%;
          background: var(--primary-background-color, #1c1c1c);
          color: var(--primary-text-color, #fff);
          font-family: var(--paper-font-body1_-_font-family, 'Roboto', sans-serif);
        }
        
        .container {
          height: 100%;
          display: flex;
          flex-direction: column;
        }
        
        .header {
          background: var(--primary-color, #03a9f4);
          padding: 16px 24px;
          display: flex;
          align-items: center;
          gap: 12px;
          box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }
        
        .header h1 {
          margin: 0;
          font-size: 20px;
          font-weight: 500;
          flex: 1;
        }
        
        .header-icon {
          width: 32px;
          height: 32px;
          fill: white;
        }
        
        .header-actions {
          display: flex;
          gap: 8px;
        }
        
        .tabs {
          display: flex;
          background: var(--card-background-color, #1e1e1e);
          border-bottom: 1px solid var(--divider-color, #333);
        }
        
        .tab {
          flex: 1;
          padding: 12px 16px;
          text-align: center;
          cursor: pointer;
          border: none;
          background: transparent;
          color: var(--secondary-text-color, #888);
          font-size: 14px;
          font-weight: 500;
          transition: all 0.2s;
          border-bottom: 2px solid transparent;
        }
        
        .tab:hover {
          background: var(--secondary-background-color, #2a2a2a);
        }
        
        .tab.active {
          color: var(--primary-color, #03a9f4);
          border-bottom-color: var(--primary-color, #03a9f4);
        }
        
        .content {
          flex: 1;
          overflow-y: auto;
          padding: 16px;
        }
        
        .card {
          background: var(--card-background-color, #1e1e1e);
          border-radius: 8px;
          padding: 16px;
          margin-bottom: 16px;
          box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .card-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 16px;
        }
        
        .card-title {
          font-size: 16px;
          font-weight: 500;
          margin: 0;
        }
        
        .hub-section {
          margin-bottom: 24px;
        }
        
        .hub-header {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 12px 16px;
          background: linear-gradient(135deg, var(--primary-color, #03a9f4), #0288d1);
          border-radius: 8px 8px 0 0;
          color: white;
        }
        
        .hub-icon {
          width: 24px;
          height: 24px;
          fill: white;
        }
        
        .hub-title {
          font-size: 16px;
          font-weight: 500;
          flex: 1;
        }
        
        .hub-badge {
          background: rgba(255,255,255,0.2);
          padding: 4px 10px;
          border-radius: 12px;
          font-size: 12px;
        }
        
        .hub-content {
          background: var(--card-background-color, #1e1e1e);
          border-radius: 0 0 8px 8px;
          padding: 16px;
          border: 1px solid var(--divider-color, #333);
          border-top: none;
        }
        
        .contact-list {
          list-style: none;
          padding: 0;
          margin: 0;
        }
        
        .contact-item {
          display: flex;
          align-items: center;
          padding: 12px;
          border-radius: 8px;
          margin-bottom: 8px;
          background: var(--secondary-background-color, #2a2a2a);
          transition: background 0.2s;
        }
        
        .contact-item:hover {
          background: rgba(3, 169, 244, 0.1);
        }
        
        .contact-avatar {
          width: 40px;
          height: 40px;
          border-radius: 50%;
          background: var(--primary-color, #03a9f4);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 18px;
          font-weight: 500;
          margin-right: 12px;
          color: white;
        }
        
        .contact-info {
          flex: 1;
        }
        
        .contact-name {
          font-weight: 500;
          margin-bottom: 2px;
        }
        
        .contact-phone {
          font-size: 13px;
          color: var(--secondary-text-color, #888);
          font-family: monospace;
        }
        
        .contact-actions {
          display: flex;
          gap: 8px;
        }
        
        .btn {
          padding: 8px 16px;
          border-radius: 4px;
          border: none;
          cursor: pointer;
          font-size: 14px;
          font-weight: 500;
          transition: all 0.2s;
          display: inline-flex;
          align-items: center;
          gap: 6px;
        }
        
        .btn-primary {
          background: var(--primary-color, #03a9f4);
          color: white;
        }
        
        .btn-primary:hover {
          filter: brightness(1.1);
        }
        
        .btn-secondary {
          background: var(--secondary-background-color, #2a2a2a);
          color: var(--primary-text-color, #fff);
        }
        
        .btn-secondary:hover {
          background: var(--divider-color, #333);
        }
        
        .btn-danger {
          background: #f44336;
          color: white;
        }
        
        .btn-icon {
          padding: 8px;
          border-radius: 50%;
          width: 36px;
          height: 36px;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        
        .btn-add-account {
          background: linear-gradient(135deg, #4caf50, #388e3c);
          color: white;
          padding: 10px 20px;
        }
        
        .btn-add-account:hover {
          filter: brightness(1.1);
        }
        
        .form-group {
          margin-bottom: 16px;
        }
        
        .form-group label {
          display: block;
          margin-bottom: 6px;
          font-size: 14px;
          color: var(--secondary-text-color, #888);
        }
        
        .form-group input, .form-group textarea, .form-group select {
          width: 100%;
          padding: 10px 12px;
          border: 1px solid var(--divider-color, #333);
          border-radius: 4px;
          background: var(--secondary-background-color, #2a2a2a);
          color: var(--primary-text-color, #fff);
          font-size: 14px;
          box-sizing: border-box;
        }
        
        .form-group input:focus, .form-group textarea:focus, .form-group select:focus {
          outline: none;
          border-color: var(--primary-color, #03a9f4);
        }
        
        .form-row {
          display: flex;
          gap: 12px;
        }
        
        .form-row .form-group {
          flex: 1;
        }
        
        .empty-state {
          text-align: center;
          padding: 48px 24px;
          color: var(--secondary-text-color, #888);
        }
        
        .empty-state svg {
          width: 64px;
          height: 64px;
          margin-bottom: 16px;
          opacity: 0.5;
        }
        
        .loading {
          display: flex;
          justify-content: center;
          padding: 48px;
        }
        
        .spinner {
          width: 40px;
          height: 40px;
          border: 3px solid var(--divider-color, #333);
          border-top-color: var(--primary-color, #03a9f4);
          border-radius: 50%;
          animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        
        .toast {
          position: fixed;
          bottom: 24px;
          left: 50%;
          transform: translateX(-50%) translateY(100px);
          padding: 12px 24px;
          border-radius: 4px;
          font-size: 14px;
          opacity: 0;
          transition: all 0.3s;
          z-index: 1000;
        }
        
        .toast.show {
          transform: translateX(-50%) translateY(0);
          opacity: 1;
        }
        
        .toast.success {
          background: #4caf50;
          color: white;
        }
        
        .toast.error {
          background: #f44336;
          color: white;
        }
        
        .status-item {
          display: flex;
          justify-content: space-between;
          padding: 12px 0;
          border-bottom: 1px solid var(--divider-color, #333);
        }
        
        .status-item:last-child {
          border-bottom: none;
        }
        
        .status-label {
          color: var(--secondary-text-color, #888);
        }
        
        .status-value {
          font-weight: 500;
        }
        
        .status-value.online {
          color: #4caf50;
        }
        
        .no-accounts {
          text-align: center;
          padding: 60px 24px;
        }
        
        .no-accounts svg {
          width: 80px;
          height: 80px;
          margin-bottom: 24px;
          opacity: 0.6;
          fill: var(--primary-color, #03a9f4);
        }
        
        .no-accounts h2 {
          margin: 0 0 12px 0;
          font-size: 22px;
        }
        
        .no-accounts p {
          margin: 0 0 24px 0;
          color: var(--secondary-text-color, #888);
        }
        
        .inline-add-form {
          display: flex;
          gap: 8px;
          margin-top: 12px;
          padding-top: 12px;
          border-top: 1px solid var(--divider-color, #333);
        }
        
        .inline-add-form input {
          flex: 1;
          padding: 8px 12px;
          border: 1px solid var(--divider-color, #333);
          border-radius: 4px;
          background: var(--secondary-background-color, #2a2a2a);
          color: var(--primary-text-color, #fff);
          font-size: 14px;
        }
      </style>
    `;

    const header = `
      <div class="header">
        <svg class="header-icon" viewBox="0 0 24 24">
          <path fill="currentColor" d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.17L4 17.17V4h16v12z"/>
        </svg>
        <h1>TextNow</h1>
        <div class="header-actions">
          <button class="btn btn-add-account" id="add-account-btn" title="Add TextNow Account">
            <svg width="18" height="18" viewBox="0 0 24 24">
              <path fill="currentColor" d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>
            </svg>
            Add Account
          </button>
        </div>
      </div>
    `;

    const tabs = `
      <div class="tabs">
        <button class="tab ${this._activeTab === 'contacts' ? 'active' : ''}" data-tab="contacts">
          Contacts
        </button>
        <button class="tab ${this._activeTab === 'status' ? 'active' : ''}" data-tab="status">
          Status
        </button>
      </div>
    `;

    let content = "";
    
    if (this._loading) {
      content = `<div class="loading"><div class="spinner"></div></div>`;
    } else if (this._activeTab === "contacts") {
      content = this._renderContactsTab();
    } else if (this._activeTab === "status") {
      content = this._renderStatusTab();
    }

    this.shadowRoot.innerHTML = `
      ${styles}
      <div class="container">
        ${header}
        ${tabs}
        <div class="content">
          ${content}
        </div>
      </div>
      <div class="toast"></div>
    `;

    this._attachEventListeners();
  }

  _renderContactsTab() {
    if (this._entries.length === 0) {
      return `
        <div class="no-accounts">
          <svg viewBox="0 0 24 24">
            <path d="M15 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm-9-2V7H4v3H1v2h3v3h2v-3h3v-2H6zm9 4c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
          </svg>
          <h2>No TextNow Accounts</h2>
          <p>Add a TextNow account to start managing contacts and sending messages.</p>
          <button class="btn btn-add-account" id="add-first-account">
            <svg width="18" height="18" viewBox="0 0 24 24">
              <path fill="currentColor" d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>
            </svg>
            Add Your First Account
          </button>
        </div>
      `;
    }

    // Render each hub/account with its contacts
    let hubsHtml = "";
    
    for (const entry of this._entries) {
      const contacts = this._contactsByEntry[entry.entry_id] || [];
      const contactCount = contacts.length;
      
      let contactsListHtml = "";
      if (contacts.length === 0) {
        contactsListHtml = `
          <div class="empty-state" style="padding: 24px;">
            <p>No contacts yet. Add one below!</p>
          </div>
        `;
      } else {
        const items = contacts.map(contact => `
          <li class="contact-item" data-id="${contact.id}" data-entry="${entry.entry_id}">
            <div class="contact-avatar">${contact.name.charAt(0).toUpperCase()}</div>
            <div class="contact-info">
              <div class="contact-name">${contact.name}</div>
              <div class="contact-phone">${this._maskPhone(contact.phone)}</div>
            </div>
            <div class="contact-actions">
              <button class="btn btn-danger btn-icon delete-contact" data-id="${contact.id}" data-entry="${entry.entry_id}" title="Delete">
                <svg width="18" height="18" viewBox="0 0 24 24">
                  <path fill="currentColor" d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/>
                </svg>
              </button>
            </div>
          </li>
        `).join("");
        
        contactsListHtml = `<ul class="contact-list">${items}</ul>`;
      }
      
      hubsHtml += `
        <div class="hub-section">
          <div class="hub-header">
            <svg class="hub-icon" viewBox="0 0 24 24">
              <path fill="currentColor" d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
            </svg>
            <span class="hub-title">${entry.title}</span>
            <span class="hub-badge">${contactCount} contact${contactCount !== 1 ? 's' : ''}</span>
          </div>
          <div class="hub-content">
            ${contactsListHtml}
            <div class="inline-add-form">
              <input type="text" class="add-name" data-entry="${entry.entry_id}" placeholder="Name">
              <input type="tel" class="add-phone" data-entry="${entry.entry_id}" placeholder="Phone (e.g. 5551234567)">
              <button class="btn btn-primary add-contact-inline" data-entry="${entry.entry_id}">Add</button>
            </div>
          </div>
        </div>
      `;
    }

    return hubsHtml;
  }


  _renderStatusTab() {
    if (this._entries.length === 0) {
      return `
        <div class="card">
          <h3 class="card-title">No Accounts Configured</h3>
          <p style="color: var(--secondary-text-color);">Add a TextNow account to see status information.</p>
        </div>
      `;
    }
    
    let totalContacts = 0;
    for (const entryId in this._contactsByEntry) {
      totalContacts += (this._contactsByEntry[entryId] || []).length;
    }
    
    let statusHtml = `
      <div class="card">
        <h3 class="card-title">Overview</h3>
        <div class="status-item">
          <span class="status-label">Total Accounts</span>
          <span class="status-value">${this._entries.length}</span>
        </div>
        <div class="status-item">
          <span class="status-label">Total Contacts</span>
          <span class="status-value">${totalContacts}</span>
        </div>
      </div>
    `;
    
    // Status for each account
    for (const entry of this._entries) {
      const contacts = this._contactsByEntry[entry.entry_id] || [];
      statusHtml += `
        <div class="card">
          <h3 class="card-title">${entry.title}</h3>
          <div class="status-item">
            <span class="status-label">Status</span>
            <span class="status-value online">Connected</span>
          </div>
          <div class="status-item">
            <span class="status-label">Contacts</span>
            <span class="status-value">${contacts.length}</span>
          </div>
          <div class="status-item">
            <span class="status-label">Entry ID</span>
            <span class="status-value" style="font-size:11px; word-break:break-all; font-family:monospace;">${entry.entry_id}</span>
          </div>
        </div>
      `;
    }
    
    statusHtml += `
      <div class="card">
        <h3 class="card-title">Quick Actions</h3>
        <div style="display:flex; gap:8px; flex-wrap:wrap;">
          <button class="btn btn-secondary" id="refresh-all">Refresh All Data</button>
          <button class="btn btn-secondary" onclick="window.location.href='/config/integrations/integration/textnow'">Integration Settings</button>
        </div>
      </div>
    `;
    
    return statusHtml;
  }

  _attachEventListeners() {
    // Tab switching
    this.shadowRoot.querySelectorAll(".tab").forEach(tab => {
      tab.addEventListener("click", (e) => {
        this._activeTab = e.target.dataset.tab;
        this._render();
      });
    });

    // Add account buttons
    const addAccountBtn = this.shadowRoot.querySelector("#add-account-btn");
    if (addAccountBtn) {
      addAccountBtn.addEventListener("click", () => this._addNewAccount());
    }
    
    const addFirstAccountBtn = this.shadowRoot.querySelector("#add-first-account");
    if (addFirstAccountBtn) {
      addFirstAccountBtn.addEventListener("click", () => this._addNewAccount());
    }

    // Inline add contact forms
    this.shadowRoot.querySelectorAll(".add-contact-inline").forEach(btn => {
      btn.addEventListener("click", (e) => {
        const entryId = e.target.dataset.entry;
        const nameInput = this.shadowRoot.querySelector(`.add-name[data-entry="${entryId}"]`);
        const phoneInput = this.shadowRoot.querySelector(`.add-phone[data-entry="${entryId}"]`);
        
        const name = nameInput?.value?.trim();
        const phone = phoneInput?.value?.trim();
        
        if (name && phone) {
          this._addContact(entryId, name, phone);
          nameInput.value = "";
          phoneInput.value = "";
        } else {
          this._showToast("Please enter name and phone number", true);
        }
      });
    });

    // Delete contact
    this.shadowRoot.querySelectorAll(".delete-contact").forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const contactId = e.currentTarget.dataset.id;
        const entryId = e.currentTarget.dataset.entry;
        this._deleteContact(entryId, contactId);
      });
    });

    // Refresh all
    const refreshAllBtn = this.shadowRoot.querySelector("#refresh-all");
    if (refreshAllBtn) {
      refreshAllBtn.addEventListener("click", () => this._loadEntries());
    }
  }
}

customElements.define("textnow-panel", TextNowPanel);

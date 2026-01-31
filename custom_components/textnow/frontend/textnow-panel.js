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
    this._contacts = [];
    this._selectedContact = null;
    this._messages = [];
    this._activeTab = "contacts";
    this._loading = false;
    this._entryId = null;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._entryId) {
      this._findEntryId();
    }
  }

  set panel(panel) {
    this._config = panel.config;
  }

  async _findEntryId() {
    if (!this._hass) return;
    
    // Find the TextNow config entry using our custom endpoint
    try {
      const entries = await this._hass.callWS({
        type: "textnow/get_entries",
      });
      
      if (entries && entries.length > 0) {
        this._entryId = entries[0].entry_id;
        await this._loadContacts();
        this._render();
      } else {
        console.warn("No TextNow entries found");
        this._render();
      }
    } catch (e) {
      console.error("Failed to find TextNow entry:", e);
      this._render();
    }
  }

  async _loadContacts() {
    if (!this._hass || !this._entryId) return;
    
    this._loading = true;
    this._render();
    
    try {
      const result = await this._hass.callWS({
        type: "textnow/contacts_list",
        entry_id: this._entryId,
      });
      this._contacts = result || [];
    } catch (e) {
      console.error("Failed to load contacts:", e);
      this._contacts = [];
    }
    
    this._loading = false;
    this._render();
  }

  async _addContact(name, phone) {
    if (!this._hass || !this._entryId) return;
    
    try {
      await this._hass.callWS({
        type: "textnow/contacts_add",
        entry_id: this._entryId,
        name: name,
        phone: phone,
      });
      await this._loadContacts();
      this._showToast("Contact added successfully!");
    } catch (e) {
      console.error("Failed to add contact:", e);
      this._showToast("Failed to add contact: " + e.message, true);
    }
  }

  async _deleteContact(contactId) {
    if (!this._hass || !this._entryId) return;
    
    if (!confirm("Are you sure you want to delete this contact?")) return;
    
    try {
      await this._hass.callWS({
        type: "textnow/contacts_delete",
        entry_id: this._entryId,
        id: contactId,
      });
      await this._loadContacts();
      this._showToast("Contact deleted!");
    } catch (e) {
      console.error("Failed to delete contact:", e);
      this._showToast("Failed to delete contact: " + e.message, true);
    }
  }

  async _sendMessage(contactId, message) {
    if (!this._hass || !this._entryId || !message.trim()) return;
    
    try {
      await this._hass.callWS({
        type: "textnow/send_test",
        entry_id: this._entryId,
        id: contactId,
        message: message,
      });
      this._showToast("Message sent!");
      return true;
    } catch (e) {
      console.error("Failed to send message:", e);
      this._showToast("Failed to send message: " + e.message, true);
      return false;
    }
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
          background: var(--primary-color, #03a9f4);
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
        
        .form-group {
          margin-bottom: 16px;
        }
        
        .form-group label {
          display: block;
          margin-bottom: 6px;
          font-size: 14px;
          color: var(--secondary-text-color, #888);
        }
        
        .form-group input, .form-group textarea {
          width: 100%;
          padding: 10px 12px;
          border: 1px solid var(--divider-color, #333);
          border-radius: 4px;
          background: var(--secondary-background-color, #2a2a2a);
          color: var(--primary-text-color, #fff);
          font-size: 14px;
          box-sizing: border-box;
        }
        
        .form-group input:focus, .form-group textarea:focus {
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
        
        .message-compose {
          display: flex;
          gap: 8px;
          margin-top: 16px;
        }
        
        .message-compose input {
          flex: 1;
          padding: 10px 12px;
          border: 1px solid var(--divider-color, #333);
          border-radius: 4px;
          background: var(--secondary-background-color, #2a2a2a);
          color: var(--primary-text-color, #fff);
          font-size: 14px;
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
      </style>
    `;

    const header = `
      <div class="header">
        <svg class="header-icon" viewBox="0 0 24 24">
          <path fill="currentColor" d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.17L4 17.17V4h16v12z"/>
        </svg>
        <h1>TextNow</h1>
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
    const addForm = `
      <div class="card">
        <h3 class="card-title">Add New Contact</h3>
        <div class="form-row">
          <div class="form-group">
            <label>Name</label>
            <input type="text" id="new-contact-name" placeholder="John Doe">
          </div>
          <div class="form-group">
            <label>Phone Number</label>
            <input type="tel" id="new-contact-phone" placeholder="5551234567">
          </div>
        </div>
        <button class="btn btn-primary" id="add-contact-btn">Add Contact</button>
      </div>
    `;

    let contactsList = "";
    if (this._contacts.length === 0) {
      contactsList = `
        <div class="empty-state">
          <svg viewBox="0 0 24 24">
            <path fill="currentColor" d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
          </svg>
          <p>No contacts yet</p>
          <p>Add a contact above to get started</p>
        </div>
      `;
    } else {
      const items = this._contacts.map(contact => `
        <li class="contact-item" data-id="${contact.id}">
          <div class="contact-avatar">${contact.name.charAt(0).toUpperCase()}</div>
          <div class="contact-info">
            <div class="contact-name">${contact.name}</div>
            <div class="contact-phone">${contact.phone}</div>
          </div>
          <div class="contact-actions">
            <button class="btn btn-danger btn-icon delete-contact" data-id="${contact.id}" title="Delete">
              <svg width="18" height="18" viewBox="0 0 24 24">
                <path fill="currentColor" d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/>
              </svg>
            </button>
          </div>
        </li>
      `).join("");
      
      contactsList = `
        <div class="card">
          <div class="card-header">
            <h3 class="card-title">Contacts (${this._contacts.length})</h3>
            <button class="btn btn-secondary" id="refresh-contacts">Refresh</button>
          </div>
          <ul class="contact-list">${items}</ul>
        </div>
      `;
    }

    return addForm + contactsList;
  }


  _renderStatusTab() {
    const contactCount = this._contacts.length;
    
    return `
      <div class="card">
        <h3 class="card-title">Integration Status</h3>
        <div class="status-item">
          <span class="status-label">Status</span>
          <span class="status-value online">Connected</span>
        </div>
        <div class="status-item">
          <span class="status-label">Contacts</span>
          <span class="status-value">${contactCount}</span>
        </div>
        <div class="status-item">
          <span class="status-label">Entry ID</span>
          <span class="status-value" style="font-size:12px; word-break:break-all;">${this._entryId || 'Loading...'}</span>
        </div>
      </div>
      
      <div class="card">
        <h3 class="card-title">Quick Actions</h3>
        <div style="display:flex; gap:8px; flex-wrap:wrap;">
          <button class="btn btn-secondary" id="refresh-all">Refresh Data</button>
          <button class="btn btn-secondary" onclick="window.location.href='/config/integrations/integration/textnow'">Integration Settings</button>
        </div>
      </div>
    `;
  }

  _attachEventListeners() {
    // Tab switching
    this.shadowRoot.querySelectorAll(".tab").forEach(tab => {
      tab.addEventListener("click", (e) => {
        this._activeTab = e.target.dataset.tab;
        this._render();
      });
    });

    // Add contact
    const addBtn = this.shadowRoot.querySelector("#add-contact-btn");
    if (addBtn) {
      addBtn.addEventListener("click", () => {
        const name = this.shadowRoot.querySelector("#new-contact-name").value;
        const phone = this.shadowRoot.querySelector("#new-contact-phone").value;
        if (name && phone) {
          this._addContact(name, phone);
        } else {
          this._showToast("Please enter name and phone number", true);
        }
      });
    }

    // Delete contact
    this.shadowRoot.querySelectorAll(".delete-contact").forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const contactId = e.currentTarget.dataset.id;
        this._deleteContact(contactId);
      });
    });

    // Refresh contacts
    const refreshBtn = this.shadowRoot.querySelector("#refresh-contacts");
    if (refreshBtn) {
      refreshBtn.addEventListener("click", () => this._loadContacts());
    }

    // Refresh all
    const refreshAllBtn = this.shadowRoot.querySelector("#refresh-all");
    if (refreshAllBtn) {
      refreshAllBtn.addEventListener("click", () => this._loadContacts());
    }

  }
}

customElements.define("textnow-panel", TextNowPanel);

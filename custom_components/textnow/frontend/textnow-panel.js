// TextNow Panel - Custom Element for Home Assistant
class TextNowPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.contacts = [];
    this.entryId = null;
    this.loading = false;
    this.error = null;
    this.showAddDialog = false;
    this.editingContact = null;
    this.newContact = { name: "", phone: "" };
    this.testMessage = { contactId: "", message: "" };
    this.showTestDialog = false;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this.entryId) {
      this.loadEntryId();
    }
    if (this.entryId && this.contacts.length === 0 && !this.loading) {
      this.loadContacts();
    }
  }

  async loadEntryId() {
    try {
      const result = await this._hass.callWS({
        type: "config_entries/list",
      });
      const textnowEntry = result.find((e) => e.domain === "textnow");
      if (textnowEntry) {
        this.entryId = textnowEntry.entry_id;
        this.update();
      } else {
        this.error = "TextNow integration not found. Please set up the integration first.";
        this.update();
      }
    } catch (error) {
      console.error("Error loading entry ID:", error);
      this.error = "Failed to load integration entry";
      this.update();
    }
  }

  async loadContacts() {
    if (!this.entryId) return;
    
    this.loading = true;
    this.error = null;
    this.update();
    
    try {
      const result = await this._hass.callWS({
        type: "textnow/contacts_list",
        entry_id: this.entryId,
      });
      this.contacts = result || [];
      this.loading = false;
      this.update();
    } catch (error) {
      console.error("Error loading contacts:", error);
      this.error = error.message || "Failed to load contacts";
      this.loading = false;
      this.update();
    }
  }

  async addContact() {
    const name = this.newContact.name.trim();
    let phone = this.newContact.phone.trim();

    if (!name || !phone) {
      this.showError("Name and phone are required");
      return;
    }

    // Remove +1 prefix if present for validation
    if (phone.startsWith("+1")) {
      phone = phone.substring(2);
    } else if (phone.startsWith("1") && phone.length === 11) {
      phone = phone.substring(1);
    }

    // Validate it's exactly 10 digits
    if (phone.length !== 10 || !/^\d+$/.test(phone)) {
      this.showError("Phone number must be 10 digits (with or without +1 prefix)");
      return;
    }

    this.loading = true;
    this.update();

    try {
      await this._hass.callWS({
        type: "textnow/contacts_add",
        entry_id: this.entryId,
        name: name,
        phone: phone, // Backend will format it
      });

      this.showAddDialog = false;
      this.newContact = { name: "", phone: "" };
      await this.loadContacts();
    } catch (error) {
      console.error("Error adding contact:", error);
      this.showError(error.message || "Failed to add contact");
      this.loading = false;
      this.update();
    }
  }

  async updateContact(contactId) {
    const name = this.editingContact.name.trim();
    let phone = this.editingContact.phone.trim();

    if (!name || !phone) {
      this.showError("Name and phone are required");
      return;
    }

    // Remove +1 prefix if present for validation
    if (phone.startsWith("+1")) {
      phone = phone.substring(2);
    } else if (phone.startsWith("1") && phone.length === 11) {
      phone = phone.substring(1);
    }

    // Validate it's exactly 10 digits
    if (phone.length !== 10 || !/^\d+$/.test(phone)) {
      this.showError("Phone number must be 10 digits (with or without +1 prefix)");
      return;
    }

    this.loading = true;
    this.update();

    try {
      await this._hass.callWS({
        type: "textnow/contacts_update",
        entry_id: this.entryId,
        id: contactId,
        name: name,
        phone: phone, // Backend will format it
      });

      this.editingContact = null;
      await this.loadContacts();
    } catch (error) {
      console.error("Error updating contact:", error);
      this.showError(error.message || "Failed to update contact");
      this.loading = false;
      this.update();
    }
  }

  async deleteContact(contactId) {
    if (!confirm("Delete this contact?")) return;

    this.loading = true;
    this.update();

    try {
      await this._hass.callWS({
        type: "textnow/contacts_delete",
        entry_id: this.entryId,
        id: contactId,
      });

      await this.loadContacts();
    } catch (error) {
      console.error("Error deleting contact:", error);
      this.showError(error.message || "Failed to delete contact");
      this.loading = false;
      this.update();
    }
  }

  async sendTestMessage() {
    const message = this.testMessage.message.trim();
    const contactId = this.testMessage.contactId;

    if (!message) {
      this.showError("Message is required");
      return;
    }

    if (!contactId) {
      this.showError("Please select a contact");
      return;
    }

    this.loading = true;
    this.update();

    try {
      await this._hass.callWS({
        type: "textnow/send_test",
        entry_id: this.entryId,
        id: contactId,
        message: message,
      });

      this.showTestDialog = false;
      this.testMessage = { contactId: "", message: "" };
      this.showError(null);
      this.showSuccess("Test message sent successfully!");
      this.loading = false;
      this.update();
    } catch (error) {
      console.error("Error sending test message:", error);
      this.showError(error.message || "Failed to send test message");
      this.loading = false;
      this.update();
    }
  }

  showError(message) {
    this.error = message;
    this.update();
    if (message) {
      setTimeout(() => {
        this.error = null;
        this.update();
      }, 5000);
    }
  }

  showSuccess(message) {
    // Simple success notification
    alert(message);
  }

  update() {
    this.render();
  }

  render() {
    if (!this.shadowRoot) return;

    const html = `
      <style>
        :host {
          display: block;
          padding: 16px;
          font-family: var(--mdc-typography-font-family, Roboto, sans-serif);
        }
        .header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 24px;
        }
        .header h1 {
          margin: 0;
          font-size: 24px;
          font-weight: 400;
        }
        .status {
          display: inline-block;
          padding: 4px 12px;
          border-radius: 12px;
          font-size: 12px;
          font-weight: 500;
        }
        .status.loaded {
          background-color: #4caf50;
          color: white;
        }
        .status.unavailable {
          background-color: #f44336;
          color: white;
        }
        .error {
          background-color: #ffebee;
          color: #c62828;
          padding: 12px;
          border-radius: 4px;
          margin-bottom: 16px;
        }
        .actions {
          display: flex;
          gap: 8px;
          margin-bottom: 16px;
        }
        button {
          background-color: var(--primary-color, #03a9f4);
          color: white;
          border: none;
          padding: 8px 16px;
          border-radius: 4px;
          cursor: pointer;
          font-size: 14px;
        }
        button:hover {
          opacity: 0.9;
        }
        button:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        button.danger {
          background-color: #f44336;
        }
        .contacts-table {
          width: 100%;
          border-collapse: collapse;
          background: var(--card-background-color, white);
          border-radius: 4px;
          overflow: hidden;
        }
        .contacts-table th,
        .contacts-table td {
          padding: 12px;
          text-align: left;
          border-bottom: 1px solid var(--divider-color, #e0e0e0);
        }
        .contacts-table th {
          background-color: var(--primary-color, #03a9f4);
          color: white;
          font-weight: 500;
        }
        .contacts-table tr:last-child td {
          border-bottom: none;
        }
        .empty-state {
          text-align: center;
          padding: 48px;
          color: var(--secondary-text-color, #757575);
        }
        .dialog-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.5);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
        }
        .dialog {
          background: var(--card-background-color, white);
          border-radius: 8px;
          padding: 24px;
          min-width: 400px;
          max-width: 90%;
        }
        .dialog h2 {
          margin-top: 0;
        }
        .dialog-actions {
          display: flex;
          justify-content: flex-end;
          gap: 8px;
          margin-top: 24px;
        }
        input, textarea {
          width: 100%;
          padding: 8px;
          border: 1px solid var(--divider-color, #e0e0e0);
          border-radius: 4px;
          font-size: 14px;
          box-sizing: border-box;
        }
        input:focus, textarea:focus {
          outline: none;
          border-color: var(--primary-color, #03a9f4);
        }
        .form-group {
          margin-bottom: 16px;
        }
        .form-group label {
          display: block;
          margin-bottom: 4px;
          font-size: 14px;
          font-weight: 500;
        }
        select {
          width: 100%;
          padding: 8px;
          border: 1px solid var(--divider-color, #e0e0e0);
          border-radius: 4px;
          font-size: 14px;
        }
        .loading {
          text-align: center;
          padding: 24px;
          color: var(--secondary-text-color, #757575);
        }
      </style>
      
      <div class="header">
        <h1>TextNow Contacts</h1>
        <span class="status ${this.entryId ? 'loaded' : 'unavailable'}">
          ${this.entryId ? 'Loaded' : 'Unavailable'}
        </span>
      </div>

      ${this.error ? `<div class="error">${this.error}</div>` : ''}

      ${this.loading && this.contacts.length === 0 ? `
        <div class="loading">Loading contacts...</div>
      ` : `
        <div class="actions">
          <button data-action="add-contact">Add Contact</button>
          <button data-action="test-message">Send Test Message</button>
        </div>

        ${this.contacts.length === 0 ? `
          <div class="empty-state">
            No contacts added yet. Click "Add Contact" to get started.
          </div>
        ` : `
          <table class="contacts-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Phone</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              ${this.contacts.map(contact => `
                <tr>
                  <td>${this.escapeHtml(contact.name)}</td>
                  <td>${this.escapeHtml(contact.phone)}</td>
                  <td>
                    <button data-action="edit" data-contact-id="${contact.id}">Edit</button>
                    <button class="danger" data-action="delete" data-contact-id="${contact.id}">Delete</button>
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        `}
      `}

      ${this.showAddDialog ? this.renderAddDialog() : ''}
      ${this.editingContact ? this.renderEditDialog() : ''}
      ${this.showTestDialog ? this.renderTestDialog() : ''}
    `;

    this.shadowRoot.innerHTML = html;
    
    // Attach event listeners
    this.attachEventListeners();
  }

  renderAddDialog() {
    return `
      <div class="dialog-overlay" data-action="close-dialog" data-dialog="add">
        <div class="dialog">
          <h2>Add Contact</h2>
          <div class="form-group">
            <label>Name</label>
            <input type="text" id="add-name" value="${this.escapeHtml(this.newContact.name)}">
          </div>
          <div class="form-group">
            <label>Phone (+1 followed by 10 digits)</label>
            <input type="text" id="add-phone" value="${this.escapeHtml(this.newContact.phone)}" 
                   pattern="[+0-9]*" maxlength="13">
            <small>Enter +1XXXXXXXXXX or XXXXXXXXXX (10 digits)</small>
          </div>
          <div class="dialog-actions">
            <button data-action="cancel-add">Cancel</button>
            <button data-action="save-add">Save</button>
          </div>
        </div>
      </div>
    `;
  }

  renderEditDialog() {
    const contact = this.contacts.find(c => 
      c.name === this.editingContact.name || 
      c.phone.replace('+1', '') === this.editingContact.phone
    );
    if (!contact) {
      this.editingContact = null;
      this.update();
      return '';
    }

    return `
      <div class="dialog-overlay" data-action="close-dialog" data-dialog="edit">
        <div class="dialog">
          <h2>Edit Contact</h2>
          <div class="form-group">
            <label>Name</label>
            <input type="text" id="edit-name" value="${this.escapeHtml(this.editingContact.name)}">
          </div>
          <div class="form-group">
            <label>Phone (+1 followed by 10 digits)</label>
            <input type="text" id="edit-phone" value="${this.escapeHtml(this.editingContact.phone)}" 
                   pattern="[+0-9]*" maxlength="13">
            <small>Enter +1XXXXXXXXXX or XXXXXXXXXX (10 digits)</small>
          </div>
          <div class="dialog-actions">
            <button data-action="cancel-edit">Cancel</button>
            <button data-action="save-edit" data-contact-id="${contact.id}">Save</button>
          </div>
        </div>
      </div>
    `;
  }

  renderTestDialog() {
    return `
      <div class="dialog-overlay" data-action="close-dialog" data-dialog="test">
        <div class="dialog">
          <h2>Send Test Message</h2>
          <div class="form-group">
            <label>Contact</label>
            <select id="test-contact">
              <option value="">Select a contact</option>
              ${this.contacts.map(contact => `
                <option value="${contact.id}" ${contact.id === this.testMessage.contactId ? 'selected' : ''}>
                  ${this.escapeHtml(contact.name)} (${this.escapeHtml(contact.phone)})
                </option>
              `).join('')}
            </select>
          </div>
          <div class="form-group">
            <label>Message</label>
            <textarea id="test-message" rows="4">${this.escapeHtml(this.testMessage.message)}</textarea>
          </div>
          <div class="dialog-actions">
            <button data-action="cancel-test">Cancel</button>
            <button data-action="send-test">Send</button>
          </div>
        </div>
      </div>
    `;
  }

  attachEventListeners() {
    // Event delegation for buttons and inputs
    this.shadowRoot.addEventListener('click', (e) => {
      const target = e.target;
      const action = target.getAttribute('data-action');
      
      if (!action) {
        // Check if clicking dialog overlay
        if (target.classList.contains('dialog-overlay')) {
          const dialog = target.getAttribute('data-dialog');
          if (dialog === 'add') {
            this.showAddDialog = false;
          } else if (dialog === 'edit') {
            this.editingContact = null;
          } else if (dialog === 'test') {
            this.showTestDialog = false;
          }
          this.update();
        }
        return;
      }

      switch (action) {
        case 'add-contact':
          this.showAddDialog = true;
          this.update();
          break;
        case 'test-message':
          this.showTestDialog = true;
          this.update();
          break;
        case 'edit':
          const editContactId = target.getAttribute('data-contact-id');
          const contact = this.contacts.find(c => c.id === editContactId);
          if (contact) {
            this.editingContact = {
              name: contact.name,
              phone: contact.phone.replace('+1', ''),
            };
            this.update();
          }
          break;
        case 'delete':
          const deleteContactId = target.getAttribute('data-contact-id');
          this.deleteContact(deleteContactId);
          break;
        case 'save-add':
          const addName = this.shadowRoot.getElementById('add-name')?.value || '';
          const addPhone = this.shadowRoot.getElementById('add-phone')?.value || '';
          this.newContact = { name: addName, phone: addPhone };
          this.addContact();
          break;
        case 'cancel-add':
          this.showAddDialog = false;
          this.newContact = { name: '', phone: '' };
          this.update();
          break;
        case 'save-edit':
          const editContactId2 = target.getAttribute('data-contact-id');
          const editName = this.shadowRoot.getElementById('edit-name')?.value || '';
          const editPhone = this.shadowRoot.getElementById('edit-phone')?.value || '';
          this.editingContact = { name: editName, phone: editPhone };
          this.updateContact(editContactId2);
          break;
        case 'cancel-edit':
          this.editingContact = null;
          this.update();
          break;
        case 'send-test':
          const testContact = this.shadowRoot.getElementById('test-contact')?.value || '';
          const testMessage = this.shadowRoot.getElementById('test-message')?.value || '';
          this.testMessage = { contactId: testContact, message: testMessage };
          this.sendTestMessage();
          break;
        case 'cancel-test':
          this.showTestDialog = false;
          this.testMessage = { contactId: '', message: '' };
          this.update();
          break;
      }
    });

    // Handle input changes for test dialog
    this.shadowRoot.addEventListener('change', (e) => {
      if (e.target.id === 'test-contact') {
        this.testMessage.contactId = e.target.value;
      }
    });

    this.shadowRoot.addEventListener('input', (e) => {
      if (e.target.id === 'test-message') {
        this.testMessage.message = e.target.value;
      }
    });
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
}

customElements.define('textnow-panel', TextNowPanel);


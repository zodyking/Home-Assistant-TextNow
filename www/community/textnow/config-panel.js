// TextNow Config Panel
class TextNowConfigPanel extends HTMLElement {
  constructor() {
    super();
    this.entryId = null;
    this.contacts = [];
  }

  setConfig(config) {
    this.entryId = config.entry_id;
    this.loadData();
  }

  async loadData() {
    try {
      const response = await fetch(`/api/textnow/config?entry_id=${this.entryId}`);
      const data = await response.json();
      
      this.config = data;
      this.contacts = data.contacts || {};
      this.render();
    } catch (error) {
      console.error("Error loading config:", error);
    }
  }

  render() {
    this.innerHTML = `
      <ha-card header="TextNow Configuration">
        <div class="card-content">
          <div class="section">
            <h3>Account Settings</h3>
            <div class="form-group">
              <label>Username:</label>
              <span>${this.config?.username || "N/A"}</span>
            </div>
            <div class="form-group">
              <label>Polling Interval:</label>
              <span>${this.config?.polling_interval || 30} seconds</span>
            </div>
            <div class="form-group">
              <label>Allowed Phones:</label>
              <span>${(this.config?.allowed_phones || []).join(", ") || "None"}</span>
            </div>
            <mwc-button onclick="window.open('/config/integrations/integration/${this.entryId}', '_blank')">
              Edit Settings
            </mwc-button>
          </div>

          <div class="section">
            <h3>Contacts</h3>
            <div id="contacts-list"></div>
            <mwc-button id="add-contact-btn" raised>
              Add Contact
            </mwc-button>
          </div>
        </div>
      </ha-card>
    `;

    this.renderContacts();
    this.attachEventListeners();
  }

  renderContacts() {
    const list = this.shadowRoot?.getElementById("contacts-list") || 
                 this.querySelector("#contacts-list");
    
    if (!list) return;

    if (Object.keys(this.contacts).length === 0) {
      list.innerHTML = "<p>No contacts added yet.</p>";
      return;
    }

    list.innerHTML = Object.entries(this.contacts).map(([id, contact]) => `
      <div class="contact-item">
        <div>
          <strong>${contact.name}</strong><br>
          <small>${contact.phone}</small>
        </div>
        <div>
          <mwc-icon-button icon="edit" data-id="${id}"></mwc-icon-button>
          <mwc-icon-button icon="delete" data-id="${id}"></mwc-icon-button>
        </div>
      </div>
    `).join("");
  }

  attachEventListeners() {
    // Add contact button
    const addBtn = this.shadowRoot?.getElementById("add-contact-btn") ||
                   this.querySelector("#add-contact-btn");
    if (addBtn) {
      addBtn.addEventListener("click", () => this.showAddContactDialog());
    }

    // Edit/Delete buttons
    const buttons = this.shadowRoot?.querySelectorAll("mwc-icon-button") ||
                    this.querySelectorAll("mwc-icon-button");
    buttons?.forEach(btn => {
      btn.addEventListener("click", (e) => {
        const id = e.target.closest("mwc-icon-button")?.dataset.id;
        const action = e.target.closest("mwc-icon-button")?.icon;
        if (action === "edit") {
          this.editContact(id);
        } else if (action === "delete") {
          this.deleteContact(id);
        }
      });
    });
  }

  showAddContactDialog() {
    // Simple prompt for now - can be enhanced with a proper dialog
    const name = prompt("Contact Name:");
    if (!name) return;
    
    const phone = prompt("Phone Number:");
    if (!phone) return;

    this.addContact(name, phone);
  }

  async addContact(name, phone) {
    const contactId = `contact_${name.toLowerCase().replace(/\s+/g, "_")}`;
    
    try {
      const response = await fetch("/api/textnow/config", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          entry_id: this.entryId,
          action: "add_contact",
          contact_id: contactId,
          name: name,
          phone: phone,
        }),
      });

      if (response.ok) {
        await this.loadData();
      }
    } catch (error) {
      console.error("Error adding contact:", error);
    }
  }

  async deleteContact(contactId) {
    if (!confirm("Delete this contact?")) return;

    try {
      const response = await fetch("/api/textnow/config", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          entry_id: this.entryId,
          action: "delete_contact",
          contact_id: contactId,
        }),
      });

      if (response.ok) {
        await this.loadData();
      }
    } catch (error) {
      console.error("Error deleting contact:", error);
    }
  }

  editContact(contactId) {
    const contact = this.contacts[contactId];
    if (!contact) return;

    const name = prompt("Contact Name:", contact.name);
    if (!name) return;

    const phone = prompt("Phone Number:", contact.phone);
    if (!phone) return;

    this.updateContact(contactId, name, phone);
  }

  async updateContact(contactId, name, phone) {
    try {
      const response = await fetch("/api/textnow/config", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          entry_id: this.entryId,
          action: "update_contact",
          contact_id: contactId,
          name: name,
          phone: phone,
        }),
      });

      if (response.ok) {
        await this.loadData();
      }
    } catch (error) {
      console.error("Error updating contact:", error);
    }
  }
}

customElements.define("textnow-config-panel", TextNowConfigPanel);


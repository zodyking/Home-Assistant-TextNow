// TextNow Contact Management Panel
import { html, LitElement } from "lit";
import { customElement, property, state } from "lit/decorators.js";

@customElement("textnow-panel")
class TextNowPanel extends LitElement {
  @property({ type: Object }) hass;
  @property({ type: Boolean }) narrow;
  @state() contacts = {};
  @state() entryId = null;
  @state() loading = true;
  @state() showAddDialog = false;
  @state() editingContact = null;
  @state() newContact = { name: "", phone: "" };

  async firstUpdated() {
    await this.loadContacts();
  }

  async loadContacts() {
    this.loading = true;
    try {
      // Get the first TextNow config entry
      const entries = Object.values(this.hass.configEntries.entries).filter(
        (entry) => entry.domain === "textnow"
      );
      
      if (entries.length === 0) {
        this.loading = false;
        return;
      }

      this.entryId = entries[0].entry_id;
      const response = await fetch(`/api/textnow/config?entry_id=${this.entryId}`);
      const data = await response.json();
      this.contacts = data.contacts || {};
    } catch (error) {
      console.error("Error loading contacts:", error);
    } finally {
      this.loading = false;
    }
  }

  formatPhone(phone) {
    // Remove +1 prefix for display
    return phone ? phone.replace("+1", "") : "";
  }

  async addContact() {
    if (!this.newContact.name || !this.newContact.phone) {
      alert("Name and phone are required");
      return;
    }

    try {
      const contactId = `contact_${this.newContact.name.toLowerCase().replace(/\s+/g, "_")}`;
      const response = await fetch("/api/textnow/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          entry_id: this.entryId,
          action: "add_contact",
          contact_id: contactId,
          name: this.newContact.name,
          phone: this.newContact.phone,
        }),
      });

      const result = await response.json();
      if (result.success) {
        this.showAddDialog = false;
        this.newContact = { name: "", phone: "" };
        await this.loadContacts();
      } else {
        alert(result.error || "Failed to add contact");
      }
    } catch (error) {
      alert("Error adding contact: " + error.message);
    }
  }

  async deleteContact(contactId) {
    if (!confirm("Delete this contact?")) return;

    try {
      const response = await fetch("/api/textnow/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          entry_id: this.entryId,
          action: "delete_contact",
          contact_id: contactId,
        }),
      });

      const result = await response.json();
      if (result.success) {
        await this.loadContacts();
      } else {
        alert(result.error || "Failed to delete contact");
      }
    } catch (error) {
      alert("Error deleting contact: " + error.message);
    }
  }

  async updateContact(contactId) {
    const contact = this.contacts[contactId];
    if (!contact) return;

    try {
      const response = await fetch("/api/textnow/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          entry_id: this.entryId,
          action: "update_contact",
          contact_id: contactId,
          name: contact.name,
          phone: contact.phone,
        }),
      });

      const result = await response.json();
      if (result.success) {
        this.editingContact = null;
        await this.loadContacts();
      } else {
        alert(result.error || "Failed to update contact");
      }
    } catch (error) {
      alert("Error updating contact: " + error.message);
    }
  }

  render() {
    if (this.loading) {
      return html`<ha-card><div class="card-content">Loading...</div></ha-card>`;
    }

    return html`
      <ha-app-layout>
        <app-header slot="header" fixed>
          <app-toolbar>
            <ha-menu-button .hass=${this.hass} .narrow=${this.narrow}></ha-menu-button>
            <div main-title>TextNow Contacts</div>
          </app-toolbar>
        </app-header>

        <div class="content">
          <ha-card>
            <div class="card-content">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                <h2>Contacts</h2>
                <mwc-button raised @click=${() => (this.showAddDialog = true)}>
                  Add Contact
                </mwc-button>
              </div>

              ${Object.keys(this.contacts).length === 0
                ? html`<p>No contacts added yet.</p>`
                : html`
                    <div class="contacts-list">
                      ${Object.entries(this.contacts).map(
                        ([id, contact]) => html`
                          <div class="contact-item">
                            <div>
                              <strong>${contact.name}</strong><br>
                              <small>${contact.phone}</small>
                            </div>
                            <div>
                              <mwc-icon-button
                                icon="edit"
                                @click=${() => (this.editingContact = id)}
                              ></mwc-icon-button>
                              <mwc-icon-button
                                icon="delete"
                                @click=${() => this.deleteContact(id)}
                              ></mwc-icon-button>
                            </div>
                          </div>
                        `
                      )}
                    </div>
                  `}
            </div>
          </ha-card>
        </div>
      </ha-app-layout>

      ${this.showAddDialog
        ? html`
            <ha-dialog
              open
              .heading=${"Add Contact"}
              @closed=${() => (this.showAddDialog = false)}
            >
              <div class="form-content">
                <paper-input
                  label="Name"
                  .value=${this.newContact.name}
                  @value-changed=${(e) => (this.newContact.name = e.detail.value)}
                ></paper-input>
                <paper-input
                  label="Phone (10 digits)"
                  .value=${this.newContact.phone}
                  @value-changed=${(e) => (this.newContact.phone = e.detail.value)}
                  pattern="[0-9]*"
                ></paper-input>
                <small>Phone will be formatted as +1XXXXXXXXXX</small>
              </div>
              <mwc-button slot="primaryAction" @click=${this.addContact}>
                Add
              </mwc-button>
              <mwc-button slot="secondaryAction" dialogAction="cancel">
                Cancel
              </mwc-button>
            </ha-dialog>
          `
        : ""}
    `;
  }

  static get styles() {
    return `
      .content {
        padding: 16px;
      }
      .contacts-list {
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      .contact-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px;
        border: 1px solid var(--divider-color);
        border-radius: 4px;
      }
      .form-content {
        padding: 16px;
      }
    `;
  }
}


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
      // Get entry ID from config entries
      const entries = await this.hass.callApi("GET", "config/config_entries/entry");
      const textnowEntry = entries.find((e) => e.domain === "textnow");

      if (!textnowEntry) {
        this.contacts = {};
        this.loading = false;
        return;
      }

      this.entryId = textnowEntry.entry_id;
      
      // Get contacts using authenticated API call
      const data = await this.hass.callApi(
        "GET",
        `textnow/config?entry_id=${this.entryId}`
      );
      this.contacts = data.contacts || {};
    } catch (error) {
      console.error("Error loading contacts:", error);
      this.contacts = {};
    } finally {
      this.loading = false;
    }
  }

  async addContact() {
    const name = this.newContact.name.trim();
    let phone = this.newContact.phone.trim();

    if (!name || !phone) {
      alert("Name and phone are required");
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
      alert("Phone number must be 10 digits (with or without +1 prefix)");
      return;
    }

    // Use the cleaned phone number (backend will add +1)
    phone = phone;

    try {
      let contactId = `contact_${name.toLowerCase().replace(/\s+/g, "_")}`;
      
      // Ensure unique contact_id
      let counter = 1;
      const originalId = contactId;
      while (contactId in this.contacts) {
        contactId = `${originalId}_${counter}`;
        counter += 1;
      }

      await this.hass.callApi("POST", "textnow/config", {
        entry_id: this.entryId,
        action: "add_contact",
        contact_id: contactId,
        name: name,
        phone: phone,
      });

      this.showAddDialog = false;
      this.newContact = { name: "", phone: "" };
      await this.loadContacts();
    } catch (error) {
      alert("Error adding contact: " + error.message);
    }
  }

  async updateContact(contactId) {
    const name = this.editingContact.name.trim();
    let phone = this.editingContact.phone.trim();

    if (!name || !phone) {
      alert("Name and phone are required");
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
      alert("Phone number must be 10 digits (with or without +1 prefix)");
      return;
    }

    // Use the cleaned phone number (backend will add +1)
    phone = phone;

    try {
      await this.hass.callApi("POST", "textnow/config", {
        entry_id: this.entryId,
        action: "update_contact",
        contact_id: contactId,
        name: name,
        phone: phone,
      });

      this.editingContact = null;
      await this.loadContacts();
    } catch (error) {
      alert("Error updating contact: " + error.message);
    }
  }

  async deleteContact(contactId) {
    if (!confirm("Delete this contact?")) return;

    try {
      await this.hass.callApi("POST", "textnow/config", {
        entry_id: this.entryId,
        action: "delete_contact",
        contact_id: contactId,
      });

      await this.loadContacts();
    } catch (error) {
      alert("Error deleting contact: " + error.message);
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
            <ha-menu-button
              .hass=${this.hass}
              .narrow=${this.narrow}
            ></ha-menu-button>
            <div main-title>TextNow Contacts</div>
          </app-toolbar>
        </app-header>

        <div class="content">
          <ha-card>
            <div class="card-content">
              <div
                style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;"
              >
                <h2>Contacts</h2>
                <mwc-button raised @click=${() => (this.showAddDialog = true)}>
                  Add Contact
                </mwc-button>
              </div>

              ${Object.keys(this.contacts).length === 0
                ? html`<div class="empty-state">
                    No contacts added yet. Click "Add Contact" to get started.
                  </div>`
                : html`
                    <div class="contact-list">
                      ${Object.entries(this.contacts).map(
                        ([id, contact]) => html`
                          <div class="contact-card">
                            <div class="contact-info">
                              <h3>${contact.name}</h3>
                              <p>${contact.phone}</p>
                            </div>
                            <div class="contact-actions">
                              <mwc-button
                                @click=${() => {
                                  this.editingContact = {
                                    name: contact.name,
                                    phone: contact.phone.replace("+1", ""),
                                  };
                                }}
                              >
                                Edit
                              </mwc-button>
                              <mwc-button
                                class="danger"
                                @click=${() => this.deleteContact(id)}
                              >
                                Delete
                              </mwc-button>
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

      <!-- Add Dialog -->
      ${this.showAddDialog
        ? html`
            <ha-dialog
              open
              @closed=${() => (this.showAddDialog = false)}
              .heading=${"Add Contact"}
            >
              <div>
                <ha-textfield
                  label="Name"
                  .value=${this.newContact.name}
                  @input=${(e) => (this.newContact.name = e.target.value)}
                ></ha-textfield>
                <ha-textfield
                  label="Phone (+1 followed by 10 digits)"
                  .value=${this.newContact.phone}
                  @input=${(e) => (this.newContact.phone = e.target.value)}
                  pattern="[+0-9]*"
                  maxlength="13"
                  helper="Enter +1XXXXXXXXXX or XXXXXXXXXX (10 digits)"
                ></ha-textfield>
              </div>
              <mwc-button slot="primaryAction" @click=${this.addContact}>
                Save
              </mwc-button>
              <mwc-button slot="secondaryAction" @click=${() => (this.showAddDialog = false)}>
                Cancel
              </mwc-button>
            </ha-dialog>
          `
        : ""}

      <!-- Edit Dialog -->
      ${this.editingContact
        ? html`
            <ha-dialog
              open
              @closed=${() => (this.editingContact = null)}
              .heading=${"Edit Contact"}
            >
              <div>
                <ha-textfield
                  label="Name"
                  .value=${this.editingContact.name}
                  @input=${(e) => (this.editingContact.name = e.target.value)}
                ></ha-textfield>
                <ha-textfield
                  label="Phone (+1 followed by 10 digits)"
                  .value=${this.editingContact.phone}
                  @input=${(e) => (this.editingContact.phone = e.target.value)}
                  pattern="[+0-9]*"
                  maxlength="13"
                  helper="Enter +1XXXXXXXXXX or XXXXXXXXXX (10 digits)"
                ></ha-textfield>
              </div>
              <mwc-button
                slot="primaryAction"
                @click=${() =>
                  this.updateContact(
                    Object.keys(this.contacts).find(
                      (id) => this.contacts[id].name === this.editingContact.name
                    )
                  )}
              >
                Save
              </mwc-button>
              <mwc-button
                slot="secondaryAction"
                @click=${() => (this.editingContact = null)}
              >
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
      .contact-list {
        display: grid;
        gap: 16px;
      }
      .contact-card {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 16px;
      }
      .contact-info h3 {
        margin: 0 0 8px 0;
      }
      .contact-info p {
        margin: 0;
        color: var(--secondary-text-color);
      }
      .contact-actions {
        display: flex;
        gap: 8px;
      }
      .empty-state {
        text-align: center;
        padding: 48px;
        color: var(--secondary-text-color);
      }
      ha-textfield {
        display: block;
        margin-bottom: 16px;
      }
    `;
  }
}


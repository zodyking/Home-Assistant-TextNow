# TextNow Home Assistant Integration

<div align="center">

![Home Assistant TextNow Integration](images/banner.png)

</div>

A lightweight Home Assistant integration for sending and receiving SMS messages through TextNow.

## Features

- Send SMS messages to contacts
- Receive SMS messages (automatic polling)
- Contact management via integration options
- Sensor entities per contact with message history
- Event-driven automations

## Installation

### HACS

1. Open HACS → Integrations
2. Click ⋮ → Custom repositories
3. Add: `https://github.com/zodyking/Home-Assistant-TextNow`
4. Category: Integration
5. Install → Restart Home Assistant

### Manual

1. Copy `textnow` folder to `config/custom_components/textnow/`
2. Restart Home Assistant
3. Settings → Devices & Services → Add Integration → TextNow

## Configuration

### Initial Setup

You need three pieces of information from your TextNow account:

#### Step 1: Get Your Username

1. Go to [textnow.com](https://www.textnow.com) and sign in
2. Go to Settings page
3. Your username is displayed on the settings page (this is NOT your email address)

#### Step 2: Get connect.sid Cookie

1. While logged into TextNow, press **F12** to open browser DevTools
2. Click the **Network** tab
3. Refresh the page (F5)
4. In the Network tab, click on any request (like `consent-token` or a request with your username)
5. In the **Request Headers** section, find the **Cookie** field
6. Look for `connect.sid=` in the cookie string
7. Copy everything after the `=` sign up to (but not including) the `;` semicolon

**Example:** If you see `connect.sid=abc123xyz; other=value`, copy only `abc123xyz`

#### Step 3: Get _csrf Cookie

1. In the same **Cookie** field from Step 2, look for `_csrf=`
2. Copy everything after the `=` sign up to (but not including) the `;` semicolon

**Example:** If you see `_csrf=xyz789abc; other=value`, copy only `xyz789abc`

#### Step 4: Enter in Home Assistant

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for **TextNow**
3. Enter your username, connect.sid cookie value, and _csrf cookie value
4. Complete the setup

### Options

After initial setup, you can configure:

- **Polling Interval**: How often to check for new messages (default: 30 seconds)
- **Allowed Phones**: Phone number allowlist for security (optional)
- **Contacts**: Add/edit/delete contacts with name and phone number

### Managing Contacts

1. Settings → Devices & Services → TextNow → Options → Contacts
2. Add contact: Name + Phone number (10 digits)
3. Phone numbers auto-format to `+1XXXXXXXXXX`
4. Each contact creates: `sensor.textnow_<contact_name>`

## Usage

### Service: `textnow.send`

Send an SMS message to a contact.

**Service Data:**
- `contact_id` (required) - Select contact entity from dropdown (e.g., `sensor.textnow_brandon`)
- `message` (required) - Message text (multiline supported)

**In Automation UI:**
1. Add action: TextNow: Send Message
2. Select contact from dropdown
3. Enter message
4. Save

### Event: `textnow_message_received`

Fired when a new message is received. Use this event as a trigger in automations.

**Event Data:**
- `phone` - Phone number of sender
- `text` - Message text content
- `message_id` - Unique message ID
- `timestamp` - ISO timestamp
- `contact_id` - Contact identifier

**Automation Trigger:**
Use `textnow_message_received` as an event trigger to react to incoming messages.

### Sensor Entities

Each contact has a sensor: `sensor.textnow_<contact_name>`

**State:** Displays the last received message text (or "No messages" if none)

**Attributes:**
- `phone` - Phone number
- `last_inbound` - Last received message text
- `last_inbound_ts` - Timestamp of last received message
- `last_outbound` - Status of last sent message
- `last_outbound_ts` - Timestamp of last sent message

## Examples

### Send SMS on Button Press

Create an automation that sends an SMS when a button is pressed.

**Trigger:** Button state change  
**Action:** TextNow: Send Message

### Auto-Reply to Messages

Create an automation that automatically replies to incoming messages.

**Trigger:** `textnow_message_received` event  
**Action:** TextNow: Send Message (use `{{ trigger.event.data.contact_id }}` for contact)

### Alert When Door Opens

Create an automation that sends an SMS alert when a door sensor opens.

**Trigger:** Door sensor state change  
**Action:** TextNow: Send Message

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Messages not received | Check `allowed_phones` list in Options |
| Contact not found | Verify contact exists in Options → Contacts |
| Authentication errors | Re-copy cookies from browser (they expire periodically) |
| Service GUI not showing | Clear browser cache, restart Home Assistant |
| API errors | Check Home Assistant logs for detailed error messages |
| Cookie copy issues | Make sure you copy only the value between `=` and `;`, not including the semicolon |

## Requirements

- Home Assistant 2023.1.0 or later
- Valid TextNow account with active session cookies
- Internet connection

## Security

- **Phone Allowlist**: Configure in Options to only process messages from allowed numbers
- **Cookie Security**: Cookies provide full account access - store securely
- **Local Storage**: All data stored locally in Home Assistant

## Support

- **Issues**: [GitHub Issues](https://github.com/zodyking/Home-Assistant-TextNow/issues)

---

Made with ❤️ for the Home Assistant community

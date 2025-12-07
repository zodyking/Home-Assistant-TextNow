# TextNow Home Assistant Integration

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

1. **Username**: Your TextNow account username
2. **connect.sid Cookie**: 
   - Open browser DevTools (F12) → Application → Cookies → `https://www.textnow.com`
   - Copy `connect.sid` value
3. **_csrf Cookie**: Copy `_csrf` value from same location

### Options

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

Send an SMS message.

**Service Data:**
- `contact_id` (required) - Select contact entity (e.g., `sensor.textnow_brandon`)
- `message` (required) - Message text (multiline supported)

**YAML Example:**
```yaml
service: textnow.send
data:
  contact_id: sensor.textnow_brandon
  message: "Hello from Home Assistant!"
```

**Automation UI:**
1. Add action: TextNow: Send Message
2. Select contact from dropdown
3. Enter message
4. Save

### Event: `textnow_message_received`

Fired when a new message is received.

**Event Data:**
- `phone` - Phone number
- `text` - Message text
- `message_id` - Unique message ID
- `timestamp` - ISO timestamp
- `contact_id` - Contact identifier

**Automation Example:**
```yaml
automation:
  - alias: "Notify on TextNow Message"
    trigger:
      - platform: event
        event_type: textnow_message_received
    action:
      - service: notify.mobile_app
        data:
          title: "New TextNow Message"
          message: "{{ trigger.event.data.text }}"
```

### Sensor Entities

Each contact has a sensor: `sensor.textnow_<contact_name>`

**State:** Last received message text (or "No messages")

**Attributes:**
- `phone` - Phone number
- `last_inbound` - Last received message text
- `last_inbound_ts` - Timestamp of last received message
- `last_outbound` - Status of last sent message
- `last_outbound_ts` - Timestamp of last sent message
- `pending` - Dictionary (legacy, not used)
- `context` - Dictionary (legacy, not used)

## Examples

### Send SMS on Button Press
```yaml
automation:
  - alias: "TextNow - Button Alert"
    trigger:
      - platform: state
        entity_id: input_button.send_alert
        to: "pressed"
    action:
      - service: textnow.send
        data:
          contact_id: sensor.textnow_brandon
          message: "Button was pressed at {{ now() }}"
```

### Auto-Reply to Messages
```yaml
automation:
  - alias: "TextNow - Auto Reply"
    trigger:
      - platform: event
        event_type: textnow_message_received
    action:
      - service: textnow.send
        data:
          contact_id: "{{ trigger.event.data.contact_id }}"
          message: "Thanks for your message!"
```

### Alert When Door Opens
```yaml
automation:
  - alias: "TextNow - Door Alert"
    trigger:
      - platform: state
        entity_id: binary_sensor.front_door
        to: "on"
    action:
      - service: textnow.send
        data:
          contact_id: sensor.textnow_brandon
          message: "🚨 Front door opened!"
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Messages not received | Check `allowed_phones` list in Options |
| Contact not found | Verify contact exists in Options → Contacts |
| Authentication errors | Re-copy cookies from browser (they expire) |
| Service GUI not showing | Clear browser cache, restart Home Assistant |
| API errors | Check Home Assistant logs |

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

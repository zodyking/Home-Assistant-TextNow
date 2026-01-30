# TextNow Home Assistant Integration

<div align="center">

![Home Assistant TextNow Integration](images/banner.png)

**Send SMS, MMS, and voice messages through TextNow. Create interactive SMS menus for home automation control.**

[![GitHub Release](https://img.shields.io/github/v/release/zodyking/Home-Assistant-TextNow?style=flat-square)](https://github.com/zodyking/Home-Assistant-TextNow/releases)
[![License](https://img.shields.io/github/license/zodyking/Home-Assistant-TextNow?style=flat-square)](LICENSE)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg?style=flat-square)](https://hacs.xyz)

</div>

---

## Features

- **Send SMS Messages** - Text any phone number through your TextNow account
- **Send MMS Messages** - Send images with optional captions
- **Send Voice Messages** - Send audio recordings as voice messages
- **Interactive SMS Menus** - Send numbered menus and wait for user selection
- **Message Triggers** - Trigger automations when messages are received
- **Phrase Detection** - Trigger automations when specific phrases are received
- **Contact Management** - Manage contacts through the integration UI
- **Sensor Entities** - Track message history per contact

---

## Table of Contents

- [Installation](#installation)
- [Configuration](#configuration)
- [Services](#services)
  - [Send Message](#service-textnowsend)
  - [Send Menu](#service-textnowsend_menu)
- [Triggers](#triggers)
  - [SMS Message Received](#trigger-sms-message-received)
  - [Phrase Received](#trigger-phrase-received)
- [Automation Examples](#automation-examples)
- [Sensor Entities](#sensor-entities)
- [Troubleshooting](#troubleshooting)

---

## Installation

### HACS (Recommended)

1. Open HACS → Integrations
2. Click ⋮ → **Custom repositories**
3. Add: `https://github.com/zodyking/Home-Assistant-TextNow`
4. Category: **Integration**
5. Click **Install** → Restart Home Assistant

### Manual Installation

1. Download the `textnow` folder from this repository
2. Copy to `config/custom_components/textnow/`
3. Restart Home Assistant
4. Go to Settings → Devices & Services → Add Integration → **TextNow**

---

## Configuration

### Initial Setup

You need your TextNow credentials from the browser:

#### Step 1: Get Your Username

1. Go to [textnow.com](https://www.textnow.com) and sign in
2. Go to **Settings** page
3. Your username is displayed (this is NOT your email address)

#### Step 2: Get Cookies from Browser

1. While logged into TextNow, press **F12** to open DevTools
2. Click the **Network** tab → Refresh the page (F5)
3. Click any request → Find the **Cookie** header
4. Copy these cookie values:
   - `connect.sid` - Session cookie
   - `_csrf` - CSRF token
   - `XSRF-TOKEN` - XSRF token (if present)

> **Tip:** Copy the entire cookie string and paste it in the setup - the integration will parse it automatically.

#### Step 3: Add Integration

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for **TextNow**
3. Enter your username and cookie values
4. Complete the setup

### Managing Contacts

1. Settings → Devices & Services → TextNow → **Configure**
2. Add contacts with Name and Phone Number (10 digits)
3. Phone numbers auto-format to `+1XXXXXXXXXX`
4. Each contact creates a sensor: `sensor.textnow_<contact_name>`

---

## Services

### Service: `textnow.send`

Send an SMS, MMS, or voice message to a contact.

| Field | Required | Description |
|-------|----------|-------------|
| `contact_id` | Yes | Contact entity (e.g., `sensor.textnow_john`) |
| `message` | No* | Text message content |
| `mms_image` | No* | Path to image file for MMS |
| `voice_audio` | No* | Path to audio file for voice message |

*At least one of `message`, `mms_image`, or `voice_audio` is required.

**Example - Send SMS:**
```yaml
service: textnow.send
data:
  contact_id: sensor.textnow_john
  message: "Hello from Home Assistant!"
```

**Example - Send MMS with Image:**
```yaml
service: textnow.send
data:
  contact_id: sensor.textnow_john
  message: "Check out this photo!"
  mms_image: /config/www/photo.jpg
```

**Example - Send Voice Message:**
```yaml
service: textnow.send
data:
  contact_id: sensor.textnow_john
  voice_audio: /config/www/recording.mp3
```

---

### Service: `textnow.send_menu`

Send an interactive menu and wait for the user's response. This service **blocks** until a response is received or timeout occurs.

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `contact_id` | Yes | - | Contact entity to send menu to |
| `options` | Yes | - | Menu options (one per line) |
| `include_header` | No | `true` | Show header text |
| `header` | No | "Please select an option:" | Header text |
| `include_footer` | No | `true` | Show footer text |
| `footer` | No | "Reply with the number of your choice" | Footer text |
| `timeout` | No | `30` | Seconds to wait for response |

**Response Variable:**

Use `response_variable` to capture the user's selection:

| Field | Description |
|-------|-------------|
| `option` | Selected option number (1, 2, 3...) |
| `option_index` | Zero-based index (0, 1, 2...) |
| `value` | The text of the selected option |
| `raw_text` | Exact text the user sent |
| `contact_name` | Name of the contact |
| `phone` | Phone number |
| `timed_out` | `true` if no response received |

**Example - Interactive Light Control:**

```yaml
service: textnow.send_menu
data:
  contact_id: sensor.textnow_john
  options: |
    Turn on lights
    Turn off lights
    Dim lights to 50%
response_variable: user_choice
```

The user receives:
```
Please select an option:

1. Turn on lights
2. Turn off lights
3. Dim lights to 50%

Reply with the number of your choice
```

When they reply with "1", `user_choice.option` equals `1`.

---

## Triggers

### Trigger: SMS Message Received

Triggers when **any contact** sends an SMS message.

**Setup in UI:**
1. Create new automation → Add trigger
2. Select **Device** → Choose **TextNow** device
3. Select **"SMS message received"**

**Available Variables:**

| Variable | Description |
|----------|-------------|
| `trigger.event.data.contact_name` | Name of sender |
| `trigger.event.data.text` | Message content |
| `trigger.event.data.phone` | Phone number |
| `trigger.event.data.contact_id` | Contact ID for use with services |

**YAML Example:**
```yaml
trigger:
  - platform: event
    event_type: textnow_message_received
```

---

### Trigger: Phrase Received

Triggers when a message contains a **specific phrase**.

**Setup in UI:**
1. Create new automation → Add trigger
2. Select **Device** → Choose **TextNow** device
3. Select **"Phrase received in SMS"**
4. Enter the phrase to match

**Available Variables:**

Same as [SMS Message Received](#trigger-sms-message-received).

**YAML Example:**
```yaml
trigger:
  - platform: event
    event_type: textnow_message_received
condition:
  - condition: template
    value_template: "{{ 'turn on lights' in trigger.event.data.text | lower }}"
```

---

## Automation Examples

### Example 1: SMS-Controlled Light Menu

When anyone texts you, send them a menu to control lights:

```yaml
automation:
  - alias: "SMS Light Control Menu"
    trigger:
      - platform: event
        event_type: textnow_message_received
    action:
      # Send menu to whoever texted
      - service: textnow.send_menu
        data:
          contact_id: "sensor.textnow_{{ trigger.event.data.contact_id }}"
          header: "🏠 Home Control Menu"
          options: |
            Turn on living room lights
            Turn off living room lights
            Turn on all lights
            Turn off all lights
          footer: "Reply with number (1-4)"
          timeout: 60
        response_variable: choice
      
      # Handle their selection
      - choose:
          - conditions: "{{ choice.option == 1 }}"
            sequence:
              - service: light.turn_on
                target:
                  entity_id: light.living_room
              - service: textnow.send
                data:
                  contact_id: "sensor.textnow_{{ trigger.event.data.contact_id }}"
                  message: "✅ Living room lights turned ON"
          
          - conditions: "{{ choice.option == 2 }}"
            sequence:
              - service: light.turn_off
                target:
                  entity_id: light.living_room
              - service: textnow.send
                data:
                  contact_id: "sensor.textnow_{{ trigger.event.data.contact_id }}"
                  message: "✅ Living room lights turned OFF"
          
          - conditions: "{{ choice.timed_out }}"
            sequence:
              - service: textnow.send
                data:
                  contact_id: "sensor.textnow_{{ trigger.event.data.contact_id }}"
                  message: "⏰ Menu timed out. Text again to start over."
```

---

### Example 2: Phrase-Triggered Automation

Turn on lights when someone texts "lights on":

```yaml
automation:
  - alias: "SMS Phrase - Lights On"
    trigger:
      - platform: event
        event_type: textnow_message_received
    condition:
      - condition: template
        value_template: "{{ 'lights on' in trigger.event.data.text | lower }}"
    action:
      - service: light.turn_on
        target:
          entity_id: light.living_room
      - service: textnow.send
        data:
          contact_id: "sensor.textnow_{{ trigger.event.data.contact_id }}"
          message: "Lights turned on! 💡"
```

---

### Example 3: Send Alert When Door Opens

```yaml
automation:
  - alias: "Door Open SMS Alert"
    trigger:
      - platform: state
        entity_id: binary_sensor.front_door
        to: "on"
    action:
      - service: textnow.send
        data:
          contact_id: sensor.textnow_john
          message: "🚪 Alert: Front door was opened at {{ now().strftime('%I:%M %p') }}"
```

---

### Example 4: Security Camera Snapshot via MMS

```yaml
automation:
  - alias: "Motion Detected - Send Camera Snapshot"
    trigger:
      - platform: state
        entity_id: binary_sensor.front_yard_motion
        to: "on"
    action:
      - service: camera.snapshot
        target:
          entity_id: camera.front_yard
        data:
          filename: /config/www/snapshot.jpg
      - delay: 2  # Wait for snapshot to save
      - service: textnow.send
        data:
          contact_id: sensor.textnow_john
          message: "🚨 Motion detected in front yard!"
          mms_image: /config/www/snapshot.jpg
```

---

### Example 5: Auto-Reply with Status

```yaml
automation:
  - alias: "SMS Auto-Reply with Home Status"
    trigger:
      - platform: event
        event_type: textnow_message_received
    condition:
      - condition: template
        value_template: "{{ 'status' in trigger.event.data.text | lower }}"
    action:
      - service: textnow.send
        data:
          contact_id: "sensor.textnow_{{ trigger.event.data.contact_id }}"
          message: >
            🏠 Home Status Report
            
            🌡️ Temperature: {{ states('sensor.temperature') }}°F
            💡 Lights On: {{ states.light | selectattr('state', 'eq', 'on') | list | count }}
            🔒 Doors Locked: {{ states('lock.front_door') }}
            🚗 Garage: {{ states('cover.garage_door') }}
```

---

## Sensor Entities

Each contact creates a sensor: `sensor.textnow_<contact_name>`

**State:** Last received message text (or "No messages")

**Attributes:**

| Attribute | Description |
|-----------|-------------|
| `phone` | Contact's phone number |
| `last_inbound` | Last received message |
| `last_inbound_ts` | Timestamp of last received message |
| `last_outbound` | Status of last sent message |
| `last_outbound_ts` | Timestamp of last sent message |

---

## Events

### Event: `textnow_message_received`

Fired when a new SMS is received.

**Event Data:**

| Field | Description |
|-------|-------------|
| `phone` | Sender's phone number |
| `text` | Message content |
| `contact_name` | Contact's name |
| `contact_id` | Contact ID |
| `message_id` | Unique message ID |
| `timestamp` | ISO timestamp |

### Event: `textnow_reply_parsed`

Fired when a reply matches a pending menu/prompt expectation.

**Event Data:**

| Field | Description |
|-------|-------------|
| `phone` | Sender's phone number |
| `value` | Parsed value |
| `option_index` | Selected option index |
| `raw_text` | Original message text |

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Messages not received | Check `allowed_phones` in Options, verify phone is in list |
| Contact not found | Verify contact exists in Options → Contacts |
| Authentication errors | Re-copy cookies from browser (they expire) |
| Menu not waiting for response | Increase `timeout` value, check logs for errors |
| MMS not sending | Verify file path is correct, file exists |
| Trigger not firing | Restart Home Assistant after adding triggers |

**View Logs:**
```
Settings → System → Logs → Filter by "textnow"
```

---

## Requirements

- Home Assistant 2023.7.0 or later (for service response variables)
- Valid TextNow account with active session
- Internet connection

---

## Security

- **Phone Allowlist**: Restrict which numbers can trigger automations
- **Cookie Security**: Session cookies provide full account access - keep them secure
- **Local Storage**: All data stored locally in Home Assistant

---

## Support

- **Issues**: [GitHub Issues](https://github.com/zodyking/Home-Assistant-TextNow/issues)
- **Discussions**: [GitHub Discussions](https://github.com/zodyking/Home-Assistant-TextNow/discussions)

---

Made with ❤️ for the Home Assistant community

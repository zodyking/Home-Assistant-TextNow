# TextNow Home Assistant Integration

<div align="center">

![Home Assistant TextNow Integration](images/banner.png)

**Send and receive SMS/MMS messages through TextNow. Create interactive SMS menus for smart home control.**

[![GitHub Release](https://img.shields.io/github/v/release/zodyking/Home-Assistant-TextNow?style=flat-square)](https://github.com/zodyking/Home-Assistant-TextNow/releases)
[![License](https://img.shields.io/github/license/zodyking/Home-Assistant-TextNow?style=flat-square)](LICENSE)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg?style=flat-square)](https://hacs.xyz)

</div>

---

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Initial Configuration](#initial-configuration)
- [Managing Contacts](#managing-contacts)
- [Services Reference](#services-reference)
  - [textnow.send](#textnowsend)
  - [textnow.send_menu](#textnowsend_menu)
- [Triggers Reference](#triggers-reference)
  - [SMS Message Received](#sms-message-received-trigger)
  - [Phrase Received in SMS](#phrase-received-in-sms-trigger)
- [Automation Examples](#automation-examples)
- [Template Variables Reference](#template-variables-reference)
- [Troubleshooting](#troubleshooting)

---

## Features

| Feature | Description |
|---------|-------------|
| **Send SMS** | Send text messages to any phone number |
| **Send MMS** | Send images with optional captions |
| **Send Voice Messages** | Send audio files as voice messages |
| **Interactive Menus** | Send numbered menus, wait for response, take action |
| **Message Triggers** | Trigger automations when ANY contact texts you |
| **Phrase Triggers** | Trigger automations when a specific word/phrase is received |
| **Contact Sensors** | Track message history per contact |

---

## Installation

### HACS Installation (Recommended)

1. Open **HACS** → **Integrations**
2. Click the **⋮** menu → **Custom repositories**
3. Enter URL: `https://github.com/zodyking/Home-Assistant-TextNow`
4. Select Category: **Integration**
5. Click **Add**
6. Find "TextNow" in the list → Click **Download**
7. **Restart Home Assistant**

### Manual Installation

1. Download the `custom_components/textnow` folder from this repository
2. Copy it to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

---

## Initial Configuration

### Step 1: Get Your TextNow Username

1. Go to [textnow.com](https://www.textnow.com) and sign in
2. Click on **Settings** (gear icon)
3. Your username is displayed on the settings page
   - ⚠️ This is your **username**, NOT your email address

### Step 2: Get Your Browser Cookies

1. While logged into TextNow, press **F12** to open Developer Tools
2. Click the **Network** tab
3. Refresh the page (press F5)
4. Click on any network request
5. Look for the **Cookie** header in Request Headers
6. You need these cookie values:
   - `connect.sid` - Your session ID
   - `_csrf` - CSRF token
   - `XSRF-TOKEN` - XSRF token (if present)

**Tip:** You can copy the entire cookie string - the integration will parse it automatically.

### Step 3: Add the Integration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for **TextNow**
4. Enter your username and paste your cookie string
5. Click **Submit**

---

## Managing Contacts

Before you can send messages, you need to add contacts.

### Adding a Contact

1. Go to **Settings** → **Devices & Services** → **TextNow**
2. Click **Configure**
3. Select **Add Contact**
4. Enter:
   - **Name**: Contact's name (e.g., "John")
   - **Phone**: 10-digit phone number (e.g., "5551234567")
5. Click **Submit**

Each contact creates a sensor entity: `sensor.textnow_<name>`

**Example:** Adding contact "John" creates `sensor.textnow_john`

---

## Services Reference

### textnow.send

Send an SMS, MMS, or voice message to a contact.

#### Service Fields

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `contact_id` | **Yes** | Entity | The contact sensor to send to (e.g., `sensor.textnow_john`) |
| `message` | No* | String | Text message content |
| `mms_image` | No* | String | File path to image for MMS |
| `voice_audio` | No* | String | File path to audio for voice message |

*At least one of `message`, `mms_image`, or `voice_audio` is required.

#### Example: Send SMS

**UI Method:**
1. Go to **Developer Tools** → **Services**
2. Select **TextNow: Send Message**
3. Select contact from dropdown
4. Enter message text
5. Click **Call Service**

**YAML Method:**
```yaml
service: textnow.send
data:
  contact_id: sensor.textnow_john
  message: "Hello from Home Assistant!"
```

#### Example: Send MMS (Image)

```yaml
service: textnow.send
data:
  contact_id: sensor.textnow_john
  message: "Check out this photo!"
  mms_image: /config/www/images/photo.jpg
```

Supported image formats: `.jpg`, `.jpeg`, `.png`, `.gif`

#### Example: Send Voice Message

```yaml
service: textnow.send
data:
  contact_id: sensor.textnow_john
  voice_audio: /config/www/audio/message.mp3
```

Supported audio formats: `.mp3`, `.wav`

---

### textnow.send_menu

Send an interactive numbered menu and **wait for the user's response**. This service blocks until a response is received or timeout occurs.

#### Service Fields

| Field | Required | Default | Type | Description |
|-------|----------|---------|------|-------------|
| `contact_id` | **Yes** | - | String | Contact entity or template (e.g., `sensor.textnow_john` or `sensor.textnow_{{ trigger.contact_id }}`) |
| `options` | **Yes** | - | String | Menu options, **one per line** |
| `include_header` | No | `true` | Boolean | Show header text before options |
| `header` | No | "Please select an option:" | String | Header text |
| `include_footer` | No | `true` | Boolean | Show footer text after options |
| `footer` | No | "Reply with the number of your choice" | String | Footer text |
| `timeout` | No | `30` | Number | Seconds to wait for response (5-3600) |
| `number_format` | No | `"{n}. {option}"` | String | Format for each option line |

#### How It Works

1. Service sends the menu as an SMS
2. Service **waits** for the user to reply
3. User replies with a number (1, 2, 3, etc.)
4. Service returns the response as a variable
5. Your automation continues based on their choice

#### The Menu Message

When you call `send_menu`, the user receives a message like:

```
Please select an option:

1. Turn on lights
2. Turn off lights
3. Lock all doors

Reply with the number of your choice
```

#### Response Variable

Use `response_variable` to capture the user's response:

```yaml
service: textnow.send_menu
data:
  contact_id: sensor.textnow_john
  options: |
    Turn on lights
    Turn off lights
response_variable: user_choice
```

The `user_choice` variable contains:

| Field | Type | Description |
|-------|------|-------------|
| `option` | Integer | Selected option number (1, 2, 3...) |
| `option_index` | Integer | Zero-based index (0, 1, 2...) |
| `value` | String | Text of the selected option |
| `raw_text` | String | Exact text the user sent |
| `contact_name` | String | Name of the contact |
| `contact_id` | String | Contact ID |
| `phone` | String | Phone number |
| `timed_out` | Boolean | `true` if no response before timeout |

#### Example: Basic Menu

**In the UI:**
1. Add action → **TextNow: Send Menu**
2. **Contact**: `sensor.textnow_john`
3. **Menu Options**:
   ```
   Turn on lights
   Turn off lights
   Check status
   ```
4. Add a **Choose** action after to handle the response

**In YAML:**
```yaml
service: textnow.send_menu
data:
  contact_id: sensor.textnow_john
  options: |
    Turn on lights
    Turn off lights
    Check status
  timeout: 60
response_variable: choice
```

#### Example: Dynamic Contact (Reply to Sender)

When someone texts you, reply to THEM specifically:

```yaml
service: textnow.send_menu
data:
  contact_id: "sensor.textnow_{{ trigger.contact_id }}"
  options: |
    Turn on lights
    Turn off lights
response_variable: choice
```

The `{{ trigger.contact_id }}` template automatically uses the contact who triggered the automation.

#### Example: Custom Header and Footer

```yaml
service: textnow.send_menu
data:
  contact_id: sensor.textnow_john
  header: "🏠 Smart Home Control"
  options: |
    Living room lights ON
    Living room lights OFF
    Bedroom lights ON
    Bedroom lights OFF
  footer: "Reply 1-4 to select"
  timeout: 120
response_variable: choice
```

#### Example: No Header/Footer

```yaml
service: textnow.send_menu
data:
  contact_id: sensor.textnow_john
  include_header: false
  include_footer: false
  options: |
    Yes
    No
response_variable: choice
```

---

## Triggers Reference

TextNow provides two trigger types that appear under **Device** triggers.

### SMS Message Received Trigger

Fires when **any contact** sends you an SMS message.

#### Setting Up in the UI

1. Create a new automation
2. Click **+ Add Trigger**
3. Select **Device**
4. Search for and select **TextNow**
5. Choose **SMS message received**
6. Save

#### What This Trigger Provides

When the trigger fires, you get access to these variables:

| Variable | Description |
|----------|-------------|
| `{{ trigger.contact_name }}` | Name of the person who texted |
| `{{ trigger.contact_id }}` | Contact ID (use for sending replies) |
| `{{ trigger.message }}` | The message text |
| `{{ trigger.text }}` | Same as message |
| `{{ trigger.phone }}` | Phone number |

#### YAML Example

```yaml
automation:
  - alias: "Log all incoming SMS"
    trigger:
      - platform: device
        domain: textnow
        device_id: <your_textnow_device_id>
        type: message_received
    action:
      - service: logbook.log
        data:
          name: "SMS Received"
          message: "{{ trigger.contact_name }} said: {{ trigger.message }}"
```

---

### Phrase Received in SMS Trigger

Fires when a message contains a **specific phrase** you define.

#### Setting Up in the UI

1. Create a new automation
2. Click **+ Add Trigger**
3. Select **Device**
4. Search for and select **TextNow**
5. Choose **Phrase received in SMS**
6. Enter the phrase to match in **Phrase to match** field
7. Save

#### How Phrase Matching Works

- Matching is **case-insensitive** ("LIGHTS" matches "lights")
- Phrase can appear **anywhere** in the message
- Message "Please turn on the lights now" matches phrase "lights"
- Message "Turn on the lights" matches phrase "turn on"

#### What This Trigger Provides

Same variables as [SMS Message Received](#what-this-trigger-provides), plus:

| Variable | Description |
|----------|-------------|
| `{{ trigger.matched_phrase }}` | The phrase that was matched |

#### YAML Example

```yaml
automation:
  - alias: "Lights on via SMS"
    trigger:
      - platform: device
        domain: textnow
        device_id: <your_textnow_device_id>
        type: phrase_received
        phrase: "lights on"
    action:
      - service: light.turn_on
        target:
          entity_id: light.living_room
      - service: textnow.send
        data:
          contact_id: "sensor.textnow_{{ trigger.contact_id }}"
          message: "Lights turned on! 💡"
```

---

## Automation Examples

### Example 1: Interactive Light Control Menu

When anyone texts the word "menu", send them a control menu and act on their response.

```yaml
automation:
  - alias: "SMS Menu Control"
    trigger:
      - platform: device
        domain: textnow
        device_id: <your_device_id>
        type: phrase_received
        phrase: "menu"
    
    action:
      # Send menu to whoever texted
      - service: textnow.send_menu
        data:
          contact_id: "sensor.textnow_{{ trigger.contact_id }}"
          header: "🏠 Home Control"
          options: |
            Turn on lights
            Turn off lights
            Lock doors
            Unlock doors
          footer: "Reply 1-4"
          timeout: 60
        response_variable: choice
      
      # Handle their selection
      - choose:
          # Option 1: Turn on lights
          - conditions: "{{ choice.option == 1 }}"
            sequence:
              - service: light.turn_on
                target:
                  entity_id: light.living_room
              - service: textnow.send
                data:
                  contact_id: "sensor.textnow_{{ trigger.contact_id }}"
                  message: "✅ Lights turned ON"
          
          # Option 2: Turn off lights
          - conditions: "{{ choice.option == 2 }}"
            sequence:
              - service: light.turn_off
                target:
                  entity_id: light.living_room
              - service: textnow.send
                data:
                  contact_id: "sensor.textnow_{{ trigger.contact_id }}"
                  message: "✅ Lights turned OFF"
          
          # Option 3: Lock doors
          - conditions: "{{ choice.option == 3 }}"
            sequence:
              - service: lock.lock
                target:
                  entity_id: lock.front_door
              - service: textnow.send
                data:
                  contact_id: "sensor.textnow_{{ trigger.contact_id }}"
                  message: "🔒 Doors locked"
          
          # Option 4: Unlock doors
          - conditions: "{{ choice.option == 4 }}"
            sequence:
              - service: lock.unlock
                target:
                  entity_id: lock.front_door
              - service: textnow.send
                data:
                  contact_id: "sensor.textnow_{{ trigger.contact_id }}"
                  message: "🔓 Doors unlocked"
          
          # Timeout - no response
          - conditions: "{{ choice.timed_out }}"
            sequence:
              - service: textnow.send
                data:
                  contact_id: "sensor.textnow_{{ trigger.contact_id }}"
                  message: "⏰ Menu timed out. Text 'menu' to try again."
```

### Example 2: Simple Phrase Commands

Create multiple automations for different phrases:

**Lights On:**
```yaml
automation:
  - alias: "SMS - Lights On"
    trigger:
      - platform: device
        domain: textnow
        device_id: <your_device_id>
        type: phrase_received
        phrase: "lights on"
    action:
      - service: light.turn_on
        target:
          entity_id: all
      - service: textnow.send
        data:
          contact_id: "sensor.textnow_{{ trigger.contact_id }}"
          message: "All lights turned on! 💡"
```

**Lights Off:**
```yaml
automation:
  - alias: "SMS - Lights Off"
    trigger:
      - platform: device
        domain: textnow
        device_id: <your_device_id>
        type: phrase_received
        phrase: "lights off"
    action:
      - service: light.turn_off
        target:
          entity_id: all
      - service: textnow.send
        data:
          contact_id: "sensor.textnow_{{ trigger.contact_id }}"
          message: "All lights turned off! 🌙"
```

### Example 3: Security Alert with Camera Snapshot

Send an MMS with a camera snapshot when motion is detected:

```yaml
automation:
  - alias: "Motion Alert with Photo"
    trigger:
      - platform: state
        entity_id: binary_sensor.front_door_motion
        to: "on"
    action:
      # Take a snapshot
      - service: camera.snapshot
        target:
          entity_id: camera.front_door
        data:
          filename: /config/www/motion_snapshot.jpg
      
      # Wait for file to save
      - delay:
          seconds: 2
      
      # Send MMS alert
      - service: textnow.send
        data:
          contact_id: sensor.textnow_john
          message: "🚨 Motion detected at front door!"
          mms_image: /config/www/motion_snapshot.jpg
```

### Example 4: Home Status Report

When someone texts "status", reply with current home status:

```yaml
automation:
  - alias: "SMS Status Report"
    trigger:
      - platform: device
        domain: textnow
        device_id: <your_device_id>
        type: phrase_received
        phrase: "status"
    action:
      - service: textnow.send
        data:
          contact_id: "sensor.textnow_{{ trigger.contact_id }}"
          message: >
            🏠 HOME STATUS
            
            🌡️ Inside: {{ states('sensor.indoor_temperature') }}°F
            🌡️ Outside: {{ states('sensor.outdoor_temperature') }}°F
            💡 Lights on: {{ states.light | selectattr('state', 'eq', 'on') | list | count }}
            🔒 Front door: {{ states('lock.front_door') }}
            🚗 Garage: {{ states('cover.garage_door') }}
            👤 Home: {{ states('person.john') }}
```

### Example 5: Yes/No Confirmation

Ask for confirmation before running an action:

```yaml
automation:
  - alias: "Arm Security via SMS"
    trigger:
      - platform: device
        domain: textnow
        device_id: <your_device_id>
        type: phrase_received
        phrase: "arm security"
    action:
      # Ask for confirmation
      - service: textnow.send_menu
        data:
          contact_id: "sensor.textnow_{{ trigger.contact_id }}"
          header: "⚠️ Arm security system?"
          options: |
            Yes, arm now
            No, cancel
          include_footer: false
          timeout: 30
        response_variable: confirm
      
      - choose:
          - conditions: "{{ confirm.option == 1 }}"
            sequence:
              - service: alarm_control_panel.alarm_arm_away
                target:
                  entity_id: alarm_control_panel.home
              - service: textnow.send
                data:
                  contact_id: "sensor.textnow_{{ trigger.contact_id }}"
                  message: "🔒 Security system ARMED"
          
          - conditions: "{{ confirm.option == 2 or confirm.timed_out }}"
            sequence:
              - service: textnow.send
                data:
                  contact_id: "sensor.textnow_{{ trigger.contact_id }}"
                  message: "❌ Cancelled"
```

---

## Template Variables Reference

### Available in Trigger Context

When using the TextNow triggers, these variables are available:

| Variable | Example | Description |
|----------|---------|-------------|
| `{{ trigger.contact_name }}` | "John" | Contact's name |
| `{{ trigger.contact_id }}` | "contact_john" | Contact ID for services |
| `{{ trigger.message }}` | "Hello there" | Message text |
| `{{ trigger.text }}` | "Hello there" | Same as message |
| `{{ trigger.phone }}` | "+15551234567" | Phone number |
| `{{ trigger.matched_phrase }}` | "lights on" | Matched phrase (phrase trigger only) |

### Using Contact ID in Services

To reply to whoever sent the message:

```yaml
service: textnow.send
data:
  contact_id: "sensor.textnow_{{ trigger.contact_id }}"
  message: "Got your message!"
```

### Response Variable Fields

After `send_menu` with `response_variable: choice`:

| Variable | Example | Description |
|----------|---------|-------------|
| `{{ choice.option }}` | `1` | Selected option (1, 2, 3...) |
| `{{ choice.option_index }}` | `0` | Zero-based index |
| `{{ choice.value }}` | "Turn on lights" | Option text |
| `{{ choice.raw_text }}` | "1" | What user typed |
| `{{ choice.timed_out }}` | `false` | True if timeout |
| `{{ choice.contact_name }}` | "John" | Who responded |

---

## Sensor Entities

Each contact creates a sensor entity with message history.

### Entity ID Format

`sensor.textnow_<contact_name>`

Example: Contact "John Doe" → `sensor.textnow_john_doe`

### Sensor State

The sensor's state is the last received message text, or "No messages" if none.

### Sensor Attributes

| Attribute | Description |
|-----------|-------------|
| `phone` | Contact's phone number |
| `last_inbound` | Last received message text |
| `last_inbound_ts` | Timestamp of last received message |
| `last_outbound` | "Sent" after sending a message |
| `last_outbound_ts` | Timestamp of last sent message |

---

## Troubleshooting

### Trigger Not Firing

1. **Check the phrase is in the message**: Phrase matching looks for the phrase ANYWHERE in the message (case-insensitive)
2. **Verify the contact exists**: The sender must be a saved contact
3. **Check allowed phones**: If you configured an allowed phones list, ensure the number is included
4. **Enable debug logging**:

```yaml
# configuration.yaml
logger:
  default: info
  logs:
    custom_components.textnow: debug
```

Then check **Settings → System → Logs** after sending a test message.

### Menu Not Waiting for Response

- Increase the `timeout` value (default is 30 seconds)
- Check that the contact can send messages to your TextNow number
- Verify the `send_menu` service has `response_variable` set

### Authentication Errors

- TextNow cookies expire periodically
- Re-copy fresh cookies from your browser
- Make sure you're copying the cookie VALUES, not the names

### Messages Not Sending

- Check Home Assistant logs for error details
- Verify the contact exists in your contacts list
- Ensure the phone number is valid (10 digits)

### Finding Your Device ID

For YAML triggers, you need the device ID:

1. Go to **Settings → Devices & Services → TextNow**
2. Click on the **TextNow** device
3. Look at the URL - the device ID is in the URL
4. Or use the UI to create the trigger first, then switch to YAML mode to see the ID

---

## Requirements

- Home Assistant 2023.7.0 or later
- Valid TextNow account
- Active session cookies from browser

---

## Security Notes

- **Allowed Phones**: Restrict which phone numbers can trigger automations
- **Cookie Security**: Session cookies provide full TextNow account access - keep them secure
- **Local Storage**: All data is stored locally in Home Assistant

---

## Support

- **Issues**: [GitHub Issues](https://github.com/zodyking/Home-Assistant-TextNow/issues)
- **Discussions**: [GitHub Discussions](https://github.com/zodyking/Home-Assistant-TextNow/discussions)

---

Made with ❤️ for the Home Assistant community

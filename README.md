# 🚀 TextNow Home Assistant Integration

<div align="center">

![TextNow Integration](https://img.shields.io/badge/Home%20Assistant-TextNow-blue?style=for-the-badge&logo=home-assistant)
![HACS](https://img.shields.io/badge/HACS-Custom-orange?style=for-the-badge)
![Version](https://img.shields.io/badge/version-1.0.0-green?style=for-the-badge)
![License](https://img.shields.io/badge/license-MIT-blue?style=for-the-badge)

**A powerful Home Assistant integration for TextNow SMS that enables multi-step conversational automations**

[Features](#-features) • [Installation](#-installation) • [Configuration](#-configuration) • [Usage](#-usage) • [Examples](#-examples) • [Support](#-support)

</div>

---

## ✨ Features

- 📱 **Full SMS Support** - Send and receive SMS messages through TextNow
- 🔄 **Automatic Polling** - Real-time message polling with deduplication
- 👥 **Contact Management** - UI-managed contact list with names and phone numbers
- 🎯 **Smart Choice Prompts** - Send prompts with numbered options and parse user selections
- 📊 **Sensor Entities** - Per-contact sensors with message history and context
- 🔐 **Security** - Phone number allowlist for enhanced security
- 💾 **Persistent Storage** - Contacts, pending expectations, and context data
- ⚡ **Event-Driven** - Fire events for received messages and parsed replies
- 🔧 **Generic Primitives** - Build complex multi-step automations with simple services

## 📦 Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations**
3. Click the three dots menu (⋮) → **Custom repositories**
4. Add repository: `https://github.com/zodyking/Home-Assistant-TextNow`
5. Select category: **Integration**
6. Click **Install**
7. Restart Home Assistant

### Manual Installation

1. Copy the `textnow` folder to your `custom_components` directory:
   ```
   config/custom_components/textnow/
   ```
2. Restart Home Assistant
3. Go to **Settings** → **Devices & Services** → **Add Integration**
4. Search for **TextNow** and follow the setup wizard

## ⚙️ Configuration

### Initial Setup

The initial setup only requires your TextNow account credentials:

1. **Username**: Your TextNow account username
2. **connect.sid Cookie**: Found in your browser's cookies when logged into TextNow
   - Open browser DevTools (F12) → Application/Storage → Cookies → `https://www.textnow.com`
   - Copy the value of `connect.sid`
3. **_csrf Cookie**: Same location, copy the value of `_csrf`

**Note:** Polling interval and allowed phones can be configured later in the Options menu.

### Managing Contacts

Contacts can be managed in two ways:

**Option 1: Side Menu (Recommended)**
1. Click **TextNow** in the Home Assistant side menu
2. Use the GUI to add, edit, or delete contacts
3. Phone numbers are automatically formatted as `+1XXXXXXXXXX` (10 digits required)

**Option 2: Integration Options**
1. Go to **Settings** → **Devices & Services** → **TextNow** → **Options**
2. Select **Contacts** to manage your contact list
3. Add contacts with a name and phone number (10 digits, auto-formatted with +1 prefix)
4. Each contact creates a sensor entity: `sensor.textnow_<contact_name>`

**Phone Number Format:**
- Enter 10 digits (e.g., `2122037678`)
- Automatically formatted to `+12122037678`
- Non-numeric characters are stripped
- Leading "1" is handled automatically

## 🎮 Usage

### Services

#### `textnow.send`

Send an SMS message to a contact.

```yaml
service: textnow.send
data:
  contact_id: sensor.textnow_contact_1  # Select from entity dropdown
  message: "Hello, this is a test message"
```

**Note:** Only `contact_id` is required. The phone number is automatically retrieved from the selected contact.

#### `textnow.prompt`

Send a prompt message with numbered choices and wait for a reply. The reply will be parsed and a `textnow_reply_parsed` event will be fired.

**Features:**
- Automatically numbers options (1, 2, 3, etc.)
- Accepts replies by number or text match
- Contact selection auto-fills phone number
- Options are required (newline or comma-separated)

```yaml
service: textnow.prompt
data:
  contact_id: sensor.textnow_contact_1  # Select from dropdown or use contact_id
  key: user_choice
  prompt: "Please choose an option"
  options: "Option 1\nOption 2\nOption 3"  # Required - newline or comma-separated
  ttl_seconds: 300
```

**Contact Selection:**
- Use entity selector to choose from your TextNow contacts
- Phone number auto-fills when a contact is selected
- Can also use `contact_id` directly (e.g., `contact_1`) or `phone` number

#### `textnow.clear_pending`

Clear pending expectations for a contact.

```yaml
service: textnow.clear_pending
data:
  contact_id: sensor.textnow_contact_1  # Select from entity dropdown
  key: user_choice  # Optional: clears all if not specified
```

#### `textnow.set_context`

Set or merge context data for a contact.

```yaml
service: textnow.set_context
data:
  contact_id: sensor.textnow_contact_1  # Select from entity dropdown
  data:
    step: 1
    user_name: "John"
    preferences: "dark_mode"
```

### Events

#### `textnow_message_received`

Fired when a new message is received.

```yaml
event_type: textnow_message_received
event_data:
  phone: "+1234567890"
  text: "Hello"
  message_id: "msg_123"
  timestamp: "2024-01-01T12:00:00"
  contact_id: "contact_1"
```

#### `textnow_reply_parsed`

Fired when a reply matches a pending expectation.

```yaml
event_type: textnow_reply_parsed
event_data:
  phone: "+1234567890"
  contact_id: "contact_1"
  key: "user_choice"
  type: "choice"
  value: "Option 1"
  raw_text: "1"
  option_index: 0
```

### Sensor Attributes

Each contact sensor (`sensor.textnow_<contact_name>`) includes:

- `phone` - Phone number
- `last_inbound` - Last received message text
- `last_inbound_ts` - Timestamp of last received message
- `last_outbound` - Status of last sent message
- `last_outbound_ts` - Timestamp of last sent message
- `pending` - Dictionary of pending expectations
- `context` - Dictionary of context data

## 📚 Examples

### Example 1: Simple Command Handler

When a user sends "START", begin a conversation flow:

```yaml
automation:
  - alias: "TextNow - Start Flow"
    trigger:
      - platform: event
        event_type: textnow_message_received
        event_data:
          text: "START"
    action:
      - service: textnow.set_context
        data:
          contact_id: "{{ trigger.event.data.contact_id }}"
          data:
            step: 1
      - service: textnow.send
        data:
          contact_id: "{{ trigger.event.data.contact_id }}"
          message: "Welcome! Please choose an option:"
      - service: textnow.prompt
        data:
          contact_id: "{{ trigger.event.data.contact_id }}"
          key: "menu_choice"
          prompt: "Please choose an option:"
          options: "Lights\nTemperature\nMusic"
          ttl_seconds: 300
```

### Example 2: Multi-Step Flow with TTS

Complete 3-step automation: command → prompt choice → prompt text → call TTS.

```yaml
automation:
  - alias: "TextNow - Handle Menu Choice"
    trigger:
      - platform: event
        event_type: textnow_reply_parsed
        event_data:
          key: "menu_choice"
    action:
      - service: textnow.set_context
        data:
          contact_id: "{{ trigger.event.data.contact_id }}"
          data:
            step: 2
            choice: "{{ trigger.event.data.value }}"
      - choose:
          - conditions:
              - condition: template
                value_template: "{{ trigger.event.data.value == 'Lights' }}"
            sequence:
              - service: textnow.send
                data:
                  contact_id: "{{ trigger.event.data.contact_id }}"
                  message: "What would you like to do with the lights?"
              - service: textnow.prompt
                data:
                  contact_id: "{{ trigger.event.data.contact_id }}"
                  key: "lights_action"
                  prompt: "What would you like to do?"
                  options: "Turn On\nTurn Off\nDim 50%\nDim 25%"
                  ttl_seconds: 300

  - alias: "TextNow - Execute Action with TTS"
    trigger:
      - platform: event
        event_type: textnow_reply_parsed
        event_data:
          key: "lights_action"
    action:
      - service: light.turn_on
        target:
          entity_id: light.living_room
      - service: tts.google_translate_say
        data:
          entity_id: media_player.living_room
          message: "Lights have been {{ trigger.event.data.value }}"
      - service: textnow.send
        data:
          contact_id: "{{ trigger.event.data.contact_id }}"
          message: "Action completed! Check your devices."
```

### Example 3: Using Context for State Management

Store and retrieve state between conversation steps:

```yaml
automation:
  - alias: "TextNow - Use Context"
    trigger:
      - platform: event
        event_type: textnow_reply_parsed
    action:
      - service: textnow.set_context
        data:
          contact_id: "{{ trigger.event.data.contact_id }}"
          data:
            last_action: "{{ trigger.event.data.value }}"
            timestamp: "{{ now().isoformat() }}"
      - condition: template
        value_template: >
          {{ state_attr('sensor.textnow_contact_1', 'context').get('last_action') == 'lights' }}
      - service: textnow.send
        data:
          contact_id: "{{ trigger.event.data.contact_id }}"
          message: "You chose lights last time too!"
```

### Example 4: Contact Autocomplete

Using the entity selector for easy contact selection:

```yaml
service: textnow.prompt
data:
  contact_id: sensor.textnow_john  # Select from entity dropdown
  key: "user_preference"
  prompt: "Choose your preference:"
  options: "Email\nSMS\nPhone Call"
  ttl_seconds: 300
```

**Note:** When using the service UI, you can select contacts from a dropdown, and the phone number will automatically fill in.

## 🎯 Key Features

### Contact-Only Services
- All services require only `contact_id` (no phone field)
- Select `sensor.textnow_<contact_name>` from entity dropdown
- Phone number automatically retrieved from contact
- Works in both YAML and UI service calls

### Automatic Phone Formatting
- Phone numbers automatically formatted as `+1XXXXXXXXXX`
- Validates exactly 10 digits
- Strips non-numeric characters
- Handles leading "1" country code

### Choice-Based Prompts
- All prompts use choice-based selection
- Options are automatically numbered (1, 2, 3, etc.)
- Users can reply with number or text match
- Supports partial text matching
- Options field is required

## 🔧 Advanced Features

### Keep Pending for Multiple Replies

Allow multiple replies to the same prompt:

```yaml
service: textnow.prompt
data:
  contact_id: sensor.textnow_contact_1
  key: "multiple_items"
  prompt: "Select items (reply with number, send DONE when finished):"
  options: "Item 1\nItem 2\nItem 3\nDONE"
  keep_pending: true
  ttl_seconds: 600
```

### Phone Number Format

Phone numbers should be in E.164 format (e.g., `+1234567890`) for best compatibility.

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| Messages not being received | Check that the phone number is in the `allowed_phones` list |
| Prompts not working | Ensure the TTL hasn't expired (default 300 seconds) |
| Contact not found | Use the entity selector (`sensor.textnow_contact_name`) or ensure `contact_id` matches exactly |
| Options not working | Options field is required - provide at least one option (newline or comma-separated) |
| Authentication errors | Verify cookies are valid and not expired. Re-copy from browser |
| API errors | Check the Home Assistant logs for detailed error messages |

## 📋 Requirements

- Home Assistant 2023.1.0 or later
- Valid TextNow account with active session cookies
- Internet connection for API calls

## 🔒 Security

- **Phone Allowlist**: Only process messages from numbers in your allowed list
- **Cookie Security**: Store cookies securely - they provide full account access
- **Local Storage**: All data (contacts, pending, context) is stored locally in Home Assistant

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Built for the Home Assistant community
- Uses TextNow's public API endpoints
- Inspired by the need for conversational SMS automations

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/zodyking/Home-Assistant-TextNow/issues)
- **Discussions**: [GitHub Discussions](https://github.com/zodyking/Home-Assistant-TextNow/discussions)

---

<div align="center">

**Made with ❤️ for the Home Assistant community**

⭐ Star this repo if you find it useful!

</div>


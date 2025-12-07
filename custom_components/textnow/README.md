# TextNow Home Assistant Integration

A Home Assistant custom integration for TextNow that provides generic conversation primitives for building multi-step SMS automations.

## Features

- **Config Flow UI**: Easy setup with username and cookie authentication
- **Contact Management**: UI-managed contact list with name and phone number
- **Message Polling**: Automatic polling of unread messages with deduplication
- **Events**: Fires `textnow_message_received` and `textnow_reply_parsed` events
- **Services**: Send messages, prompt for replies, manage pending expectations, and set context
- **Sensors**: One sensor per contact with attributes for phone, timestamps, pending, and context
- **Storage**: Persistent storage for contacts, pending expectations, and context

## Installation

1. Copy the `textnow` folder to your `custom_components` directory in Home Assistant
2. Restart Home Assistant
3. Go to Settings → Devices & Services → Add Integration
4. Search for "TextNow" and follow the setup wizard

## Configuration

### Initial Setup

1. **Username**: Your TextNow account username
2. **connect.sid Cookie**: Found in your browser's cookies when logged into TextNow
3. **_csrf Cookie**: Found in your browser's cookies when logged into TextNow
4. **Polling Interval**: How often to check for new messages (default: 30 seconds)
5. **Allowed Phones**: Comma-separated list of phone numbers to accept messages from (security feature)

### Managing Contacts

1. Go to Settings → Devices & Services → TextNow → Options
2. Select "Contacts" to manage your contact list
3. Add contacts with a name and phone number
4. Each contact will create a sensor entity: `sensor.textnow_<contact_name>`

## Services

### textnow.send

Send an SMS message to a phone number or contact.

```yaml
service: textnow.send
data:
  contact_id: contact_1
  message: "Hello, this is a test message"
```

or

```yaml
service: textnow.send
data:
  phone: "+1234567890"
  message: "Hello, this is a test message"
```

### textnow.prompt

Send a prompt message and wait for a reply. The reply will be parsed and a `textnow_reply_parsed` event will be fired.

```yaml
service: textnow.prompt
data:
  contact_id: contact_1
  key: user_choice
  prompt: "Please choose an option"
  type: choice
  options:
    - "Option 1"
    - "Option 2"
    - "Option 3"
  ttl_seconds: 300
```

**Types:**
- `choice`: Expects a numbered choice or text match from options
- `text`: Accepts any text (optionally with regex validation)
- `number`: Expects a numeric value
- `boolean`: Expects yes/no, true/false, etc.

### textnow.clear_pending

Clear pending expectations for a phone number or contact.

```yaml
service: textnow.clear_pending
data:
  contact_id: contact_1
  key: user_choice  # Optional: clears all if not specified
```

### textnow.set_context

Set or merge context data for a phone number or contact.

```yaml
service: textnow.set_context
data:
  contact_id: contact_1
  data:
    step: 1
    user_name: "John"
    preferences: "dark_mode"
```

## Events

### textnow_message_received

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

### textnow_reply_parsed

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

## Sensor Attributes

Each contact sensor (`sensor.textnow_<contact_name>`) has the following attributes:

- `phone`: Phone number
- `last_inbound`: Last received message text
- `last_inbound_ts`: Timestamp of last received message
- `last_outbound`: Status of last sent message
- `last_outbound_ts`: Timestamp of last sent message
- `pending`: Dictionary of pending expectations
- `context`: Dictionary of context data

## Example: Multi-Step SMS Automation

This example shows how to create a 3-automation flow: command → prompt choice → prompt text → call TTS.

### Step 1: Command Handler

When a user sends "START", begin the flow:

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
          prompt: "1. Lights\n2. Temperature\n3. Music"
          type: choice
          options:
            - "Lights"
            - "Temperature"
            - "Music"
          ttl_seconds: 300
```

### Step 2: Choice Handler

Handle the menu choice and prompt for text input:

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
                  prompt: "Enter your command (e.g., 'turn on', 'dim 50%')"
                  type: text
                  ttl_seconds: 300
          - conditions:
              - condition: template
                value_template: "{{ trigger.event.data.value == 'Temperature' }}"
            sequence:
              - service: textnow.send
                data:
                  contact_id: "{{ trigger.event.data.contact_id }}"
                  message: "What temperature would you like?"
              - service: textnow.prompt
                data:
                  contact_id: "{{ trigger.event.data.contact_id }}"
                  key: "temperature_value"
                  prompt: "Enter temperature (e.g., 72)"
                  type: number
                  ttl_seconds: 300
          - conditions:
              - condition: template
                value_template: "{{ trigger.event.data.value == 'Music' }}"
            sequence:
              - service: textnow.send
                data:
                  contact_id: "{{ trigger.event.data.contact_id }}"
                  message: "What song would you like to play?"
              - service: textnow.prompt
                data:
                  contact_id: "{{ trigger.event.data.contact_id }}"
                  key: "song_name"
                  prompt: "Enter song name or artist"
                  type: text
                  ttl_seconds: 300
```

### Step 3: Execute Action and TTS

Handle the text input and execute the action with TTS confirmation:

```yaml
automation:
  - alias: "TextNow - Execute Action with TTS"
    trigger:
      - platform: event
        event_type: textnow_reply_parsed
        event_data:
          key: "lights_action"
      - platform: event
        event_type: textnow_reply_parsed
        event_data:
          key: "temperature_value"
      - platform: event
        event_type: textnow_reply_parsed
        event_data:
          key: "song_name"
    action:
      - service: textnow.set_context
        data:
          contact_id: "{{ trigger.event.data.contact_id }}"
          data:
            step: 3
            action_value: "{{ trigger.event.data.value }}"
      - choose:
          - conditions:
              - condition: template
                value_template: "{{ trigger.event.data.key == 'lights_action' }}"
            sequence:
              - service: light.turn_on
                target:
                  entity_id: light.living_room
                data:
                  brightness_pct: >
                    {% if 'dim' in trigger.event.data.value.lower() %}
                      {{ trigger.event.data.value | regex_findall_index('(\d+)', 0) | int }}
                    {% else %}
                      100
                    {% endif %}
              - service: tts.google_translate_say
                data:
                  entity_id: media_player.living_room
                  message: "Lights have been {{ trigger.event.data.value }}"
      - choose:
          - conditions:
              - condition: template
                value_template: "{{ trigger.event.data.key == 'temperature_value' }}"
            sequence:
              - service: climate.set_temperature
                target:
                  entity_id: climate.thermostat
                data:
                  temperature: "{{ trigger.event.data.value | int }}"
              - service: tts.google_translate_say
                data:
                  entity_id: media_player.living_room
                  message: "Temperature set to {{ trigger.event.data.value }} degrees"
      - choose:
          - conditions:
              - condition: template
                value_template: "{{ trigger.event.data.key == 'song_name' }}"
            sequence:
              - service: media_player.play_media
                target:
                  entity_id: media_player.living_room
                data:
                  media_content_id: "{{ trigger.event.data.value }}"
                  media_content_type: "music"
              - service: tts.google_translate_say
                data:
                  entity_id: media_player.living_room
                  message: "Playing {{ trigger.event.data.value }}"
      - service: textnow.send
        data:
          contact_id: "{{ trigger.event.data.contact_id }}"
          message: "Action completed! Check your devices."
      - service: textnow.clear_pending
        data:
          contact_id: "{{ trigger.event.data.contact_id }}"
```

## Advanced Usage

### Using Context for State Management

The context feature allows you to store state between steps:

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

### Regex Validation

Use regex to validate text input:

```yaml
service: textnow.prompt
data:
  contact_id: contact_1
  key: "zip_code"
  prompt: "Enter your zip code (5 digits)"
  type: text
  regex: "^\\d{5}$"
  ttl_seconds: 300
```

### Keep Pending for Multiple Replies

Use `keep_pending: true` to allow multiple replies to the same prompt:

```yaml
service: textnow.prompt
data:
  contact_id: contact_1
  key: "multiple_items"
  prompt: "Enter items (one per message, send DONE when finished)"
  type: text
  keep_pending: true
  ttl_seconds: 600
```

## Troubleshooting

- **Messages not being received**: Check that the phone number is in the allowed_phones list
- **Prompts not working**: Ensure the TTL hasn't expired (default 300 seconds)
- **Contact not found**: Make sure the contact_id matches exactly (case-sensitive)
- **PyTextNow_API errors**: Check that cookies are valid and not expired

## Notes

- All blocking PyTextNow_API calls are run in an executor to avoid blocking the event loop
- Message IDs are deduplicated to prevent processing the same message twice
- Pending expectations automatically expire after TTL
- Context data is merged, not replaced, when using `textnow.set_context`


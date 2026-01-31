# Home Assistant TextNow Integration – SMS/MMS Control Your Smart Home

![TextNow Banner|690x460](upload://YOUR_BANNER_IMAGE_HERE.png)

A powerful Home Assistant integration for sending and receiving SMS/MMS messages through TextNow. Control your smart home via text messages with interactive menus, auto-replies, and phrase-based triggers!

---

## Quick Install

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=zodyking&repository=Home-Assistant-TextNow&category=integration)

**Manual HACS Setup:**
1. HACS → Integrations → **⋮** menu → Custom repositories
2. URL: `https://github.com/zodyking/Home-Assistant-TextNow`
3. Category: Integration → Add
4. Search "TextNow" → Download
5. Restart Home Assistant

---

## ✨ Features

- **📱 Send SMS/MMS/Voice Messages** - Text, images, or audio to any contact
- **📥 Receive Messages** - Automatic polling for incoming messages
- **🎯 Smart Triggers** - Fire automations on any message or specific phrases
- **🔄 Auto-Reply** - Automatically respond to whoever texted you
- **📋 Interactive Menus** - Send numbered menus, wait for response, take action
- **👤 Contact Management** - Add/edit/remove contacts via UI
- **📊 Message History** - Sensor entities track message history per contact

---

## 🔧 Initial Setup

### Step 1: Get Your TextNow Credentials

You need **3 values** from TextNow:

1. **Username** (from TextNow Settings - NOT your email address)
2. **`connect.sid`** cookie value
3. **`_csrf`** cookie value

[details="How to Get Cookie Values"]

1. Sign into [textnow.com](https://www.textnow.com)
2. Press **F12** to open Developer Tools
3. Go to **Network** tab
4. Refresh the page (F5)
5. Click any request in the list
6. Find **Request Headers** → **Cookie**
7. Copy the **value** after `connect.sid=` (everything until the next `;`)
8. Copy the **value** after `_csrf=` (everything until the next `;`)

**Example Cookie String:**
```
connect.sid=s%3Axxxxxx.yyyyyy; _csrf=zzzzzzz; other=stuff
```

You need:
- `connect.sid`: `s%3Axxxxxx.yyyyyy`
- `_csrf`: `zzzzzzz`

[/details]

### Step 2: Add Integration in Home Assistant

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for **TextNow**
4. Enter:
   - **Username**: Your TextNow username
   - **Connect SID**: The `connect.sid` cookie value
   - **CSRF Token**: The `_csrf` cookie value
5. Click **Submit**

### Step 3: Add Contacts

1. Go to **Settings** → **Devices & Services** → **TextNow**
2. Click **Configure**
3. Select **Add Contact**
4. Enter:
   - **Name**: Contact name (e.g., "John")
   - **Phone**: 10-digit phone number (e.g., "5551234567")
5. Click **Submit**

Each contact creates a sensor: `sensor.textnow_<name>`

---

## 📤 Services

### textnow.send - Send Messages

Send SMS, MMS (images), or voice messages to any contact.

![Send Message Service|690x460](upload://YOUR_SEND_MESSAGE_IMAGE.png)

[details="Service Fields & Examples"]

**Fields:**

| Field | Description |
|-------|-------------|
| **Contact** | **Leave unchecked** to auto-reply to trigger sender<br>**Check and select** to send to specific contact |
| **Message** | Text message content |
| **Image** | File path for MMS image (e.g., `/config/www/photo.jpg`) |
| **Audio file** | File path for voice message (e.g., `/config/www/audio.mp3`) |

**Example 1: Send to specific contact**
```yaml
service: textnow.send
data:
  contact_id: sensor.textnow_john
  message: "Hello from Home Assistant!"
```

**Example 2: Auto-reply to trigger sender**
```yaml
# No contact needed - automatically replies to whoever triggered the automation
service: textnow.send
data:
  message: "Got your message!"
```

**Example 3: Send MMS with photo**
```yaml
service: textnow.send
data:
  contact_id: sensor.textnow_john
  message: "Motion detected at front door!"
  mms_image: /config/www/snapshots/front_door.jpg
```

[/details]

---

### textnow.send_menu - Interactive SMS Menus

Send a numbered menu via SMS and **wait for the user's response**. Perfect for interactive smart home control!

![Send Menu Service|690x460](upload://YOUR_SEND_MENU_IMAGE.png)

[details="How It Works"]

1. Service sends numbered menu via SMS
2. Service **waits** for user to reply with a number
3. User texts back "1", "2", "3", etc.
4. Service returns their choice as a variable
5. Your automation continues based on their selection

**What the user receives:**
```
Please select an option:

1. Turn on lights
2. Turn off lights
3. Lock doors

Reply with the number of your choice
```

[/details]

[details="Service Fields"]

| Field | Default | Description |
|-------|---------|-------------|
| **Contact** | - | Leave unchecked for auto-reply, or check to select contact |
| **Menu Options** | - | **One option per line** |
| **Include Header** | On | Show header before options |
| **Header Text** | "Please select an option:" | Custom header |
| **Include Footer** | On | Show footer after options |
| **Footer Text** | "Reply with the number..." | Custom footer |
| **Timeout** | 30 seconds | Wait time for response |

[/details]

[details="Complete Menu Example"]

```yaml
service: textnow.send_menu
data:
  # Leave contact empty to auto-reply to trigger sender
  options: |
    Turn on lights
    Turn off lights
    Lock all doors
  timeout: 60
response_variable: user_choice

# Handle their response
- choose:
    - conditions: "{{ user_choice.option == 1 }}"
      sequence:
        - service: light.turn_on
          target:
            entity_id: light.living_room
        - service: textnow.send
          data:
            message: "✅ Lights turned ON"
    
    - conditions: "{{ user_choice.option == 2 }}"
      sequence:
        - service: light.turn_off
          target:
            entity_id: light.living_room
        - service: textnow.send
          data:
            message: "✅ Lights turned OFF"
    
    - conditions: "{{ user_choice.option == 3 }}"
      sequence:
        - service: lock.lock
          target:
            entity_id: lock.front_door
        - service: textnow.send
          data:
            message: "🔒 Doors locked"
    
    - conditions: "{{ user_choice.timed_out }}"
      sequence:
        - service: textnow.send
          data:
            message: "⏰ Menu timed out"
```

**Response Variable Fields:**
- `user_choice.option` - Selected number (1, 2, 3...)
- `user_choice.value` - Text of selected option
- `user_choice.timed_out` - True if no response before timeout

[/details]

---

## 🎯 Triggers

### SMS Message Received

Fires when **any contact** sends you a message.

![SMS Received Trigger|690x460](upload://YOUR_SMS_RECEIVED_IMAGE.png)

[details="Setup & Variables"]

**Setup in UI:**
1. Create automation → Add Trigger → **Device**
2. Select **TextNow** device
3. Choose **SMS message received**

**Available Variables:**
- `{{ trigger.contact_name }}` - Sender's name
- `{{ trigger.contact_id }}` - Contact ID (use for replies)
- `{{ trigger.message }}` - Message text
- `{{ trigger.phone }}` - Phone number

**Example:**
```yaml
automation:
  - alias: "Log all SMS"
    trigger:
      - platform: device
        domain: textnow
        device_id: <your_device_id>
        type: message_received
    action:
      - service: logbook.log
        data:
          message: "{{ trigger.contact_name }}: {{ trigger.message }}"
```

[/details]

---

### Phrase Received in SMS

Fires when a message contains a **specific phrase** (case-insensitive).

![Phrase Received Trigger|690x460](upload://YOUR_PHRASE_RECEIVED_IMAGE.png)

[details="Setup & Examples"]

**Setup in UI:**
1. Create automation → Add Trigger → **Device**
2. Select **TextNow** device
3. Choose **Phrase received in SMS**
4. Enter the phrase to match

**Matching Rules:**
- Case-insensitive: "LIGHTS" matches "lights"
- Anywhere in message: "please turn on the lights" matches phrase "lights"

**Example: Control lights via SMS**
```yaml
automation:
  - alias: "Lights On via SMS"
    trigger:
      - platform: device
        domain: textnow
        device_id: <your_device_id>
        type: phrase_received
        phrase: "lights on"
    action:
      - service: light.turn_on
        target:
          entity_id: light.living_room
      - service: textnow.send
        data:
          message: "Lights turned on! 💡"
```

[/details]

---

## 🎬 Real-World Examples

[details="Interactive Menu - Full Smart Home Control"]

Text "menu" to control your entire home:

```yaml
automation:
  - alias: "SMS Smart Home Menu"
    trigger:
      - platform: device
        domain: textnow
        device_id: <your_device_id>
        type: phrase_received
        phrase: "menu"
    
    action:
      - service: textnow.send_menu
        data:
          header: "🏠 Smart Home Control"
          options: |
            Living room lights ON
            Living room lights OFF
            Lock all doors
            Unlock front door
            Garage door open/close
            Temperature status
          footer: "Reply 1-6 to select"
          timeout: 120
        response_variable: choice
      
      - choose:
          - conditions: "{{ choice.option == 1 }}"
            sequence:
              - service: light.turn_on
                target:
                  area_id: living_room
              - service: textnow.send
                data:
                  message: "✅ Living room lights ON"
          
          - conditions: "{{ choice.option == 2 }}"
            sequence:
              - service: light.turn_off
                target:
                  area_id: living_room
              - service: textnow.send
                data:
                  message: "✅ Living room lights OFF"
          
          - conditions: "{{ choice.option == 3 }}"
            sequence:
              - service: lock.lock
                target:
                  entity_id: all
              - service: textnow.send
                data:
                  message: "🔒 All doors locked"
          
          # Add more options as needed...
```

[/details]

[details="Security Alert with Camera Snapshot"]

Send MMS with camera photo when motion is detected:

```yaml
automation:
  - alias: "Motion Alert with Photo"
    trigger:
      - platform: state
        entity_id: binary_sensor.front_door_motion
        to: "on"
    
    action:
      - service: camera.snapshot
        target:
          entity_id: camera.front_door
        data:
          filename: /config/www/snapshots/motion.jpg
      
      - delay: 2
      
      - service: textnow.send
        data:
          contact_id: sensor.textnow_john
          message: "🚨 Motion detected at front door!"
          mms_image: /config/www/snapshots/motion.jpg
```

[/details]

[details="Home Status Report via SMS"]

Text "status" to get current home status:

```yaml
automation:
  - alias: "SMS Home Status"
    trigger:
      - platform: device
        domain: textnow
        device_id: <your_device_id>
        type: phrase_received
        phrase: "status"
    
    action:
      - service: textnow.send
        data:
          message: |
            🏠 HOME STATUS
            
            🌡️ Inside: {{ states('sensor.indoor_temp') }}°F
            🌡️ Outside: {{ states('sensor.outdoor_temp') }}°F
            💡 Lights on: {{ states.light | selectattr('state', 'eq', 'on') | list | count }}
            🔒 Front door: {{ states('lock.front_door') }}
            🚗 Garage: {{ states('cover.garage_door') }}
            👤 Home: {{ expand('person') | selectattr('state', 'eq', 'home') | list | count }} people
```

[/details]

[details="Emergency Mode Activation"]

Text "emergency" to activate security mode and get confirmation:

```yaml
automation:
  - alias: "Emergency Mode via SMS"
    trigger:
      - platform: device
        domain: textnow
        device_id: <your_device_id>
        type: phrase_received
        phrase: "emergency"
    
    action:
      # Turn on all lights
      - service: light.turn_on
        target:
          entity_id: all
      
      # Lock all doors
      - service: lock.lock
        target:
          entity_id: all
      
      # Arm alarm
      - service: alarm_control_panel.alarm_arm_away
        target:
          entity_id: alarm_control_panel.home
      
      # Send confirmation
      - service: textnow.send
        data:
          message: |
            🚨 EMERGENCY MODE ACTIVATED
            
            ✅ All lights turned ON
            ✅ All doors locked
            ✅ Security system armed
            
            Text "disarm" to deactivate
```

[/details]

---

## 📊 Contact Sensors

Each contact creates a sensor entity with message history.

**Entity format:** `sensor.textnow_<contact_name>`

**Attributes:**
- `phone` - Contact's phone number
- `last_inbound` - Last received message
- `last_inbound_ts` - Timestamp of last received
- `last_outbound` - Last sent message status
- `last_outbound_ts` - Timestamp of last sent

---

## 🔍 Troubleshooting

[details="Common Issues"]

**Triggers not firing:**
- Verify sender is a saved contact
- Check phrase is in the message (case-insensitive matching)
- Enable debug logging:
```yaml
logger:
  logs:
    custom_components.textnow: debug
```

**Authentication errors:**
- Cookies expire periodically - re-copy fresh cookies
- Make sure you copied cookie **values** (not names)

**Messages not sending:**
- Check Home Assistant logs for errors
- Verify contact exists
- Ensure phone number is valid (10 digits)

**Menu not waiting for response:**
- Increase `timeout` value
- Verify `response_variable` is set
- Check contact can send messages to your TextNow number

[/details]

---

## 📝 Requirements

- Home Assistant 2023.7.0+
- Valid TextNow account (free or paid)
- Active browser session for cookies

---

## 🔗 Links

- [GitHub Repository](https://github.com/zodyking/Home-Assistant-TextNow)
- [Issues & Bug Reports](https://github.com/zodyking/Home-Assistant-TextNow/issues)
- [Full Documentation](https://github.com/zodyking/Home-Assistant-TextNow#readme)

---

## ⚠️ Notes

- **Cookie Expiration**: TextNow session cookies expire periodically. You'll need to refresh them.
- **Message Polling**: Integration polls for messages every 30 seconds by default.
- **Rate Limiting**: Be mindful of TextNow's rate limits when sending messages.
- **Contact Management**: Add contacts via integration configuration before sending messages.

---

Made with ❤️ for the Home Assistant community

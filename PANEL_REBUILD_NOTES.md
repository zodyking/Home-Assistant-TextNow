# TextNow Panel Rebuild - Technical Notes

## Why the 401 Unauthorized Error Occurred

The original panel implementation attempted to serve JavaScript via a custom HTTP view (`/api/textnow/panel.js`) with `requires_auth = False`. However, when the panel was registered as an iframe pointing to this endpoint, Home Assistant's frontend security model blocked the request because:

1. **Iframe Security**: Home Assistant's frontend treats iframe panels as external content and applies strict security policies
2. **Authentication Context**: Even with `requires_auth = False`, the iframe context doesn't have access to the authenticated session
3. **CORS/Origin Issues**: The iframe approach creates cross-origin issues that prevent proper authentication

## The Correct Solution

The new implementation follows Home Assistant's recommended approach:

### 1. Static Frontend Module
- **Location**: `custom_components/textnow/frontend/textnow-panel.js`
- **Served via**: Static path registration using `StaticPathConfig`
- **URL**: `/textnow-panel.js` (served directly, not through `/api/`)

### 2. Panel Registration
- **Method**: `async_register_built_in_panel` with `component_name="custom"`
- **Config**: Uses `_panel_custom` with `embed_iframe: false`
- **Result**: Panel loads as a native frontend module, not an iframe

### 3. WebSocket API
- **Replaces**: HTTP REST API (`/api/textnow/config`)
- **Benefits**: 
  - Automatic authentication (WebSocket connections inherit HA session)
  - Real-time bidirectional communication
  - No CORS issues
  - Better error handling

### 4. Frontend Implementation
- **Custom Element**: `textnow-panel` extends `HTMLElement`
- **Authentication**: Uses `hass.callWS()` which automatically handles auth
- **No Raw Fetch**: All API calls go through Home Assistant's authenticated helpers

## File Structure

```
custom_components/textnow/
├── __init__.py              # Registers panel and WebSocket API
├── panel.py                 # Panel registration and static path setup
├── websocket.py             # WebSocket command handlers
└── frontend/
    └── textnow-panel.js     # Frontend custom element
```

## Key Changes

1. **Removed**:
   - `config_panel.py` (old HTTP views)
   - `panel/panel.html` and `panel/panel.js` (old iframe approach)
   - All `/api/textnow/panel.js` references

2. **Added**:
   - `panel.py` - Panel registration using proper HA APIs
   - `websocket.py` - WebSocket commands for panel communication
   - `frontend/textnow-panel.js` - Native frontend module

3. **Updated**:
   - `__init__.py` - Now registers WebSocket API and panel correctly

## Why This Works

1. **No Iframe**: Panel loads as a native frontend module, avoiding iframe security restrictions
2. **Static Path**: JS file is served via static path registration, not custom HTTP view
3. **WebSocket Auth**: All panel operations use WebSocket which inherits HA authentication
4. **Native Integration**: Panel is registered as a built-in panel, not an external iframe

## Testing

After restarting Home Assistant:
1. Panel should appear in the sidebar automatically
2. No 401 errors should occur
3. All contact management operations should work
4. Test message sending should function correctly


# LAN Share (WebRTC Direct P2P + Extension Launcher)

A fast, high-speed, local peer-to-peer file sharing and chat application designed to work **100% offline** over local Wi-Fi networks or mobile hotspots.

Built with direct **WebRTC DataChannels** (simple-peer), a **Python Flask + Socket.IO** signaling server, and a sleek **Chrome / Edge Extension Launcher** with Native Messaging.

---

## Key Highlights

- **Direct WebRTC Audio & Video Calling**: Make real-time peer-to-peer **Audio Calls** (with live waveform animations & ringback tones) and **Video Calls** (with remote video feeds and local picture-in-picture view). Dedicated call action buttons (green phone receiver for audio call, blue camera for video call) are seamlessly integrated into the mobile and desktop headers.
- **Dual Master Themes**:
  - **Light Theme**: Crystal-clear **Liquid Glassmorphism** & Neumorphism (specular white borders, frosted glass pill capsules, subtle drop shadows, and vibrant emerald accents).
  - **Dark Theme**: Stealth **Matte Carbon & Obsidian Spatial Theme** (deep charcoal backgrounds `#111417`, raised dual-shadow spatial cards, recessed well inputs, and high-tech neon mint & cyber cyan glowing cores).
  - One-click instant theme toggle with custom stroke **Sun & Crescent Moon** icons available across desktop and popup launcher.
- **Mobile-First Icon Theme**: Mobile header matches native phone layouts with dedicated circular action buttons (📣 Sound Horn, 📞 Phone Call, 📹 Video Camera, ⚃ QR Scanner, ⚙️ Settings / Diagnostics), emoji quick reaction bar, and floating glass capsule input dock.
- **100% Offline Capable**: Zero internet required. All client libraries (`socket.io.min.js`, `simplepeer.min.js`) are bundled locally within `/static/`. Transfers work at full Wi-Fi / Hotspot hardware speeds.
- **Chunked File Streaming with Flow Control**: Transfers files of any size with chunk-level backpressure management (`bufferedAmount` throttling) and real-time progress bars.
- **Queued Outbox**: Messages or files sent before a peer enters the room are held in a local outbox and automatically transmitted as soon as a peer connects.
- **Dynamic IP & Instant QR Codes**: Automatically detects network interface changes (e.g. connecting to a phone's mobile hotspot) and generates fresh QR codes on the fly via `/api/info` and `/qr.png`.
- **Clipboard & Media Sharing**: Paste screenshots directly from the clipboard (<kbd>Ctrl+V</kbd>), drag & drop files into the window, inspect photos in a full lightbox, and toggle audio chimes.
- **Multi-Tier Reliable Server Stop**: Stop button utilizes in-process HTTP signals (`/api/stop`), Win32 process termination, and PowerShell sweeps to guarantee instantaneous server shutdown.

---

## Screenshots

<div align="center">
  <h3>🖥️ Desktop Interface (Liquid Glassmorphism & Matte Carbon Dark)</h3>
  <img src="Photo/desktop.png" alt="LAN Share Desktop Web Client (Light Glassmorphic)" width="850" style="border-radius: 8px; max-width: 100%; margin-bottom: 12px;" />
  <img src="Photo/desktop_dark.png" alt="LAN Share Desktop Web Client (Matte Carbon Dark)" width="850" style="border-radius: 8px; max-width: 100%;" />
</div>

<br>

<div align="center">
  <table>
    <thead>
      <tr>
        <th align="center">📱 Mobile Phone Interface</th>
        <th align="center">🧩 Extension Popup Launcher</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td align="center" valign="top">
          <img src="Photo/phone.png" alt="Mobile Web Interface (Light)" width="320" style="border-radius: 8px; max-width: 100%; margin-bottom: 8px;" /><br>
          <img src="Photo/phone_dark.png" alt="Mobile Web Interface (Dark)" width="320" style="border-radius: 8px; max-width: 100%;" />
        </td>
        <td align="center" valign="top">
          <img src="Photo/extension.png" alt="Extension Popup (Light)" width="320" style="border-radius: 8px; max-width: 100%; margin-bottom: 8px;" /><br>
          <img src="Photo/extension_dark.png" alt="Extension Popup (Dark)" width="320" style="border-radius: 8px; max-width: 100%;" />
        </td>
      </tr>
    </tbody>
  </table>
</div>

---

## Project Structure

```
lan-share/
├── server.py                        # Flask + Socket.IO signaling relay & dynamic QR server
├── requirements.txt                 # Python dependencies
├── static/
│   ├── client.html                  # Full P2P messaging & file transfer web client
│   ├── socket.io.min.js             # Localized Socket.IO client (offline)
│   └── simplepeer.min.js            # Localized SimplePeer WebRTC client (offline)
├── extension/                       # Chrome & Edge Extension
│   ├── manifest.json                # Extension manifest v3
│   ├── popup.html                   # Extension popup UI (Dual Glassmorphic / Matte Carbon theme)
│   ├── popup.js                     # Server launcher & monitor
│   └── background.js                # Minimal service worker
├── native-host/                     # Native Messaging Host
│   ├── lan_share_host.py            # Python native host (start/stop server, PID tracker)
│   ├── lan_share_host_windows.json  # Chrome native host manifest
│   ├── start_server.bat             # Windows launcher wrapper
│   ├── register_native_host_windows.reg # Registry entry for Google Chrome
│   └── register_native_host_edge.reg    # Registry entry for Microsoft Edge
└── Photo/                           # Visual assets & screenshots
```

---

## Quick Start (Direct Server)

### 1. Prerequisites
Ensure Python 3.10+ is installed:
```bash
python --version
```

Install the required packages:
```bash
pip install -r requirements.txt
```

### 2. Run the Signaling Server
```bash
python server.py
```
By default, the server will bind to `0.0.0.0:5000` and display your local network IP:
```
📱 QR code saved as lan_share_qr.png (points to http://192.168.x.x:5000/)
🔗 Open on other devices: http://192.168.x.x:5000/
```

> [!TIP]
> **Mobile Audio & Video Calling**: Mobile browsers (Android Chrome, iOS Safari) require HTTPS to grant microphone and camera permissions over LAN IPs. Start the server with `--ssl` to enable instant self-signed HTTPS:
> ```bash
> python server.py --ssl
> ```
> Open `https://<your-lan-ip>:5000/` on your phone (tap "Advanced" → "Proceed to site" once). Full hardware microphone and camera calling will be unlocked!

### 3. Open on Devices
- **Desktop**: Visit `http://localhost:5000/` in your browser.
- **Phone / Other PCs**: Connect to the same Wi-Fi or mobile hotspot and open `http://<your-lan-ip>:5000/` or scan the QR code.
- Ensure both devices join the same room name (default is `default`).

---

## Browser Extension Setup (Chrome, Edge & Brave)

The included browser extension allows you to start, monitor, and stop the LAN Share server directly from your browser toolbar.

### 1. Register the Native Messaging Host
Open the `native-host/` folder:
- **Automatic (Recommended)**: Double-click `install_native_host.cmd`. It automatically detects your project path and registers the native host for **Google Chrome**, **Microsoft Edge**, **Brave Browser**, and **Chromium**.
- **Manual**: Double-click `register_native_host_windows.reg`, `register_native_host_edge.reg`, or `register_native_host_brave.reg` and click **Yes**.

### 2. Load the Extension
1. Open your browser and navigate to `chrome://extensions`, `edge://extensions`, or `brave://extensions`.
2. Enable **Developer mode** (toggle in the top-right or sidebar).
3. Click **Load unpacked** and select the `extension/` directory.
4. Copy the newly generated **Extension ID** (e.g. `bolgcfjflofmejbacpjeolmgcicpblac`).
5. Ensure your extension ID is listed in `native-host/lan_share_host_windows.json` under `"allowed_origins"`.

### 3. Use the Extension
- Click the **LAN Share** icon in your extensions toolbar.
- Click **Start Server** to launch the server and open the web app.
- Click **Stop Server** to terminate the server.

---

## Mobile Hotspot Usage (Zero Internet)

1. Turn on your smartphone's **Portable Hotspot** (Mobile Data can be turned **OFF**).
2. Connect your laptop to the smartphone's Wi-Fi hotspot.
3. Start the LAN Share server on your laptop.
4. In the web app, click **Scan QR** or look at the detected IP in the bottom-left sidebar.
5. On your phone, open your mobile browser and navigate to the address shown.
6. Share files, images, and messages at full Wi-Fi speed without using any mobile data.

---

## Troubleshooting

- **Windows Firewall blocking mobile connections**:
  Windows often classifies mobile hotspots as "Public Networks". If other devices cannot reach port `5000`, run this command in PowerShell (Run as Administrator):
  ```powershell
  New-NetFirewallRule -DisplayName "LAN Share (Port 5000)" -Direction Inbound -LocalPort 5000 -Protocol TCP -Action Allow -Profile Any
  ```
- **Stopping server reports port busy**:
  The server supports a direct HTTP stop endpoint (`/api/stop`) as well as native host taskkill. If a port is held by an old session, restart the server via the extension or run:
  ```powershell
  Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
  ```
- **Clipboard copying on mobile**:
  HTTP endpoints restrict the modern asynchronous Clipboard API on mobile. LAN Share includes an automatic `document.execCommand` fallback so the 📋 button works seamlessly everywhere.

---

## License

MIT License © 2025-2026 [Beebek Sharma](https://github.com/Beebek-Sharma)

from flask import Flask, send_from_directory, request, jsonify, send_file
from flask_socketio import SocketIO, join_room, emit, disconnect
import qrcode
import os
import socket
import sys
import argparse
import io
from collections import defaultdict

# Ensure UTF-8 output encoding for console output on Windows
if sys.platform == 'win32':
    try:
        if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

app = Flask(__name__, static_folder='static')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading", ping_timeout=8, ping_interval=4)

# Track usernames per room so clients can show names
rooms = defaultdict(dict)  # room -> { sid: name }
sid_to_room = {}

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # doesn't actually send packets; used to determine local IP route
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        finally:
            s.close()
        return ip
    except Exception:
        try:
            ips = [ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith('127.') and not ip.startswith('169.254.')]
            if ips:
                return ips[0]
        except Exception:
            pass
        return "127.0.0.1"

@app.route('/')
def index():
    return send_from_directory('static', 'client.html')

import threading
import time

@app.route('/api/stop', methods=['POST', 'GET'])
def api_stop():
    def shutdown():
        time.sleep(0.3)
        os._exit(0)
    threading.Thread(target=shutdown, daemon=True).start()
    return jsonify({ "stopped": True, "message": "Server shutting down" })

@app.route('/api/info')
def api_info():
    ip = get_local_ip()
    scheme = "https" if request.is_secure else "http"
    port = request.host.split(':')[1] if ':' in request.host else (443 if request.is_secure else 5000)
    http_port = app.config.get('HTTP_PORT', 5000)
    https_port = app.config.get('HTTPS_PORT', 5001)
    all_ips = []
    try:
        all_ips = [i for i in socket.gethostbyname_ex(socket.gethostname())[2] if not i.startswith('127.') and not i.startswith('169.254.')]
    except Exception:
        pass
    return jsonify({
        "ip": ip,
        "port": port,
        "scheme": scheme,
        "url": f"{scheme}://{ip}:{port}/",
        "http_port": http_port,
        "https_port": https_port,
        "http_url": f"http://{ip}:{http_port}/" if http_port else None,
        "https_url": f"https://{ip}:{https_port}/" if https_port else None,
        "all_ips": all_ips
    })

@app.route('/qr.png')
def qr_image():
    # Dynamically generate QR code for the current active network IP
    try:
        ip = get_local_ip()
        qr_type = request.args.get('type')  # 'http', 'https', or None
        http_port = app.config.get('HTTP_PORT', 5000)
        https_port = app.config.get('HTTPS_PORT', 5001)

        if qr_type == 'https' and https_port:
            url = f"https://{ip}:{https_port}/"
        elif qr_type == 'http' and http_port:
            url = f"http://{ip}:{http_port}/"
        elif request.is_secure:
            port = request.host.split(':')[1] if ':' in request.host else 443
            url = f"https://{ip}:{port}/"
        else:
            url = f"https://{ip}:{https_port}/" if https_port else f"http://{ip}:{http_port}/"

        img = qrcode.make(url)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return send_file(buf, mimetype='image/png')
    except Exception:
        try:
            return send_from_directory('.', 'lan_share_qr.png')
        except Exception:
            return ('', 404)

@socketio.on('join-room')
def handle_join(data):
    room = data.get('room', 'default')
    name = data.get('name') or f"User-{request.sid[-4:]}"
    client_id = data.get('clientId')
    join_room(room)

    # If this client_id is already in rooms[room] under another (stale/previous) sid, evict it immediately
    if client_id:
        stale_sids = [s for s, info in list(rooms[room].items()) if isinstance(info, dict) and info.get('clientId') == client_id and s != request.sid]
        for stale_sid in stale_sids:
            rooms[room].pop(stale_sid, None)
            sid_to_room.pop(stale_sid, None)
            emit('peer-left', { 'id': stale_sid }, room=room, include_self=False)
            try:
                disconnect(stale_sid)
            except Exception:
                pass

    rooms[room][request.sid] = { 'name': name, 'clientId': client_id }
    sid_to_room[request.sid] = room

    # Send existing peers to the joiner (excluding this client and any of its previous sids)
    current = []
    for sid, info in rooms[room].items():
        if sid == request.sid:
            continue
        c_id = info.get('clientId') if isinstance(info, dict) else None
        if client_id and c_id == client_id:
            continue
        nm = info.get('name') if isinstance(info, dict) else info
        current.append({ 'id': sid, 'name': nm, 'clientId': c_id })

    emit('peers', current)
    # Notify others about this joiner
    emit('peer-joined', { 'id': request.sid, 'name': name, 'clientId': client_id }, room=room, include_self=False)

@socketio.on('signal')
def handle_signal(data):
    to = data.get('to')
    emit('signal', data, to=to)

@socketio.on('call-event')
def handle_call_event(data):
    to = data.get('to')
    if to:
        emit('call-event', data, to=to)
    else:
        room = sid_to_room.get(request.sid)
        if room:
            emit('call-event', data, room=room, include_self=False)

@socketio.on('update-name')
def handle_update_name(data):
    new_name = (data.get('name') or '').strip()
    if new_name and request.sid in sid_to_room:
        room = sid_to_room[request.sid]
        if isinstance(rooms[room].get(request.sid), dict):
            rooms[room][request.sid]['name'] = new_name
        else:
            rooms[room][request.sid] = { 'name': new_name }
        emit('peer-renamed', { 'id': request.sid, 'name': new_name }, room=room, include_self=False)

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    room = sid_to_room.pop(sid, None)
    name = None
    if room and sid in rooms[room]:
        entry = rooms[room].pop(sid, None)
        if isinstance(entry, dict):
            name = entry.get('name')
        else:
            name = entry
        if not rooms[room]:
            rooms.pop(room, None)
    payload = { 'id': sid, 'name': name } if name else { 'id': sid }
    if room:
        emit('peer-left', payload, room=room, include_self=False)
    else:
        emit('peer-left', payload, broadcast=True)

def ensure_self_signed_cert(cert_path='cert.pem', key_path='key.pem', ip='127.0.0.1'):
    try:
        if os.path.exists(cert_path) and os.path.exists(key_path):
            return cert_path, key_path
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        import datetime, ipaddress

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "LAN Share Local P2P"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "LAN Share")
        ])
        alt_names = [
            x509.DNSName("localhost"),
            x509.IPAddress(ipaddress.IPv4Address("127.0.0.1"))
        ]
        try:
            alt_names.append(x509.IPAddress(ipaddress.IPv4Address(ip)))
        except Exception:
            pass

        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1))
            .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=3650))
            .add_extension(x509.SubjectAlternativeName(alt_names), critical=False)
            .sign(key, hashes.SHA256())
        )

        with open(key_path, "wb") as f:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))
        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        return cert_path, key_path
    except Exception as e:
        print("⚠️ Could not generate self-signed cert:", e)
        return None, None

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="LAN Share Signaling Server")
    parser.add_argument('--port', type=int, default=5000, help='HTTP port (default: 5000)')
    parser.add_argument('--https-port', type=int, default=5001, help='HTTPS port (default: 5001)')
    parser.add_argument('--no-ssl', action='store_true', help='Disable HTTPS server')
    parser.add_argument('--ssl-only', action='store_true', help='Only run HTTPS on primary port')
    parser.add_argument('--ssl', action='store_true', help='Alias for HTTPS mode')
    parser.add_argument('--no-qr', action='store_true', help='Do not create QR file')
    args = parser.parse_args()

    ip = get_local_ip()
    http_port = args.port
    https_port = args.https_port if not args.no_ssl else None

    if args.ssl_only or (args.ssl and args.no_ssl):
        https_port = http_port
        http_port = None

    app.config['HTTP_PORT'] = http_port
    app.config['HTTPS_PORT'] = https_port

    ssl_context = None
    if https_port:
        cert_file, key_file = ensure_self_signed_cert('cert.pem', 'key.pem', ip)
        if cert_file and key_file:
            ssl_context = (cert_file, key_file)
        else:
            https_port = None
            app.config['HTTPS_PORT'] = None

    print("\n" + "=" * 62)
    print("   🌐 LAN Share - Instant P2P File Sharing & Calling")
    print("=" * 62)
    if http_port:
        print(f"   ⚡ HTTP  (Chat & Fast Transfers) : http://{ip}:{http_port}/")
        print(f"      Local: http://localhost:{http_port}/")
    if https_port and ssl_context:
        print(f"   🔒 HTTPS (Voice & Video Calls)   : https://{ip}:{https_port}/")
        print(f"      Local: https://localhost:{https_port}/")
    print("=" * 62)
    print("   📱 Mobile devices: Connect to the same Wi-Fi network.")
    if https_port:
        print("   🔒 Note for Mobile: Use the HTTPS link to grant Camera/Mic access.")
    print("=" * 62 + "\n")

    if not args.no_qr and (https_port or http_port):
        try:
            qr_target = f"https://{ip}:{https_port}/" if https_port else f"http://{ip}:{http_port}/"
            img = qrcode.make(qr_target)
            qr_file = "lan_share_qr.png"
            img.save(qr_file)
            print(f"📱 QR code saved to {qr_file} (points to {qr_target})")
        except Exception as e:
            print("⚠️ Could not generate QR code:", e)

    # Start servers
    if http_port and https_port and ssl_context:
        # Dual-server mode: run HTTPS in background thread and HTTP in main thread
        def run_https():
            try:
                socketio.run(app, host='0.0.0.0', port=https_port, ssl_context=ssl_context, allow_unsafe_werkzeug=True)
            except Exception as e:
                print("HTTPS server error:", e)

        https_thread = threading.Thread(target=run_https, daemon=True)
        https_thread.start()
        socketio.run(app, host='0.0.0.0', port=http_port, allow_unsafe_werkzeug=True)
    elif https_port and ssl_context:
        socketio.run(app, host='0.0.0.0', port=https_port, ssl_context=ssl_context, allow_unsafe_werkzeug=True)
    else:
        socketio.run(app, host='0.0.0.0', port=http_port or 5000, allow_unsafe_werkzeug=True)

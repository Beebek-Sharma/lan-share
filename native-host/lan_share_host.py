import sys, os, json, struct, subprocess, socket, time, urllib.request, signal

# Native Messaging helpers

def send_message(msg: dict):
    data = json.dumps(msg).encode('utf-8')
    sys.stdout.buffer.write(struct.pack('<I', len(data)))
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def read_message():
    raw_len = sys.stdin.buffer.read(4)
    if len(raw_len) == 0:
        return None
    msg_len = struct.unpack('<I', raw_len)[0]
    data = sys.stdin.buffer.read(msg_len)
    if not data:
        return None
    return json.loads(data.decode('utf-8'))


def is_port_open(port: int, host: str = '127.0.0.1', timeout: float = 0.2) -> bool:
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        return True
    except Exception:
        return False
    finally:
        try:
            s.close()
        except Exception:
            pass


def _append(host_log: str, line: str):
    try:
        with open(host_log, 'a', encoding='utf-8') as f:
            f.write(line + "\n")
    except Exception:
        pass


def _read_tail(path: str, max_bytes: int = 2000) -> str | None:
    try:
        size = os.path.getsize(path)
        with open(path, 'rb') as f:
            if size > max_bytes:
                f.seek(size - max_bytes)
            data = f.read().decode('utf-8', errors='ignore')
            return data
    except Exception:
        return None


def start_server(project_dir: str, port: int = 5000) -> dict:
    # If already up, short-circuit
    if is_port_open(port):
        return {"started": True, "ready": True, "alreadyRunning": True, "port": port}

    py = sys.executable or 'python'
    server_py = os.path.join(project_dir, 'server.py')
    if not os.path.exists(server_py):
        return {"started": False, "error": f"server.py not found in {project_dir}"}

    DETACHED_PROCESS = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP

    host_log = os.path.join(project_dir, 'lan_share_host.log')
    server_log = os.path.join(project_dir, 'lan_share_server.log')
    _append(host_log, f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] start requested on port {port} using {py}")

    try:
        # Redirect server stdout/stderr to a logfile for diagnostics
        logf = open(server_log, 'ab', buffering=0)
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUTF8'] = '1'
        proc = subprocess.Popen([py, server_py, '--port', str(port)], cwd=project_dir,
                          stdout=logf, stderr=logf,
                          creationflags=flags, env=env)
        # Record PID for reliable stopping
        try:
            with open(os.path.join(project_dir, 'lan_share_server.pid'), 'w', encoding='utf-8') as pf:
                pf.write(str(proc.pid))
        except Exception:
            pass
    except Exception as e:
        _append(host_log, f"spawn failed: {e}")
        return {"started": False, "error": f"spawn failed: {e}"}

    # Wait for readiness up to ~8 seconds
    deadline = time.time() + 8.0
    while time.time() < deadline:
        if is_port_open(port):
            return {"started": True, "ready": True, "port": port}
        time.sleep(0.3)

    log_tail = _read_tail(server_log)
    if log_tail:
        _append(host_log, "timeout waiting for server; tail follows:\n" + log_tail)
    return {"started": True, "ready": False, "port": port, "error": "timeout", "logTail": (log_tail or None)}


def find_pids_for_server(port: int, project_dir: str = None) -> list:
    """Find all PIDs listening on the given TCP port or in the saved pidfile."""
    pids = set()

    # 1. Check saved pidfile first
    if project_dir:
        pid_file = os.path.join(project_dir, 'lan_share_server.pid')
        if os.path.exists(pid_file):
            try:
                with open(pid_file, 'r', encoding='utf-8') as f:
                    saved_pid = int(f.read().strip())
                    if saved_pid > 0:
                        pids.add(saved_pid)
            except Exception:
                pass

    # 2. Netstat check (Windows & Unix)
    try:
        if os.name == 'nt':
            out = subprocess.check_output(['netstat', '-ano', '-p', 'tcp'], text=True, errors='ignore')
            target = f":{port}"
            for line in out.splitlines():
                if 'LISTEN' in line.upper():
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        local_addr = parts[1]
                        if local_addr.endswith(target):
                            try:
                                pids.add(int(parts[-1]))
                            except ValueError:
                                pass
        else:
            out = subprocess.check_output(['lsof', '-i', f':{port}', '-sTCP:LISTEN', '-Pn'], text=True, errors='ignore')
            for line in out.splitlines()[1:]:
                parts = line.split()
                if len(parts) > 1 and parts[1].isdigit():
                    pids.add(int(parts[1]))
    except Exception:
        pass

    # 3. PowerShell Get-NetTCPConnection (Windows fallback)
    if os.name == 'nt' and not pids:
        try:
            ps_cmd = f"(Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue).OwningProcess"
            out = subprocess.check_output(['powershell', '-NoProfile', '-Command', ps_cmd], text=True, errors='ignore').strip()
            for line in out.splitlines():
                line = line.strip()
                if line.isdigit() and int(line) > 0:
                    pids.add(int(line))
        except Exception:
            pass

    return list(pids)


def request_http_stop(port: int) -> bool:
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/stop", method="POST")
        with urllib.request.urlopen(req, timeout=0.8) as resp:
            return resp.status == 200
    except Exception:
        return False


def kill_pid(pid: int) -> bool:
    if pid <= 0:
        return False
    success = False

    # Method 1: os.kill
    try:
        os.kill(pid, signal.SIGTERM)
        success = True
    except Exception:
        pass

    # Method 2: Win32 TerminateProcess via ctypes
    if os.name == 'nt':
        try:
            import ctypes
            PROCESS_TERMINATE = 0x0001
            h = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
            if h:
                ctypes.windll.kernel32.TerminateProcess(h, 1)
                ctypes.windll.kernel32.CloseHandle(h)
                success = True
        except Exception:
            pass

        # Method 3: taskkill with full System32 path
        taskkill_cmd = r'C:\Windows\System32\taskkill.exe' if os.path.exists(r'C:\Windows\System32\taskkill.exe') else 'taskkill'
        try:
            res = subprocess.run([taskkill_cmd, '/PID', str(pid), '/T', '/F'],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0:
                success = True
        except Exception:
            pass

    return success


def stop_server(project_dir: str, port: int = 5000) -> dict:
    host_log = os.path.join(project_dir, 'lan_share_host.log')
    _append(host_log, f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] stop requested on port {port}")

    if not is_port_open(port):
        pid_file = os.path.join(project_dir, 'lan_share_server.pid')
        if os.path.exists(pid_file):
            try: os.remove(pid_file)
            except Exception: pass
        _append(host_log, f"server already stopped on port {port}")
        return {"stopped": True, "alreadyStopped": True, "port": port}

    # Step 1: Send HTTP stop request to /api/stop
    http_ok = request_http_stop(port)
    if http_ok:
        _append(host_log, "HTTP /api/stop signal accepted by server")

    # Step 2: Find all PIDs and terminate them
    pids = find_pids_for_server(port, project_dir)
    for pid in pids:
        ok = kill_pid(pid)
        _append(host_log, f"killed PID {pid} (success={ok})")

    # Step 3: Wait and re-check with active cleanup
    deadline = time.time() + 4.0
    while time.time() < deadline:
        if not is_port_open(port):
            pid_file = os.path.join(project_dir, 'lan_share_server.pid')
            if os.path.exists(pid_file):
                try: os.remove(pid_file)
                except Exception: pass
            _append(host_log, f"server stopped successfully on port {port}")
            return {"stopped": True, "port": port, "pids": pids}

        # If port still open, re-check PIDs and force PowerShell kill
        remaining = find_pids_for_server(port, project_dir)
        for pid in remaining:
            kill_pid(pid)

        if os.name == 'nt':
            try:
                ps_kill = f"Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | ForEach-Object {{ Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }}"
                subprocess.run(['powershell', '-NoProfile', '-Command', ps_kill],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

        time.sleep(0.25)

    if not is_port_open(port):
        pid_file = os.path.join(project_dir, 'lan_share_server.pid')
        if os.path.exists(pid_file):
            try: os.remove(pid_file)
            except Exception: pass
        _append(host_log, f"server stopped on port {port} after force cleanup")
        return {"stopped": True, "port": port}

    _append(host_log, f"port {port} still open after all kill methods")
    return {"stopped": False, "error": "port-still-open", "port": port, "pids": pids}


def main():
    # project_dir is parent of this file's directory
    here = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.abspath(os.path.join(here, os.pardir))

    req = read_message()
    if not req:
        # No message; gracefully exit
        return

    action = req.get('action')
    port = int(req.get('port') or 5000)
    if action == 'start':
        res = start_server(project_dir, port=port)
        send_message(res)
    elif action == 'stop':
        res = stop_server(project_dir, port=port)
        send_message(res)
    else:
        send_message({"error": "unknown action", "received": req})


if __name__ == '__main__':
    # Ensure stdio is in binary mode on Windows
    if os.name == 'nt':
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    main()

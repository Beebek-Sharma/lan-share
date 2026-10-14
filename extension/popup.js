// Helper: fetch with timeout
function fetchWithTimeout(url, opts = {}, timeout = 1000) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(new Error('timeout'));
    }, timeout);
    fetch(url, opts).then(res => {
      clearTimeout(timer);
      resolve(res);
    }).catch(err => {
      clearTimeout(timer);
      reject(err);
    });
  });
}

// Helper: promise wrapper for sendNativeMessage
function sendNativeMessage(message) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendNativeMessage('lan_share_host', message, response => {
      if (chrome.runtime.lastError) {
        reject(chrome.runtime.lastError);
        return;
      }
      resolve(response);
    });
  });
}

// Poll localhost until it responds or timeout (ms)
async function waitForServer(url = 'http://localhost:5000', timeout = 5000, interval = 300) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    try {
      await fetchWithTimeout(url, { method: 'GET', mode: 'no-cors' }, 800);
      return true;
    } catch (e) {
      await new Promise(r => setTimeout(r, interval));
    }
  }
  return false;
}

function getPort() {
  const el = document.getElementById('port');
  const p = parseInt(el && el.value, 10);
  return Number.isFinite(p) && p > 0 ? p : 5000;
}

async function isServerUp() {
  try {
    const port = getPort();
    await fetchWithTimeout(`http://localhost:${port}`, { method: 'GET', mode: 'no-cors' }, 500);
    return true;
  } catch {
    return false;
  }
}

// UI State Manager
let currentLanUrl = '';

async function updateUiState() {
  const up = await isServerUp();
  const openBtn = document.getElementById('openApp');
  const stopBtn = document.getElementById('stopServer');
  const startBtn = document.getElementById('startServer');
  const badge = document.getElementById('serverBadge');
  const badgeText = document.getElementById('badgeText');
  const ipCard = document.getElementById('ipCard');
  const ipDisplay = document.getElementById('ipDisplay');
  const status = document.getElementById('status');

  if (openBtn) openBtn.disabled = !up;
  if (stopBtn) stopBtn.disabled = !up;

  if (up) {
    if (badge) badge.className = 'status-indicator running';
    if (badgeText) badgeText.textContent = 'Running';
    // Try to fetch server info for LAN IP
    try {
      const port = getPort();
      const res = await fetchWithTimeout(`http://localhost:${port}/api/info`, {}, 800);
      if (res.ok) {
        const data = await res.json();
        currentLanUrl = data.url || `http://localhost:${port}`;
        if (ipDisplay) ipDisplay.textContent = currentLanUrl;
        if (ipCard) ipCard.classList.add('show');
      }
    } catch {
      const port = getPort();
      currentLanUrl = `http://localhost:${port}`;
      if (ipDisplay) ipDisplay.textContent = currentLanUrl;
      if (ipCard) ipCard.classList.add('show');
    }
  } else {
    if (badge) badge.className = 'status-indicator';
    if (badgeText) badgeText.textContent = 'Offline';
    if (ipCard) ipCard.classList.remove('show');
  }
}

// Wire elements
const openBtn = document.getElementById('openApp');
const stopBtn = document.getElementById('stopServer');
const startBtn = document.getElementById('startServer');
const portInput = document.getElementById('port');
const copyIpBtn = document.getElementById('copyIpBtn');

if (copyIpBtn) {
  copyIpBtn.onclick = () => {
    if (currentLanUrl) {
      const copyPromise = (navigator.clipboard && navigator.clipboard.writeText)
        ? navigator.clipboard.writeText(currentLanUrl)
        : new Promise((res, rej) => {
            const ta = document.createElement('textarea');
            ta.value = currentLanUrl;
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
            res();
          });

      copyPromise.then(() => {
        copyIpBtn.textContent = '✅';
        setTimeout(() => { copyIpBtn.textContent = '📋'; }, 2000);
      }).catch(() => {});
    }
  };
}

if (openBtn) {
  openBtn.onclick = () => {
    const port = getPort();
    chrome.tabs.create({ url: `http://localhost:${port}` });
  };
}

if (stopBtn) {
  stopBtn.onclick = async () => {
    const status = document.getElementById('status');
    const port = getPort();
    stopBtn.disabled = true;
    status.innerText = 'Stopping server...';

    // 1. Direct HTTP stop signal
    try {
      fetch(`http://localhost:${port}/api/stop`, { method: 'POST', mode: 'no-cors' }).catch(() => {});
    } catch (e) {}

    // 2. Native host stop
    try {
      const resp = await sendNativeMessage({ action: 'stop', port });
      if (resp && resp.stopped) {
        status.innerText = 'Server stopped successfully.';
      } else {
        await new Promise(r => setTimeout(r, 400));
        const closed = !(await isServerUp());
        if (closed) {
          status.innerText = 'Server stopped successfully.';
        } else {
          const errDetail = resp && resp.error ? ` (${resp.error})` : '';
          status.innerText = `Could not stop server${errDetail}.`;
        }
      }
    } catch (e) {
      await new Promise(r => setTimeout(r, 500));
      const closed = !(await isServerUp());
      if (closed) {
        status.innerText = 'Server stopped successfully.';
      } else {
        const detail = e && (e.message || e.toString());
        status.innerText = `Failed to contact native host: ${detail}`;
      }
    }
    await updateUiState();
  };
}

if (startBtn) {
  startBtn.onclick = async () => {
    const status = document.getElementById('status');
    const port = getPort();
    const originalLabel = startBtn.innerHTML;
    startBtn.disabled = true;
    startBtn.innerHTML = '<span>⏳</span> Starting...';
    status.innerText = 'Checking running server...';

    // Quick check: if already up
    try {
      await fetchWithTimeout(`http://localhost:${port}`, { method: 'GET', mode: 'no-cors' }, 700);
      chrome.tabs.create({ url: `http://localhost:${port}` });
      status.innerText = 'Server already running — opened web app.';
      startBtn.disabled = false;
      startBtn.innerHTML = originalLabel;
      await updateUiState();
      return;
    } catch (e) {}

    status.innerText = 'Starting server via native host...';
    try {
      if (portInput) portInput.disabled = true;
      const resp = await sendNativeMessage({ action: 'start', port });
      if (!resp || !resp.started) {
        const errDetail = resp && resp.error ? ` (${resp.error})` : '';
        status.innerText = `Native host did not start server${errDetail}.`;
        console.warn('Native host start response:', resp);
        startBtn.disabled = false;
        startBtn.innerHTML = originalLabel;
        if (portInput) portInput.disabled = false;
        await updateUiState();
        return;
      }

      status.innerText = 'Waiting for server to be ready...';
      const up = await waitForServer(`http://localhost:${port}`, 8000, 300);
      if (up) {
        status.innerText = 'Server ready — opened web app.';
        chrome.tabs.create({ url: `http://localhost:${port}` });
        startBtn.disabled = false;
        startBtn.innerHTML = originalLabel;
      } else {
        status.innerText = 'Server timed out during startup.';
        console.warn('Server startup timed out');
        startBtn.disabled = false;
        startBtn.innerHTML = originalLabel;
      }
    } catch (err) {
      const detail = (err && (err.message || err.toString())) || '';
      status.innerText = `Native host error: ${detail || 'check registration'}`;
      console.error('sendNativeMessage start error:', detail, err);
      startBtn.disabled = false;
      startBtn.innerHTML = originalLabel;
    }
    if (portInput) portInput.disabled = false;
    await updateUiState();
  };
}

if (portInput) {
  portInput.addEventListener('input', () => {
    updateUiState();
  });
}

const SUN_SVG = `<svg class="theme-icon-svg sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
  <circle cx="12" cy="12" r="4.5"></circle>
  <line x1="12" y1="1.5" x2="12" y2="4"></line>
  <line x1="12" y1="20" x2="12" y2="22.5"></line>
  <line x1="4.22" y1="4.22" x2="6" y2="6"></line>
  <line x1="18" y1="18" x2="19.78" y2="19.78"></line>
  <line x1="1.5" y1="12" x2="4" y2="12"></line>
  <line x1="20" y1="12" x2="22.5" y2="12"></line>
  <line x1="4.22" y1="19.78" x2="6" y2="18"></line>
  <line x1="18" y1="6" x2="19.78" y2="4.22"></line>
</svg>`;

const MOON_SVG = `<svg class="theme-icon-svg moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M20.5 13.2A8.5 8.5 0 1 1 10.8 3.5a6.8 6.8 0 0 0 9.7 9.7z"></path>
</svg>`;

// Theme Toggle in Popup
function updatePopupTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  const themeBtn = document.getElementById('themeToggleBtn');
  if (themeBtn) {
    themeBtn.innerHTML = theme === 'dark' ? MOON_SVG : SUN_SVG;
    themeBtn.title = theme === 'dark' ? 'Switch to Light Theme' : 'Switch to Dark Theme';
  }
}

const themeBtn = document.getElementById('themeToggleBtn');
if (themeBtn) {
  const urlTheme = new URLSearchParams(window.location.search).get('theme');
  const curTheme = urlTheme || localStorage.getItem('lan-share-theme') || 'light';
  updatePopupTheme(curTheme);

  themeBtn.onclick = () => {
    const cur = document.documentElement.getAttribute('data-theme') || 'light';
    const next = cur === 'light' ? 'dark' : 'light';
    localStorage.setItem('lan-share-theme', next);
    updatePopupTheme(next);
  };
}

// Initial state check
updateUiState().then(() => {
  const status = document.getElementById('status');
  if (status && status.innerText === 'Checking server status...') {
    status.innerText = 'Ready';
  }
});

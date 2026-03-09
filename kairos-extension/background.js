// Kairos Extension — Background Service Worker
// Handles API calls to kairos.bar with session cookies

const KAIROS_BASE = 'https://kairos.bar';

// Keep service worker alive during long-running API calls (MV3 workaround)
let keepAliveInterval = null;
function startKeepAlive() {
  if (keepAliveInterval) return;
  keepAliveInterval = setInterval(() => chrome.runtime.getPlatformInfo(() => {}), 25000);
}
function stopKeepAlive() {
  if (keepAliveInterval) { clearInterval(keepAliveInterval); keepAliveInterval = null; }
}

// Listen for messages from content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'KAIROS_ASK') {
    handleAskKairos(message, sendResponse);
    return true; // Keep channel open for async response
  }

  if (message.type === 'KAIROS_CHECK_AUTH') {
    checkAuth(sendResponse);
    return true;
  }

  if (message.type === 'KAIROS_GET_COURSES') {
    getCourses(sendResponse);
    return true;
  }

  if (message.type === 'KAIROS_CAPTURE_TAB') {
    captureTab(sender, sendResponse);
    return true;
  }
});

async function handleAskKairos(message, sendResponse) {
  startKeepAlive();
  try {
    // Get CSRF token from cookies
    const csrfCookie = await chrome.cookies.get({
      url: KAIROS_BASE,
      name: 'csrftoken'
    });

    const sessionCookie = await chrome.cookies.get({
      url: KAIROS_BASE,
      name: 'sessionid'
    });

    if (!sessionCookie) {
      sendResponse({ success: false, error: 'not_authenticated', message: 'Inicia sesión en kairos.bar primero.' });
      return;
    }

    const headers = {
      'Content-Type': 'application/json',
      'Cookie': `sessionid=${sessionCookie.value}` + (csrfCookie ? `; csrftoken=${csrfCookie.value}` : ''),
      'X-Kairos-Extension': '1'
    };
    if (csrfCookie) {
      headers['X-CSRFToken'] = csrfCookie.value;
    }

    const body = {
      text: message.text,
      course_id: message.courseId || null,
      canvas_course_id: message.canvasCourseId || null,
      image_base64: message.imageBase64 || null
    };

    const response = await fetch(`${KAIROS_BASE}/api/extension/ask/`, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
      credentials: 'include'
    });

    if (response.status === 403 || response.status === 401) {
      sendResponse({ success: false, error: 'not_authenticated', message: 'Sesión expirada. Inicia sesión en kairos.bar.' });
      return;
    }

    if (!response.ok) {
      console.error('[Kairos BG] HTTP error:', response.status, response.statusText);
      sendResponse({ success: false, error: 'server', message: `Error del servidor (${response.status}). Intenta de nuevo.` });
      return;
    }

    let data;
    try {
      data = await response.json();
    } catch (parseErr) {
      console.error('[Kairos BG] JSON parse error:', parseErr);
      sendResponse({ success: false, error: 'parse', message: 'Respuesta inválida del servidor.' });
      return;
    }

    sendResponse(data);
  } catch (err) {
    console.error('[Kairos BG] Network error:', err.message || err);
    sendResponse({ success: false, error: 'network', message: 'No se pudo conectar con Kairos. Verifica tu conexión.' });
  } finally {
    stopKeepAlive();
  }
}

async function checkAuth(sendResponse) {
  try {
    const sessionCookie = await chrome.cookies.get({
      url: KAIROS_BASE,
      name: 'sessionid'
    });
    sendResponse({ authenticated: !!sessionCookie });
  } catch {
    sendResponse({ authenticated: false });
  }
}

async function getCourses(sendResponse) {
  try {
    const sessionCookie = await chrome.cookies.get({ url: KAIROS_BASE, name: 'sessionid' });
    const csrfCookie = await chrome.cookies.get({ url: KAIROS_BASE, name: 'csrftoken' });

    if (!sessionCookie) {
      sendResponse({ success: false, courses: [] });
      return;
    }

    const headers = {
      'Cookie': `sessionid=${sessionCookie.value}` + (csrfCookie ? `; csrftoken=${csrfCookie.value}` : ''),
      'X-Kairos-Extension': '1'
    };

    const response = await fetch(`${KAIROS_BASE}/api/extension/courses/`, { headers });
    const data = await response.json();
    sendResponse(data);
  } catch {
    sendResponse({ success: false, courses: [] });
  }
}

async function captureTab(sender, sendResponse) {
  try {
    const tabId = sender.tab ? sender.tab.id : null;
    if (!tabId) {
      sendResponse(null);
      return;
    }
    const dataUrl = await chrome.tabs.captureVisibleTab(sender.tab.windowId, { format: 'png' });
    sendResponse(dataUrl);
  } catch (err) {
    console.error('[Kairos BG] captureTab error:', err);
    sendResponse(null);
  }
}

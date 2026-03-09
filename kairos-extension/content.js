// Kairos Extension — Content Script
// Detects text selection, shows Kairos button, opens popup with RAG response.

(function () {
  'use strict';
  if (document.getElementById('kairos-ext-root')) return; // Already injected

  // ── Palette ──
  const P = {
    primary: '#3355ff',
    primaryHover: '#2244dd',
    secondary: '#f6558b',
    accent: '#1a6df2',
    bg: '#ffffff',
    bgSoft: '#f5f7fa',
    text: '#1a1a2e',
    textMuted: '#6b7280',
    border: '#e5e7eb',
    shadow: 'rgba(51,85,255,.12)',
    radius: '14px',
    font: "'Inter','Segoe UI',system-ui,-apple-system,sans-serif",
  };

  // ── Host element (shadow DOM isolates styles) ──
  const host = document.createElement('div');
  host.id = 'kairos-ext-root';
  host.style.cssText = 'all:initial;position:fixed;z-index:2147483647;pointer-events:none;top:0;left:0;width:0;height:0;';
  document.documentElement.appendChild(host);
  const shadow = host.attachShadow({ mode: 'open' });

  // ── Inject Google Fonts (Inter) into host page head ──
  if (!document.querySelector('link[data-kairos-font]')) {
    const fontLink = document.createElement('link');
    fontLink.rel = 'stylesheet';
    fontLink.href = 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap';
    fontLink.setAttribute('data-kairos-font', '1');
    document.head.appendChild(fontLink);
  }

  // ── Styles inside shadow DOM ──
  const style = document.createElement('style');
  style.textContent = `
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    @import url('https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css');

    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    /* ── Floating Action Button ── */
    .kairos-fab {
      position: fixed;
      display: none;
      align-items: center;
      gap: 8px;
      padding: 10px 18px;
      background: ${P.primary};
      color: #fff;
      border: none;
      border-radius: 50px;
      font: 600 13px/1 ${P.font};
      cursor: pointer;
      box-shadow: 0 4px 20px ${P.shadow}, 0 2px 8px rgba(0,0,0,.08);
      transition: all .2s ease;
      pointer-events: auto;
      z-index: 2147483647;
      white-space: nowrap;
    }
    .kairos-fab:hover { background: ${P.primaryHover}; transform: translateY(-1px); box-shadow: 0 6px 28px ${P.shadow}; }
    .kairos-fab svg { width: 16px; height: 16px; fill: #fff; flex-shrink: 0; }

    /* ── Popup Overlay ── */
    .kairos-popup {
      position: fixed;
      display: none;
      flex-direction: column;
      width: 420px;
      max-width: calc(100vw - 32px);
      max-height: 70vh;
      background: ${P.bg};
      border-radius: ${P.radius};
      box-shadow: 0 12px 48px rgba(0,0,0,.15), 0 4px 16px rgba(0,0,0,.08);
      overflow: hidden;
      pointer-events: auto;
      font-family: ${P.font};
      color: ${P.text};
      z-index: 2147483647;
      animation: kairosSlideIn .25s ease;
    }
    @keyframes kairosSlideIn {
      from { opacity: 0; transform: translateY(12px) scale(.97); }
      to   { opacity: 1; transform: translateY(0) scale(1); }
    }

    /* Header */
    .kairos-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 14px 18px;
      background: ${P.primary};
      color: #fff;
    }
    .kairos-header-left { display: flex; align-items: center; gap: 8px; font-weight: 700; font-size: 15px; }
    .kairos-header-left svg { width: 20px; height: 20px; }
    .kairos-close {
      background: rgba(255,255,255,.15);
      border: none;
      color: #fff;
      width: 28px; height: 28px;
      border-radius: 8px;
      font-size: 18px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: background .15s;
    }
    .kairos-close:hover { background: rgba(255,255,255,.3); }

    /* Body */
    .kairos-body { padding: 16px 18px; overflow-y: auto; flex: 1; }

    /* Selected text preview */
    .kairos-selected-label { font-size: 11px; font-weight: 600; color: ${P.textMuted}; text-transform: uppercase; letter-spacing: .5px; margin-bottom: 6px; }
    .kairos-selected-text {
      background: ${P.bgSoft};
      border: 1px solid ${P.border};
      border-radius: 10px;
      padding: 12px 14px;
      font-size: 13px;
      line-height: 1.6;
      color: ${P.text};
      max-height: 100px;
      overflow-y: auto;
      margin-bottom: 14px;
      white-space: pre-wrap;
    }

    /* Resolve button */
    .kairos-resolve {
      width: 100%;
      padding: 12px;
      background: ${P.primary};
      color: #fff;
      border: none;
      border-radius: 10px;
      font: 600 14px/1 ${P.font};
      cursor: pointer;
      transition: all .15s;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
    }
    .kairos-resolve:hover { background: ${P.primaryHover}; }
    .kairos-resolve:disabled { opacity: .5; cursor: not-allowed; }
    .kairos-resolve svg { width: 16px; height: 16px; fill: #fff; }

    /* Divider */
    .kairos-divider { height: 1px; background: ${P.border}; margin: 16px 0; }

    /* Response */
    .kairos-response { display: none; }
    .kairos-response-label { font-size: 11px; font-weight: 600; color: ${P.primary}; text-transform: uppercase; letter-spacing: .5px; margin-bottom: 10px; display: flex; align-items: center; gap: 6px; }
    .kairos-answer {
      font-size: 14px;
      line-height: 1.7;
      color: ${P.text};
    }

    /* Loading spinner */
    .kairos-loading {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 20px 0;
      color: ${P.textMuted};
      font-size: 13px;
    }
    .kairos-spinner {
      width: 20px; height: 20px;
      border: 2.5px solid ${P.border};
      border-top-color: ${P.primary};
      border-radius: 50%;
      animation: kSpin .7s linear infinite;
    }
    @keyframes kSpin { to { transform: rotate(360deg); } }

    /* Footer */
    .kairos-footer {
      padding: 10px 18px;
      border-top: 1px solid ${P.border};
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .kairos-footer-link {
      font-size: 12px;
      color: ${P.primary};
      text-decoration: none;
      font-weight: 500;
    }
    .kairos-footer-link:hover { text-decoration: underline; }
    .kairos-footer-brand { font-size: 11px; color: ${P.textMuted}; }

    /* ── Auth prompt ── */
    .kairos-auth {
      display: none;
      flex-direction: column;
      align-items: center;
      gap: 12px;
      padding: 30px 18px;
      text-align: center;
    }
    .kairos-auth p { font-size: 14px; color: ${P.textMuted}; line-height: 1.5; }
    .kairos-auth a {
      display: inline-block;
      padding: 10px 24px;
      background: ${P.primary};
      color: #fff;
      border-radius: 10px;
      font: 600 14px/1 ${P.font};
      text-decoration: none;
      transition: background .15s;
    }
    .kairos-auth a:hover { background: ${P.primaryHover}; }

    /* ── Markdown content styles ── */
    .kairos-answer h1, .kairos-answer h2, .kairos-answer h3,
    .kairos-answer h4, .kairos-answer h5, .kairos-answer h6 {
      margin: .8em 0 .4em; font-weight: 700; line-height: 1.3; color: ${P.text};
    }
    .kairos-answer h3 { font-size: 1.05em; }
    .kairos-answer h4 { font-size: 1em; }
    .kairos-answer p { margin: 0 0 .6em; }
    .kairos-answer p:last-child { margin-bottom: 0; }
    .kairos-answer ul, .kairos-answer ol { margin: .4em 0 .6em 1.4em; }
    .kairos-answer li { margin-bottom: .2em; }
    .kairos-answer strong { font-weight: 700; }
    .kairos-answer em { font-style: italic; }
    .kairos-answer a { color: ${P.accent}; text-decoration: underline; }
    .kairos-answer blockquote {
      border-left: 3px solid ${P.primary};
      margin: .5em 0; padding: 4px 12px;
      background: ${P.bgSoft}; border-radius: 4px;
      color: ${P.textMuted};
    }
    .kairos-answer code:not(.block) {
      background: ${P.bgSoft}; padding: 2px 5px; border-radius: 4px;
      font-family: 'Fira Code',Consolas,monospace; font-size: .88em;
      color: ${P.secondary};
    }
    .kairos-answer pre {
      background: #1e1e2e; color: #cdd6f4;
      padding: 12px 14px; border-radius: 10px;
      overflow-x: auto; margin: .6em 0;
      font-size: .85em; line-height: 1.5;
      white-space: pre;
    }
    .kairos-answer pre code { background: none; padding: 0; color: inherit; font-size: inherit; }
    .kairos-answer .table-wrap { overflow-x: auto; margin: .6em 0; border-radius: 8px; border: 1px solid ${P.border}; }
    .kairos-answer table { width: 100%; border-collapse: collapse; font-size: .88em; }
    .kairos-answer th, .kairos-answer td {
      border: 1px solid ${P.border};
      padding: 8px 10px; text-align: left;
    }
    .kairos-answer th { background: ${P.bgSoft}; font-weight: 600; }
    .kairos-answer tr:nth-child(even) { background: ${P.bgSoft}; }
    .kairos-answer hr { border: none; border-top: 1px solid ${P.border}; margin: .8em 0; }
    .kairos-answer img { max-width: 100%; border-radius: 8px; margin: .4em 0; }

    /* ── LaTeX math fallback (before KaTeX renders) ── */
    .kairos-math { font-family: 'KaTeX_Main','Times New Roman',serif; }
    .kairos-math[data-display="true"] { display: block; text-align: center; margin: .8em 0; font-size: 1.1em; overflow-x: auto; }
    .kairos-answer .katex-display { overflow-x: auto; overflow-y: hidden; padding: 4px 0; }

    /* ── Screenshot capture overlay ── */
    .kairos-capture-overlay {
      position: fixed;
      top: 0; left: 0; width: 100vw; height: 100vh;
      background: rgba(0,0,0,.3);
      cursor: crosshair;
      z-index: 2147483647;
      pointer-events: auto;
      display: none;
    }
    .kairos-capture-hint {
      position: fixed;
      top: 16px;
      left: 50%;
      transform: translateX(-50%);
      background: ${P.primary};
      color: #fff;
      padding: 10px 24px;
      border-radius: 50px;
      font: 600 13px/1 ${P.font};
      box-shadow: 0 4px 16px ${P.shadow};
      z-index: 2147483648;
      pointer-events: none;
      display: none;
    }
    .kairos-capture-rect {
      position: fixed;
      border: 2px solid ${P.primary};
      background: rgba(51,85,255,.08);
      z-index: 2147483647;
      pointer-events: none;
      display: none;
    }

    /* Camera FAB */
    .kairos-cam-fab {
      position: fixed;
      display: none;
      align-items: center;
      gap: 8px;
      padding: 10px 16px;
      background: ${P.secondary};
      color: #fff;
      border: none;
      border-radius: 50px;
      font: 600 13px/1 ${P.font};
      cursor: pointer;
      box-shadow: 0 4px 20px rgba(246,85,139,.2), 0 2px 8px rgba(0,0,0,.08);
      transition: all .2s ease;
      pointer-events: auto;
      z-index: 2147483647;
      white-space: nowrap;
    }
    .kairos-cam-fab:hover { background: #e5436f; transform: translateY(-1px); }
  `;
  shadow.appendChild(style);

  // ── SVG icon (sparkle) ──
  const sparkleIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v4m0 12v4m10-10h-4M6 12H2m15.07-7.07l-2.83 2.83M9.76 14.24l-2.83 2.83m11.14 0l-2.83-2.83M9.76 9.76L6.93 6.93"/></svg>`;

  // ── FAB Button ──
  const fab = document.createElement('button');
  fab.className = 'kairos-fab';
  fab.innerHTML = `<svg viewBox="0 0 24 24"><path d="M12 2L9.19 8.63 2 9.24l5.46 4.73L5.82 21 12 17.27 18.18 21l-1.64-7.03L22 9.24l-7.19-.61z"/></svg> Resolver con Kairos`;
  shadow.appendChild(fab);

  // ── Camera FAB Button ──
  const camFab = document.createElement('button');
  camFab.className = 'kairos-cam-fab';
  camFab.innerHTML = `📷 Capturar pantalla`;
  shadow.appendChild(camFab);

  // ── Screenshot capture overlay (lives in shadow DOM) ──
  const captureOverlay = document.createElement('div');
  captureOverlay.className = 'kairos-capture-overlay';
  shadow.appendChild(captureOverlay);

  const captureHint = document.createElement('div');
  captureHint.className = 'kairos-capture-hint';
  captureHint.textContent = 'Arrastra para seleccionar un área · Esc para cancelar';
  shadow.appendChild(captureHint);

  const captureRect = document.createElement('div');
  captureRect.className = 'kairos-capture-rect';
  shadow.appendChild(captureRect);

  // ── Popup ──
  const popup = document.createElement('div');
  popup.className = 'kairos-popup';
  popup.innerHTML = `
    <div class="kairos-header">
      <div class="kairos-header-left">
        <svg viewBox="0 0 24 24" fill="#fff"><path d="M12 2L9.19 8.63 2 9.24l5.46 4.73L5.82 21 12 17.27 18.18 21l-1.64-7.03L22 9.24l-7.19-.61z"/></svg>
        Kairos
      </div>
      <button class="kairos-close" id="kairosClose">×</button>
    </div>
    <div class="kairos-body">
      <div class="kairos-auth" id="kairosAuth">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="${P.primary}"><path d="M12 2L9.19 8.63 2 9.24l5.46 4.73L5.82 21 12 17.27 18.18 21l-1.64-7.03L22 9.24l-7.19-.61z"/></svg>
        <p>Inicia sesión en Kairos para usar el asistente IA.</p>
        <a href="https://kairos.bar/" target="_blank">Iniciar sesión en Kairos</a>
      </div>
      <div id="kairosMain">
        <div class="kairos-selected-label">Texto seleccionado</div>
        <div class="kairos-selected-text" id="kairosText"></div>
        <button class="kairos-resolve" id="kairosResolve">
          <svg viewBox="0 0 24 24"><path d="M12 2L9.19 8.63 2 9.24l5.46 4.73L5.82 21 12 17.27 18.18 21l-1.64-7.03L22 9.24l-7.19-.61z"/></svg>
          Resolver con Kairos
        </button>
        <div class="kairos-divider"></div>
        <div class="kairos-response" id="kairosResponse">
          <div class="kairos-response-label">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="${P.primary}"><path d="M12 2L9.19 8.63 2 9.24l5.46 4.73L5.82 21 12 17.27 18.18 21l-1.64-7.03L22 9.24l-7.19-.61z"/></svg>
            Respuesta de Kairos
          </div>
          <div class="kairos-answer" id="kairosAnswer"></div>
        </div>
        <div class="kairos-loading" id="kairosLoading" style="display:none;">
          <div class="kairos-spinner"></div>
          Kairos está pensando…
        </div>
      </div>
    </div>
    <div class="kairos-footer">
      <a class="kairos-footer-link" href="https://kairos.bar/" target="_blank">💬 Abrir chat completo</a>
      <span class="kairos-footer-brand">Kairos AI v1.0</span>
    </div>
  `;
  shadow.appendChild(popup);

  // Inject a small page script that loads KaTeX and exposes a render trigger.
  // This runs in the page context so it can load external libs and access the
  // shadow root (we created an open shadow root above).
  (function injectKaTeXLoader(){
    try {
      const loader = document.createElement('script');
      loader.type = 'text/javascript';
      loader.textContent = `(function(){
        if(window.__kairos_katex_ready) return;
        function loadScript(src){return new Promise((res,rej)=>{const s=document.createElement('script');s.src=src;s.onload=res;s.onerror=rej;document.head.appendChild(s);});}
        Promise.resolve()
          .then(()=>loadScript('https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.js'))
          .then(()=>loadScript('https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/contrib/auto-render.min.js'))
          .then(()=>{window.__kairos_katex_ready=true;console.info('[Kairos] KaTeX loaded');})
          .catch(e=>{console.warn('[Kairos] KaTeX load failed', e)});

        window.kairosRenderLatex = function(){
          try{
            if(!window.__kairos_katex_ready || !window.renderMathInElement) return false;
            const host = document.getElementById('kairos-ext-root');
            if(!host || !host.shadowRoot) return false;
            const answer = host.shadowRoot.querySelector('.kairos-answer');
            if(!answer) return false;
            renderMathInElement(answer, {
              delimiters: [
                {left: '$$', right: '$$', display: true},
                {left: '$', right: '$', display: false}
              ],
              ignoredTags: ['script','noscript','style','textarea','pre','code'],
              throwOnError: false
            });
            return true;
          }catch(err){console.warn('[Kairos] renderLatex error', err); return false;}
        };

        window.addEventListener('kairos-render-latex', ()=>{ window.kairosRenderLatex && window.kairosRenderLatex(); });
      })();`;
      document.documentElement.appendChild(loader);
    } catch (e) {
      console.warn('[Kairos] injectKaTeXLoader failed', e);
    }
  })();

  // ── Refs ──
  const $ = (s) => shadow.querySelector(s);
  const closeBtn = $('#kairosClose');
  const resolveBtn = $('#kairosResolve');
  const selectedTextEl = $('#kairosText');
  const responseEl = $('#kairosResponse');
  const answerEl = $('#kairosAnswer');
  const loadingEl = $('#kairosLoading');
  const authEl = $('#kairosAuth');
  const mainEl = $('#kairosMain');

  let selectedText = '';
  let isPopupOpen = false;
  let isCapturing = false;
  let capturedImageB64 = null;

  // ── Detect Canvas course ID from URL ──
  function detectCanvasCourseId() {
    const m = window.location.pathname.match(/\/courses\/(\d+)/);
    return m ? parseInt(m[1]) : null;
  }

  // ── Text selection → show FAB ──
  document.addEventListener('mouseup', (e) => {
    if (isPopupOpen || isCapturing) return;
    // Ignore clicks inside our own UI
    if (host.contains(e.target)) return;

    setTimeout(() => {
      const sel = window.getSelection();
      const text = sel ? sel.toString().trim() : '';

      if (text.length > 5) {
        selectedText = text;
        fab.style.display = 'flex';
        camFab.style.display = 'none';
        // Position near selection
        const range = sel.getRangeAt(0);
        const rect = range.getBoundingClientRect();
        fab.style.top = Math.max(8, rect.bottom + 8) + 'px';
        fab.style.left = Math.min(window.innerWidth - 240, Math.max(8, rect.left)) + 'px';
      } else {
        fab.style.display = 'none';
        // Show camera FAB at bottom-right when no text selected
        camFab.style.display = 'flex';
        camFab.style.bottom = '24px';
        camFab.style.right = '24px';
        camFab.style.top = 'auto';
        camFab.style.left = 'auto';
      }
    }, 10);
  });

  // Show camera FAB on load
  setTimeout(() => {
    if (!isPopupOpen) {
      camFab.style.display = 'flex';
      camFab.style.bottom = '24px';
      camFab.style.right = '24px';
      camFab.style.top = 'auto';
      camFab.style.left = 'auto';
    }
  }, 1000);

  // Hide FAB on scroll or click elsewhere
  document.addEventListener('mousedown', (e) => {
    if (host.contains(e.target)) return;
    if (!isPopupOpen) fab.style.display = 'none';
  });

  // ── FAB click → open popup ──
  fab.addEventListener('click', () => {
    fab.style.display = 'none';
    openPopup();
  });

  function openPopup() {
    isPopupOpen = true;
    popup.style.display = 'flex';
    // Position: center-right of viewport
    popup.style.top = '16vh';
    popup.style.right = '24px';
    popup.style.left = 'auto';

    // Restore label for text mode
    const label = shadow.querySelector('.kairos-selected-label');
    if (label) label.textContent = 'Texto seleccionado';

    // Truncate preview if very long
    selectedTextEl.textContent = selectedText.length > 500
      ? selectedText.slice(0, 500) + '…'
      : selectedText;

    // Reset state
    responseEl.style.display = 'none';
    loadingEl.style.display = 'none';
    resolveBtn.disabled = false;

    // Check auth
    chrome.runtime.sendMessage({ type: 'KAIROS_CHECK_AUTH' }, (res) => {
      if (res && res.authenticated) {
        authEl.style.display = 'none';
        mainEl.style.display = 'block';
      } else {
        authEl.style.display = 'flex';
        mainEl.style.display = 'none';
      }
    });
  }

  function closePopup() {
    isPopupOpen = false;
    popup.style.display = 'none';
    capturedImageB64 = null;
    // Restore label for next use
    const label = shadow.querySelector('.kairos-selected-label');
    if (label) label.textContent = 'Texto seleccionado';
    // Show camera FAB again
    camFab.style.display = 'flex';
  }

  closeBtn.addEventListener('click', closePopup);

  // ── Resolve button ──
  resolveBtn.addEventListener('click', () => {
    resolveBtn.disabled = true;
    loadingEl.style.display = 'flex';
    responseEl.style.display = 'none';

    const canvasCourseId = detectCanvasCourseId();

    const msg = {
      type: 'KAIROS_ASK',
      text: selectedText,
      canvasCourseId: canvasCourseId
    };

    // Attach screenshot image if captured
    if (capturedImageB64) {
      msg.imageBase64 = capturedImageB64;
      capturedImageB64 = null;
    }

    chrome.runtime.sendMessage(msg, (res) => {
      loadingEl.style.display = 'none';
      resolveBtn.disabled = false;

      if (res && res.success) {
        answerEl.innerHTML = miniMarkdown(res.response || res.answer || '');
        // Trigger KaTeX rendering with retry (CDN loads async)
        function triggerLatex(){ try{ window.dispatchEvent(new Event('kairos-render-latex')); }catch(e){} }
        triggerLatex();
        setTimeout(triggerLatex, 300);
        setTimeout(triggerLatex, 800);
        setTimeout(triggerLatex, 2000);
        responseEl.style.display = 'block';
      } else {
        const msg = (res && res.message) || 'Error desconocido';
        if (res && res.error === 'not_authenticated') {
          authEl.style.display = 'flex';
          mainEl.style.display = 'none';
        } else {
          answerEl.innerHTML = `<p style="color:${P.secondary}">${escapeHtml(msg)}</p>`;
          responseEl.style.display = 'block';
        }
      }
    });
  });

  // ── Escape key closes popup ──
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (isCapturing) cancelCapture();
      else if (isPopupOpen) closePopup();
    }
  });

  // ==========================================================================
  // SCREENSHOT CAPTURE — Region selection like Windows Snipping Tool
  // ==========================================================================

  let captureStart = null;

  camFab.addEventListener('click', () => {
    camFab.style.display = 'none';
    fab.style.display = 'none';
    startCapture();
  });

  function startCapture() {
    isCapturing = true;
    captureOverlay.style.display = 'block';
    captureHint.style.display = 'block';
    captureRect.style.display = 'none';
  }

  function cancelCapture() {
    isCapturing = false;
    captureOverlay.style.display = 'none';
    captureHint.style.display = 'none';
    captureRect.style.display = 'none';
    captureStart = null;
    // Show camera FAB again
    camFab.style.display = 'flex';
  }

  captureOverlay.addEventListener('mousedown', (e) => {
    captureStart = { x: e.clientX, y: e.clientY };
    captureRect.style.display = 'block';
    captureRect.style.left = e.clientX + 'px';
    captureRect.style.top = e.clientY + 'px';
    captureRect.style.width = '0';
    captureRect.style.height = '0';
  });

  captureOverlay.addEventListener('mousemove', (e) => {
    if (!captureStart) return;
    const x = Math.min(captureStart.x, e.clientX);
    const y = Math.min(captureStart.y, e.clientY);
    const w = Math.abs(e.clientX - captureStart.x);
    const h = Math.abs(e.clientY - captureStart.y);
    captureRect.style.left = x + 'px';
    captureRect.style.top = y + 'px';
    captureRect.style.width = w + 'px';
    captureRect.style.height = h + 'px';
  });

  captureOverlay.addEventListener('mouseup', (e) => {
    if (!captureStart) return;
    const x = Math.min(captureStart.x, e.clientX);
    const y = Math.min(captureStart.y, e.clientY);
    const w = Math.abs(e.clientX - captureStart.x);
    const h = Math.abs(e.clientY - captureStart.y);
    captureStart = null;

    // Ignore tiny selections (accidental clicks)
    if (w < 20 || h < 20) {
      cancelCapture();
      return;
    }

    // Hide overlay before capture so it's not in the screenshot
    captureOverlay.style.display = 'none';
    captureHint.style.display = 'none';
    captureRect.style.display = 'none';
    host.style.display = 'none';

    // Ask background to capture the visible tab
    setTimeout(() => {
      try {
        chrome.runtime.sendMessage({ type: 'KAIROS_CAPTURE_TAB' }, (dataUrl) => {
          host.style.display = '';
          isCapturing = false;

          if (chrome.runtime.lastError || !dataUrl) {
            console.warn('[Kairos] captureTab failed:', chrome.runtime.lastError?.message || 'no data');
            cancelCapture();
            return;
          }

          // Crop the region from the full-page screenshot
          cropImage(dataUrl, x, y, w, h, window.devicePixelRatio || 1)
            .then((croppedB64) => {
              capturedImageB64 = croppedB64;
              selectedText = '';
              openPopupWithImage(croppedB64);
            })
            .catch(() => {
              host.style.display = '';
              cancelCapture();
            });
        });
      } catch (err) {
        // Extension context invalidated (e.g. after update/reload)
        console.warn('[Kairos] sendMessage failed:', err);
        host.style.display = '';
        isCapturing = false;
        cancelCapture();
      }
    }, 120); // Delay so the overlay is gone before capture
  });

  function cropImage(dataUrl, x, y, w, h, dpr) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement('canvas');
        canvas.width = w * dpr;
        canvas.height = h * dpr;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, x * dpr, y * dpr, w * dpr, h * dpr, 0, 0, w * dpr, h * dpr);
        resolve(canvas.toDataURL('image/png'));
      };
      img.onerror = reject;
      img.src = dataUrl;
    });
  }

  function openPopupWithImage(imgDataUrl) {
    isPopupOpen = true;
    popup.style.display = 'flex';
    popup.style.top = '16vh';
    popup.style.right = '24px';
    popup.style.left = 'auto';

    // Show image preview instead of text
    const label = shadow.querySelector('.kairos-selected-label');
    label.textContent = 'Captura de pantalla';
    selectedTextEl.innerHTML = `<img src="${imgDataUrl}" style="max-width:100%;max-height:160px;border-radius:8px;">`;

    responseEl.style.display = 'none';
    loadingEl.style.display = 'none';
    resolveBtn.disabled = false;

    chrome.runtime.sendMessage({ type: 'KAIROS_CHECK_AUTH' }, (res) => {
      if (res && res.authenticated) {
        authEl.style.display = 'none';
        mainEl.style.display = 'block';
      } else {
        authEl.style.display = 'flex';
        mainEl.style.display = 'none';
      }
    });
  }

  // ── Minimal Markdown → HTML renderer ──
  function miniMarkdown(text) {
    if (!text) return '';
    let html = text;

    // ── Protect LaTeX from markdown processing ──
    const mathBlocks = [];
    // Display math $$...$$ (must come before inline $...$)
    html = html.replace(/\$\$([\s\S]*?)\$\$/g, (_, formula) => {
      const idx = mathBlocks.length;
      mathBlocks.push({ formula, display: true });
      return `%%KMATH${idx}%%`;
    });
    // Inline math $...$ (no newlines inside)
    html = html.replace(/(?<!\$)\$(?!\$)([^\$\n]+?)\$(?!\$)/g, (_, formula) => {
      const idx = mathBlocks.length;
      mathBlocks.push({ formula, display: false });
      return `%%KMATH${idx}%%`;
    });

    // Escape HTML entities first (then selectively unescape our markdown)
    html = escapeHtml(html);

    // Code blocks (``` ... ```)
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
      return `<pre><code class="block">${code.trim()}</code></pre>`;
    });

    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Headers (### )
    html = html.replace(/^#### (.+)$/gm, '<h4>$1</h4>');
    html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
    html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
    html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');

    // Bold + italic
    html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

    // Horizontal rule
    html = html.replace(/^---$/gm, '<hr>');

    // Blockquotes
    html = html.replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>');

    // Tables (pipe syntax)
    html = html.replace(/((?:^\|.+\|$\n?)+)/gm, (block) => {
      const rows = block.trim().split('\n').filter(r => r.trim());
      if (rows.length < 2) return block;
      // Check for separator row
      const sepIdx = rows.findIndex(r => /^\|[\s\-:|]+\|$/.test(r));
      let headerEnd = sepIdx > 0 ? sepIdx : 1;
      let tableHtml = '<div class="table-wrap"><table>';
      // Header
      tableHtml += '<thead>';
      for (let i = 0; i < headerEnd; i++) {
        const cells = rows[i].split('|').filter((_, idx, arr) => idx > 0 && idx < arr.length - 1);
        tableHtml += '<tr>' + cells.map(c => `<th>${c.trim()}</th>`).join('') + '</tr>';
      }
      tableHtml += '</thead><tbody>';
      const startData = sepIdx > 0 ? sepIdx + 1 : headerEnd;
      for (let i = startData; i < rows.length; i++) {
        const cells = rows[i].split('|').filter((_, idx, arr) => idx > 0 && idx < arr.length - 1);
        tableHtml += '<tr>' + cells.map(c => `<td>${c.trim()}</td>`).join('') + '</tr>';
      }
      tableHtml += '</tbody></table></div>';
      return tableHtml;
    });

    // Unordered lists
    html = html.replace(/((?:^[\-\*] .+$\n?)+)/gm, (block) => {
      const items = block.trim().split('\n');
      return '<ul>' + items.map(i => `<li>${i.replace(/^[\-\*] /, '')}</li>`).join('') + '</ul>';
    });

    // Ordered lists
    html = html.replace(/((?:^\d+\. .+$\n?)+)/gm, (block) => {
      const items = block.trim().split('\n');
      return '<ol>' + items.map(i => `<li>${i.replace(/^\d+\. /, '')}</li>`).join('') + '</ol>';
    });

    // Links and images
    html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1">');
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

    // Paragraphs: replace double newlines with </p><p>
    html = html.replace(/\n{2,}/g, '</p><p>');
    // Single newlines → <br>
    html = html.replace(/\n/g, '<br>');

    // Wrap in paragraph if not already wrapped
    if (!html.startsWith('<h') && !html.startsWith('<ul') && !html.startsWith('<ol') && !html.startsWith('<pre') && !html.startsWith('<div') && !html.startsWith('<table')) {
      html = '<p>' + html + '</p>';
    }

    // ── Restore LaTeX blocks (safe for innerHTML, KaTeX auto-render finds $$ delimiters) ──
    mathBlocks.forEach((block, i) => {
      const ph = `%%KMATH${i}%%`;
      const safeFormula = escapeHtml(block.formula);
      if (block.display) {
        html = html.replace(ph, `<div class="kairos-math" data-display="true">$$${safeFormula}$$</div>`);
      } else {
        html = html.replace(ph, `<span class="kairos-math">$${safeFormula}$</span>`);
      }
    });

    return html;
  }

  function escapeHtml(text) {
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }
})();

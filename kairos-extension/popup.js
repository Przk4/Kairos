// Kairos Extension — Popup Script
// Checks auth status when the popup opens.

document.addEventListener('DOMContentLoaded', () => {
  const statusBox = document.getElementById('statusBox');
  const statusDot = document.getElementById('statusDot');
  const statusText = document.getElementById('statusText');
  const infoText = document.getElementById('infoText');
  const loginBtn = document.getElementById('loginBtn');

  chrome.runtime.sendMessage({ type: 'KAIROS_CHECK_AUTH' }, (res) => {
    if (res && res.authenticated) {
      statusBox.className = 'status ok';
      statusDot.className = 'dot green';
      statusText.textContent = 'Conectado a Kairos';
      infoText.textContent = 'Selecciona texto en cualquier página y haz clic en "Resolver con Kairos" para obtener respuestas.';
      loginBtn.style.display = 'none';
    } else {
      statusBox.className = 'status no';
      statusDot.className = 'dot red';
      statusText.textContent = 'No conectado';
      infoText.textContent = 'Necesitas iniciar sesión en kairos.bar para usar la extensión.';
      loginBtn.style.display = 'block';
    }
  });
});

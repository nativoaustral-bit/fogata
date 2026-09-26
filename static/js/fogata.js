/**
 * FOGATA — JavaScript Progresivo (ES5 Estricto)
 * Compatible con Legacy Compatibility Targets: iOS 9.3+, Android 4.4/5+, Safari 9+
 * Cero dependencias externas. Fallback silencioso ante ausencia de APIs modernas.
 */

(function () {
  'use strict';

  // =========================================================================
  // 1. Control de Zoom Tipográfico (A- / A+)
  // =========================================================================
  function initZoomControl() {
    var letraEl = document.getElementById('cuerpo-letra');
    var btnMenos = document.getElementById('btn-zoom-menos');
    var btnMas = document.getElementById('btn-zoom-mas');

    if (!letraEl) {
      return;
    }

    var STORAGE_KEY = 'fogata_font_size';
    var MIN_SIZE = 12;
    var MAX_SIZE = 40;
    var STEP = 2;

    // Obtener tamaño guardado o inicial
    var currentSize = 18;
    try {
      var saved = window.localStorage && window.localStorage.getItem(STORAGE_KEY);
      if (saved) {
        var parsed = parseInt(saved, 10);
        if (!isNaN(parsed) && parsed >= MIN_SIZE && parsed <= MAX_SIZE) {
          currentSize = parsed;
        }
      }
    } catch (e) {
      // Ignorar fallos de acceso a localStorage (ej: modo incógnito en iOS 9)
    }

    function aplicarTamanio(size) {
      letraEl.style.fontSize = size + 'px';
      try {
        if (window.localStorage) {
          window.localStorage.setItem(STORAGE_KEY, size.toString());
        }
      } catch (e) {
        // Fallback silencioso
      }
    }

    aplicarTamanio(currentSize);

    if (btnMenos) {
      btnMenos.addEventListener('click', function (e) {
        e.preventDefault();
        if (currentSize - STEP >= MIN_SIZE) {
          currentSize -= STEP;
          aplicarTamanio(currentSize);
        }
      });
    }

    if (btnMas) {
      btnMas.addEventListener('click', function (e) {
        e.preventDefault();
        if (currentSize + STEP <= MAX_SIZE) {
          currentSize += STEP;
          aplicarTamanio(currentSize);
        }
      });
    }
  }

  // =========================================================================
  // 2. Wake Lock API (Mantener pantalla encendida en atril)
  // =========================================================================
  function initWakeLock() {
    var btnWake = document.getElementById('btn-wakelock');
    if (!btnWake) {
      return;
    }

    // Si la API no existe en el navegador (Legacy Targets), degradar limpiamente
    if (!('wakeLock' in navigator) || !navigator.wakeLock.request) {
      btnWake.title = 'Bloqueo de suspensión no soportado por este navegador';
      btnWake.innerHTML = '<span>📱 Mantener encendido no disp.</span>';
      btnWake.style.opacity = '0.5';
      btnWake.style.cursor = 'default';
      btnWake.disabled = true;
      return;
    }

    var wakeLockObj = null;

    function activarWakeLock() {
      navigator.wakeLock.request('screen').then(function (lock) {
        wakeLockObj = lock;
        btnWake.className = 'wakelock-btn active';
        btnWake.innerHTML = '<span>💡 Pantalla fija</span>';

        wakeLockObj.addEventListener('release', function () {
          wakeLockObj = null;
          btnWake.className = 'wakelock-btn';
          btnWake.innerHTML = '<span>💤 Mantener activa</span>';
        });
      })['catch'](function () {
        wakeLockObj = null;
        btnWake.className = 'wakelock-btn';
        btnWake.innerHTML = '<span>💤 Mantener activa</span>';
      });
    }

    function liberarWakeLock() {
      if (wakeLockObj !== null) {
        wakeLockObj.release();
        wakeLockObj = null;
      }
    }

    btnWake.addEventListener('click', function (e) {
      e.preventDefault();
      if (wakeLockObj === null) {
        activarWakeLock();
      } else {
        liberarWakeLock();
      }
    });

    // Intentar activar por defecto al entrar a Modo Músico
    activarWakeLock();

    // Re-adquirir si el usuario cambia de pestaña y regresa
    document.addEventListener('visibilitychange', function () {
      if (wakeLockObj !== null && document.visibilityState === 'visible') {
        activarWakeLock();
      }
    });
  }

  // =========================================================================
  // 3. Copiar Enlace de Sesión Compartida
  // =========================================================================
  function initCopyLink() {
    var btnCopy = document.getElementById('btn-copiar-enlace');
    var inputUrl = document.getElementById('input-enlace-compartido');

    if (!btnCopy || !inputUrl) {
      return;
    }

    btnCopy.addEventListener('click', function (e) {
      e.preventDefault();
      inputUrl.select();
      if (inputUrl.setSelectionRange) {
        inputUrl.setSelectionRange(0, 99999);
      }

      var copiado = false;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(inputUrl.value).then(function () {
          mostrarMensajeCopiado();
        })['catch'](function () {
          fallbackCopy();
        });
      } else {
        fallbackCopy();
      }

      function fallbackCopy() {
        try {
          copiado = document.execCommand('copy');
          if (copiado) {
            mostrarMensajeCopiado();
          }
        } catch (err) {
          // Si falla, el input ya está seleccionado para copia manual
        }
      }

      function mostrarMensajeCopiado() {
        var textoOriginal = btnCopy.innerHTML;
        btnCopy.innerHTML = '✓ ¡Copiado!';
        btnCopy.style.borderColor = '#4caf50';
        setTimeout(function () {
          btnCopy.innerHTML = textoOriginal;
          btnCopy.style.borderColor = '';
        }, 2200);
      }
    });
  }

  // Inicialización al cargar el DOM
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      initZoomControl();
      initWakeLock();
      initCopyLink();
    });
  } else {
    initZoomControl();
    initWakeLock();
    initCopyLink();
  }
})();

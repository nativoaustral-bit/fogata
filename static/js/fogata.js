/**
 * FOGATA — JavaScript Progresivo (ES5 Estricto)
 * Compatible con Legacy Compatibility Targets: iOS 9.3+, Android 4.4/5+, Safari 9+
 * Cero dependencias externas. Fallback silencioso ante ausencia de APIs modernas.
 * Fase 2: Auto-Scroll, Velocidad Ajustable, Navegación de Bloques y Prioridad Manual.
 */

(function () {
  'use strict';

  // =========================================================================
  // 1. Control de Zoom Tipográfico (A- / A+)
  // =========================================================================
  function initZoomControl(onSizeChange) {
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
      // Conservar ratio de lectura aproximado antes del cambio
      var totalScroll = document.documentElement.scrollHeight - window.innerHeight;
      var ratio = totalScroll > 0 ? (window.pageYOffset / totalScroll) : 0;

      letraEl.style.fontSize = size + 'px';

      // Reajustar scroll proporcional para mantener la estrofa actual visible
      var newTotalScroll = document.documentElement.scrollHeight - window.innerHeight;
      if (newTotalScroll > 0 && ratio > 0) {
        window.scrollTo(0, Math.round(ratio * newTotalScroll));
      }

      try {
        if (window.localStorage) {
          window.localStorage.setItem(STORAGE_KEY, size.toString());
        }
      } catch (e) {
        // Fallback silencioso
      }

      if (typeof onSizeChange === 'function') {
        onSizeChange();
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

  // =========================================================================
  // 4. Auto-Scroll y Navegación por Bloques (Fase 2)
  // =========================================================================
  function initAutoScrollAndBloques() {
    var cuerpoLetra = document.getElementById('cuerpo-letra');
    var btnScrollToggle = document.getElementById('btn-scroll-toggle');

    if (!cuerpoLetra || !btnScrollToggle) {
      return null;
    }

    var iconoPlay = document.getElementById('icono-scroll-play');
    var textoPlay = document.getElementById('texto-scroll-play');
    var btnVelMenos = document.getElementById('btn-vel-menos');
    var btnVelMas = document.getElementById('btn-vel-mas');
    var indicadorVel = document.getElementById('indicador-velocidad');
    var btnBloqueAnt = document.getElementById('btn-bloque-ant');
    var btnBloqueSig = document.getElementById('btn-bloque-sig');

    var STORAGE_KEY_SPEED = 'fogata_scroll_speed';
    var NIVELES_VELOCIDAD = [
      { nivel: 1, etiqueta: 'Muy lenta', pxPorSegundo: 14 },
      { nivel: 2, etiqueta: 'Lenta',     pxPorSegundo: 24 },
      { nivel: 3, etiqueta: 'Normal',    pxPorSegundo: 38 },
      { nivel: 4, etiqueta: 'Rápida',    pxPorSegundo: 58 },
      { nivel: 5, etiqueta: 'Muy rápida',pxPorSegundo: 88 }
    ];

    // Recuperar velocidad guardada (por defecto nivel 3: Normal)
    var nivelActual = 3;
    try {
      var savedSpeed = window.localStorage && window.localStorage.getItem(STORAGE_KEY_SPEED);
      if (savedSpeed) {
        var parsedSpeed = parseInt(savedSpeed, 10);
        if (!isNaN(parsedSpeed) && parsedSpeed >= 1 && parsedSpeed <= 5) {
          nivelActual = parsedSpeed;
        }
      }
    } catch (e) {
      // Fallback silencioso
    }

    function actualizarEtiquetaVelocidad() {
      if (indicadorVel) {
        indicadorVel.textContent = NIVELES_VELOCIDAD[nivelActual - 1].etiqueta;
      }
      if (btnVelMenos) {
        btnVelMenos.disabled = (nivelActual <= 1);
        btnVelMenos.style.opacity = (nivelActual <= 1) ? '0.35' : '1';
      }
      if (btnVelMas) {
        btnVelMas.disabled = (nivelActual >= 5);
        btnVelMas.style.opacity = (nivelActual >= 5) ? '0.35' : '1';
      }
      try {
        if (window.localStorage) {
          window.localStorage.setItem(STORAGE_KEY_SPEED, nivelActual.toString());
        }
      } catch (e) {}
    }

    actualizarEtiquetaVelocidad();

    if (btnVelMenos) {
      btnVelMenos.addEventListener('click', function (e) {
        e.preventDefault();
        if (nivelActual > 1) {
          nivelActual -= 1;
          actualizarEtiquetaVelocidad();
        }
      });
    }

    if (btnVelMas) {
      btnVelMas.addEventListener('click', function (e) {
        e.preventDefault();
        if (nivelActual < 5) {
          nivelActual += 1;
          actualizarEtiquetaVelocidad();
        }
      });
    }

    // Estado del Auto-Scroll
    var isAutoScrolling = false;
    var animFrameId = null;
    var timerFallbackId = null;
    var lastTime = null;
    var acumuladorPx = 0;
    var lastProgrammaticScrollY = -1;
    var isPerformingBlockJump = false;

    function pausarAutoScroll() {
      if (!isAutoScrolling) {
        return;
      }
      isAutoScrolling = false;

      if (animFrameId !== null) {
        if (window.cancelAnimationFrame) {
          window.cancelAnimationFrame(animFrameId);
        }
        animFrameId = null;
      }
      if (timerFallbackId !== null) {
        window.clearTimeout(timerFallbackId);
        timerFallbackId = null;
      }

      lastTime = null;
      acumuladorPx = 0;

      btnScrollToggle.className = 'atril-play-btn';
      btnScrollToggle.title = 'Iniciar auto-scroll';
      btnScrollToggle.setAttribute('aria-label', 'Iniciar auto-scroll');
      if (iconoPlay) {
        iconoPlay.innerHTML = '&#9654;'; // ▶
      }
      if (textoPlay) {
        textoPlay.textContent = 'Auto-scroll';
      }
    }

    function tick() {
      if (!isAutoScrolling) {
        return;
      }

      var now = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();
      if (!lastTime) {
        lastTime = now;
      }
      var dt = (now - lastTime) / 1000;
      lastTime = now;

      // Tope de seguridad para evitar saltos en background/tab inactivo
      if (dt > 0.1) {
        dt = 0.1;
      }

      var velPxSec = NIVELES_VELOCIDAD[nivelActual - 1].pxPorSegundo;
      acumuladorPx += velPxSec * dt;

      var maxScroll = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);

      if (acumuladorPx >= 1) {
        var step = Math.floor(acumuladorPx);
        acumuladorPx -= step;

        var nextY = window.pageYOffset + step;
        if (nextY >= maxScroll) {
          window.scrollTo(0, maxScroll);
          lastProgrammaticScrollY = maxScroll;
          pausarAutoScroll();
          return;
        }

        window.scrollBy(0, step);
        lastProgrammaticScrollY = window.pageYOffset;
      }

      // Verificación de fin de canción
      if (window.pageYOffset >= maxScroll - 4) {
        pausarAutoScroll();
        return;
      }

      programarFrame();
    }

    function programarFrame() {
      if (!isAutoScrolling) {
        return;
      }
      if (window.requestAnimationFrame) {
        animFrameId = window.requestAnimationFrame(tick);
      } else {
        timerFallbackId = window.setTimeout(tick, 30);
      }
    }

    function iniciarAutoScroll() {
      if (isAutoScrolling) {
        return;
      }

      var maxScroll = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
      if (window.pageYOffset >= maxScroll - 4) {
        return; // Ya está al final de la canción
      }

      isAutoScrolling = true;
      lastTime = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();
      acumuladorPx = 0;
      lastProgrammaticScrollY = window.pageYOffset;

      btnScrollToggle.className = 'atril-play-btn is-playing';
      btnScrollToggle.title = 'Pausar auto-scroll';
      btnScrollToggle.setAttribute('aria-label', 'Pausar auto-scroll');
      if (iconoPlay) {
        iconoPlay.innerHTML = '&#10074;&#10074;'; // ⏸
      }
      if (textoPlay) {
        textoPlay.textContent = 'Pausar';
      }

      programarFrame();
    }

    btnScrollToggle.addEventListener('click', function (e) {
      e.preventDefault();
      if (isAutoScrolling) {
        pausarAutoScroll();
      } else {
        iniciarAutoScroll();
      }
    });

    // Criterio 1: Scroll manual del usuario -> PAUSAR
    function onManualUserScroll() {
      if (isAutoScrolling && !isPerformingBlockJump) {
        pausarAutoScroll();
      }
    }

    window.addEventListener('wheel', onManualUserScroll, false);
    window.addEventListener('touchmove', onManualUserScroll, false);
    window.addEventListener('scroll', function () {
      if (isAutoScrolling && !isPerformingBlockJump) {
        if (lastProgrammaticScrollY >= 0) {
          var diff = Math.abs(window.pageYOffset - lastProgrammaticScrollY);
          // Si el usuario movió la barra de scroll manualmente más de 20px
          if (diff > 20) {
            pausarAutoScroll();
          }
        }
      }
    }, false);

    // Criterio 9: Pausar al pasar a segundo plano y PERMANECER pausado al regresar
    document.addEventListener('visibilitychange', function () {
      if (document.visibilityState === 'hidden') {
        if (isAutoScrolling) {
          pausarAutoScroll();
        }
      }
    });

    // =========================================================================
    // Detección y Navegación de Bloques
    // =========================================================================
    var posicionesBloques = [];

    function recalcularBloques() {
      posicionesBloques = [];
      if (!cuerpoLetra) return;

      var text = cuerpoLetra.textContent || cuerpoLetra.innerText || '';
      var lines = text.split('\n');
      if (lines.length === 0) return;

      var lineHeight = 26;
      if (window.getComputedStyle) {
        var computedLh = parseFloat(window.getComputedStyle(cuerpoLetra).lineHeight);
        if (!isNaN(computedLh) && computedLh > 0) {
          lineHeight = computedLh;
        }
      }

      var preTop = cuerpoLetra.offsetTop || 0;
      var blockLineIndices = [0];

      for (var i = 1; i < lines.length; i++) {
        var lineTrim = lines[i].trim();
        var prevTrim = lines[i - 1].trim();
        var esInicioBloque = false;

        if (lineTrim !== '' && prevTrim === '') {
          esInicioBloque = true;
        } else if (lineTrim.indexOf('[') === 0 && lineTrim.indexOf(']') > 1) {
          esInicioBloque = true;
        }

        if (esInicioBloque) {
          blockLineIndices.push(i);
        }
      }

      for (var b = 0; b < blockLineIndices.length; b++) {
        var idx = blockLineIndices[b];
        var y = Math.max(0, preTop + (idx * lineHeight) - 20);
        posicionesBloques.push(y);
      }

      // Deduplicar posiciones muy cercanas (< 25px)
      var filtrados = [];
      for (var f = 0; f < posicionesBloques.length; f++) {
        if (f === 0 || (posicionesBloques[f] - filtrados[filtrados.length - 1] > 25)) {
          filtrados.push(posicionesBloques[f]);
        }
      }
      posicionesBloques = filtrados;
    }

    recalcularBloques();

    function ejecutarSaltoBloque(targetY) {
      var maxScroll = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
      if (targetY > maxScroll) targetY = maxScroll;
      if (targetY < 0) targetY = 0;

      isPerformingBlockJump = true;
      lastProgrammaticScrollY = targetY;

      try {
        if ('scrollBehavior' in document.documentElement.style) {
          window.scrollTo({ top: targetY, behavior: 'smooth' });
        } else {
          window.scrollTo(0, targetY);
        }
      } catch (err) {
        window.scrollTo(0, targetY);
      }

      setTimeout(function () {
        isPerformingBlockJump = false;
        lastProgrammaticScrollY = window.pageYOffset;
      }, 450);
    }

    function avanzarBloque() {
      var currentY = window.pageYOffset;
      var targetY = null;

      if (posicionesBloques.length > 1) {
        for (var i = 0; i < posicionesBloques.length; i++) {
          if (posicionesBloques[i] > currentY + 30) {
            targetY = posicionesBloques[i];
            break;
          }
        }
        if (targetY === null) {
          targetY = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
        }
      } else {
        // Criterio 4: Fallback tolerante para canciones sin bloques (65% del viewport)
        targetY = currentY + (window.innerHeight * 0.65);
      }

      ejecutarSaltoBloque(targetY);
    }

    function retrocederBloque() {
      var currentY = window.pageYOffset;
      var targetY = null;

      if (posicionesBloques.length > 1) {
        for (var i = posicionesBloques.length - 1; i >= 0; i--) {
          if (posicionesBloques[i] < currentY - 30) {
            targetY = posicionesBloques[i];
            break;
          }
        }
        if (targetY === null) {
          targetY = 0;
        }
      } else {
        // Fallback
        targetY = currentY - (window.innerHeight * 0.65);
        if (targetY < 0) targetY = 0;
      }

      ejecutarSaltoBloque(targetY);
    }

    if (btnBloqueSig) {
      btnBloqueSig.addEventListener('click', function (e) {
        e.preventDefault();
        avanzarBloque();
      });
    }

    if (btnBloqueAnt) {
      btnBloqueAnt.addEventListener('click', function (e) {
        e.preventDefault();
        retrocederBloque();
      });
    }

    // Recalcular bloques ante redimensión o rotación de pantalla
    window.addEventListener('resize', recalcularBloques);
    window.addEventListener('orientationchange', recalcularBloques);

    return {
      recalcularBloques: recalcularBloques
    };
  }

  // Inicialización al cargar el DOM
  function inicializarTodo() {
    var autoScrollCtrl = initAutoScrollAndBloques();

    initZoomControl(function () {
      if (autoScrollCtrl && autoScrollCtrl.recalcularBloques) {
        setTimeout(autoScrollCtrl.recalcularBloques, 40);
      }
    });

    initWakeLock();
    initCopyLink();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', inicializarTodo);
  } else {
    inicializarTodo();
  }
})();

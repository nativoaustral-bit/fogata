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
      recalcularBloques: recalcularBloques,
      pausarAutoScroll: pausarAutoScroll
    };
  }

  // =========================================================================
  // 6. Transposición y Notación Dinámica en Atril (Fase 3)
  // =========================================================================
  function initTransposicionYNotacion() {
    var letraEl = document.getElementById('cuerpo-letra');
    if (!letraEl) {
      return;
    }

    var btnSubir = document.getElementById('btn-tono-subir');
    var btnBajar = document.getElementById('btn-tono-bajar');
    var btnReset = document.getElementById('btn-tono-reset');
    var btnToggleNotacion = document.getElementById('btn-toggle-notacion');
    var indicadorTono = document.getElementById('indicador-tono');
    var indicadorNotacionTexto = document.getElementById('indicador-notacion-texto');
    var atrilTagTonalidad = document.getElementById('atril-tag-tonalidad');
    var atrilListaAcordes = document.getElementById('atril-lista-acordes');

    var PITCH_SHARP_AMERICAN = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
    var PITCH_FLAT_AMERICAN  = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B'];
    var PITCH_SHARP_LATIN    = ['Do', 'Do#', 'Re', 'Re#', 'Mi', 'Fa', 'Fa#', 'Sol', 'Sol#', 'La', 'La#', 'Si'];
    var PITCH_FLAT_LATIN     = ['Do', 'Reb', 'Re', 'Mib', 'Mi', 'Fa', 'Solb', 'Sol', 'Lab', 'La', 'Sib', 'Si'];

    var TONALIDADES_BEMOLES = {
      'F': 1, 'BB': 1, 'EB': 1, 'AB': 1, 'DB': 1, 'GB': 1,
      'DM': 1, 'GM': 1, 'CM': 1, 'FM': 1, 'BBM': 1, 'EBM': 1,
      'FA': 1, 'SIB': 1, 'MIB': 1, 'LAB': 1, 'REB': 1, 'SOLB': 1,
      'REM': 1, 'SOLM': 1, 'DOM': 1, 'FAM': 1, 'SIBM': 1
    };

    var STORAGE_NOTATION_KEY = 'fogata_chord_notation';

    // Leer estado inicial desde el servidor
    var semitonos = parseInt(letraEl.getAttribute('data-semitonos') || '0', 10);
    if (isNaN(semitonos) || semitonos < -6 || semitonos > 6) {
      semitonos = 0;
    }

    var tonalidadOriginal = (letraEl.getAttribute('data-tonalidad') || '').trim();
    var notacion = letraEl.getAttribute('data-notacion') || 'original';

    // Recuperar preferencia de notación guardada en localStorage si existe (Criterio 11)
    try {
      if (window.localStorage) {
        var savedNotation = window.localStorage.getItem(STORAGE_NOTATION_KEY);
        if (savedNotation === 'american' || savedNotation === 'latin') {
          notacion = savedNotation;
        }
      }
    } catch (e) {
      // Ignorar fallos de localStorage
    }

    function resolverUsarBemoles(semitones) {
      if (tonalidadOriginal) {
        var tUpper = tonalidadOriginal.toUpperCase();
        if (tUpper.indexOf('B') !== -1 || tUpper.indexOf('♭') !== -1 || TONALIDADES_BEMOLES[tUpper]) {
          return true;
        }
        if (tUpper.indexOf('#') !== -1 || tUpper.indexOf('♯') !== -1) {
          return false;
        }
      }

      // Conteo de bemoles vs sostenidos en acordes originales
      var chords = letraEl.querySelectorAll('.acorde');
      var bCount = 0;
      var sharpCount = 0;
      for (var i = 0; i < chords.length; i++) {
        var orig = chords[i].getAttribute('data-original') || '';
        if (orig.indexOf('b') !== -1 || orig.indexOf('♭') !== -1) {
          bCount++;
        }
        if (orig.indexOf('#') !== -1 || orig.indexOf('♯') !== -1) {
          sharpCount++;
        }
      }
      if (bCount > sharpCount) return true;
      if (sharpCount > bCount) return false;

      return semitones < 0;
    }

    function formatearPitch(pitch, usarBemoles, targetNotation) {
      var p = ((pitch % 12) + 12) % 12;
      if (targetNotation === 'latin') {
        return usarBemoles ? PITCH_FLAT_LATIN[p] : PITCH_SHARP_LATIN[p];
      }
      return usarBemoles ? PITCH_FLAT_AMERICAN[p] : PITCH_SHARP_AMERICAN[p];
    }

    function transformarAcordeSpan(span, semitones, targetNotation) {
      var rootAttr = span.getAttribute('data-root');
      if (rootAttr === null || rootAttr === '') {
        return span.getAttribute('data-original') || span.textContent;
      }

      var rootPitch = parseInt(rootAttr, 10);
      if (isNaN(rootPitch)) {
        return span.getAttribute('data-original') || span.textContent;
      }

      var mod = span.getAttribute('data-mod') || '';
      var bassAttr = span.getAttribute('data-bass');
      var usarBemoles = resolverUsarBemoles(semitones);

      var effectiveNotation = targetNotation;
      if (effectiveNotation === 'original') {
        var origText = span.getAttribute('data-original') || '';
        var esLatina = /^(Do|Re|Mi|Fa|Sol|La|Si)/i.test(origText);
        effectiveNotation = esLatina ? 'latin' : 'american';
      }

      var newRoot = formatearPitch(rootPitch + semitones, usarBemoles, effectiveNotation);
      var newBass = '';

      if (bassAttr !== null && bassAttr !== '') {
        var bassPitch = parseInt(bassAttr, 10);
        if (!isNaN(bassPitch)) {
          newBass = '/' + formatearPitch(bassPitch + semitones, usarBemoles, effectiveNotation);
        }
      }

      return newRoot + mod + newBass;
    }

    function generarTextoTonalidad(semitones, targetNotation) {
      var usarBemoles = resolverUsarBemoles(semitones);
      var signo = semitones > 0 ? ('+' + semitones) : ('' + semitones);

      if (tonalidadOriginal) {
        var MAPA_TONO = {
          'C': 0, 'DO': 0, 'D': 2, 'RE': 2, 'E': 4, 'MI': 4,
          'F': 5, 'FA': 5, 'G': 7, 'SOL': 7, 'A': 9, 'LA': 9, 'B': 11, 'SI': 11
        };
        var m = tonalidadOriginal.match(/^(Sol|Do|Re|Mi|Fa|La|Si|[A-G])([#b♯♭])?(.*)$/i);
        if (m) {
          var rName = m[1].toUpperCase();
          var acc = m[2] || '';
          var tMod = m[3] || '';
          var baseP = MAPA_TONO[rName];
          if (baseP !== undefined) {
            if (acc === '#' || acc === '♯') baseP = (baseP + 1) % 12;
            else if (acc === 'b' || acc === '♭') baseP = (baseP - 1 + 12) % 12;
            var effNotation = targetNotation === 'original' ? (/^(Do|Re|Mi|Fa|Sol|La|Si)/i.test(m[1]) ? 'latin' : 'american') : targetNotation;
            var newTonoName = formatearPitch(baseP + semitones, usarBemoles, effNotation) + tMod;

            if (semitones === 0) {
              if (targetNotation !== 'original') {
                return 'Tono: ' + newTonoName;
              }
              return 'Tono: ' + tonalidadOriginal;
            }
            return 'Original: ' + tonalidadOriginal + ' (' + signo + ': ' + newTonoName + ')';
          }
        }
        if (semitones === 0) return 'Tono: ' + tonalidadOriginal;
        return 'Original: ' + tonalidadOriginal + ' (' + signo + ')';
      }

      if (semitones === 0) return 'Tono: Original';
      return 'Tono: ' + signo;
    }

    function actualizarAtrilDOM() {
      // 1. Transformar todos los acordes en el DOM
      var chords = letraEl.querySelectorAll('.acorde');
      var uniqueChords = [];
      var seenChords = {};

      for (var i = 0; i < chords.length; i++) {
        var span = chords[i];
        var nuevoTexto = transformarAcordeSpan(span, semitonos, notacion);
        span.textContent = nuevoTexto;

        if (!seenChords[nuevoTexto]) {
          seenChords[nuevoTexto] = true;
          uniqueChords.push(nuevoTexto);
        }
      }

      // 2. Actualizar etiquetas de tonalidad
      var textoTono = generarTextoTonalidad(semitonos, notacion);
      if (indicadorTono) {
        indicadorTono.textContent = textoTono;
      }
      if (atrilTagTonalidad) {
        atrilTagTonalidad.textContent = textoTono;
      }

      // 3. Actualizar resumen de acordes
      if (atrilListaAcordes) {
        atrilListaAcordes.textContent = uniqueChords.join(' · ');
      }

      // 4. Actualizar texto de botón de notación
      if (indicadorNotacionTexto) {
        indicadorNotacionTexto.textContent = (notacion === 'latin') ? 'Do Re Mi' : 'A B C';
      }

      // 5. Actualizar atributos en pre
      letraEl.setAttribute('data-semitonos', semitonos.toString());
      letraEl.setAttribute('data-notacion', notacion);

      // 6. Actualizar enlaces GET de fallback para sincronía si recarga
      actualizarHrefs();
    }

    function actualizarHrefs() {
      var posMatch = window.location.search.match(/pos=(\d+)/);
      var posParam = posMatch ? ('&pos=' + posMatch[1]) : '';

      var semMenos = Math.max(-6, semitonos - 1);
      var semMas = Math.min(6, semitonos + 1);
      var notacionAlterna = (notacion === 'latin') ? 'american' : 'latin';

      if (btnBajar) {
        btnBajar.href = '?semitonos=' + semMenos + '&notacion=' + notacion + posParam;
      }
      if (btnReset) {
        btnReset.href = '?semitonos=0&notacion=' + notacion + posParam;
      }
      if (btnSubir) {
        btnSubir.href = '?semitonos=' + semMas + '&notacion=' + notacion + posParam;
      }
      if (btnToggleNotacion) {
        btnToggleNotacion.href = '?semitonos=' + semitonos + '&notacion=' + notacionAlterna + posParam;
      }
    }

    // Interceptar clics para actualización instantánea sin recarga de página (Criterio 13)
    if (btnSubir) {
      btnSubir.addEventListener('click', function (e) {
        e.preventDefault();
        if (semitonos < 6) {
          semitonos++;
          actualizarAtrilDOM();
        }
      });
    }

    if (btnBajar) {
      btnBajar.addEventListener('click', function (e) {
        e.preventDefault();
        if (semitonos > -6) {
          semitonos--;
          actualizarAtrilDOM();
        }
      });
    }

    if (btnReset) {
      btnReset.addEventListener('click', function (e) {
        e.preventDefault();
        semitonos = 0;
        actualizarAtrilDOM();
      });
    }

    if (btnToggleNotacion) {
      btnToggleNotacion.addEventListener('click', function (e) {
        e.preventDefault();
        notacion = (notacion === 'latin') ? 'american' : 'latin';
        try {
          if (window.localStorage) {
            window.localStorage.setItem(STORAGE_NOTATION_KEY, notacion);
          }
        } catch (err) {
          // Ignorar fallos de localStorage
        }
        actualizarAtrilDOM();
      });
    }

    // Aplicar estado inicial
    actualizarAtrilDOM();
  }

  // =========================================================================
  // 7. Edición Rápida de Acordes (Fase 3: Criterios 2, 3, 4, 5)
  // =========================================================================
  function initEdicionAcordesRapida() {
    var preEdicion = document.getElementById('cuerpo-edicion-acordes');
    if (!preEdicion) {
      return;
    }

    var formEdicion = document.getElementById('form-edicion-acorde');
    var modal = document.getElementById('modal-edicion-acorde');
    var modalBtnCerrar = document.getElementById('modal-btn-cerrar');
    var modalBtnCancelar = document.getElementById('modal-btn-cancelar');
    var modalBtnGuardarUno = document.getElementById('modal-btn-guardar-uno');
    var modalBtnGuardarTodos = document.getElementById('modal-btn-guardar-todos');
    var modalLabelActual = document.getElementById('modal-acorde-actual-label');
    var modalInputNuevo = document.getElementById('modal-input-nuevo-acorde');

    var inputNumLinea = document.getElementById('edit-num-linea');
    var inputColInicio = document.getElementById('edit-col-inicio');
    var inputColFin = document.getElementById('edit-col-fin');
    var inputTextoOriginal = document.getElementById('edit-texto-original');
    var inputModo = document.getElementById('edit-modo');
    var inputNuevoAcorde = document.getElementById('input-nuevo-acorde');
    var badgeAcordeActual = document.getElementById('badge-acorde-actual');
    var btnCancelar = document.getElementById('btn-cancelar-edicion');
    var btnGuardarUno = document.getElementById('btn-guardar-uno');
    var btnGuardarTodos = document.getElementById('btn-guardar-todos');

    var acordeSeleccionadoEl = null;

    function deseleccionar() {
      if (acordeSeleccionadoEl) {
        acordeSeleccionadoEl.className = acordeSeleccionadoEl.className.replace(/\bacorde-seleccionado\b/g, '').trim();
        acordeSeleccionadoEl = null;
      }
      if (modal) {
        modal.style.display = 'none';
        modal.setAttribute('aria-hidden', 'true');
      }
      if (btnCancelar) {
        btnCancelar.style.display = 'none';
      }
    }

    function seleccionarAcorde(span) {
      deseleccionar();
      acordeSeleccionadoEl = span;
      span.className = (span.className + ' acorde-seleccionado').trim();

      var linea = span.getAttribute('data-linea');
      var inicio = span.getAttribute('data-inicio');
      var fin = span.getAttribute('data-fin');
      var original = span.getAttribute('data-original') || span.textContent.trim();

      if (inputNumLinea) inputNumLinea.value = linea;
      if (inputColInicio) inputColInicio.value = inicio;
      if (inputColFin) inputColFin.value = fin;
      if (inputTextoOriginal) inputTextoOriginal.value = original;
      if (inputNuevoAcorde) inputNuevoAcorde.value = original;
      if (badgeAcordeActual) badgeAcordeActual.textContent = original;

      if (modalLabelActual) modalLabelActual.textContent = original;
      if (modalInputNuevo) modalInputNuevo.value = original;

      if (btnCancelar) {
        btnCancelar.style.display = 'inline-flex';
      }

      // Si existe modal, mostrarlo para mejor ergonomía en pantallas táctiles y móviles
      if (modal) {
        modal.style.display = 'flex';
        modal.setAttribute('aria-hidden', 'false');
        if (modalInputNuevo) {
          setTimeout(function () {
            modalInputNuevo.focus();
            modalInputNuevo.select();
          }, 60);
        }
      } else if (inputNuevoAcorde) {
        inputNuevoAcorde.focus();
        inputNuevoAcorde.select();
      }
    }

    // Manejar clics y pulsaciones sobre los acordes editables
    preEdicion.addEventListener('click', function (e) {
      var target = e.target;
      while (target && target !== preEdicion) {
        if (target.className && target.className.indexOf('acorde-editable') !== -1) {
          e.preventDefault();
          seleccionarAcorde(target);
          return;
        }
        target = target.parentNode;
      }
    });

    preEdicion.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.keyCode === 13 || e.key === ' ' || e.keyCode === 32) {
        var target = e.target;
        if (target && target.className && target.className.indexOf('acorde-editable') !== -1) {
          e.preventDefault();
          seleccionarAcorde(target);
        }
      }
    });

    if (btnGuardarUno) {
      btnGuardarUno.addEventListener('click', function () {
        if (inputModo) inputModo.value = 'uno';
      });
    }

    if (btnGuardarTodos) {
      btnGuardarTodos.addEventListener('click', function () {
        if (inputModo) inputModo.value = 'todos';
      });
    }

    if (btnCancelar) {
      btnCancelar.addEventListener('click', function (e) {
        e.preventDefault();
        deseleccionar();
      });
    }

    if (modalBtnCerrar) {
      modalBtnCerrar.addEventListener('click', function () {
        deseleccionar();
      });
    }

    if (modalBtnCancelar) {
      modalBtnCancelar.addEventListener('click', function () {
        deseleccionar();
      });
    }

    if (modalBtnGuardarUno && formEdicion) {
      modalBtnGuardarUno.addEventListener('click', function () {
        if (inputNuevoAcorde && modalInputNuevo) {
          inputNuevoAcorde.value = modalInputNuevo.value.trim();
        }
        if (inputModo) inputModo.value = 'uno';
        formEdicion.submit();
      });
    }

    if (modalBtnGuardarTodos && formEdicion) {
      modalBtnGuardarTodos.addEventListener('click', function () {
        if (inputNuevoAcorde && modalInputNuevo) {
          inputNuevoAcorde.value = modalInputNuevo.value.trim();
        }
        if (inputModo) inputModo.value = 'todos';
        formEdicion.submit();
      });
    }

    if (modal) {
      modal.addEventListener('click', function (e) {
        if (e.target === modal) {
          deseleccionar();
        }
      });
    }

    // Tecla Escape para cerrar
    document.addEventListener('keydown', function (e) {
      if ((e.key === 'Escape' || e.keyCode === 27) && modal && modal.style.display === 'flex') {
        deseleccionar();
      }
    });
  }

  // =========================================================================
  // 8. Diagramas de Acordes en Modo Tocar (Fase 4)
  // =========================================================================
  function initDiagramasAtril(autoScrollCtrl) {
    var letraEl = document.getElementById('cuerpo-letra');
    var modal = document.getElementById('modal-diagrama-acorde');
    if (!letraEl || !modal) {
      return;
    }

    var modalTitulo = document.getElementById('modal-diagrama-titulo');
    var modalSvg = document.getElementById('modal-diagrama-svg');
    var modalMensaje = document.getElementById('modal-diagrama-mensaje');
    var modalAlerta = document.getElementById('modal-diagrama-alerta');
    var btnCerrar = document.getElementById('btn-cerrar-diagrama');
    var btnCerrarPie = document.getElementById('btn-cerrar-diagrama-pie');

    // Caché en memoria para evitar peticiones repetidas (Criterio 9)
    // Clave conceptual: root|mod|bass
    var diagramCache = {};
    window.__FOGATA_DIAGRAM_CACHE__ = diagramCache;

    // Criterio 6 (Fase 5): Precargar biblioteca completa de 64 digitaciones
    function precargarBatchDiagramas() {
      var xhr = new XMLHttpRequest();
      xhr.open('GET', '/canciones/diagramas/batch/', true);
      xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
      xhr.setRequestHeader('Accept', 'application/json');

      xhr.onreadystatechange = function () {
        if (xhr.readyState === 4 && xhr.status === 200) {
          try {
            var data = JSON.parse(xhr.responseText);
            if (data && data.ok && data.diagramas) {
              for (var k in data.diagramas) {
                if (Object.prototype.hasOwnProperty.call(data.diagramas, k)) {
                  var it = data.diagramas[k];
                  var bassKey = (it.bass !== null && it.bass !== undefined) ? it.bass.toString() : '';
                  var baseKey = it.root + '|' + it.mod + '|' + bassKey;
                  diagramCache[baseKey + '|american'] = {
                    ok: true,
                    disponible: true,
                    nombre: it.nombre_american,
                    svg: it.svg_american
                  };
                  diagramCache[baseKey + '|latin'] = {
                    ok: true,
                    disponible: true,
                    nombre: it.nombre_latin,
                    svg: it.svg_latin
                  };
                }
              }
            }
          } catch (e) {
            // Silencioso
          }
        }
      };

      xhr.send();
    }

    precargarBatchDiagramas();

    function cerrarModal() {
      modal.style.display = 'none';
      if (modalSvg) {
        modalSvg.innerHTML = '';
      }
      if (modalMensaje) {
        modalMensaje.style.display = 'none';
      }
      if (modalAlerta) {
        modalAlerta.style.display = 'none';
      }
      // Criterio 8.6: Permanecer pausado después del cierre (NO reanudar auto-scroll)
    }

    if (btnCerrar) {
      btnCerrar.addEventListener('click', function (e) {
        e.preventDefault();
        cerrarModal();
      });
    }

    if (btnCerrarPie) {
      btnCerrarPie.addEventListener('click', function (e) {
        e.preventDefault();
        cerrarModal();
      });
    }

    modal.addEventListener('click', function (e) {
      if (e.target === modal) {
        cerrarModal();
      }
    });

    document.addEventListener('keydown', function (e) {
      if ((e.key === 'Escape' || e.keyCode === 27) && modal.style.display === 'flex') {
        cerrarModal();
      }
    });

    function mostrarDiagramaEnModal(data) {
      if (modalTitulo) {
        modalTitulo.textContent = data.nombre || 'Diagrama';
      }

      if (data.advertencia_afinacion && modalAlerta) {
        modalAlerta.style.display = 'block';
      } else if (modalAlerta) {
        modalAlerta.style.display = 'none';
      }

      if (data.disponible && data.svg && modalSvg) {
        modalSvg.innerHTML = data.svg;
        modalSvg.style.display = 'flex';
        if (modalMensaje) {
          modalMensaje.style.display = 'none';
        }
      } else {
        if (modalSvg) {
          modalSvg.innerHTML = '';
          modalSvg.style.display = 'none';
        }
        if (modalMensaje) {
          modalMensaje.textContent = data.mensaje || 'Diagrama aún no disponible para este acorde.';
          modalMensaje.style.display = 'block';
        }
      }

      modal.style.display = 'flex';
    }

    function solicitarDiagrama(effRoot, mod, effBass, notacion, cancionId) {
      var bassKey = (effBass !== null && effBass !== undefined) ? effBass.toString() : '';
      var cacheKey = effRoot + '|' + mod + '|' + bassKey + '|' + notacion;

      if (diagramCache[cacheKey]) {
        mostrarDiagramaEnModal(diagramCache[cacheKey]);
        return;
      }

      var url = '/canciones/diagrama/?root=' + encodeURIComponent(effRoot) +
                '&mod=' + encodeURIComponent(mod) +
                '&bass=' + encodeURIComponent(bassKey) +
                '&notacion=' + encodeURIComponent(notacion) +
                '&format=json';

      if (cancionId) {
        url += '&cancion_id=' + encodeURIComponent(cancionId);
      }

      // XHR clásico compatible con ES5 (Criterio 8)
      var xhr = new XMLHttpRequest();
      xhr.open('GET', url, true);
      xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
      xhr.setRequestHeader('Accept', 'application/json');

      xhr.onreadystatechange = function () {
        if (xhr.readyState === 4) {
          if (xhr.status === 200) {
            try {
              var resp = JSON.parse(xhr.responseText);
              if (resp.ok) {
                diagramCache[cacheKey] = resp;
                mostrarDiagramaEnModal(resp);
              }
            } catch (err) {
              // Silencioso ante JSON inválido
            }
          }
        }
      };

      xhr.send();
    }

    function manejarSeleccionAcorde(el, e) {
      var acordeSpan = null;
      if (el && el.className && el.className.indexOf('acorde') !== -1) {
        acordeSpan = el;
      } else if (el && el.parentElement && el.parentElement.className && el.parentElement.className.indexOf('acorde') !== -1) {
        acordeSpan = el.parentElement;
      } else if (el && el.querySelector && el.querySelector('.acorde')) {
        acordeSpan = el.querySelector('.acorde');
      }

      if (!acordeSpan) {
        return;
      }

      // Criterio 8.1: Pausar auto-scroll si estaba activo
      if (autoScrollCtrl && typeof autoScrollCtrl.pausarAutoScroll === 'function') {
        autoScrollCtrl.pausarAutoScroll();
      }

      // Criterio 8.2: Conservar window.pageYOffset (evitar salto nativo de link)
      if (e && e.preventDefault) {
        e.preventDefault();
      }

      var rootAttr = acordeSpan.getAttribute('data-root');
      if (rootAttr === null || rootAttr === '') {
        return;
      }

      var rootOrig = parseInt(rootAttr, 10);
      if (isNaN(rootOrig)) {
        return;
      }

      var mod = acordeSpan.getAttribute('data-mod') || '';
      var bassAttr = acordeSpan.getAttribute('data-bass');
      var bassOrig = (bassAttr !== null && bassAttr !== '') ? parseInt(bassAttr, 10) : null;
      if (isNaN(bassOrig)) {
        bassOrig = null;
      }

      // Transposición y notación activa (Criterios 10 y 11)
      var semitonos = parseInt(letraEl.getAttribute('data-semitonos') || '0', 10);
      if (isNaN(semitonos)) {
        semitonos = 0;
      }

      var notacion = letraEl.getAttribute('data-notacion') || 'american';
      if (notacion === 'original') {
        var origText = acordeSpan.getAttribute('data-original') || '';
        notacion = /^(Do|Re|Mi|Fa|Sol|La|Si)/i.test(origText) ? 'latin' : 'american';
      }

      var cancionId = letraEl.getAttribute('data-cancion-id') || '';

      // Criterio 10: Pitch efectivo ya calculado
      var effRoot = ((rootOrig + semitonos) % 12 + 12) % 12;
      var effBass = (bassOrig !== null) ? (((bassOrig + semitonos) % 12 + 12) % 12) : null;

      solicitarDiagrama(effRoot, mod, effBass, notacion, cancionId);
    }

    letraEl.addEventListener('click', function (e) {
      manejarSeleccionAcorde(e.target, e);
    });

    letraEl.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.keyCode === 13 || e.key === ' ' || e.keyCode === 32) {
        manejarSeleccionAcorde(e.target, e);
      }
    });
  }

  // =========================================================================
  // 9. PWA, Service Worker y Gestión Offline Deliberada (Fase 5)
  // =========================================================================

  function initServiceWorkerAndPWA() {
    // Registro progresivo del Service Worker (Legacy First)
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(function () {
        // Fallback silencioso
      });
    }

    // Instalación PWA (beforeinstallprompt)
    var btnInstalar = document.getElementById('btn-instalar-pwa');
    var deferredPrompt = null;

    window.addEventListener('beforeinstallprompt', function (e) {
      e.preventDefault();
      deferredPrompt = e;
      if (btnInstalar) {
        btnInstalar.style.display = 'inline-flex';
      }
    });

    if (btnInstalar) {
      btnInstalar.addEventListener('click', function () {
        if (!deferredPrompt) {
          return;
        }
        deferredPrompt.prompt();
        deferredPrompt.userChoice.then(function () {
          deferredPrompt = null;
          btnInstalar.style.display = 'none';
        }).catch(function () {
          btnInstalar.style.display = 'none';
        });
      });
    }
  }

  function initConectividadBanner() {
    var banner = document.getElementById('indicador-sin-conexion');
    if (!banner) {
      return;
    }

    function actualizar() {
      // Criterio 16: navigator.onLine únicamente para indicación visual
      if (navigator.onLine === false) {
        banner.style.display = 'block';
      } else {
        banner.style.display = 'none';
      }
    }

    window.addEventListener('online', actualizar);
    window.addEventListener('offline', actualizar);
    actualizar();
  }

  function initRestriccionMutacionesOffline() {
    // Criterio 5: En modo offline, no permitir operaciones mutables hacia el servidor
    document.addEventListener('submit', function (e) {
      if (navigator.onLine === false) {
        var form = e.target;
        if (form && form.method && form.method.toUpperCase() === 'POST') {
          e.preventDefault();
          alert('Esta acción necesita conexión.');
        }
      }
    });
  }

  function initGestionFogatasOffline() {
    var panel = document.getElementById('panel-offline-fogata');
    if (!panel) {
      return;
    }

    var fogataId = parseInt(panel.getAttribute('data-fogata-id'), 10);
    if (isNaN(fogataId)) {
      return;
    }

    var fogataNombre = panel.getAttribute('data-fogata-nombre') || ('Fogata #' + fogataId);
    var totalCanciones = parseInt(panel.getAttribute('data-canciones-count') || '0', 10);

    var btnDescargar = document.getElementById('btn-descargar-offline');
    var btnEliminar = document.getElementById('btn-eliminar-offline');
    var badgeEstado = document.getElementById('badge-estado-offline');
    var textoEstado = document.getElementById('texto-estado-offline');
    var barraProgreso = document.getElementById('barra-progreso-offline');
    var progresoFill = document.getElementById('progreso-fill-offline');

    var STORAGE_KEY = 'fogata_offline_repertorios';

    function obtenerRepertorios() {
      try {
        var raw = window.localStorage && window.localStorage.getItem(STORAGE_KEY);
        return raw ? JSON.parse(raw) : [];
      } catch (e) {
        return [];
      }
    }

    function guardarRepertorios(lista) {
      try {
        if (window.localStorage) {
          window.localStorage.setItem(STORAGE_KEY, JSON.stringify(lista));
        }
      } catch (e) {
        // Fallback
      }
    }

    function encontrarRepertorio() {
      var lista = obtenerRepertorios();
      for (var i = 0; i < lista.length; i++) {
        if (lista[i].id === fogataId) {
          return lista[i];
        }
      }
      return null;
    }

    function actualizarUI() {
      var rep = encontrarRepertorio();
      if (rep) {
        if (badgeEstado) {
          badgeEstado.className = 'offline-status-badge saved';
          badgeEstado.textContent = '✓ Guardada offline';
        }
        if (btnDescargar) {
          btnDescargar.textContent = '↻ Actualizar versión offline';
        }
        if (btnEliminar) {
          btnEliminar.style.display = 'inline-flex';
        }
        if (textoEstado) {
          var fechaStr = rep.guardado_en ? new Date(rep.guardado_en).toLocaleDateString() : '';
          textoEstado.textContent = 'Disponible en este dispositivo sin internet.' + (fechaStr ? ' (Guardada: ' + fechaStr + ')' : '');
        }
      } else {
        if (badgeEstado) {
          badgeEstado.className = 'offline-status-badge not-saved';
          badgeEstado.textContent = 'No descargada';
        }
        if (btnDescargar) {
          btnDescargar.textContent = '⬇ Disponible sin conexión';
        }
        if (btnEliminar) {
          btnEliminar.style.display = 'none';
        }
        if (textoEstado) {
          textoEstado.textContent = 'Descarga las páginas de este setlist y la biblioteca de diagramas para tocar en lugares sin señal.';
        }
      }
    }

    actualizarUI();

    if (btnDescargar) {
      btnDescargar.addEventListener('click', function (e) {
        e.preventDefault();

        if (!('caches' in window) || typeof fetch !== 'function') {
          alert('Tu dispositivo actual no soporta almacenamiento offline de PWA. Puedes usar Fogata online normalmente.');
          return;
        }

        var repAnterior = encontrarRepertorio();

        // Criterio 8: Construir lista estricta de URLs de la Fogata
        var urls = [
          '/fogatas/' + fogataId + '/',
          '/canciones/diagramas/batch/'
        ];

        for (var p = 1; p <= totalCanciones; p++) {
          urls.push('/fogatas/' + fogataId + '/tocar/?pos=' + p);
        }

        if (barraProgreso) {
          barraProgreso.style.display = 'block';
        }
        if (progresoFill) {
          progresoFill.style.width = '0%';
        }
        btnDescargar.disabled = true;
        btnDescargar.textContent = 'Preparando... (0/' + urls.length + ')';

        var respuestasExitosas = [];

        function descargarPaso(index) {
          if (index >= urls.length) {
            // Criterio 18: Todas las páginas respondieron 200 -> Almacenar atómicamente
            window.caches.open('fogata-offline').then(function (cache) {
              var promesasPut = respuestasExitosas.map(function (item) {
                return cache.put(item.url, item.response);
              });
              return Promise.all(promesasPut);
            }).then(function () {
              var lista = obtenerRepertorios();
              var idx = -1;
              for (var j = 0; j < lista.length; j++) {
                if (lista[j].id === fogataId) {
                  idx = j;
                  break;
                }
              }
              var reg = {
                id: fogataId,
                nombre: fogataNombre,
                canciones_count: totalCanciones,
                guardado_en: Date.now()
              };
              if (idx >= 0) {
                lista[idx] = reg;
              } else {
                lista.push(reg);
              }
              guardarRepertorios(lista);

              if (barraProgreso) {
                barraProgreso.style.display = 'none';
              }
              btnDescargar.disabled = false;
              actualizarUI();
              alert('✓ Fogata «' + fogataNombre + '» guardada con éxito para tocar sin conexión.');
            }).catch(function (err) {
              if (barraProgreso) {
                barraProgreso.style.display = 'none';
              }
              btnDescargar.disabled = false;
              actualizarUI();
              // Criterio 19: Manejo de cuota
              if (err && (err.name === 'QuotaExceededError' || err.code === 22)) {
                alert('No hay suficiente espacio para guardar esta Fogata sin conexión.');
              } else {
                alert('Ocurrió un error al almacenar la Fogata sin conexión.');
              }
            });
            return;
          }

          var targetUrl = urls[index];
          fetch(targetUrl, { cache: 'no-cache' }).then(function (res) {
            if (!res.ok || res.status !== 200) {
              // Criterio 17 y 18: Falló una petición -> abortar sin estados parciales
              if (barraProgreso) {
                barraProgreso.style.display = 'none';
              }
              btnDescargar.disabled = false;
              actualizarUI();
              if (repAnterior) {
                alert('No pudimos completar la descarga. Tu Fogata anterior no fue modificada.');
              } else {
                alert('No pudimos completar la descarga. Verifica tu conexión e intenta nuevamente.');
              }
              return;
            }

            respuestasExitosas.push({ url: targetUrl, response: res });
            var pct = Math.round(((index + 1) / urls.length) * 100);
            if (progresoFill) {
              progresoFill.style.width = pct + '%';
            }
            btnDescargar.textContent = 'Descargando... (' + (index + 1) + '/' + urls.length + ')';
            descargarPaso(index + 1);
          }).catch(function () {
            if (barraProgreso) {
              barraProgreso.style.display = 'none';
            }
            btnDescargar.disabled = false;
            actualizarUI();
            if (repAnterior) {
              alert('No pudimos completar la descarga. Tu Fogata anterior no fue modificada.');
            } else {
              alert('No pudimos completar la descarga. Verifica tu conexión e intenta nuevamente.');
            }
          });
        }

        descargarPaso(0);
      });
    }

    if (btnEliminar) {
      btnEliminar.addEventListener('click', function (e) {
        e.preventDefault();
        // Criterio 9: Eliminación deliberada de una Fogata offline
        if (!confirm('¿Quitar «' + fogataNombre + '» del almacenamiento sin conexión?')) {
          return;
        }

        if (!('caches' in window)) {
          return;
        }

        window.caches.open('fogata-offline').then(function (cache) {
          var aBorrar = ['/fogatas/' + fogataId + '/'];
          for (var p = 1; p <= totalCanciones; p++) {
            aBorrar.push('/fogatas/' + fogataId + '/tocar/?pos=' + p);
          }
          // NO eliminar batch de diagramas ni recursos técnicos compartidos
          var promesasDel = aBorrar.map(function (u) {
            return cache.delete(u);
          });
          return Promise.all(promesasDel);
        }).then(function () {
          var lista = obtenerRepertorios();
          var filtrada = [];
          for (var k = 0; k < lista.length; k++) {
            if (lista[k].id !== fogataId) {
              filtrada.push(lista[k]);
            }
          }
          guardarRepertorios(filtrada);
          actualizarUI();
          alert('Fogata quitada del almacenamiento sin conexión.');
        });
      });
    }
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
    initTransposicionYNotacion();
    initEdicionAcordesRapida();
    initDiagramasAtril(autoScrollCtrl);

    // Módulos PWA y Offline
    initServiceWorkerAndPWA();
    initConectividadBanner();
    initRestriccionMutacionesOffline();
    initGestionFogatasOffline();
    initLogoutCleanup();
  }

  function initLogoutCleanup() {
    var btnLogout = document.getElementById('btn-logout');
    if (btnLogout) {
      var form = btnLogout.closest('form');
      if (form) {
        form.addEventListener('submit', function () {
          try {
            if ('caches' in window) {
              caches.delete('fogata-offline');
            }
            if (window.localStorage) {
              window.localStorage.removeItem('fogata_offline_repertorios');
            }
          } catch (e) {}
        });
      }
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', inicializarTodo);
  } else {
    inicializarTodo();
  }
})();


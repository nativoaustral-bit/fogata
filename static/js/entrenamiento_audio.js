/**
 * FOGATA — Motor de Audio Nativo para «Entrena tu oído»
 * Síntesis de cuerdas pulsadas mediante algoritmo físico Karplus-Strong sobre Web Audio API.
 * Cero dependencias externas. Cero librerías pesadas. 100% compatible mobile.
 */

(function (window) {
  'use strict';

  var audioCtx = null;
  var masterGain = null;
  var compressor = null;
  var activeSources = [];
  var scheduledTimeouts = [];
  var bufferCache = {};

  function obtenerAudioContext() {
    if (!audioCtx) {
      var AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextClass) {
        console.warn('Web Audio API no disponible en este navegador.');
        return null;
      }
      audioCtx = new AudioContextClass();

      // Compresor/limitador suave para evitar cualquier saturación o click
      compressor = audioCtx.createDynamicsCompressor();
      compressor.threshold.setValueAtTime(-12, audioCtx.currentTime);
      compressor.knee.setValueAtTime(8, audioCtx.currentTime);
      compressor.ratio.setValueAtTime(4, audioCtx.currentTime);
      compressor.attack.setValueAtTime(0.005, audioCtx.currentTime);
      compressor.release.setValueAtTime(0.05, audioCtx.currentTime);

      masterGain = audioCtx.createGain();
      masterGain.gain.setValueAtTime(0.85, audioCtx.currentTime);

      masterGain.connect(compressor);
      compressor.connect(audioCtx.destination);
    }

    if (audioCtx.state === 'suspended') {
      audioCtx.resume();
    }

    return audioCtx;
  }

  function midiAFrecuencia(midi) {
    return 440.0 * Math.pow(2.0, (midi - 69) / 12.0);
  }

  /**
   * Genera un AudioBuffer con el timbre acústico de una cuerda pulsada.
   * Utiliza el modelo físico Karplus-Strong con atenuación de armónicos.
   */
  function sintetizarCuerda(frecuencia, duracionSegundos) {
    var ctx = obtenerAudioContext();
    if (!ctx) return null;

    var duracion = duracionSegundos || 2.4;
    var sampleRate = ctx.sampleRate;
    var totalSamples = Math.floor(sampleRate * duracion);
    var buffer = ctx.createBuffer(1, totalSamples, sampleRate);
    var canal = buffer.getChannelData(0);

    var periodo = Math.max(2, Math.round(sampleRate / frecuencia));

    // Excitación inicial (ataque de púa/yema): pulso de ruido filtrado
    var prev = 0;
    for (var i = 0; i < periodo; i++) {
      var ruido = (Math.random() * 2.0 - 1.0);
      // Filtro paso-bajo inicial para suavizar el chasquido y dar calidez acústica
      prev = (ruido + prev) * 0.5;
      canal[i] = prev * 0.85;
    }

    // Lazo de realimentación con decaimiento dependiente de la frecuencia
    // Cuerdas más agudas decaen ligeramente más rápido que las graves
    var factorDecaimiento = 0.993 - (frecuencia / 25000.0);
    if (factorDecaimiento < 0.985) factorDecaimiento = 0.985;

    for (var j = periodo; j < totalSamples; j++) {
      // Filtro promediador de 2 muestras (simula absorción de energía en cejuela y puente)
      canal[j] = 0.5 * (canal[j - periodo] + canal[j - periodo - 1]) * factorDecaimiento;
    }

    // Suave fade-out en los últimos 40ms para evitar corte abrupto
    var fadeSamples = Math.floor(sampleRate * 0.04);
    var startIndex = totalSamples - fadeSamples;
    for (var k = 0; k < fadeSamples; k++) {
      var mult = 1.0 - (k / fadeSamples);
      canal[startIndex + k] *= mult;
    }

    return buffer;
  }

  function obtenerBufferNota(frecuencia) {
    var key = Math.round(frecuencia * 10) / 10;
    if (!bufferCache[key]) {
      bufferCache[key] = sintetizarCuerda(frecuencia, 2.4);
    }
    return bufferCache[key];
  }

  /**
   * Detiene de inmediato cualquier sonido activo o secuencia en progreso.
   */
  function detenerTodo() {
    // Cancelar timeouts pendientes de progresiones
    for (var i = 0; i < scheduledTimeouts.length; i++) {
      clearTimeout(scheduledTimeouts[i]);
    }
    scheduledTimeouts = [];

    // Detener fuentes activas
    if (activeSources.length > 0 && audioCtx) {
      for (var s = 0; s < activeSources.length; s++) {
        try {
          activeSources[s].stop();
          activeSources[s].disconnect();
        } catch (e) {
          // Ignorar si ya estaba detenida
        }
      }
      activeSources = [];
    }
  }

  /**
   * Reproduce una nota individual.
   */
  function reproducirNota(frecuencia, volumen, inicioDelay) {
    var ctx = obtenerAudioContext();
    if (!ctx) return;

    var buf = obtenerBufferNota(frecuencia);
    if (!buf) return;

    var src = ctx.createBufferSource();
    src.buffer = buf;

    var gain = ctx.createGain();
    var vol = volumen !== undefined ? volumen : 0.8;
    gain.gain.setValueAtTime(vol, ctx.currentTime);

    src.connect(gain);
    gain.connect(masterGain);

    var tInicio = ctx.currentTime + (inicioDelay || 0);
    src.start(tInicio);
    activeSources.push(src);

    src.onended = function () {
      var idx = activeSources.indexOf(src);
      if (idx !== -1) activeSources.splice(idx, 1);
    };
  }

  /**
   * Reproduce un acorde en rasgueo descendente natural de guitarra.
   */
  function reproducirAcorde(notasMidi, tiempoStrum) {
    detenerTodo();
    var ctx = obtenerAudioContext();
    if (!ctx) return;

    var notasValidas = [];
    for (var i = 0; i < notasMidi.length; i++) {
      if (notasMidi[i] >= 0) {
        notasValidas.push(notasMidi[i]);
      }
    }

    if (notasValidas.length === 0) return;

    // Retardo natural entre cuerdas (35ms por cuerda)
    var delayPaso = tiempoStrum || 0.035;

    for (var n = 0; n < notasValidas.length; n++) {
      var freq = midiAFrecuencia(notasValidas[n]);
      var delay = n * delayPaso;
      // Las notas graves tienen un poco más de energía física
      var vol = 0.75 - (n * 0.03);
      reproducirNota(freq, vol, delay);
    }
  }

  /**
   * Reproduce una secuencia de acordes con cadencia musical.
   */
  function reproducirProgresion(secuenciaAcordes, intervaloEntreAcordes, callbackPaso, callbackFin) {
    detenerTodo();
    var intervalo = intervaloEntreAcordes || 1800; // 1.8 segundos por acorde

    for (var i = 0; i < secuenciaAcordes.length; i++) {
      (function (indice) {
        var tid = setTimeout(function () {
          if (callbackPaso) callbackPaso(indice);
          var acorde = secuenciaAcordes[indice];
          reproducirAcorde(acorde, 0.032);

          if (indice === secuenciaAcordes.length - 1 && callbackFin) {
            var finTid = setTimeout(function () {
              callbackFin();
            }, intervalo);
            scheduledTimeouts.push(finTid);
          }
        }, indice * intervalo);
        scheduledTimeouts.push(tid);
      })(i);
    }
  }

  // Exponer API pública
  window.FogataAudio = {
    inicializar: obtenerAudioContext,
    detener: detenerTodo,
    reproducirNota: function (frecuencia, volumen) {
      detenerTodo();
      reproducirNota(frecuencia, volumen || 0.85, 0);
    },
    reproducirNotaMidi: function (midi, volumen) {
      detenerTodo();
      reproducirNota(midiAFrecuencia(midi), volumen || 0.85, 0);
    },
    reproducirAcorde: reproducirAcorde,
    reproducirProgresion: reproducirProgresion,
    midiAFrecuencia: midiAFrecuencia,
  };

})(window);


/**
 * FOGATA — Motor de Audio Acústico para «Entrena tu oído»
 * Síntesis física de guitarra acústica (Extended Karplus-Strong / Jaffe-Smith)
 * con resonancia de caja de resonancia armónica y modelado de ataque de púa/yema.
 * Cero saturación digital. Cero dependencias externas. 100% compatible mobile.
 */

(function (window) {
  'use strict';

  var audioCtx = null;
  var masterGain = null;
  var limiter = null;
  var bodyBus = null;
  var activeVoices = [];
  var scheduledTimeouts = [];
  var bufferCache = {};

  /**
   * Inicializa el grafo de audio con modelado acústico de cuerpo de guitarra.
   */
  function obtenerAudioContext() {
    if (!audioCtx) {
      var AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextClass) {
        console.warn('Web Audio API no disponible en este navegador.');
        return null;
      }
      audioCtx = new AudioContextClass();

      // Bus de entrada con filtros de resonancia de caja de guitarra acústica
      bodyBus = audioCtx.createGain();
      bodyBus.gain.setValueAtTime(1.0, audioCtx.currentTime);

      // 1. Filtro paso-alto: elimina sub-graves sucios (<75 Hz)
      var hpFilter = audioCtx.createBiquadFilter();
      hpFilter.type = 'highpass';
      hpFilter.frequency.setValueAtTime(75, audioCtx.currentTime);

      // 2. Resonancia de aire de la caja (Helmholtz ~105 Hz, Q=2.2)
      var airResonance = audioCtx.createBiquadFilter();
      airResonance.type = 'peaking';
      airResonance.frequency.setValueAtTime(105, audioCtx.currentTime);
      airResonance.Q.setValueAtTime(2.2, audioCtx.currentTime);
      airResonance.gain.setValueAtTime(3.5, audioCtx.currentTime);

      // 3. Resonancia de madera de la tapa armónica (~225 Hz, Q=2.5)
      var woodResonance = audioCtx.createBiquadFilter();
      woodResonance.type = 'peaking';
      woodResonance.frequency.setValueAtTime(225, audioCtx.currentTime);
      woodResonance.Q.setValueAtTime(2.5, audioCtx.currentTime);
      woodResonance.gain.setValueAtTime(3.0, audioCtx.currentTime);

      // 4. Atenuación de estridencia digital (~2800 Hz) para calidez de nylon/bronce
      var warmNotch = audioCtx.createBiquadFilter();
      warmNotch.type = 'peaking';
      warmNotch.frequency.setValueAtTime(2800, audioCtx.currentTime);
      warmNotch.Q.setValueAtTime(1.2, audioCtx.currentTime);
      warmNotch.gain.setValueAtTime(-3.5, audioCtx.currentTime);

      // 5. Suave caída acústica natural por encima de 5500 Hz
      var highCut = audioCtx.createBiquadFilter();
      highCut.type = 'lowpass';
      highCut.frequency.setValueAtTime(5500, audioCtx.currentTime);

      // Ganancia maestra con amplio margen dinámico (headroom anti-saturación)
      masterGain = audioCtx.createGain();
      masterGain.gain.setValueAtTime(0.78, audioCtx.currentTime);

      // Limitador transparente de seguridad (techo en -1.5 dBFS)
      // Solo actúa ante picos inesperados; en operación normal no comprime ni distorsiona
      limiter = audioCtx.createDynamicsCompressor();
      limiter.threshold.setValueAtTime(-1.5, audioCtx.currentTime);
      limiter.knee.setValueAtTime(3.0, audioCtx.currentTime);
      limiter.ratio.setValueAtTime(16.0, audioCtx.currentTime);
      limiter.attack.setValueAtTime(0.003, audioCtx.currentTime);
      limiter.release.setValueAtTime(0.12, audioCtx.currentTime);

      // Conexión del bus acústico en serie
      bodyBus.connect(hpFilter);
      hpFilter.connect(airResonance);
      airResonance.connect(woodResonance);
      woodResonance.connect(warmNotch);
      warmNotch.connect(highCut);
      highCut.connect(masterGain);
      masterGain.connect(limiter);
      limiter.connect(audioCtx.destination);
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
   * Genera un AudioBuffer con el timbre orgánico de una cuerda de guitarra acústica.
   * Modela la deformación física triangular inicial, la fricción de la púa y el decaimiento armónico.
   */
  function sintetizarCuerdaAcustica(frecuencia, duracionSegundos) {
    var ctx = obtenerAudioContext();
    if (!ctx) return null;

    var duracion = duracionSegundos || 2.8;
    var sampleRate = ctx.sampleRate;
    var totalSamples = Math.floor(sampleRate * duracion);
    var buffer = ctx.createBuffer(1, totalSamples, sampleRate);
    var canal = buffer.getChannelData(0);

    var periodo = Math.max(2, Math.round(sampleRate / frecuencia));
    // Punto de pulsado físico de la púa (~20% de la longitud de la cuerda desde el puente)
    var puntoPua = Math.max(1, Math.round(periodo * 0.20));

    // Excitación física: perfil de deformación triangular + fricción suavizada de la púa
    var lpRuido = 0;
    for (var i = 0; i < periodo; i++) {
      // Perfil triangular de la cuerda estirada antes de soltarse
      var triangulo = (i < puntoPua) ? (i / puntoPua) : ((periodo - i) / (periodo - puntoPua));
      // Fricción acústica de ataque filtrada (sin estridencia blanca)
      var ruido = (Math.random() * 2.0 - 1.0);
      lpRuido += 0.35 * (ruido - lpRuido);

      canal[i] = (triangulo * 0.40) + (lpRuido * 0.60);
    }

    // Lazo de realimentación (ecuación de onda con amortiguamiento dependiente de frecuencia)
    // Las cuerdas graves sostienen más tiempo (~3.2s) que las agudas (~2.0s)
    var factorDecaimiento = 0.9968 - (frecuencia / 36000.0);
    if (factorDecaimiento < 0.984) factorDecaimiento = 0.984;

    for (var j = periodo; j < totalSamples; j++) {
      var p1 = j - periodo;
      var p2 = (p1 > 0) ? (p1 - 1) : (periodo - 1); // Protección estricta contra índices negativos / NaN
      canal[j] = 0.5 * (canal[p1] + canal[p2]) * factorDecaimiento;
    }

    // Suave fade-out en los últimos 45ms para evitar cualquier click final
    var fadeSamples = Math.floor(sampleRate * 0.045);
    var startFade = totalSamples - fadeSamples;
    for (var k = 0; k < fadeSamples; k++) {
      var mult = 1.0 - (k / fadeSamples);
      canal[startFade + k] *= mult;
    }

    return buffer;
  }

  function obtenerBufferNota(frecuencia) {
    var key = Math.round(frecuencia * 10) / 10;
    if (!bufferCache[key]) {
      bufferCache[key] = sintetizarCuerdaAcustica(frecuencia, 2.8);
    }
    return bufferCache[key];
  }

  /**
   * Cancela cualquier temporizador pendiente de secuencias de acordes.
   */
  function limpiarTimeouts() {
    for (var i = 0; i < scheduledTimeouts.length; i++) {
      clearTimeout(scheduledTimeouts[i]);
    }
    scheduledTimeouts = [];
  }

  /**
   * Amortigua con un micro-fade out cualquier cuerda activa para evitar
   * acumulación o chasquidos de DC al cambiar de nota/acorde.
   */
  function amortiguarVoces(fadeMs) {
    if (activeVoices.length > 0 && audioCtx) {
      var fadeSec = (fadeMs || 35) / 1000.0;
      var tNow = audioCtx.currentTime;
      for (var s = 0; s < activeVoices.length; s++) {
        var v = activeVoices[s];
        try {
          if (v.gain && v.gain.gain) {
            v.gain.gain.cancelScheduledValues(tNow);
            v.gain.gain.setValueAtTime(v.gain.gain.value, tNow);
            v.gain.gain.linearRampToValueAtTime(0.0001, tNow + fadeSec);
          }
          if (v.src) {
            v.src.stop(tNow + fadeSec + 0.005);
          }
        } catch (e) {
          // Ya terminado o desconectado
        }
      }
      activeVoices = [];
    }
  }

  /**
   * Detiene de inmediato cualquier sonido activo o secuencia en progreso sin chasquidos.
   */
  function detenerTodo() {
    limpiarTimeouts();
    amortiguarVoces(20);
  }

  /**
   * Reproduce una cuerda individual con ganancia calibrada.
   */
  function reproducirCuerda(frecuencia, volumen, inicioDelay) {
    var ctx = obtenerAudioContext();
    if (!ctx) return;

    var buf = obtenerBufferNota(frecuencia);
    if (!buf) return;

    var src = ctx.createBufferSource();
    src.buffer = buf;

    var gain = ctx.createGain();
    var vol = volumen !== undefined ? volumen : 0.42;
    gain.gain.setValueAtTime(vol, ctx.currentTime);

    src.connect(gain);
    gain.connect(bodyBus);

    var tInicio = ctx.currentTime + (inicioDelay || 0);
    src.start(tInicio);

    var voiceItem = { src: src, gain: gain };
    activeVoices.push(voiceItem);

    src.onended = function () {
      var idx = activeVoices.indexOf(voiceItem);
      if (idx !== -1) activeVoices.splice(idx, 1);
    };
  }

  /**
   * Reproduce una nota solista en registro natural de guitarra.
   */
  function reproducirNota(frecuencia, volumen) {
    detenerTodo();
    // Volumen solista calibrado para excelente presencia sin sobrecarga
    reproducirCuerda(frecuencia, volumen || 0.45, 0);
  }

  /**
   * Reproduce un acorde en rasgueo descendente natural de guitarra acústica.
   * Aplica escalado de ganancia proporcional al número de cuerdas (anti-saturación)
   * y micro-retardo humano entre cuerdas (curva de rasgueo real).
   *
   * @param {Array<number>} notasMidi - Arreglo con notas MIDI de las cuerdas.
   * @param {boolean} [limpiarSecuencia=true] - Si es false, no cancela los timeouts de una progresión en curso.
   */
  function reproducirAcorde(notasMidi, limpiarSecuencia) {
    if (limpiarSecuencia !== false) {
      limpiarTimeouts();
    }
    amortiguarVoces(40);

    var ctx = obtenerAudioContext();
    if (!ctx) return;
    if (ctx.state === 'suspended') {
      ctx.resume();
    }

    var notasValidas = [];
    for (var i = 0; i < notasMidi.length; i++) {
      if (notasMidi[i] >= 0) {
        notasValidas.push(notasMidi[i]);
      }
    }

    var numCuerdas = notasValidas.length;
    if (numCuerdas === 0) return;

    // Escalado de volumen por cuerda: mantiene la suma polifónica dentro de un rango limpio (-9 a -8 dBFS)
    var volumenPorCuerda = 0.38 / Math.sqrt(numCuerdas);

    // Curva de rasgueo natural humana (micro-retardos ligeramente decrecientes en el barrido)
    var retardosStrum = [0.0, 0.030, 0.056, 0.078, 0.096, 0.112];

    for (var n = 0; n < numCuerdas; n++) {
      var freq = midiAFrecuencia(notasValidas[n]);
      var delay = (n < retardosStrum.length) ? retardosStrum[n] : (n * 0.024);

      // Leve contorno de peso: cuerdas graves tienen un 10% más de masa que las agudas
      var factorPeso = 1.05 - (n * 0.03);
      var volFinal = volumenPorCuerda * factorPeso;

      reproducirCuerda(freq, volFinal, delay);
    }
  }

  /**
   * Reproduce una secuencia de acordes con cadencia musical natural.
   */
  function reproducirProgresion(secuenciaAcordes, intervaloEntreAcordes, callbackPaso, callbackFin) {
    detenerTodo();
    var ctx = obtenerAudioContext();
    if (!ctx || !secuenciaAcordes || !secuenciaAcordes.length) return;
    if (ctx.state === 'suspended') {
      ctx.resume();
    }

    var intervalo = intervaloEntreAcordes || 1700; // 1.7 segundos por acorde
    var totalAcordes = secuenciaAcordes.length;

    for (var i = 0; i < totalAcordes; i++) {
      (function (indice) {
        var tid = setTimeout(function () {
          if (callbackPaso) callbackPaso(indice, totalAcordes);
          var acorde = secuenciaAcordes[indice];
          reproducirAcorde(acorde, false); // Importante: false preserva los timeouts de la progresión

          if (indice === totalAcordes - 1 && callbackFin) {
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
    reproducirNota: reproducirNota,
    reproducirNotaMidi: function (midi, volumen) {
      reproducirNota(midiAFrecuencia(midi), volumen);
    },
    reproducirAcorde: reproducirAcorde,
    reproducirProgresion: reproducirProgresion,
    midiAFrecuencia: midiAFrecuencia,
  };

})(window);

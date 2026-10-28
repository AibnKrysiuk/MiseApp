// Temporizador: cuenta regresiva con anillo de progreso y aviso sonoro.
(function () {
  var dial = document.getElementById('dial');
  if (!dial) return;

  var C = 2 * Math.PI * 88;          // circunferencia del anillo
  var ring = document.getElementById('ring');
  var pantalla = document.getElementById('pantalla');
  var estado = document.getElementById('estado');
  var etiqueta = document.getElementById('etiqueta');
  var btnIniciar = document.getElementById('btn-iniciar');
  var campos = ['t-h', 't-m', 't-s'].map(function (id) { return document.getElementById(id); });
  var nombre = document.getElementById('t-nombre');

  var total = 600, restante = 600, finAt = 0, reloj = null, audio = null;

  ring.style.strokeDasharray = C;

  function pad(n) { return String(n).padStart(2, '0'); }
  function formato(s) {
    var h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), seg = s % 60;
    return (h ? h + ':' + pad(m) : pad(m)) + ':' + pad(seg);
  }
  function pintar() {
    pantalla.textContent = formato(restante);
    ring.style.strokeDashoffset = total ? C * (1 - restante / total) : C;
    etiqueta.textContent = nombre.value.trim() || 'Temporizador';
  }
  function leerCampos() {
    var v = campos.map(function (c) { return Math.max(0, parseInt(c.value, 10) || 0); });
    return v[0] * 3600 + v[1] * 60 + v[2];
  }
  function escribirCampos(s) {
    campos[0].value = Math.floor(s / 3600);
    campos[1].value = Math.floor(s % 3600 / 60);
    campos[2].value = s % 60;
  }
  function bloquear(b) { campos.concat([nombre]).forEach(function (c) { c.disabled = b; }); }
  function detener() { if (reloj) { clearInterval(reloj); reloj = null; } }

  function fijar(s) {
    detener();
    total = restante = s;
    dial.classList.remove('listo');
    estado.textContent = 'Listo para empezar';
    btnIniciar.textContent = 'Iniciar';
    bloquear(false);
    pintar();
  }

  function pitido() {
    try {
      var AC = window.AudioContext || window.webkitAudioContext;
      audio = audio || new AC();
      if (audio.state === 'suspended') audio.resume();
      [0, 0.35, 0.7].forEach(function (t) {
        var o = audio.createOscillator(), g = audio.createGain();
        o.frequency.value = 880; g.gain.value = 0.15;
        o.connect(g); g.connect(audio.destination);
        o.start(audio.currentTime + t); o.stop(audio.currentTime + t + 0.2);
      });
    } catch (e) {}
  }

  function terminar() {
    detener();
    restante = 0;
    dial.classList.add('listo');
    estado.textContent = '¡Listo!';
    btnIniciar.textContent = 'Iniciar';
    bloquear(false);
    pintar();
    pitido();
  }

  function iniciar() {
    if (reloj) {                       // pausar
      detener();
      estado.textContent = 'En pausa';
      btnIniciar.textContent = 'Continuar';
      return;
    }
    if (restante <= 0) { fijar(total || leerCampos()); }
    if (restante <= 0) return;
    if (audio && audio.state === 'suspended') audio.resume();
    finAt = Date.now() + restante * 1000;
    estado.textContent = 'En marcha';
    btnIniciar.textContent = 'Pausar';
    bloquear(true);
    reloj = setInterval(function () {
      restante = Math.max(0, Math.ceil((finAt - Date.now()) / 1000));
      pintar();
      if (restante === 0) terminar();
    }, 250);
  }

  btnIniciar.addEventListener('click', function () {
    // El audio solo se habilita después de un gesto del usuario: lo preparamos al tocar Iniciar.
    if (!reloj && !audio) { try { var AC = window.AudioContext || window.webkitAudioContext; audio = new AC(); } catch (e) {} }
    iniciar();
  });
  document.getElementById('btn-reiniciar').addEventListener('click', function () { fijar(total); });

  campos.forEach(function (c) { c.addEventListener('input', function () { fijar(leerCampos()); }); });
  nombre.addEventListener('input', pintar);

  document.querySelectorAll('.preset').forEach(function (b) {
    b.addEventListener('click', function () {
      var s = parseInt(b.dataset.seg, 10);
      escribirCampos(s);
      if (b.dataset.nombre) nombre.value = b.dataset.nombre;
      fijar(s);
    });
  });

  pintar();
})();

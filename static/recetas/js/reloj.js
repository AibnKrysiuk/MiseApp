// Reloj de la barra lateral: fecha y hora siempre visibles, en todas las páginas.
(function () {
  var hora = document.getElementById('reloj-hora');
  var seg = document.getElementById('reloj-seg');
  var fecha = document.getElementById('reloj-fecha');
  if (!hora || !seg || !fecha) return;

  function tick() {
    var d = new Date();
    hora.textContent = d.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit', hour12: false });
    seg.textContent = ':' + String(d.getSeconds()).padStart(2, '0');
    fecha.textContent = d.toLocaleDateString('es-AR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  }
  tick();
  setInterval(tick, 1000);
})();

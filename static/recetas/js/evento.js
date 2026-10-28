// Calcular evento: escala las recetas elegidas según invitados y margen, y arma el ticket de compra.
(function () {
  var nodo = document.getElementById('datos-recetas');
  var lista = document.getElementById('ev-lista');
  if (!lista) return;

  // Recetas que manda Django con json_script: {pk: {n, p, ing: [[nombre, cantidad, unidad, precio], ...]}}
  var RECETAS = {};
  try { RECETAS = JSON.parse(nodo.textContent) || {}; } catch (e) {}
  if (typeof RECETAS !== 'object') RECETAS = {};

  var $ = function (id) { return document.getElementById(id); };
  var checks = document.querySelectorAll('.menu-op input');

  function plata(n) { return '$ ' + Math.round(n).toLocaleString('es-AR'); }
  function redondear(cant, u) {
    return (u === 'g' || u === 'ml') ? Math.ceil(cant / 5) * 5 : Math.ceil(cant);
  }
  function cantidad(c, u) {
    if (u === 'g' && c >= 1000) return (c / 1000).toLocaleString('es-AR', { maximumFractionDigits: 2 }) + ' kg';
    if (u === 'ml' && c >= 1000) return (c / 1000).toLocaleString('es-AR', { maximumFractionDigits: 2 }) + ' l';
    return c.toLocaleString('es-AR') + ' ' + u;
  }

  function calcular() {
    var inv = Math.max(0, parseInt($('ev-invitados').value, 10) || 0);
    var margen = (parseFloat($('ev-margen').value) || 0) / 100;
    var porciones = Math.ceil(inv * (1 + margen));
    var elegidas = [];
    checks.forEach(function (c) { if (c.checked && RECETAS[c.value]) elegidas.push(c.value); });

    var nChecks = 0;
    checks.forEach(function (c) { if (c.checked) nChecks++; });
    $('ev-menu-conteo').textContent = nChecks + (nChecks === 1 ? ' receta' : ' recetas');

    var nombre = $('ev-nombre').value.trim() || 'Evento';
    var f = $('ev-fecha').value ? new Date($('ev-fecha').value + 'T12:00:00') : null;
    var fecha = f && !isNaN(f) ? f.toLocaleDateString('es-AR', { weekday: 'long', day: 'numeric', month: 'long' }) : '';
    $('ev-titulo').textContent = nombre + (fecha ? ' · ' + fecha : '');

    lista.textContent = '';
    var vacio = !(inv > 0 && elegidas.length > 0);
    $('ev-vacio').hidden = !vacio;
    $('ev-totales').hidden = vacio;
    $('ev-res').textContent = vacio ? '' :
      inv + (inv === 1 ? ' invitado' : ' invitados') + (margen ? ' + ' + Math.round(margen * 100) + ' % de margen' : '') +
      ' = ' + porciones + ' porciones de cada receta';
    if (vacio) return;

    // Sumar los ingredientes de todas las recetas elegidas
    var suma = {};
    elegidas.forEach(function (k) {
      var r = RECETAS[k], tandas = porciones / (parseFloat(r.p) || 1);
      (r.ing || []).forEach(function (i) {
        var clave = i[0] + '|' + i[2];
        if (!suma[clave]) suma[clave] = { nombre: i[0], unidad: i[2], precio: parseFloat(i[3]) || 0, cant: 0 };
        suma[clave].cant += (parseFloat(i[1]) || 0) * tandas;
      });
    });

    var total = 0;
    Object.keys(suma)
      .map(function (k) { return suma[k]; })
      .sort(function (a, b) { return a.nombre.localeCompare(b.nombre, 'es'); })
      .forEach(function (i) {
        var c = redondear(i.cant, i.unidad);
        var precio = c * i.precio;
        total += precio;
        var li = document.createElement('li');
        [['ev-nom', i.nombre], ['ev-cant', cantidad(c, i.unidad)], ['ev-precio', plata(precio)]].forEach(function (p) {
          var s = document.createElement('span');
          s.className = p[0]; s.textContent = p[1];
          li.appendChild(s);
        });
        lista.appendChild(li);
      });

    $('ev-total').textContent = plata(total);
    $('ev-por-invitado').textContent = plata(total / inv);
  }

  ['ev-nombre', 'ev-fecha', 'ev-invitados', 'ev-margen'].forEach(function (id) {
    $(id).addEventListener('input', calcular);
    $(id).addEventListener('change', calcular);
  });
  checks.forEach(function (c) { c.addEventListener('change', calcular); });
  calcular();
})();

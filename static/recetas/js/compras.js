// Lista de compras: avance y totales al tildar, imprimir y copiar la lista.
(function () {
  var fill = document.getElementById('avance-fill');
  if (!fill) return;
  var cajas = document.querySelectorAll('.checks input[type=checkbox]');

  function plata(n) { return '$ ' + Math.round(n).toLocaleString('es-AR'); }

  function calcular() {
    var total = 0, carrito = 0, hechos = 0;
    cajas.forEach(function (c) {
      var p = parseFloat(c.dataset.precio) || 0;
      total += p;
      if (c.checked) { carrito += p; hechos++; }
    });
    var pct = cajas.length ? Math.round(hechos / cajas.length * 100) : 0;
    document.getElementById('r-hechos').textContent = hechos;
    document.getElementById('r-total').textContent = cajas.length;
    document.getElementById('r-total-precio').textContent = plata(total);
    document.getElementById('r-carrito').textContent = plata(carrito);
    document.getElementById('r-falta').textContent = plata(total - carrito);
    fill.style.width = pct + '%';
    fill.parentNode.setAttribute('aria-valuenow', pct);
  }

  document.addEventListener('change', function (e) {
    if (e.target.matches('.checks input')) calcular();
  });
  calcular();

  var imprimir = document.querySelector('[data-imprimir]');
  if (imprimir) imprimir.addEventListener('click', function () { window.print(); });

  var copiar = document.querySelector('[data-copiar]');
  if (copiar) copiar.addEventListener('click', function () {
    var lineas = [];
    document.querySelectorAll('.grupo').forEach(function (g) {
      lineas.push(g.querySelector('h3').firstChild.textContent.trim().toUpperCase());
      g.querySelectorAll('.checks li').forEach(function (li) {
        var marca = li.querySelector('input').checked ? '[x] ' : '[ ] ';
        lineas.push(marca + li.querySelector('.txt').textContent + ' (' + li.querySelector('.cant').textContent.trim() + ')');
      });
      lineas.push('');
    });
    if (!navigator.clipboard) return;
    navigator.clipboard.writeText(lineas.join('\n').trim()).then(function () {
      var antes = copiar.textContent;
      copiar.textContent = '¡Copiada!';
      setTimeout(function () { copiar.textContent = antes; }, 1500);
    });
  });
})();

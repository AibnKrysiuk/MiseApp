(function () {
  // Checklist: tachado + progreso, recordado por receta en el navegador.
  var ficha = document.querySelector('.ficha[data-receta]');
  if (ficha) {
    var key = 'mise-receta-' + ficha.dataset.receta, saved = {};
    try { saved = JSON.parse(localStorage.getItem(key)) || {}; } catch (e) {}
    var boxes = ficha.querySelectorAll('input[data-k]');
    var update = function () {
      ['i', 'p'].forEach(function (t) {
        var all = ficha.querySelectorAll('input[data-k^="' + t + '"]'), on = 0;
        all.forEach(function (b) { if (b.checked) on++; });
        var el = ficha.querySelector('[data-prog="' + t + '"]');
        if (el) el.textContent = on + ' de ' + all.length;
      });
    };
    boxes.forEach(function (b) {
      b.checked = !!saved[b.dataset.k];
      b.addEventListener('change', function () {
        saved[b.dataset.k] = b.checked;
        try { localStorage.setItem(key, JSON.stringify(saved)); } catch (e) {}
        update();
      });
    });
    update();
  }
  // Formsets: agregar filas desde empty_form.
  document.querySelectorAll('[data-agregar]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var p = btn.dataset.agregar;
      var total = document.getElementById('id_' + p + '-TOTAL_FORMS');
      var n = parseInt(total.value, 10);
      var html = document.getElementById('tpl-' + p).innerHTML.replace(/__prefix__/g, n);
      document.querySelector('.filas[data-prefix="' + p + '"]').insertAdjacentHTML('beforeend', html);
      total.value = n + 1;
    });
  });
})();

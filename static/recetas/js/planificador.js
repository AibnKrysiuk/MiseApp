// Planificador semanal: cuadro para elegir receta y confirmación al limpiar la semana.
(function () {
  var dlg = document.getElementById('plan-dialogo');

  if (dlg && dlg.showModal) {
    document.querySelectorAll('.slot-mas').forEach(function (b) {
      b.addEventListener('click', function () {
        document.getElementById('plan-fecha').value = b.dataset.fecha;
        document.getElementById('plan-turno').value = b.dataset.turno;
        var et = b.dataset.etiqueta || '';
        document.getElementById('plan-dialogo-sub').textContent = et.charAt(0).toUpperCase() + et.slice(1);
        dlg.showModal();
        document.getElementById('plan-receta').focus();
      });
    });
    document.getElementById('plan-cancelar').addEventListener('click', function () { dlg.close(); });
  }

  document.querySelectorAll('form[data-confirmar]').forEach(function (f) {
    f.addEventListener('submit', function (e) {
      if (!confirm(f.dataset.confirmar)) e.preventDefault();
    });
  });
})();

// Planificador semanal: cuadro para crear o editar una opción (con uno o varios platos).
(function () {
  var dlg = document.getElementById('plan-dialogo');
  var plantilla = document.getElementById('plan-plato-tpl');

  // Confirmación al limpiar la semana (no depende del cuadro).
  document.querySelectorAll('form[data-confirmar]').forEach(function (f) {
    f.addEventListener('submit', function (e) {
      if (!confirm(f.dataset.confirmar)) e.preventDefault();
    });
  });

  if (!dlg || !dlg.showModal || !plantilla) return;

  var contenedor = document.getElementById('plan-platos');

  function mayuscula(t) { return t.charAt(0).toUpperCase() + t.slice(1); }

  function agregarPlato(recetaId) {
    var fila = plantilla.content.firstElementChild.cloneNode(true);
    if (recetaId) fila.querySelector('select').value = String(recetaId);
    contenedor.appendChild(fila);
    return fila;
  }

  // datos: {fecha, turno, opcion, nota, recetas: [ids], etiqueta}
  function abrir(datos) {
    document.getElementById('plan-fecha').value = datos.fecha || '';
    document.getElementById('plan-turno').value = datos.turno || '';
    document.getElementById('plan-opcion').value = datos.opcion || '';
    document.getElementById('plan-nota').value = datos.nota || '';
    document.getElementById('plan-dialogo-titulo').textContent = datos.opcion ? 'Editar opción' : 'Nueva opción';
    document.getElementById('plan-dialogo-sub').textContent = mayuscula(datos.etiqueta || '');
    contenedor.textContent = '';
    (datos.recetas && datos.recetas.length ? datos.recetas : [null]).forEach(agregarPlato);
    dlg.showModal();
    contenedor.querySelector('select').focus();
  }

  document.querySelectorAll('.opcion-nueva').forEach(function (b) {
    b.addEventListener('click', function () {
      abrir({ fecha: b.dataset.fecha, turno: b.dataset.turno, etiqueta: b.dataset.etiqueta });
    });
  });

  document.querySelectorAll('.opcion-editar').forEach(function (b) {
    b.addEventListener('click', function () {
      abrir({
        opcion: b.dataset.opcion,
        nota: b.dataset.nota,
        etiqueta: b.dataset.etiqueta,
        recetas: b.dataset.recetas ? b.dataset.recetas.split(',') : [],
      });
    });
  });

  document.getElementById('plan-agregar-plato').addEventListener('click', function () {
    agregarPlato(null).querySelector('select').focus();
  });

  contenedor.addEventListener('click', function (e) {
    var quitar = e.target.closest('.plato-quitar');
    if (!quitar) return;
    var fila = quitar.closest('.plato-fila');
    if (contenedor.children.length > 1) fila.remove();   // siempre queda al menos un plato
    else fila.querySelector('select').value = '';
  });

  document.getElementById('plan-cancelar').addEventListener('click', function () { dlg.close(); });
})();

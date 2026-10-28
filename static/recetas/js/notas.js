// Notas: el mismo cuadro sirve para crear una nota nueva o editar una existente.
(function () {
  var dlg = document.getElementById('nota-dialogo');
  if (!dlg || !dlg.showModal) return;

  var pk = document.getElementById('nota-pk');
  var titulo = document.getElementById('nota-titulo');
  var texto = document.getElementById('nota-texto');
  var encabezado = document.getElementById('nota-dialogo-titulo');
  var eliminar = document.getElementById('nota-eliminar');

  function abrir(datos) {
    pk.value = datos ? datos.pk : '';
    titulo.value = datos ? datos.titulo : '';
    texto.value = datos ? datos.contenido : '';
    encabezado.textContent = datos ? 'Editar nota' : 'Nueva nota';
    eliminar.hidden = !datos;
    dlg.showModal();
    titulo.focus();
  }

  document.getElementById('nota-abrir').addEventListener('click', function () { abrir(null); });

  document.querySelectorAll('[data-nota-pk]').forEach(function (a) {
    a.addEventListener('click', function (e) {
      e.preventDefault();
      abrir({ pk: a.dataset.notaPk, titulo: a.dataset.titulo, contenido: a.dataset.contenido });
    });
  });

  document.getElementById('nota-cancelar').addEventListener('click', function () { dlg.close(); });
  eliminar.addEventListener('click', function (e) {
    if (!confirm('¿Eliminar esta nota?')) e.preventDefault();
  });
})();

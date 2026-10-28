// Colores de categoría: pasa el data-color de cada elemento a la variable CSS --c
// (solapas del índice y comidas del planificador).
(function () {
  document.querySelectorAll('[data-color]').forEach(function (el) {
    el.style.setProperty('--c', el.dataset.color);
  });
})();

// Calcular evento: editor del menú (fases -> opciones -> platos). Al enviar el formulario,
// el menú viaja como JSON en el campo oculto "estructura".
(function () {
  var editor = document.getElementById('menu-editor');
  if (!editor) return;

  var fases = document.getElementById('fases');
  var oculto = document.getElementById('ev-estructura');
  var invitados = document.getElementById('ev-invitados');
  var plantilla = document.getElementById('evento-recetas-tpl');
  var estructura = [];
  try { estructura = JSON.parse(document.getElementById('datos-estructura').textContent) || []; } catch (e) {}
  if (!Array.isArray(estructura)) estructura = [];

  var contador = 0;

  function el(tag, clase, texto) {
    var e = document.createElement(tag);
    if (clase) e.className = clase;
    if (texto) e.textContent = texto;
    return e;
  }
  function boton(texto, clase, accion) {
    var b = el('button', clase, texto);
    b.type = 'button';
    b.dataset.accion = accion;
    return b;
  }
  // Campo con su etiqueta enlazada.
  function campo(etiqueta, input, clase) {
    var id = 'ev-c' + (++contador);
    input.id = id;
    var div = el('div', 'campo' + (clase ? ' ' + clase : ''));
    var l = el('label', null, etiqueta);
    l.htmlFor = id;
    div.appendChild(l);
    div.appendChild(input);
    return div;
  }

  function filaPlato(recetaId) {
    var fila = el('div', 'plato-fila');
    var sel = el('select', 'plato-sel');
    sel.setAttribute('aria-label', 'Receta');
    sel.appendChild(plantilla.content.cloneNode(true));
    if (recetaId) sel.value = String(recetaId);
    var q = boton('×', 'plato-quitar', 'quitar-plato');
    q.setAttribute('aria-label', 'Quitar plato');
    fila.appendChild(sel);
    fila.appendChild(q);
    return fila;
  }

  function opcion(datos) {
    datos = datos || {};
    var op = el('div', 'opcion-ev');
    var campos = el('div', 'opcion-campos');

    var porciones = el('input', 'opc-porciones');
    porciones.type = 'number'; porciones.min = '0';
    porciones.value = datos.porciones != null ? datos.porciones : 10;
    campos.appendChild(campo('Porciones aprox.', porciones));

    var nota = el('input', 'opc-nota');
    nota.type = 'text'; nota.maxLength = 100; nota.placeholder = 'Ej.: vegana';
    nota.value = datos.nota || '';
    campos.appendChild(campo('Aclaración (opcional)', nota));
    op.appendChild(campos);

    var platos = el('div', 'opc-platos');
    (datos.recetas && datos.recetas.length ? datos.recetas : [null]).forEach(function (r) { platos.appendChild(filaPlato(r)); });
    op.appendChild(platos);

    var pie = el('div', 'opcion-pie');
    pie.appendChild(boton('+ Agregar otro plato', 'link-btn', 'agregar-plato'));
    pie.appendChild(boton('Quitar opción', 'link-btn peligro', 'quitar-opcion'));
    op.appendChild(pie);
    return op;
  }

  function fase(datos) {
    datos = datos || {};
    var f = el('div', 'fase');
    var cab = el('div', 'fase-cab');
    var nombre = el('input', 'fase-nombre');
    nombre.type = 'text'; nombre.maxLength = 60; nombre.placeholder = 'Ej.: Entrada';
    nombre.value = datos.nombre || '';
    cab.appendChild(campo('Fase', nombre, 'fase-campo'));
    cab.appendChild(el('span', 'fase-total'));
    cab.appendChild(boton('Quitar fase', 'link-btn peligro', 'quitar-fase'));
    f.appendChild(cab);

    var opciones = el('div', 'fase-opciones');
    (datos.opciones || []).forEach(function (o) { opciones.appendChild(opcion(o)); });
    f.appendChild(opciones);
    f.appendChild(boton('+ Agregar opción', 'btn ghost', 'agregar-opcion'));
    return f;
  }

  // Cuántas porciones suman las opciones de cada fase frente a los invitados.
  function actualizar() {
    var n = parseInt(invitados.value, 10) || 0;
    fases.querySelectorAll('.fase').forEach(function (f) {
      var suma = 0;
      f.querySelectorAll('.opc-porciones').forEach(function (i) { suma += parseInt(i.value, 10) || 0; });
      var t = f.querySelector('.fase-total');
      t.textContent = suma + ' de ' + n + ' porciones';
      t.className = 'fase-total ' + (suma === n ? 'ok' : suma < n ? 'falta' : 'sobra');
    });
  }

  // El menú tal como está en pantalla. Se descartan las opciones sin recetas y las fases totalmente vacías.
  function leer() {
    var salida = [];
    fases.querySelectorAll('.fase').forEach(function (f) {
      var nombre = f.querySelector('.fase-nombre').value.trim();
      var opciones = [];
      f.querySelectorAll('.opcion-ev').forEach(function (o) {
        var recetas = [];
        o.querySelectorAll('.plato-sel').forEach(function (s) { if (s.value) recetas.push(parseInt(s.value, 10)); });
        if (!recetas.length) return;
        opciones.push({
          porciones: parseInt(o.querySelector('.opc-porciones').value, 10) || 0,
          nota: o.querySelector('.opc-nota').value.trim(),
          recetas: recetas,
        });
      });
      if (!nombre && !opciones.length) return;
      salida.push({ nombre: nombre, opciones: opciones });
    });
    return salida;
  }

  editor.addEventListener('click', function (e) {
    var b = e.target.closest('[data-accion]');
    if (!b) return;
    var accion = b.dataset.accion;
    if (accion === 'agregar-fase') fases.appendChild(fase({ opciones: [{}] }));
    else if (accion === 'fases-tipicas') ['Entrada', 'Plato principal', 'Postre'].forEach(function (n) { fases.appendChild(fase({ nombre: n, opciones: [{}] })); });
    else if (accion === 'quitar-fase') b.closest('.fase').remove();
    else if (accion === 'agregar-opcion') b.closest('.fase').querySelector('.fase-opciones').appendChild(opcion({}));
    else if (accion === 'quitar-opcion') b.closest('.opcion-ev').remove();
    else if (accion === 'agregar-plato') b.closest('.opcion-ev').querySelector('.opc-platos').appendChild(filaPlato(null));
    else if (accion === 'quitar-plato') {
      var lista = b.closest('.opc-platos');
      if (lista.children.length > 1) b.closest('.plato-fila').remove();
      else b.closest('.plato-fila').querySelector('select').value = '';
    }
    actualizar();
  });

  editor.addEventListener('input', actualizar);
  invitados.addEventListener('input', actualizar);
  oculto.form.addEventListener('submit', function () { oculto.value = JSON.stringify(leer()); });

  estructura.forEach(function (f) { fases.appendChild(fase(f)); });
  actualizar();
})();

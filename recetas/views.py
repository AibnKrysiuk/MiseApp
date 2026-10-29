import ipaddress
import json
import re
import socket
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from . import servicios
from .forms import IngredienteForm, IngredienteFormSet, PasoFormSet, RecetaForm
from .models import (
    SECCIONES, Categoria, Evento, FaseEvento, Ingrediente, IngredienteSeguido, ItemCompra,
    ListaCompras, Nota, OpcionEvento, OpcionPlan, PlanComida, PlatoOpcionEvento,
    PlatoOpcionPlan, Receta,
)
from .utils import analizar_y_limpiar_url, extraer_datos_producto, probar_semaforo_url


# ---------------------------------------------------------------------------
# Ayudas chicas
# ---------------------------------------------------------------------------

def _entero(valor, minimo=None, maximo=None):
    """Convierte a int; None si no es un número o está fuera de rango."""
    try:
        n = int(str(valor).strip())
    except (TypeError, ValueError):
        return None
    if (minimo is not None and n < minimo) or (maximo is not None and n > maximo):
        return None
    return n


def _fecha(valor):
    """'2026-10-27' -> date; None si no es válida."""
    try:
        return date.fromisoformat(str(valor).strip())
    except ValueError:
        return None


def _lunes(d):
    return d - timedelta(days=d.weekday())


def _a_decimal(texto):
    """Convierte texto a Decimal finito (acepta coma o punto); None si no es válido."""
    try:
        valor = Decimal(str(texto).strip().replace(',', '.'))
    except (InvalidOperation, ValueError):
        return None
    return valor if valor.is_finite() else None


# ---------------------------------------------------------------------------
# Recetas
# ---------------------------------------------------------------------------

@login_required
def index(request, pk=None):
    """Índice (tarjetas, con filtro por categoría) por defecto, o detalle si viene un pk."""
    categorias = Categoria.objects.filter(usuario=request.user).order_by('nombre')
    propias = Receta.objects.filter(usuario=request.user)

    if pk is None:
        recetas = propias.select_related('categoria').order_by('titulo')

        # ?categoria=<pk> filtra las tarjetas; si no es un número válido, se ignora
        categoria_activa = _entero(request.GET.get('categoria', ''))
        if categoria_activa:
            recetas = recetas.filter(categoria_id=categoria_activa)

        return render(request, 'recetas/index.html', {
            'recetas': recetas,
            'vista': 'indice',
            'categorias': categorias,
            'categoria_activa': categoria_activa,
        })

    qs = propias.select_related('categoria').prefetch_related('pasos', 'ingredientes_detalle__ingrediente')
    receta = get_object_or_404(qs, pk=pk)
    return render(request, 'recetas/index.html', {
        'receta': receta,
        'vista': 'detalle',
        'categorias': categorias,
    })


@login_required
def receta_form(request, pk=None):
    """Crea (pk=None) o edita una receta junto con sus ingredientes y pasos."""
    receta = get_object_or_404(Receta, pk=pk, usuario=request.user) if pk else None
    # Los formularios reciben el usuario para ofrecer solo sus categorías e ingredientes.
    form = RecetaForm(request.POST or None, instance=receta, usuario=request.user)
    ingredientes = IngredienteFormSet(
        request.POST or None, instance=receta, prefix='ing', form_kwargs={'usuario': request.user},
    )
    pasos = PasoFormSet(request.POST or None, instance=receta, prefix='pas')
    if request.method == 'POST' and form.is_valid() and ingredientes.is_valid() and pasos.is_valid():
        with transaction.atomic():
            receta = form.save(commit=False)
            receta.usuario = request.user
            receta.save()
            form.save_m2m()
            ingredientes.instance = receta
            ingredientes.save()
            pasos.instance = receta
            pasos.save()
        messages.success(request, f'Receta «{receta.titulo}» guardada.')
        return redirect('recetas:detalle', pk=receta.pk)
    return render(request, 'recetas/receta_form.html', {
        'form': form, 'ingredientes': ingredientes, 'pasos': pasos, 'receta': receta,
    })


@login_required
def receta_eliminar(request, pk):
    receta = get_object_or_404(Receta, pk=pk, usuario=request.user)
    if request.method == 'POST':
        titulo = receta.titulo
        receta.delete()
        messages.success(request, f'Receta «{titulo}» eliminada.')
        return redirect('recetas:index')
    return render(request, 'recetas/confirmar_eliminar.html', {
        'objeto': receta.titulo, 'volver': 'recetas:detalle', 'pk': pk,
        'aviso': 'Se borrarán también sus ingredientes y pasos, y desaparecerá de tus planificaciones y eventos.',
    })


# ---------------------------------------------------------------------------
# Ingredientes
# ---------------------------------------------------------------------------

@login_required
def ingredientes(request, pk=None):
    """Lista, crea y edita ingredientes de recetas y consulta los ingredientes seguidos."""
    editando = get_object_or_404(Ingrediente, pk=pk, usuario=request.user) if pk else None
    form = IngredienteForm(request.POST or None, instance=editando, usuario=request.user)

    if request.method == 'POST' and form.is_valid():
        ing = form.save(commit=False)
        ing.usuario = request.user
        try:
            with transaction.atomic():
                ing.save()
        except IntegrityError:
            form.add_error('nombre', 'Ya tenés un ingrediente con ese nombre.')
        else:
            form.save_m2m()
            messages.success(request, f'Ingrediente «{ing.nombre}» guardado.')
            return redirect('recetas:ingredientes')

    lista = (Ingrediente.objects.filter(usuario=request.user)
             .annotate(usos=Count('ingredientereceta')).order_by('nombre'))
    ingredientes_seguidos = IngredienteSeguido.objects.filter(usuario=request.user, activo=True).order_by('nombre')

    return render(request, 'recetas/ingredientes.html', {
        'form': form,
        'lista': lista,
        'editando': editando,
        'ingredientes_seguidos': ingredientes_seguidos,
    })


@login_required
def ingrediente_eliminar(request, pk):
    ing = get_object_or_404(Ingrediente, pk=pk, usuario=request.user)
    usos = ing.ingredientereceta_set.count()
    if request.method == 'POST':
        nombre = ing.nombre
        ing.delete()
        messages.success(request, f'Ingrediente «{nombre}» eliminado.')
        return redirect('recetas:ingredientes')
    aviso = (f'Se usa en {usos} receta(s) y se quitará de ellas.' if usos else 'No se usa en ninguna receta.')
    return render(request, 'recetas/confirmar_eliminar.html', {
        'objeto': ing.nombre, 'volver': 'recetas:ingredientes', 'pk': None, 'aviso': aviso,
    })


# ---------------------------------------------------------------------------
# Semáforo de URLs / ingredientes seguidos
# ---------------------------------------------------------------------------

def _destino_es_publico(url):
    """Evita que el servidor haga requests a redes internas (localhost, 192.168.x.x, etc.)."""
    host = urlparse(url).hostname
    if not host:
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    return all(ipaddress.ip_address(i[4][0]).is_global for i in infos)


def _guardar_ingrediente_seguido(request):
    """Valida el formulario de guardado y crea (o actualiza, si la URL ya existe) el ingrediente seguido."""
    p = request.POST
    nombre = p.get('nombre_personalizado', '').strip()[:150]
    url = p.get('url_limpia', '').strip()
    unidad = p.get('unidad', '').strip()[:20] or 'unidades'
    cantidad = _a_decimal(p.get('cantidad'))
    precio = _a_decimal(p.get('precio'))
    partes = urlparse(url)

    if not nombre:
        messages.error(request, 'El ingrediente necesita un nombre.')
    elif partes.scheme not in ('http', 'https') or not partes.netloc:
        messages.error(request, 'La URL del producto no es válida. Volvé a verificarla.')
    elif cantidad is None or not (0 < cantidad < 10**6):
        messages.error(request, 'La cantidad debe ser un número mayor a cero.')
    else:
        try:
            fecha_fin = date.fromisoformat(p.get('fecha_fin_oferta', ''))
        except ValueError:
            fecha_fin = None
        en_oferta = p.get('en_oferta') == '1'

        _, creado = IngredienteSeguido.objects.update_or_create(
            usuario=request.user,
            url=url,
            defaults={
                'nombre': nombre,
                'precio_actual': precio.quantize(Decimal('0.01')) if precio is not None else None,
                'cantidad': cantidad.quantize(Decimal('0.01')),
                'unidad': unidad,
                'descripcion': p.get('descripcion', '').strip() or None,
                'en_oferta': en_oferta,
                'fecha_fin_oferta': fecha_fin if en_oferta else None,
                'ultima_actualizacion': timezone.now(),
            },
        )
        accion = 'guardado' if creado else 'actualizado'
        messages.success(request, f'¡Ingrediente «{nombre}» {accion} con éxito!')
    return redirect('recetas:verificar_url')


@login_required
def verificar_url(request):
    contexto = {'url_ingresada': ''}

    if request.method == 'POST':
        # CASO 1: El usuario hizo clic en "Guardar"
        if 'guardar_ingrediente' in request.POST:
            return _guardar_ingrediente_seguido(request)

        # CASO 2: El usuario hizo clic en "Verificar"
        url = request.POST.get('url', '').strip()
        contexto['url_ingresada'] = url

        if not url:
            contexto['error'] = 'Pegá la URL de un producto para verificarla.'
        else:
            if '://' not in url:
                url = 'https://' + url
            partes = urlparse(url)

            if partes.scheme not in ('http', 'https') or not partes.netloc:
                contexto['error'] = 'La URL no es válida. Debe empezar con http:// o https://.'
            else:
                analisis = analizar_y_limpiar_url(url)
                if not _destino_es_publico(analisis['url_limpia']):
                    contexto['error'] = 'No se pudo resolver el dominio o apunta a una red privada.'
                else:
                    resultado = probar_semaforo_url(analisis['url_limpia'])
                    contexto.update({
                        'dominio': analisis['dominio'],
                        'url_limpia': analisis['url_limpia'],
                        'semaforo': resultado['semaforo'],
                        'color': resultado['semaforo'].split()[0].lower(),
                        'codigo': resultado['codigo'],
                        'mensaje': resultado['mensaje'],
                    })
                    if resultado['codigo'] == 200:
                        contexto['datos'] = extraer_datos_producto(analisis['url_limpia'])

    return render(request, 'recetas/verificar_url.html', contexto)


# ---------------------------------------------------------------------------
# Planificador semanal
#   casillero (fecha + turno) -> opciones -> platos (recetas)
# ---------------------------------------------------------------------------

def _accion_planificador(request, inicio, fin):
    """Procesa los formularios del planificador (siempre vuelven a la misma semana)."""
    accion = request.POST.get('accion')

    if accion == 'guardar_opcion':
        # Crea una opción nueva en el casillero (fecha + turno) o, si viene "opcion", reemplaza sus platos.
        ids = [_entero(x, 1) for x in request.POST.getlist('recetas')]
        propias = set(Receta.objects.filter(usuario=request.user, pk__in=[i for i in ids if i]).values_list('pk', flat=True))
        if not ids or None in ids or not set(ids) <= propias:
            messages.error(request, 'Elegí al menos una receta de las tuyas para la opción.')
        else:
            with transaction.atomic():
                opcion_id = _entero(request.POST.get('opcion'), 1)
                if opcion_id:
                    opcion = get_object_or_404(OpcionPlan, pk=opcion_id, plan__usuario=request.user)
                else:
                    fecha = _fecha(request.POST.get('fecha'))
                    turno = request.POST.get('turno')
                    if fecha is None or turno not in dict(PlanComida.TURNOS):
                        messages.error(request, 'Faltan la fecha o el turno.')
                        return redirect(request.get_full_path())
                    plan, _ = PlanComida.objects.get_or_create(usuario=request.user, fecha=fecha, turno=turno)
                    ultimo = plan.opciones.order_by('-orden').values_list('orden', flat=True).first() or 0
                    opcion = OpcionPlan.objects.create(plan=plan, orden=ultimo + 1)
                opcion.nota = request.POST.get('nota', '').strip()[:100]
                opcion.save()
                opcion.platos.all().delete()
                PlatoOpcionPlan.objects.bulk_create([
                    PlatoOpcionPlan(opcion=opcion, receta_id=rid, orden=i) for i, rid in enumerate(ids, 1)
                ])
            messages.success(request, 'Opción guardada.')

    elif accion == 'quitar_opcion':
        opcion = get_object_or_404(OpcionPlan, pk=_entero(request.POST.get('opcion'), 1) or 0, plan__usuario=request.user)
        plan = opcion.plan
        opcion.delete()
        if not plan.opciones.exists():          # un casillero sin opciones no hace falta
            plan.delete()

    elif accion == 'limpiar':
        PlanComida.objects.filter(usuario=request.user, fecha__range=(inicio, fin)).delete()
        messages.success(request, 'Semana limpiada.')

    elif accion == 'armar_lista':
        porciones = _entero(request.POST.get('porciones'), 1, 10000)
        if porciones is None:
            messages.error(request, 'Indicá cuántas porciones querés de cada opción (un número mayor a cero).')
        else:
            lineas = servicios.lineas_compra(servicios.necesidades_semana(request.user, inicio, porciones))
            if not lineas:
                messages.warning(request, 'No hay nada planificado en esta semana para armar la lista.')
            else:
                lista, _ = ListaCompras.objects.get_or_create(usuario=request.user)
                servicios.regenerar_lista(lista, lineas, 'semana', semana_inicio=inicio, porciones_por_opcion=porciones)
                messages.success(request, f'Lista armada: {porciones} porciones de cada opción de la semana.')
                return redirect('recetas:lista_compras')

    return redirect(request.get_full_path())


@login_required
def planificador_semanal(request):
    hoy = timezone.localdate()
    # ?semana=AAAA-MM-DD: cualquier día de esa semana. Si no viene o es inválido, esta semana.
    inicio = _lunes(_fecha(request.GET.get('semana', '')) or hoy)
    fin = inicio + timedelta(days=6)

    if request.method == 'POST':
        return _accion_planificador(request, inicio, fin)

    planes = (PlanComida.objects.filter(usuario=request.user, fecha__range=(inicio, fin))
              .prefetch_related('opciones__platos__receta__categoria'))
    por_casillero = {(p.fecha, p.turno): p for p in planes}

    dias = []
    for i in range(7):
        f = inicio + timedelta(days=i)
        turnos = []
        for clave, etiqueta in PlanComida.TURNOS:
            plan = por_casillero.get((f, clave))
            turnos.append({
                'clave': clave, 'etiqueta': etiqueta, 'plan': plan,
                'opciones': list(plan.opciones.all()) if plan else [],
            })
        dias.append({'fecha': f, 'hoy': f == hoy, 'turnos': turnos})

    return render(request, 'recetas/planificador.html', {
        'inicio': inicio, 'fin': fin,
        'anterior': inicio - timedelta(days=7), 'siguiente': inicio + timedelta(days=7),
        'dias': dias,
        'recetas': Receta.objects.filter(usuario=request.user).select_related('categoria').order_by('titulo'),
        'planificadas': sum(1 for p in planes if p.opciones.all()),   # casilleros con opciones
        'porciones_por_defecto': 10,
    })


# ---------------------------------------------------------------------------
# Eventos
#   evento -> fases -> opciones (con porciones) -> platos (recetas)
# ---------------------------------------------------------------------------

def _estructura_evento(evento):
    """El menú del evento como datos simples, para que el navegador arme el editor."""
    if evento is None:
        return []
    return [
        {
            'nombre': fase.nombre,
            'opciones': [
                {'porciones': o.porciones, 'nota': o.nota, 'recetas': [p.receta_id for p in o.platos.all()]}
                for o in fase.opciones.all()
            ],
        }
        for fase in evento.fases.all()
    ]


def _leer_evento(request):
    """Valida el formulario del evento. Devuelve (datos limpios, lista de errores, estructura cruda)."""
    p = request.POST
    errores = []

    nombre = p.get('nombre', '').strip()[:150]
    if not nombre:
        errores.append('El evento necesita un nombre.')
    fecha = _fecha(p.get('fecha')) if p.get('fecha') else None
    invitados = _entero(p.get('invitados'), 1, 100000)
    if invitados is None:
        errores.append('Los invitados deben ser un número mayor a cero.')
    margen = _entero(p.get('margen') or 0, 0, 1000)     # libre: 0 = justo, 100 = el doble
    if margen is None:
        errores.append('El margen debe ser un porcentaje entre 0 y 1000.')

    try:
        cruda = json.loads(p.get('estructura') or '[]')
    except ValueError:
        cruda = None
    if not isinstance(cruda, list):
        errores.append('El menú no tiene un formato válido.')
        cruda = []

    fases, usadas = [], set()
    for f in cruda[:20]:
        if not isinstance(f, dict):
            continue
        nombre_fase = str(f.get('nombre', '')).strip()[:60]
        if not nombre_fase:
            errores.append('Cada fase necesita un nombre.')
            continue
        opciones = []
        for o in (f.get('opciones') or [])[:50]:
            if not isinstance(o, dict):
                continue
            ids = [_entero(x, 1) for x in (o.get('recetas') or [])]
            porciones = _entero(o.get('porciones'), 0, 100000)
            if not ids or None in ids:
                errores.append(f'Cada opción de «{nombre_fase}» necesita al menos una receta.')
                continue
            if porciones is None:
                errores.append(f'Las porciones de las opciones de «{nombre_fase}» deben ser un número.')
                continue
            usadas.update(ids)
            opciones.append({'porciones': porciones, 'nota': str(o.get('nota', '')).strip()[:100], 'recetas': ids})
        fases.append({'nombre': nombre_fase, 'opciones': opciones})

    propias = set(Receta.objects.filter(usuario=request.user, pk__in=usadas).values_list('pk', flat=True))
    if usadas - propias:
        errores.append('El menú usa recetas que no existen.')

    datos = {'nombre': nombre, 'fecha': fecha, 'invitados': invitados, 'margen': margen, 'fases': fases}
    return datos, errores, cruda


def _guardar_evento(request, evento):
    datos, errores, cruda = _leer_evento(request)
    if errores:
        for e in dict.fromkeys(errores):            # sin repetidos
            messages.error(request, e)
        return None, cruda
    with transaction.atomic():
        if evento is None:
            evento = Evento(usuario=request.user)
        evento.nombre, evento.fecha = datos['nombre'], datos['fecha']
        evento.invitados, evento.margen = datos['invitados'], datos['margen']
        evento.save()
        evento.fases.all().delete()                 # se reescribe el menú completo
        for orden_f, f in enumerate(datos['fases'], 1):
            fase = FaseEvento.objects.create(evento=evento, nombre=f['nombre'], orden=orden_f)
            for orden_o, o in enumerate(f['opciones'], 1):
                opcion = OpcionEvento.objects.create(fase=fase, orden=orden_o, nota=o['nota'], porciones=o['porciones'])
                PlatoOpcionEvento.objects.bulk_create([
                    PlatoOpcionEvento(opcion=opcion, receta_id=rid, orden=i) for i, rid in enumerate(o['recetas'], 1)
                ])
    return evento, cruda


@login_required
def calcular_evento(request, pk=None):
    """Arma un evento (fases, opciones y porciones) y calcula lo necesario para cubrirlo."""
    evento = get_object_or_404(Evento.objects.filter(usuario=request.user), pk=pk) if pk else None
    borrador, estructura = None, None

    if request.method == 'POST':
        guardado, cruda = _guardar_evento(request, evento)
        if guardado is not None:
            if request.POST.get('accion') == 'a_lista':
                lineas = servicios.lineas_compra(servicios.necesidades_evento(guardado))
                lista, _ = ListaCompras.objects.get_or_create(usuario=request.user)
                servicios.regenerar_lista(lista, lineas, 'evento', evento=guardado)
                messages.success(request, f'Lista armada para «{guardado.nombre}».')
                return redirect('recetas:lista_compras')
            messages.success(request, f'Evento «{guardado.nombre}» guardado.')
            return redirect('recetas:calcular_evento', pk=guardado.pk)
        # Hubo errores: se vuelve a mostrar lo que el usuario había escrito.
        p = request.POST
        borrador = {'nombre': p.get('nombre', ''), 'fecha': p.get('fecha', ''),
                    'invitados': p.get('invitados', ''), 'margen': p.get('margen', '')}
        estructura = cruda

    resultado = None
    if evento is not None and borrador is None:
        lineas = servicios.lineas_compra(servicios.necesidades_evento(evento))
        resultado = {'lineas': lineas, **servicios.resumen_costos(lineas, evento.invitados)}
    if estructura is None:
        if evento is not None:
            evento = Evento.objects.prefetch_related('fases__opciones__platos').get(pk=evento.pk)
        estructura = _estructura_evento(evento)

    return render(request, 'recetas/calcular_evento.html', {
        'evento': evento,
        'borrador': borrador,
        'eventos': Evento.objects.filter(usuario=request.user),
        'recetas': Receta.objects.filter(usuario=request.user).select_related('categoria').order_by('titulo'),
        'estructura': estructura,
        'resultado': resultado,
    })


@login_required
def evento_eliminar(request, pk):
    evento = get_object_or_404(Evento, pk=pk, usuario=request.user)
    if request.method == 'POST':
        nombre = evento.nombre
        evento.delete()
        messages.success(request, f'Evento «{nombre}» eliminado.')
        return redirect('recetas:calcular_evento')
    return render(request, 'recetas/confirmar_eliminar.html', {
        'objeto': evento.nombre, 'volver': 'recetas:calcular_evento', 'pk': pk,
        'aviso': 'Se borrarán también sus fases y opciones.',
    })


# ---------------------------------------------------------------------------
# Lista de compras
# ---------------------------------------------------------------------------

def _texto_a_cantidad(texto):
    """'2 paquetes' -> (2, 'paquetes'); 'servilletas' -> (1, 'servilletas'); '' -> (1, '')."""
    texto = texto.strip()
    m = re.match(r'^(\d+(?:[.,]\d+)?)\s*(.*)$', texto)
    if m:
        cantidad = _a_decimal(m.group(1))
        if cantidad is not None and 0 < cantidad < 10**6:
            return cantidad.quantize(Decimal('0.01')), m.group(2).strip()[:20]
    return Decimal(1), texto[:20]


def _accion_lista(request, lista):
    accion = request.POST.get('accion')

    if accion == 'marcar':                          # tildar/destildar un ítem (llamado con fetch)
        item = get_object_or_404(ItemCompra, pk=_entero(request.POST.get('item'), 1) or 0, lista=lista)
        item.comprado = request.POST.get('comprado') == '1'
        item.save(update_fields=['comprado'])
        return JsonResponse({'ok': True})

    if accion == 'agregar':
        nombre = request.POST.get('item', '').strip()[:150]
        if not nombre:
            messages.error(request, 'El ítem necesita un nombre.')
        else:
            seccion = request.POST.get('seccion')
            cantidad, unidad = _texto_a_cantidad(request.POST.get('cantidad', ''))
            ItemCompra.objects.create(
                lista=lista, nombre=nombre, cantidad=cantidad, unidad=unidad, manual=True,
                seccion=seccion if seccion in dict(SECCIONES) else 'otros',
            )

    elif accion == 'quitar':
        lista.items.filter(pk=_entero(request.POST.get('item'), 1) or 0).delete()

    elif accion == 'vaciar_tildados':
        lista.items.filter(comprado=True).delete()

    elif accion == 'desde_semana':
        semana = _fecha(request.POST.get('semana'))
        porciones = _entero(request.POST.get('porciones'), 1, 10000)
        if semana is None or porciones is None:
            messages.error(request, 'Indicá la semana y cuántas porciones querés de cada opción.')
        else:
            inicio = _lunes(semana)
            lineas = servicios.lineas_compra(servicios.necesidades_semana(request.user, inicio, porciones))
            if not lineas:
                messages.warning(request, 'No hay nada planificado en esa semana.')
            else:
                servicios.regenerar_lista(lista, lineas, 'semana', semana_inicio=inicio, porciones_por_opcion=porciones)
                messages.success(request, f'Lista armada con {porciones} porciones de cada opción de la semana.')

    elif accion == 'desde_evento':
        evento = get_object_or_404(Evento, pk=_entero(request.POST.get('evento'), 1) or 0, usuario=request.user)
        lineas = servicios.lineas_compra(servicios.necesidades_evento(evento))
        if not lineas:
            messages.warning(request, 'Ese evento todavía no tiene recetas en su menú.')
        else:
            servicios.regenerar_lista(lista, lineas, 'evento', evento=evento)
            messages.success(request, f'Lista armada para «{evento.nombre}».')

    return redirect('recetas:lista_compras')


@login_required
def lista_compras(request):
    lista, _ = ListaCompras.objects.get_or_create(usuario=request.user)

    if request.method == 'POST':
        return _accion_lista(request, lista)

    items = list(lista.items.select_related('ingrediente__producto_referencia'))
    por_seccion = {}
    for it in items:
        it.paquetes, precio = servicios.precio_item(it)
        it.precio = precio if precio is not None else Decimal(0)
        it.sin_precio = precio is None
        por_seccion.setdefault(it.seccion, []).append(it)

    grupos = [
        {'nombre': etiqueta, 'items': por_seccion[clave], 'subtotal': sum((i.precio for i in por_seccion[clave]), Decimal(0))}
        for clave, etiqueta in SECCIONES if clave in por_seccion
    ]

    return render(request, 'recetas/lista_compras.html', {
        'lista': lista,
        'grupos': grupos,
        'total_items': len(items),
        'secciones': SECCIONES,
        'semana_sugerida': _lunes(timezone.localdate()),
        'eventos': Evento.objects.filter(usuario=request.user),
    })


# ---------------------------------------------------------------------------
# Notas
# ---------------------------------------------------------------------------

@login_required
def notas(request):
    if request.method == 'POST':
        accion = request.POST.get('accion')
        pk = _entero(request.POST.get('pk'), 1)
        if accion == 'eliminar':
            get_object_or_404(Nota, pk=pk or 0, usuario=request.user).delete()
            messages.success(request, 'Nota eliminada.')
        elif accion == 'guardar':
            nota = get_object_or_404(Nota, pk=pk, usuario=request.user) if pk else Nota(usuario=request.user)
            nota.titulo = request.POST.get('titulo', '').strip()[:150]
            nota.contenido = request.POST.get('contenido', '').strip()
            nota.save()
            messages.success(request, 'Nota guardada.')
        return redirect('recetas:notas')

    return render(request, 'recetas/notas.html', {'notas': Nota.objects.filter(usuario=request.user)})


# ---------------------------------------------------------------------------
# Herramientas
# ---------------------------------------------------------------------------

@login_required
def temporizador(request):
    """Los tiempos de cocción de las recetas del usuario, como atajos del temporizador."""
    recetas = (Receta.objects.filter(usuario=request.user, tiempo_coccion_min__gt=0).order_by('titulo'))
    return render(request, 'recetas/temporizador.html', {
        'tiempos_recetas': [
            {'titulo': r.titulo, 'minutos': r.tiempo_coccion_min, 'segundos': r.tiempo_coccion_min * 60}
            for r in recetas
        ],
    })

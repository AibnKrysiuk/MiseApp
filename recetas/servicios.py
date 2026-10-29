"""
Cálculos de Mise: unidades, escalado de recetas y armado de la lista de compras.

La idea central: una "necesidad" es una receta y las porciones que se quieren de ella.
Con una lista de necesidades se suman los ingredientes de todas las recetas, se
redondea hacia arriba (para no quedarse corto) y se estima el costo.
"""
import math
from collections import OrderedDict
from datetime import timedelta
from decimal import Decimal, ROUND_CEILING

from django.db import transaction

from .models import ItemCompra, PlanComida, SECCIONES

# Unidad -> (unidad base, factor). Se suma siempre en la unidad base.
BASES = {
    'g': ('g', 1),
    'kg': ('g', 1000),
    'ml': ('ml', 1),
    'l': ('ml', 1000),
    'unid': ('unid', 1),
    'cucharada': ('cucharada', 1),
    'taza': ('taza', 1),
}
# Cómo se suelen escribir a mano las unidades de los ingredientes seguidos.
ALIAS = {
    'gr': 'g', 'grs': 'g', 'gramo': 'g', 'gramos': 'g',
    'kilo': 'kg', 'kilos': 'kg', 'kgs': 'kg', 'kilogramo': 'kg', 'kilogramos': 'kg',
    'lt': 'l', 'lts': 'l', 'litro': 'l', 'litros': 'l',
    'cc': 'ml', 'mililitro': 'ml', 'mililitros': 'ml',
    'unidad': 'unid', 'unidades': 'unid', 'un': 'unid', 'u': 'unid',
    'cucharadas': 'cucharada', 'tazas': 'taza',
}
ORDEN_SECCIONES = [clave for clave, _ in SECCIONES]


def a_base(cantidad, unidad):
    """(cantidad, unidad) -> (cantidad en unidad base, unidad base); None si no se reconoce la unidad."""
    clave = str(unidad or '').strip().lower().rstrip('.')
    clave = ALIAS.get(clave, clave)
    if clave not in BASES:
        return None
    base, factor = BASES[clave]
    return Decimal(cantidad) * factor, base


def _techo(valor, paso):
    """Redondea hacia arriba al múltiplo de `paso`."""
    return (Decimal(valor) / paso).to_integral_value(rounding=ROUND_CEILING) * paso


def presentar(cantidad_base, base):
    """Cantidad en unidad base -> (cantidad, unidad) para mostrar (1200 g -> 1,2 kg)."""
    if base == 'g' and cantidad_base >= 1000:
        return (cantidad_base / 1000).quantize(Decimal('0.01'), rounding=ROUND_CEILING), 'kg'
    if base == 'ml' and cantidad_base >= 1000:
        return (cantidad_base / 1000).quantize(Decimal('0.01'), rounding=ROUND_CEILING), 'l'
    return cantidad_base, {'unid': 'unidades'}.get(base, base)


def precio_estimado(ingrediente, cantidad_base, base):
    """
    Costo de comprar `cantidad_base` del ingrediente, según su producto de referencia.
    Se compran paquetes enteros: 2,5 l de leche con envases de 1 l son 3 envases.
    Devuelve (paquetes, precio) o (None, None) si no hay referencia o las unidades no coinciden.
    """
    ref = ingrediente.producto_referencia if ingrediente else None
    if ref is None or ref.precio_actual is None:
        return None, None
    conv = a_base(ref.cantidad, ref.unidad)
    if conv is None or conv[1] != base or conv[0] <= 0:
        return None, None
    paquetes = int(_techo(Decimal(cantidad_base) / conv[0], 1))
    return paquetes, paquetes * ref.precio_actual


def precio_item(item):
    """Lo mismo, para un ItemCompra ya guardado (su cantidad puede estar en kg o l)."""
    if item.ingrediente_id is None:
        return None, None
    conv = a_base(item.cantidad, item.unidad)
    if conv is None:
        return None, None
    return precio_estimado(item.ingrediente, conv[0], conv[1])


# --------------------------------------------------------------------------
# Escalado y suma de recetas
# --------------------------------------------------------------------------

def acumular(pares):
    """
    pares: iterable de (receta, porciones deseadas). Escala los ingredientes de cada receta
    (porciones deseadas / porciones que rinde) y los suma por ingrediente y unidad base.
    """
    total = OrderedDict()
    for receta, porciones in pares:
        if not porciones:
            continue
        factor = Decimal(porciones) / Decimal(receta.porciones or 1)
        for det in receta.ingredientes_detalle.all():
            conv = a_base(det.cantidad, det.unidad_medida)
            if conv is None:
                continue
            clave = (det.ingrediente_id, conv[1])
            if clave not in total:
                total[clave] = {'ingrediente': det.ingrediente, 'base': conv[1], 'cantidad': Decimal(0), 'recetas': []}
            total[clave]['cantidad'] += conv[0] * factor
            if receta.titulo not in total[clave]['recetas']:
                total[clave]['recetas'].append(receta.titulo)
    return total


def lineas_compra(acumulado):
    """Pasa lo acumulado a líneas listas para la lista de compras: redondeadas hacia arriba y con precio."""
    lineas = []
    for dato in acumulado.values():
        ing, base = dato['ingrediente'], dato['base']
        cantidad_base = _techo(dato['cantidad'], 5 if base in ('g', 'ml') else 1)
        cantidad, unidad = presentar(cantidad_base, base)
        paquetes, precio = precio_estimado(ing, cantidad_base, base)
        lineas.append({
            'ingrediente': ing, 'nombre': ing.nombre, 'seccion': ing.seccion,
            'cantidad': cantidad, 'unidad': unidad,
            'origen': ', '.join(dato['recetas'])[:255],
            'paquetes': paquetes, 'precio': precio,
        })
    lineas.sort(key=lambda l: (ORDEN_SECCIONES.index(l['seccion']) if l['seccion'] in ORDEN_SECCIONES else 99, l['nombre'].lower()))
    return lineas


def resumen_costos(lineas, personas=None):
    """Total estimado y costo por persona. Las líneas sin precio de referencia no suman."""
    total = sum((l['precio'] for l in lineas if l['precio'] is not None), Decimal(0))
    return {
        'total': total,
        'por_persona': (total / personas) if personas else None,
        'sin_precio': sum(1 for l in lineas if l['precio'] is None),
    }


# --------------------------------------------------------------------------
# De dónde salen las necesidades
# --------------------------------------------------------------------------

def necesidades_semana(usuario, inicio, porciones_por_opcion):
    """
    Todo lo necesario para tener `porciones_por_opcion` porciones de CADA plato de CADA opción
    de CADA turno de la semana que empieza en `inicio`.
    """
    planes = PlanComida.objects.filter(
        usuario=usuario, fecha__range=(inicio, inicio + timedelta(days=6)),
    ).prefetch_related('opciones__platos__receta__ingredientes_detalle__ingrediente__producto_referencia')
    pares = [
        (plato.receta, porciones_por_opcion)
        for plan in planes for opcion in plan.opciones.all() for plato in opcion.platos.all()
    ]
    return acumular(pares)


def necesidades_evento(evento):
    """
    Todo lo necesario para el evento: cada opción con sus porciones previstas más el margen
    (0 % = justo; 100 % = el doble). Cada plato de la opción se prepara para esas porciones.
    """
    fases = evento.fases.prefetch_related('opciones__platos__receta__ingredientes_detalle__ingrediente__producto_referencia')
    pares = []
    for fase in fases:
        for opcion in fase.opciones.all():
            porciones = int(_techo(Decimal(opcion.porciones) * (100 + evento.margen) / 100, 1))
            pares.extend((plato.receta, porciones) for plato in opcion.platos.all())
    return acumular(pares)


def regenerar_lista(lista, lineas, origen, semana_inicio=None, porciones_por_opcion=None, evento=None):
    """Reemplaza los ítems automáticos de la lista (los agregados a mano se conservan)."""
    with transaction.atomic():
        lista.items.filter(manual=False).delete()
        ItemCompra.objects.bulk_create([
            ItemCompra(
                lista=lista, ingrediente=l['ingrediente'], nombre=l['nombre'],
                cantidad=l['cantidad'], unidad=l['unidad'], seccion=l['seccion'], origen=l['origen'],
            )
            for l in lineas
        ])
        lista.origen = origen
        lista.semana_inicio = semana_inicio
        lista.porciones_por_opcion = porciones_por_opcion
        lista.evento = evento
        lista.save()

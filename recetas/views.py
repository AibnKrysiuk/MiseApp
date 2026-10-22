from django.contrib import messages
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
import ipaddress
import socket
from datetime import date
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse
from django.contrib.auth.decorators import login_required

from .forms import IngredienteForm, IngredienteFormSet, PasoFormSet, RecetaForm
from .models import Ingrediente, IngredienteSeguido, Receta
from .utils import analizar_y_limpiar_url, extraer_datos_producto, probar_semaforo_url



def index(request, pk=None):
    """Índice (tarjetas) o detalle de una receta."""
    recetas = Receta.objects.select_related('categoria').order_by('titulo')
    if request.GET.get('vista') == 'indice':
        return render(request, 'recetas/index.html', {'recetas': recetas, 'vista': 'indice'})
    qs = Receta.objects.prefetch_related('pasos', 'ingredientes_detalle__ingrediente')
    receta = get_object_or_404(qs, pk=pk) if pk else qs.order_by('titulo').first()
    return render(request, 'recetas/index.html', {'receta': receta, 'vista': 'detalle'})

@login_required
def receta_form(request, pk=None):
    """Crea (pk=None) o edita una receta junto con sus ingredientes y pasos."""
    receta = get_object_or_404(Receta, pk=pk) if pk else None
    form = RecetaForm(request.POST or None, instance=receta)
    ingredientes = IngredienteFormSet(request.POST or None, instance=receta, prefix='ing')
    pasos = PasoFormSet(request.POST or None, instance=receta, prefix='pas')
    if request.method == 'POST' and form.is_valid() and ingredientes.is_valid() and pasos.is_valid():
        with transaction.atomic():
            receta = form.save()
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
    receta = get_object_or_404(Receta, pk=pk)
    if request.method == 'POST':
        titulo = receta.titulo
        receta.delete()
        messages.success(request, f'Receta «{titulo}» eliminada.')
        return redirect('recetas:index')
    return render(request, 'recetas/confirmar_eliminar.html', {
        'objeto': receta.titulo, 'volver': 'recetas:detalle', 'pk': pk,
        'aviso': 'Se borrarán también sus ingredientes y pasos.',
    })

@login_required
def ingredientes(request, pk=None):
    """Lista, crea y edita ingredientes en la misma página."""
    editando = get_object_or_404(Ingrediente, pk=pk) if pk else None
    form = IngredienteForm(request.POST or None, instance=editando)
    if request.method == 'POST' and form.is_valid():
        ing = form.save()
        messages.success(request, f'Ingrediente «{ing.nombre}» guardado.')
        return redirect('recetas:ingredientes')
    lista = Ingrediente.objects.annotate(usos=Count('ingredientereceta')).order_by('nombre')
    return render(request, 'recetas/ingredientes.html', {'form': form, 'lista': lista, 'editando': editando})

@login_required
def ingrediente_eliminar(request, pk):
    ing = get_object_or_404(Ingrediente, pk=pk)
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



def _a_decimal(texto):
    """Convierte texto a Decimal finito (acepta coma o punto); None si no es válido."""
    try:
        valor = Decimal(str(texto).strip().replace(',', '.'))
    except (InvalidOperation, ValueError):
        return None
    return valor if valor.is_finite() else None

def _guardar_ingrediente_seguido(request):
    if not request.user.is_authenticated:
        messages.warning(request, 'Tenés que iniciar sesión o registrarte para guardar ingredientes seguidos.')
        return redirect('login')
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


def verificar_url(request):
    contexto = {'url_ingresada': ''}
 
    if request.method == 'POST':
        # CASO 1: El usuario hizo clic en "Guardar"
        if 'guardar_ingrediente' in request.POST:
            return _guardar_ingrediente_seguido(request)

        # CASO 2: El usuario hizo clic en "Verificar" (el código que ya tenías)
        else:
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
@login_required
def ingredientes(request, pk=None):
    """Lista, crea y edita ingredientes de recetas y consulta los ingredientes seguidos."""
    editando = get_object_or_404(Ingrediente, pk=pk) if pk else None
    form = IngredienteForm(request.POST or None, instance=editando)
    
    if request.method == 'POST' and form.is_valid():
        ing = form.save()
        messages.success(request, f'Ingrediente «{ing.nombre}» guardado.')
        return redirect('recetas:ingredientes')
        
    lista = Ingrediente.objects.annotate(usos=Count('ingredientereceta')).order_by('nombre')
    
    # <--- Agregamos la consulta de Ingredientes Seguidos
    ingredientes_seguidos = IngredienteSeguido.objects.filter(activo=True).order_by('nombre')
    
    return render(request, 'recetas/ingredientes.html', {
        'form': form, 
        'lista': lista, 
        'editando': editando,
        'ingredientes_seguidos': ingredientes_seguidos # <--- Lo pasamos al contexto
    })
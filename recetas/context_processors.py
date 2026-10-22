from .models import Receta


def indice_recetas(request):
    """Disponibiliza la lista de recetas para el índice lateral en todas las páginas."""
    return {'indice_recetas': Receta.objects.only('id', 'titulo').order_by('titulo')}

from django.urls import path
from . import views

app_name = 'recetas'

urlpatterns = [
    path('', views.index, name='index'),
    path('calcular_evento', views.calcular_evento, name='calcular_evento'),
    path('calcular_evento', views.calcular_evento, name='calcular_evento'),                       # la que ya tenés
    path('calcular_evento/<int:pk>', views.calcular_evento, name='calcular_evento'),              # nueva: mismo nombre, con pk
    path('calcular_evento/<int:pk>/eliminar', views.evento_eliminar, name='evento_eliminar'),     # nueva
    path('planificador', views.planificador_semanal, name='planificador'),
    path('lista_compras', views.lista_compras, name='lista_compras'),
    path('notas', views.notas, name='notas'),
    path('temporizador', views.temporizador, name='temporizador'),
    path('receta/nueva/', views.receta_form, name='crear'),
    path('receta/<int:pk>/', views.index, name='detalle'),
    path('receta/<int:pk>/editar/', views.receta_form, name='editar'),
    path('receta/<int:pk>/eliminar/', views.receta_eliminar, name='eliminar'),
    path('ingredientes/', views.ingredientes, name='ingredientes'),
    path('ingredientes/<int:pk>/editar/', views.ingredientes, name='ingrediente_editar'),
    path('ingredientes/<int:pk>/eliminar/', views.ingrediente_eliminar, name='ingrediente_eliminar'),
    path('verificar_url/', views.verificar_url, name='verificar_url'),
]
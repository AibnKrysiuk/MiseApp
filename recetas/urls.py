from django.urls import path
from . import views

app_name = 'recetas'

urlpatterns = [
    path('', views.index, name='index'),
    path('receta/nueva/', views.receta_form, name='crear'),
    path('receta/<int:pk>/', views.index, name='detalle'),
    path('receta/<int:pk>/editar/', views.receta_form, name='editar'),
    path('receta/<int:pk>/eliminar/', views.receta_eliminar, name='eliminar'),
    path('ingredientes/', views.ingredientes, name='ingredientes'),
    path('ingredientes/<int:pk>/editar/', views.ingredientes, name='ingrediente_editar'),
    path('ingredientes/<int:pk>/eliminar/', views.ingrediente_eliminar, name='ingrediente_eliminar'),
    path('verificar_url/', views.verificar_url, name='verificar_url'),
]
from django.contrib import admin
from .models import *
# Register your models here.

class IngredienteRecetaInline(admin.TabularInline):
    model = IngredienteReceta
    extra = 1

class PasoRecetaInline(admin.TabularInline):
    model = PasoReceta
    extra = 1

@admin.register(Receta)
class RecetaAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'categoria', 'porciones', 'creado_en')
    list_filter = ('categoria',)
    search_fields = ('titulo', 'descripcion')
    inlines = [IngredienteRecetaInline, PasoRecetaInline]

admin.site.register(Categoria)
admin.site.register(Ingrediente)
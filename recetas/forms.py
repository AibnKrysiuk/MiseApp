from django import forms
from django.forms import inlineformset_factory
from .models import Receta, Ingrediente, IngredienteReceta, PasoReceta


class IngredienteForm(forms.ModelForm):
    class Meta:
        model = Ingrediente
        fields = ['nombre']
        widgets = {'nombre': forms.TextInput(attrs={'placeholder': 'Ej. Harina 0000', 'autocomplete': 'off'})}


class RecetaForm(forms.ModelForm):
    class Meta:
        model = Receta
        fields = ['titulo', 'descripcion', 'porciones', 'tiempo_preparacion_min', 'tiempo_coccion_min', 'categoria']
        widgets = {'descripcion': forms.Textarea(attrs={'rows': 3})}


IngredienteFormSet = inlineformset_factory(
    Receta, IngredienteReceta,
    fields=['ingrediente', 'cantidad', 'unidad_medida'],
    extra=2, can_delete=True,
)

PasoFormSet = inlineformset_factory(
    Receta, PasoReceta,
    fields=['numero_paso', 'instruccion'],
    extra=2, can_delete=True,
    widgets={'instruccion': forms.Textarea(attrs={'rows': 2})},
)
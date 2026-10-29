from django import forms
from django.forms import inlineformset_factory
from .models import Receta, Ingrediente, IngredienteReceta, PasoReceta, Categoria, IngredienteSeguido

class UsuarioFormMixin:
    """
    Recibe usuario=... y limita las listas desplegables a lo que es de ese usuario
    (sus categorías, sus ingredientes y sus productos seguidos).
    """
    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        if usuario is None:
            return
        if 'categoria' in self.fields:
            self.fields['categoria'].queryset = Categoria.objects.filter(usuario=usuario)
        if 'ingrediente' in self.fields:
            self.fields['ingrediente'].queryset = Ingrediente.objects.filter(usuario=usuario)
        if 'producto_referencia' in self.fields:
            self.fields['producto_referencia'].queryset = IngredienteSeguido.objects.filter(usuario=usuario, activo=True)

class IngredienteForm(UsuarioFormMixin,forms.ModelForm):
    class Meta:
        model = Ingrediente
        fields = ['nombre']
        widgets = {'nombre': forms.TextInput(attrs={'placeholder': 'Ej. Harina 0000', 'autocomplete': 'off'})}


class RecetaForm(UsuarioFormMixin,forms.ModelForm):
    class Meta:
        model = Receta
        fields = ['titulo', 'descripcion', 'porciones', 'tiempo_preparacion_min', 'tiempo_coccion_min', 'categoria']
        widgets = {'descripcion': forms.Textarea(attrs={'rows': 3})}


class IngredienteRecetaForm(UsuarioFormMixin, forms.ModelForm):
    """Una fila de la lista de ingredientes de una receta."""
    class Meta:
        model = IngredienteReceta
        fields = ['ingrediente', 'cantidad', 'unidad_medida']


IngredienteFormSet = inlineformset_factory(
    Receta, IngredienteReceta,
    form=IngredienteRecetaForm,
    extra=1, can_delete=True,
)
PasoFormSet = inlineformset_factory(
    Receta, PasoReceta,
    fields=['numero_paso', 'instruccion'],
    extra=2, can_delete=True,
    widgets={'instruccion': forms.Textarea(attrs={'rows': 2})},
)
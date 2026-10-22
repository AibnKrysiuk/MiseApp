from django.db import models

# Create your models here.
class Categoria(models.Model):
    nombre = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.nombre


class Receta(models.Model):
    titulo = models.CharField(max_length=150, verbose_name="Título de la receta.")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción o Notas.")
    porciones = models.PositiveIntegerField(default=1, verbose_name="Cantidad de porciones.")
    tiempo_preparacion_min = models.PositiveIntegerField(default=0, verbose_name="Tiempo de preparación. (min)")
    tiempo_coccion_min = models.PositiveIntegerField(default=0, verbose_name="Tiempo de cocción. (min)")
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True, related_name="recetas")

    creado_en = models.DateTimeField(auto_now=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.titulo

class Ingrediente(models.Model):
    nombre = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nombre

class IngredienteReceta(models.Model):
    """
    Tabla intermedia para definir la cantidad y unidad exacta que lleva cada receta.
    Ejemplo: Flan de Chocolate -> 250 g de Azúcar
    """
    UNIDADES = [
        ('g', 'Gramos'),
        ('kg', 'Kilogramos'),
        ('ml', 'Mililitros'),
        ('l', 'Litros'),
        ('unid', 'Unidades'),
        ('cucharada', 'Cucharada'),
        ('taza', 'Taza'),
    ]

    receta = models.ForeignKey(Receta, on_delete=models.CASCADE, related_name='ingredientes_detalle')
    ingrediente = models.ForeignKey(Ingrediente, on_delete=models.CASCADE)
    cantidad = models.DecimalField(max_digits=8, decimal_places=2)
    unidad_medida = models.CharField(max_length=20, choices=UNIDADES)

    def __str__(self):
        return f"{self.cantidad} {self.unidad_medida} de {self.ingrediente.nombre}"

class PasoReceta(models.Model):
    """
    Pasos/Procedimiento ordenados cronológicamente.
    """
    receta = models.ForeignKey(Receta, on_delete=models.CASCADE, related_name="pasos")
    numero_paso = models.PositiveIntegerField(verbose_name="Paso N°")
    instruccion = models.TextField(verbose_name="Instrucción")

    class Meta:
        ordering = ['numero_paso']
        unique_together = ['receta', 'numero_paso']

    def __str__(self):
        return f"Paso {self.numero_paso} - {self.receta.titulo}"



class ProductoSeguido(models.Model):
    nombre = models.CharField(max_length=150, help_text="Ej: Leche sachet La Serenísima 1L")
    url = models.URLField(max_length=500, unique=True, help_text="URL limpia del producto")
    precio_actual = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    ultima_actualizacion = models.DateTimeField(null=True, blank=True)
    activo = models.BooleanField(default=True, help_text="Si está activo, el bot lo revisa periódicamente")

    def __str__(self):
        return f"{self.nombre} - ${self.precio_actual or 'Sin precio'}"

class IngredienteSeguido(models.Model):
    # Identificación personalizada por el usuario
    nombre = models.CharField(max_length=150, help_text="Nombre personalizado, ej: Leche Disco")
    
    # Datos de la URL y rastreo
    url = models.URLField(max_length=500, unique=True, help_text="URL limpia del producto")
    precio_actual = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Cantidad y unidad especificada por el usuario (ej: 1 lt, 400 g)
    cantidad = models.DecimalField(max_digits=8, decimal_places=2, default=1.0, help_text="Cantidad numérica")
    unidad = models.CharField(max_length=20, default='unidades', help_text="Unidad: lt, kg, g, cc, unidades")
    
    # Datos extraídos automáticamente por el bot
    descripcion = models.TextField(blank=True, null=True, help_text="Descripción extraída del supermercado")
    en_oferta = models.BooleanField(default=False)
    fecha_fin_oferta = models.DateField(null=True, blank=True)
    
    # Control de estado
    ultima_actualizacion = models.DateTimeField(null=True, blank=True)
    activo = models.BooleanField(default=True, help_text="Si está activo, el bot lo monitorea")

    def __str__(self):
        return f"{self.nombre} ({self.cantidad} {self.unidad}) - ${self.precio_actual or 'Sin precio'}"
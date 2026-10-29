from django.conf import settings
from django.db import models

# Create your models here.

# Secciones del supermercado: agrupan la lista de compras y se asignan a cada ingrediente.
SECCIONES = [
    ('almacen', 'Almacén'),
    ('lacteos', 'Lácteos y huevos'),
    ('carnes', 'Carnes'),
    ('verduleria', 'Verdulería'),
    ('otros', 'Otros'),
]


class Categoria(models.Model):
    # Cada usuario crea y administra las suyas (se muestran como solapas en el índice).
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="categorias")
    nombre = models.CharField(max_length=50)
    color = models.CharField(max_length=20, blank=True, help_text="Color CSS opcional, ej: #c85a32")

    class Meta:
        ordering = ['nombre']
        constraints = [
            models.UniqueConstraint(fields=['usuario', 'nombre'], name='categoria_unica_por_usuario'),
        ]

    def __str__(self):
        return self.nombre


class Receta(models.Model):
    # Relación con el usuario propietario de la receta
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recetas")
    
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
    # Ingredientes de cada usuario (así cada uno vincula sus propios precios).
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ingredientes")
    nombre = models.CharField(max_length=100)

    # Sección del supermercado, para agrupar la lista de compras.
    seccion = models.CharField(max_length=20, choices=SECCIONES, default='otros')

    # Producto seguido que se usa como referencia de precio (opcional).
    # Con esto se pueden calcular costos en la lista de compras y en el evento.
    producto_referencia = models.ForeignKey(
        'IngredienteSeguido', on_delete=models.SET_NULL, null=True, blank=True,
        related_name="ingredientes_vinculados",
        help_text="Producto cuyo precio se usa para estimar el costo de este ingrediente",
    )

    class Meta:
        ordering = ['nombre']
        constraints = [
            models.UniqueConstraint(fields=['usuario', 'nombre'], name='ingrediente_unico_por_usuario'),
        ]

    def __str__(self):
        return self.nombre


class IngredienteReceta(models.Model):
    """
    Tabla intermedia para definir la cantidad y unidad exacta que lleva cada receta.
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


# TODO (a futuro): migrar ProductoSeguido e IngredienteSeguido a una app aparte
# (por ejemplo "precios"), porque pertenecen al bot que revisa precios y no al recetario.
class ProductoSeguido(models.Model):
    # Relación con el usuario
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="productos_seguidos")
    
    nombre = models.CharField(max_length=150, help_text="Ej: Leche sachet La Serenísima 1L")
    url = models.URLField(max_length=500, help_text="URL limpia del producto") # Quitamos unique=True global para que distintos usuarios puedan seguir el mismo producto si quieren, o manejado por usuario.
    precio_actual = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    ultima_actualizacion = models.DateTimeField(null=True, blank=True)
    activo = models.BooleanField(default=True, help_text="Si está activo, el bot lo revisa periódicamente")

    def __str__(self):
        precio = self.precio_actual if self.precio_actual is not None else 'Sin precio'
        return f"{self.nombre} - ${precio}"


class IngredienteSeguido(models.Model):
    # Relación con el usuario
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ingredientes_seguidos")
    
    # Identificación personalizada por el usuario
    nombre = models.CharField(max_length=150, help_text="Nombre personalizado, ej: Leche Disco")
    
    # Datos de la URL y rastreo
    url = models.URLField(max_length=500, help_text="URL limpia del producto")
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


# =====================================================================
# TODO (a futuro): migrar los modelos de esta sección a otra app de Django
# (por ejemplo "planificacion" o "agenda"): Nota, PlanComida, OpcionPlan,
# PlatoOpcionPlan, ListaCompras, ItemCompra, Evento, FaseEvento, OpcionEvento
# y PlatoOpcionEvento. Son funciones de organización que no dependen de cómo
# se cargan las recetas; solo necesitan referenciar a Receta e Ingrediente
# (con 'recetas.Receta' / 'recetas.Ingrediente' desde la otra app).
# Mover modelos con datos ya cargados es trabajoso: conviene hacerlo antes
# de empezar a usarlos.
# =====================================================================

class Nota(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notas")
    titulo = models.CharField(max_length=150, blank=True)
    contenido = models.TextField(blank=True)
    creada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-actualizada_en']

    def __str__(self):
        return self.titulo or f"Nota {self.pk}"


class PlanComida(models.Model):
    """
    Un casillero del planificador semanal: una fecha y un turno.
    Adentro van las opciones (OpcionPlan), tantas como quiera el usuario.
    """
    TURNOS = [
        ('almuerzo', 'Almuerzo'),
        ('cena', 'Cena'),
    ]

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="plan_comidas")
    fecha = models.DateField()
    turno = models.CharField(max_length=10, choices=TURNOS)

    class Meta:
        ordering = ['fecha', 'turno']
        constraints = [
            # Un solo casillero por fecha y turno; lo que varía son las opciones de adentro.
            models.UniqueConstraint(fields=['usuario', 'fecha', 'turno'], name='un_casillero_por_turno_y_usuario'),
        ]

    def __str__(self):
        return f"{self.fecha} · {self.get_turno_display()}"


class OpcionPlan(models.Model):
    """
    Una alternativa dentro de un casillero, por ejemplo
    "Opción 1: merluza a la romana con puré y helado de vainilla".
    Sus platos son recetas (PlatoOpcionPlan).
    """
    plan = models.ForeignKey(PlanComida, on_delete=models.CASCADE, related_name="opciones")
    orden = models.PositiveIntegerField(default=1)
    nota = models.CharField(max_length=100, blank=True, help_text="Aclaración opcional, ej: sin gluten")

    class Meta:
        ordering = ['orden', 'id']

    def __str__(self):
        return f"Opción {self.orden} · {self.plan}"


class PlatoOpcionPlan(models.Model):
    """Una receta que forma parte de una opción (una opción puede tener varias)."""
    opcion = models.ForeignKey(OpcionPlan, on_delete=models.CASCADE, related_name="platos")
    receta = models.ForeignKey(Receta, on_delete=models.CASCADE, related_name="platos_planificados")
    orden = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['orden', 'id']

    def __str__(self):
        return f"{self.receta.titulo} ({self.opcion})"


class ListaCompras(models.Model):
    """
    Lista de compras del usuario (una sola, activa). Se arma desde la planificación
    semanal o desde un evento; los datos de abajo recuerdan de dónde salió.
    """
    ORIGENES = [
        ('semana', 'Planificación semanal'),
        ('evento', 'Evento'),
    ]

    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lista_compras")
    origen = models.CharField(max_length=10, choices=ORIGENES, blank=True)
    # Si salió de la semana: qué semana (lunes) y cuántas porciones de cada opción se pidieron.
    semana_inicio = models.DateField(null=True, blank=True)
    porciones_por_opcion = models.PositiveIntegerField(null=True, blank=True)
    # Si salió de un evento: cuál.
    evento = models.ForeignKey('Evento', on_delete=models.SET_NULL, null=True, blank=True, related_name="listas_compras")
    actualizada_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Lista de {self.usuario}"


class ItemCompra(models.Model):
    lista = models.ForeignKey(ListaCompras, on_delete=models.CASCADE, related_name="items")
    # Vacío cuando el ítem se agregó a mano (ej: servilletas).
    ingrediente = models.ForeignKey(Ingrediente, on_delete=models.SET_NULL, null=True, blank=True, related_name="items_compra")
    nombre = models.CharField(max_length=150)
    cantidad = models.DecimalField(max_digits=8, decimal_places=2, default=1)
    unidad = models.CharField(max_length=20, blank=True, help_text="Texto libre para los ítems a mano, ej: paquete")
    seccion = models.CharField(max_length=20, choices=SECCIONES, default='otros')
    comprado = models.BooleanField(default=False)
    # Recetas de las que sale la cantidad (texto, se llena al armar la lista).
    origen = models.CharField(max_length=255, blank=True)
    manual = models.BooleanField(default=False, help_text="Agregado a mano: no se toca al regenerar desde las recetas")

    class Meta:
        ordering = ['seccion', 'nombre']

    def __str__(self):
        return f"{self.nombre} ({self.cantidad} {self.unidad})".strip()


class Evento(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="eventos")
    nombre = models.CharField(max_length=150)
    fecha = models.DateField(null=True, blank=True)
    # Personas para las que se diseña el evento. Sirve de referencia: las porciones
    # de las opciones de cada fase deberían rondar esta cantidad.
    invitados = models.PositiveIntegerField(default=10)
    # Porcentaje extra que se suma a las porciones. Es libre: 0 (sin margen), 100 (el doble), etc.
    margen = models.PositiveSmallIntegerField(default=10, help_text="Porcentaje extra sobre las porciones previstas")
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha', '-creado_en']

    def __str__(self):
        return self.nombre


class FaseEvento(models.Model):
    """Una fase del menú del evento (entrada, plato principal, postre...). Las define el usuario."""
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name="fases")
    nombre = models.CharField(max_length=60)
    orden = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['orden', 'id']

    def __str__(self):
        return f"{self.nombre} · {self.evento}"


class OpcionEvento(models.Model):
    """
    Una opción de una fase, por ejemplo "provoleta mediterránea" o "berenjena al escabeche (vegana)".
    Como no se sabe qué elegirá cada invitado, lleva las porciones aproximadas que se prevén.
    """
    fase = models.ForeignKey(FaseEvento, on_delete=models.CASCADE, related_name="opciones")
    orden = models.PositiveIntegerField(default=1)
    nota = models.CharField(max_length=100, blank=True, help_text="Aclaración opcional, ej: vegana")
    porciones = models.PositiveIntegerField(default=1, help_text="Porciones aproximadas que se prevén para esta opción")

    class Meta:
        ordering = ['orden', 'id']

    def __str__(self):
        return f"Opción {self.orden} · {self.fase}"


class PlatoOpcionEvento(models.Model):
    """Una receta que forma parte de una opción del evento (normalmente una, pero pueden ser varias)."""
    opcion = models.ForeignKey(OpcionEvento, on_delete=models.CASCADE, related_name="platos")
    receta = models.ForeignKey(Receta, on_delete=models.CASCADE, related_name="platos_evento")
    orden = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['orden', 'id']

    def __str__(self):
        return f"{self.receta.titulo} ({self.opcion})"

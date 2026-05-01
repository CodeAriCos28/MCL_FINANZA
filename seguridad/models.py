from django.db import models

# Create your models here.
# seguridad/models.py
from django.db import models
from django.contrib.auth.models import User, Permission


class Modulo(models.Model):
    CHOICES_URLS = [
        ('dashboard', 'Dashboard Financiero'),
        ('convertidor', 'Conversor de Divisas'),
        ('gastos', 'Gestión de Gastos'),
        ('servicios', 'Pago de Servicios'),
        ('roles-index', 'Seguridad y Roles'),
    ]

    CHOICES_ICONOS = [
        ('fas fa-chart-line', 'Línea de Gráfico (Dashboard)'),
        ('fas fa-exchange-alt', 'Flechas de Cambio (Conversiones)'),
        ('fas fa-wallet', 'Billetera (Gastos)'),
        ('fas fa-file-invoice-dollar', 'Factura (Servicios)'),
        ('fas fa-shield-halved', 'Escudo (Seguridad)'),
        ('fas fa-home', 'Casa (Inicio)'),
        ('bx bxs-dashboard', 'Box Dashboard'),
        ('bx bxs-user-badge', 'Box Usuario'),
        ('bx bxs-lock-alt', 'Box Candado'),
        ('bx bxs-file-find', 'Box Auditoría'),
    ]

    nombre = models.CharField(max_length=100, unique=True)
    slug   = models.SlugField(max_length=100, unique=True)
    icono  = models.CharField(
        max_length=60, 
        choices=CHOICES_ICONOS, 
        default='fas fa-folder',
        help_text="Seleccione el icono visual del módulo"
    )
    url_name = models.CharField(
        max_length=100, 
        choices=CHOICES_URLS,
        blank=True, 
        null=True, 
        help_text="Seleccione la vista a la que apunta este módulo"
    )
    orden  = models.PositiveIntegerField(default=0)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering    = ['orden']
        verbose_name        = "Módulo"
        verbose_name_plural = "Módulos"

    def __str__(self):
        return self.nombre


class PermisoModulo(models.Model):
    """Une cada permiso de Django con su módulo visual."""
    permiso        = models.ForeignKey(
        Permission, on_delete=models.CASCADE, related_name='modulo_info'
    )
    modulo         = models.ForeignKey(
        Modulo, on_delete=models.PROTECT, related_name='permisos'
    )
    nombre_legible = models.CharField(
        max_length=100,
        help_text="Texto visible al usuario: 'Aplicar descuento'"
    )

    class Meta:
        verbose_name        = "Permiso de módulo"
        verbose_name_plural = "Permisos de módulos"

    def __str__(self):
        return f"{self.modulo.nombre} → {self.nombre_legible}"


class UserPermissionOverride(models.Model):
    """
    Excepción individual permanente por usuario.
    tiene_acceso = True  → concede aunque el rol no lo tenga
    tiene_acceso = False → bloquea aunque el rol sí lo tenga
    """
    usuario      = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='overrides'
    )
    permiso      = models.ForeignKey(Permission, on_delete=models.CASCADE)
    tiene_acceso = models.BooleanField(
        default=True,
        help_text="True = concede extra | False = bloquea del rol"
    )
    motivo     = models.CharField(max_length=255, blank=True)
    creado_en  = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='overrides_creados'
    )

    class Meta:
        unique_together     = ('usuario', 'permiso')
        verbose_name        = "Override de permiso"
        verbose_name_plural = "Overrides de permisos"

    def __str__(self):
        accion = "CONCEDE" if self.tiene_acceso else "BLOQUEA"
        return f"[{accion}] {self.usuario.username} → {self.permiso.codename}"
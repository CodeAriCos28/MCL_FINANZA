# finanzas/models.py - VERSIÓN COMPLETAMENTE CORREGIDA
from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.utils import timezone
from decimal import Decimal
import pytz

# =============================================================================
# CHOICES DEFINITIONS
# =============================================================================

CATEGORIAS_GASTOS = [
    ("ALIMENTACION", "Alimentación"),
    ("TRANSPORTE", "Transporte"),
    ("COMPRAS", "Compras"),
    ("SALUD", "Salud"),
    ("PERSONAL", "Gastos Personales"),
    ("OTROS", "Otros"),
]

SERVICIOS_TIPOS = [
    ("LUZ", "Electricidad"),
    ("AGUA", "Agua"),
    ("INTERNET", "Internet"),
    ("TELEFONO", "Teléfono"),
    ("ALQUILER", "Alquiler"),
    ("OTRO", "Otro Servicio"),
]

ESTADO_CHOICES = [
    ('ACTIVO', 'Activo'),
    ('EDITADO', 'Editado'),
    ('ELIMINADO', 'Eliminado'),
    ('PENDIENTE', 'Pendiente'),
    ('APROBADO', 'Aprobado'),
    ('RECHAZADO', 'Rechazado'),
]

TIPO_COMPROBANTE_CHOICES = [
    ('SIN_COMPROBANTE', 'Sin Comprobante'),
    ('FACTURA', 'Factura'),
    ('RECIBO', 'Recibo'),
    ('TICKET', 'Ticket'),
    ('TRANSFERENCIA', 'Transferencia'),
    ('RAFAEL', 'Rafael'),
]

# =============================================================================
# MÓDULO CONVERTIDOR (Modelo Principal) - CORREGIDO
# =============================================================================


class MovimientoEntrada(models.Model):
    monto_usd = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name="Monto en USD")
    tasa_cambio = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name="Tasa de Cambio")
    monto_pesos = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name="Monto en DOP", editable=False)
    descripcion = models.CharField(
        max_length=200, blank=True, null=True, verbose_name="Descripción")
    fecha = models.DateTimeField(
        verbose_name="Fecha de Conversión")  # NO usar auto_now_add
    imagen = models.ImageField(
        upload_to='convertidor/', null=True, blank=True, verbose_name="Imagen de Factura")

    class Meta:
        verbose_name = "Movimiento de Entrada"
        verbose_name_plural = "Movimientos de Entrada"
        ordering = ['-fecha']

    def save(self, *args, **kwargs):
        if self.monto_usd and self.tasa_cambio:
            self.monto_pesos = self.monto_usd * self.tasa_cambio
        # Si no hay fecha especificada, usar fecha actual en UTC
        if not self.fecha:
            self.fecha = timezone.now()  # timezone.now() ya retorna UTC si USE_TZ=True
        # No convertir a zona local al guardar
        super().save(*args, **kwargs)

    def __str__(self):
        # Convertir fecha a zona horaria de RD para mostrar
        fecha_rd = self.obtener_fecha_rd()
        return f"${self.monto_usd} USD → ${self.monto_pesos} DOP - {fecha_rd.strftime('%d/%m/%Y')}"

    def obtener_fecha_rd(self):
        """Obtener fecha en zona horaria de República Dominicana"""
        tz_rd = pytz.timezone('America/Santo_Domingo')
        if timezone.is_aware(self.fecha):
            return self.fecha.astimezone(tz_rd)
        else:
            # Si la fecha no es consciente de zona horaria, asumir UTC
            tz_utc = pytz.UTC
            fecha_utc = tz_utc.localize(self.fecha)
            return fecha_utc.astimezone(tz_rd)

    TIMEZONE_RD = pytz.timezone('America/Santo_Domingo')

    @property
    def fecha_rd(self):
        """Retorna la fecha en zona horaria de RD"""
        if self.fecha:
            if timezone.is_naive(self.fecha):
                fecha_aware = timezone.make_aware(self.fecha, timezone.utc)
            else:
                fecha_aware = self.fecha
            return fecha_aware.astimezone(self.TIMEZONE_RD)
        return None

    @property
    def fecha_display(self):
        """Formato dd/mm/yyyy en RD"""
        fecha_rd = self.fecha_rd
        return fecha_rd.strftime('%d/%m/%Y') if fecha_rd else ''

    @property
    def fecha_display(self):
        """Formatear fecha para mostrar (solo fecha, sin hora) en RD"""
        fecha_rd = self.obtener_fecha_rd()
        return fecha_rd.strftime('%d/%m/%Y')

    @property
    def fecha_formato_input(self):
        """Formatear fecha para input type="date" (YYYY-MM-DD)"""
        fecha_rd = self.obtener_fecha_rd()
        return fecha_rd.strftime('%Y-%m-%d')

    @property
    def fecha_completa_rd(self):
        """Fecha completa en zona horaria RD"""
        fecha_rd = self.obtener_fecha_rd()
        return fecha_rd.strftime('%d/%m/%Y %H:%M:%S')

    @property
    def descripcion_corta(self):
        """Obtener descripción corta (primeros 10 caracteres)"""
        if self.descripcion:
            return self.descripcion[:10] + '...' if len(self.descripcion) > 10 else self.descripcion
        return ''

    @property
    def mostrar_ver_mas(self):
        """Determinar si se debe mostrar el botón 'Ver más'"""
        return bool(self.descripcion and len(self.descripcion) > 10)

    @property
    def fecha_formateada(self):
        """Retorna la fecha formateada"""
        return self.fecha.strftime('%d/%m/%Y')

    @property
    def saldo_disponible(self):
        """Calcula el saldo disponible restando los gastos activos"""
        try:
            from .models import Gasto, ServicioPago
            total_gastos = Gasto.objects.filter(
                entrada=self
            ).aggregate(total=Sum('monto'))['total'] or Decimal('0.00')

            total_servicios = ServicioPago.objects.filter(
                entrada=self
            ).aggregate(total=Sum('monto'))['total'] or Decimal('0.00')

            return self.monto_pesos - total_gastos - total_servicios
        except Exception:
            return self.monto_pesos

# =============================================================================
# MÓDULO GASTOS - VERSIÓN COMPLETA CORREGIDA
# =============================================================================


class Gasto(models.Model):
    # Campos básicos
    categoria = models.CharField(
        max_length=20, choices=CATEGORIAS_GASTOS, verbose_name="Categoría")
    monto = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name="Monto del Gasto")
    descripcion = models.CharField(
        max_length=200, blank=True, null=True, verbose_name="Descripción del Gasto")
    fecha = models.DateTimeField(verbose_name="Fecha del Gasto")

    # Relación con entrada
    entrada = models.ForeignKey(
        MovimientoEntrada,
        on_delete=models.CASCADE,
        verbose_name="Movimiento Asociado",
        null=True,
        blank=True
    )

    # Campos de estado y auditoría
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='ACTIVO',
        verbose_name="Estado del Gasto"
    )

    # Campos de comprobante
    tipo_comprobante = models.CharField(
        max_length=20,
        choices=TIPO_COMPROBANTE_CHOICES,
        default='SIN_COMPROBANTE',
        verbose_name="Tipo de Comprobante"
    )

    numero_comprobante = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Número de Comprobante"
    )

    proveedor = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="Proveedor"
    )

    # Campos adicionales
    notas = models.TextField(blank=True, null=True,
                             verbose_name="Notas Adicionales")
    imagen = models.ImageField(
        upload_to='gastos/',
        null=True,
        blank=True,
        verbose_name="Imagen de Comprobante"
    )

    # Campos de auditoría
    fecha_creacion = models.DateTimeField(
        auto_now_add=True, verbose_name="Fecha de Creación")
    fecha_actualizacion = models.DateTimeField(
        auto_now=True, verbose_name="Fecha de Actualización")

    class Meta:
        verbose_name = "Gasto"
        verbose_name_plural = "Gastos"
        ordering = ['-fecha']

    def clean(self):
        """Validación personalizada para saldo disponible"""
        if self.entrada and self.monto:
            saldo_disponible = self.entrada.saldo_disponible

            # Si estamos editando un gasto existente, sumamos su monto anterior al saldo disponible
            if self.pk:
                try:
                    gasto_anterior = Gasto.objects.get(pk=self.pk)
                    saldo_disponible += gasto_anterior.monto
                except Gasto.DoesNotExist:
                    pass

            if self.monto > saldo_disponible:
                raise ValidationError(
                    f"Saldo insuficiente. Disponible: ${saldo_disponible:.2f}, "
                    f"Intenta gastar: ${self.monto:.2f}"
                )

    def save(self, *args, **kwargs):
        """Override save para incluir validaciones"""
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_categoria_display()}: ${self.monto} - {self.fecha.strftime('%d/%m/%Y')}"

    @property
    def monto_formateado(self):
        """Retorna el monto formateado como moneda"""
        return f"RD$ {self.monto:,.2f}"

    @property
    def fecha_formateada(self):
        """Retorna la fecha formateada"""
        return self.fecha.strftime('%d/%m/%Y')

# =============================================================================
# MÓDULO SERVICIOS - VERSIÓN COMPLETA CORREGIDA
# =============================================================================


class ServicioPago(models.Model):
    # Campos básicos
    tipo_servicio = models.CharField(
        max_length=20, choices=SERVICIOS_TIPOS, verbose_name="Tipo de Servicio")
    monto = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name="Monto del Pago")
    descripcion = models.CharField(
        max_length=200, blank=True, null=True, verbose_name="Descripción del Pago")
    fecha = models.DateTimeField(verbose_name="Fecha del Pago")

    # Relación con entrada
    entrada = models.ForeignKey(
        MovimientoEntrada,
        on_delete=models.CASCADE,
        verbose_name="Movimiento Asociado",
        null=True,
        blank=True
    )

    # Campos de estado y auditoría
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='ACTIVO',
        verbose_name="Estado del Pago"
    )

    # Campos de comprobante
    tipo_comprobante = models.CharField(
        max_length=20,
        choices=TIPO_COMPROBANTE_CHOICES,
        default='SIN_COMPROBANTE',
        verbose_name="Tipo de Comprobante"
    )

    numero_comprobante = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Número de Comprobante"
    )

    proveedor = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="Proveedor del Servicio"
    )

    # Campos adicionales
    notas = models.TextField(blank=True, null=True,
                             verbose_name="Notas Adicionales")
    imagen = models.ImageField(
        upload_to='servicios/',
        null=True,
        blank=True,
        verbose_name="Imagen de Comprobante"
    )

    # Campos de auditoría
    fecha_creacion = models.DateTimeField(
        auto_now_add=True, verbose_name="Fecha de Creación")
    fecha_actualizacion = models.DateTimeField(
        auto_now=True, verbose_name="Fecha de Actualización")

    class Meta:
        verbose_name = "Pago de Servicio"
        verbose_name_plural = "Pagos de Servicios"
        ordering = ['-fecha']

    def clean(self):
        """Validación personalizada para saldo disponible"""
        if self.entrada and self.monto:
            saldo_disponible = self.entrada.saldo_disponible

            # Si estamos editando un pago existente, sumamos su monto anterior al saldo disponible
            if self.pk:
                try:
                    servicio_anterior = ServicioPago.objects.get(pk=self.pk)
                    saldo_disponible += servicio_anterior.monto
                except ServicioPago.DoesNotExist:
                    pass

            if self.monto > saldo_disponible:
                raise ValidationError(
                    f"Saldo insuficiente. Disponible: ${saldo_disponible:.2f}, "
                    f"Intenta pagar: ${self.monto:.2f}"
                )

    def save(self, *args, **kwargs):
        """Override save para incluir validaciones"""
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_tipo_servicio_display()}: ${self.monto} - {self.fecha.strftime('%d/%m/%Y')}"

    @property
    def monto_formateado(self):
        """Retorna el monto formateado como moneda"""
        return f"RD$ {self.monto:,.2f}"

    @property
    def fecha_formateada(self):
        """Retorna la fecha formateada"""
        return self.fecha.strftime('%d/%m/%Y')

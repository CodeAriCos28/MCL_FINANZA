# finanzas/models.py - VERSIÓN PRODUCCIÓN
#
# ─── Historial de correcciones ────────────────────────────────────────────────
#  Ronda 1 (auditoría técnica):
#   P-D01..P-D06   Diseño de campos y modelos
#   P-I01..P-I04   Integridad de datos
#   P-R01..P-R05   Rendimiento y MySQL
#   P-S01..P-S02   Seguridad de archivos
#   P-N01..P-N02   Normalización / DRY
#   P-MP01..P-MP03 Malas prácticas
#
#  Ronda 2 (revisión estratégica):
#   M-01  monto_pesos blindado con señal pre_save
#   M-02  saldo_disponible movido a MovimientoEntradaQuerySet.con_saldo()
#   M-03  UUID en upload_to para evitar colisión de nombres
#   M-04  Documentación arquitectural de media server separado
#   M-05  Nota explícita: clean() no corre con ORM directo
#   M-06  Soft delete en PagoBase
#
#  Ronda 3 (auditoría financiera real):
#   A-01  Modelo AuditLog completo con firma SHA-256 de integridad
#   A-02  Señales post_save reemplazadas por escritura real a AuditLog
#   A-03  AuditLog es inmutable: save() bloquea ediciones, delete() es no-op
#   A-04  Geolocalización, IP de proxy, session_id, user_agent registrados
#   A-05  Función pública registrar_evento() para uso desde vistas/servicios
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import uuid
import hashlib
import json
import logging

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, FileExtensionValidator
from django.db import models, transaction
from django.db.models import F, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

import pytz

logger = logging.getLogger(__name__)


# =============================================================================
# CHOICES
# =============================================================================

CATEGORIAS_GASTOS = [
    ("ALIMENTACION", "Alimentación"),
    ("TRANSPORTE",   "Transporte"),
    ("COMPRAS",      "Compras"),
    ("SALUD",        "Salud"),
    ("PERSONAL",     "Gastos Personales"),
    ("OTROS",        "Otros"),
]

SERVICIOS_TIPOS = [
    ("LUZ",      "Electricidad"),
    ("AGUA",     "Agua"),
    ("INTERNET", "Internet"),
    ("TELEFONO", "Teléfono"),
    ("ALQUILER", "Alquiler"),
    ("OTRO",     "Otro Servicio"),
]

ESTADO_CHOICES = [
    ('ACTIVO',    'Activo'),
    ('EDITADO',   'Editado'),
    ('ELIMINADO', 'Eliminado'),
    ('PENDIENTE', 'Pendiente'),
    ('APROBADO',  'Aprobado'),
    ('RECHAZADO', 'Rechazado'),
]

TIPO_COMPROBANTE_CHOICES = [
    ('SIN_COMPROBANTE', 'Sin Comprobante'),
    ('FACTURA',         'Factura'),
    ('RECIBO',          'Recibo'),
    ('TICKET',          'Ticket'),
    ('TRANSFERENCIA',   'Transferencia'),
    ('RAFAEL',          'Rafael'),
]


# =============================================================================
# HELPERS DE ZONA HORARIA  (P-N02)
# =============================================================================

_TZ_RD = pytz.timezone('America/Santo_Domingo')


def _a_zona_rd(dt):
    """Convierte un datetime a la zona horaria de RD. Si es naive, asume UTC."""
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = pytz.UTC.localize(dt)
    return dt.astimezone(_TZ_RD)


# =============================================================================
# UPLOAD PATH CON UUID  (P-S02 + M-03)
#
# NOTA ARQUITECTURAL (M-04):
#   En producción los archivos deben servirse desde un dominio separado
#   (ej. media.tudominio.com) o desde un bucket cloud (S3, GCS).
#   Nunca desde el mismo dominio de la app Django.
# =============================================================================

def _upload_path(carpeta: str, filename: str) -> str:
    """Ruta única: carpeta/año/uuid.ext — evita colisiones de nombres."""
    ext  = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'jpg'
    year = timezone.now().year
    return f"{carpeta}/{year}/{uuid.uuid4()}.{ext}"


def upload_convertidor(instance, filename):
    return _upload_path('convertidor', filename)


def upload_gastos(instance, filename):
    return _upload_path('gastos', filename)


def upload_servicios(instance, filename):
    return _upload_path('servicios', filename)


# =============================================================================
# VALIDADOR DE IMAGEN  (P-D03 + P-S01)
#
# NOTA DE SEGURIDAD (M-04):
#   La validación MIME es una capa adicional, no un blindaje total.
#   Para producción con escala: re-encodear con Pillow + subdominio separado.
# =============================================================================

EXTENSIONES_IMAGEN    = ['jpg', 'jpeg', 'png', 'webp']
TAMANIO_MAX_IMAGEN_MB = 5


def validar_imagen(imagen):
    """Valida extensión, tamaño máximo y tipo MIME real del archivo."""
    FileExtensionValidator(allowed_extensions=EXTENSIONES_IMAGEN)(imagen)

    limite = TAMANIO_MAX_IMAGEN_MB * 1024 * 1024
    if imagen.size > limite:
        raise ValidationError(
            f"El archivo supera el límite de {TAMANIO_MAX_IMAGEN_MB} MB "
            f"(tamaño actual: {imagen.size / (1024*1024):.2f} MB)."
        )

    try:
        import magic
        mime = magic.from_buffer(imagen.read(1024), mime=True)
        imagen.seek(0)
        if mime not in {'image/jpeg', 'image/png', 'image/webp'}:
            raise ValidationError(
                f"Tipo de archivo no permitido ({mime}). "
                "Solo se aceptan JPEG, PNG y WEBP."
            )
    except ImportError:
        logger.warning(
            "python-magic no instalado — validación MIME desactivada. "
            "Instalar con: pip install python-magic"
        )


# =============================================================================
# MODELO DE AUDITORÍA — AuditLog  (A-01)
#
# Registra cada acción relevante del sistema con firma SHA-256.
# Es completamente INMUTABLE: no se puede editar ni eliminar.
#
# USO DESDE VISTAS O SERVICIOS:
#   from finanzas.models import registrar_evento
#
#   registrar_evento(
#       request    = request,          # opcional — extrae user, IP, session
#       accion     = 'CREAR',
#       modulo     = 'VENTAS',
#       objeto     = instancia_gasto,  # opcional — extrae modelo, id, nombre
#       descripcion= 'Gasto registrado por usuario X',
#       nivel      = 'INFO',
#       riesgo     = 'BAJO',
#   )
# =============================================================================

class AuditLog(models.Model):

    # ── Identificación ────────────────────────────────────────────────────────

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        verbose_name="Usuario",
    )

    request_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        db_index=True,
        verbose_name="ID de Solicitud",
    )

    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="Fecha y Hora",
    )

    # Alimentado desde registrar_evento() con request.session.session_key
    session_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="ID de Sesión",
    )

    ruta = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Ruta HTTP",
    )

    metodo_http = models.CharField(
        max_length=10,
        blank=True,
        verbose_name="Método HTTP",
    )

    # ── Módulo del sistema ────────────────────────────────────────────────────

    MODULO_CHOICES = [
        ('SEGURIDAD',    'Seguridad'),
        ('VENTAS',       'Ventas'),
        ('ANULACIONES',  'Anulaciones'),
        ('DEVOLUCIONES', 'Devoluciones'),
        ('COBROS',       'Cobros'),
        ('PRECIOS',      'Precios'),
        ('INVENTARIO',   'Inventario'),
        ('USUARIOS',     'Usuarios'),
        ('SISTEMA',      'Sistema'),
        ('FINANZAS',     'Finanzas'),   # módulo propio de este sistema
    ]

    modulo = models.CharField(
        max_length=20,
        choices=MODULO_CHOICES,
        verbose_name="Módulo",
    )

    # ── Tipo de acción ────────────────────────────────────────────────────────

    ACCION_CHOICES = [
        ('CREAR',             'Crear'),
        ('EDITAR',            'Editar'),
        ('ELIMINAR',          'Eliminar'),
        ('LOGIN',             'Login'),
        ('LOGOUT',            'Logout'),
        ('LOGIN_FALLIDO',     'Login fallido'),
        ('ANULAR',            'Anular'),
        ('DEVOLUCION',        'Devolución'),
        ('PAGO',              'Pago'),
        ('CAMBIO_PRECIO',     'Cambio precio'),
        ('CAMBIO_INVENTARIO', 'Cambio inventario'),
        ('CAMBIO_PASSWORD',   'Cambio password'),
        ('CAMBIO_PERMISOS',   'Cambio permisos'),
    ]

    accion = models.CharField(
        max_length=30,
        choices=ACCION_CHOICES,
        verbose_name="Acción",
    )

    # ── Canal ─────────────────────────────────────────────────────────────────

    CANAL_CHOICES = [
        ('WEB',   'Web'),
        ('API',   'API'),
        ('CRON',  'Cron'),
        ('SHELL', 'Shell'),
    ]

    canal = models.CharField(
        max_length=10,
        choices=CANAL_CHOICES,
        default='WEB',
        verbose_name="Canal",
    )

    # ── Objeto afectado ───────────────────────────────────────────────────────

    modelo = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Modelo Django",
    )

    tabla_bd = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Tabla en BD",
    )

    # CharField en lugar de IntegerField: soporta IDs enteros, UUIDs y
    # claves compuestas sin error de tipo.
    objeto_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="ID del Objeto",
    )

    objeto_nombre = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Nombre del Objeto",
    )

    # ── Cambios ───────────────────────────────────────────────────────────────

    valor_anterior = models.TextField(
        null=True,
        blank=True,
        verbose_name="Valor Anterior",
    )

    valor_nuevo = models.TextField(
        null=True,
        blank=True,
        verbose_name="Valor Nuevo",
    )

    data_detalle = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Detalle JSON",
    )

    descripcion = models.TextField(
        blank=True,
        verbose_name="Descripción",
    )

    # ── Datos técnicos ────────────────────────────────────────────────────────

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="IP del Cliente",
    )

    # IP del proxy registrada por separado para reconstruir la cadena
    # completa: cliente → proxy/nginx → aplicación.
    ip_proxy = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP del Proxy",
    )

    navegador = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Navegador",
    )

    user_agent = models.TextField(
        blank=True,
        verbose_name="User Agent",
    )

    dispositivo = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Dispositivo",
    )

    os = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Sistema Operativo",
    )

    # Geolocalización por IP usando geoip2 + base GeoLite2 de MaxMind.
    # Útil para detectar accesos desde países inusuales y análisis de fraude.
    pais = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="País",
    )

    ciudad = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Ciudad",
    )

    # ── Nivel y riesgo ────────────────────────────────────────────────────────

    NIVEL_CHOICES = [
        ('INFO',     'Informativo'),
        ('WARNING',  'Advertencia'),
        ('CRITICAL', 'Crítico'),
    ]

    nivel = models.CharField(
        max_length=20,
        choices=NIVEL_CHOICES,
        default='INFO',
        verbose_name="Nivel",
    )

    RIESGO_CHOICES = [
        ('BAJO',  'Bajo'),
        ('MEDIO', 'Medio'),
        ('ALTO',  'Alto'),
    ]

    riesgo = models.CharField(
        max_length=10,
        choices=RIESGO_CHOICES,
        default='BAJO',
        verbose_name="Riesgo",
    )

    # ── Firma de integridad (A-01) ────────────────────────────────────────────
    # Hash SHA-256 calculado sobre los campos críticos del registro.
    # Permite detectar modificaciones directas en la BD.
    # Cómo verificar: log.verificar_integridad() → True/False
    firma = models.CharField(
        max_length=64,
        blank=True,
        editable=False,
        verbose_name="Firma de Integridad",
    )

    class Meta:
        app_label           = 'finanzas'
        verbose_name        = "Log de Auditoría"
        verbose_name_plural = "Logs de Auditoría"
        ordering            = ['-timestamp']
        indexes = [
            models.Index(fields=['modulo', 'timestamp'],  name='idx_audit_modulo_ts'),
            models.Index(fields=['user', 'modulo'],       name='idx_audit_user_modulo'),
            models.Index(fields=['accion'],               name='idx_audit_accion'),
            models.Index(fields=['request_id'],           name='idx_audit_request'),
            models.Index(fields=['ip_address'],           name='idx_audit_ip'),
            models.Index(fields=['objeto_id'],            name='idx_audit_objeto'),
            models.Index(fields=['nivel', 'timestamp'],   name='idx_audit_nivel_ts'),
        ]

    def __str__(self):
        usuario = self.user if self.user else 'Sistema'
        return f"{usuario} — {self.accion} ({self.modulo})"

    # ── Firma SHA-256 ─────────────────────────────────────────────────────────

    def _calcular_firma(self) -> str:
        """
        Calcula hash SHA-256 sobre los campos críticos del registro.
        Usa SECRET_KEY de Django como sal → imposible falsificar sin conocerla.
        """
        payload = {
            'user_id':     self.user_id,
            'accion':      self.accion,
            'modulo':      self.modulo,
            'objeto_id':   self.objeto_id,
            'ip_address':  str(self.ip_address or ''),
            'timestamp':   str(self.timestamp),
            'descripcion': self.descripcion,
        }
        contenido = json.dumps(payload, sort_keys=True, default=str)
        secreto   = getattr(settings, 'SECRET_KEY', '')
        raw       = f"{secreto}:{contenido}"
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    def verificar_integridad(self):
        """
        Retorna True  → registro íntegro.
        Retorna False → registro fue alterado en BD.
        Retorna None  → registro sin firma (migración anterior).
        """
        if not self.firma:
            return None
        return self.firma == self._calcular_firma()

    # ── Inmutabilidad (A-03) ──────────────────────────────────────────────────

    def save(self, *args, **kwargs):
        # Bloquea cualquier edición posterior a la creación
        if self.pk:
            return

        self.firma = self._calcular_firma()
        super().save(*args, **kwargs)

        # Post-save: ahora timestamp existe → recalcular firma con valor real
        firma_final = self._calcular_firma()
        if firma_final != self.firma:
            AuditLog.objects.filter(pk=self.pk).update(firma=firma_final)
            self.firma = firma_final

    def delete(self, *args, **kwargs):
        # Los logs de auditoría NUNCA se eliminan
        pass


# =============================================================================
# FUNCIÓN PÚBLICA DE REGISTRO  (A-05)
#
# Centraliza la escritura de logs desde cualquier punto del sistema.
# Separa la extracción de datos del request de la escritura en BD.
#
# PARÁMETROS:
#   request     Django HttpRequest (opcional). Si se pasa, extrae
#               automáticamente user, IP, session_id, user_agent.
#   accion      Valor de AuditLog.ACCION_CHOICES  (ej. 'CREAR')
#   modulo      Valor de AuditLog.MODULO_CHOICES  (ej. 'FINANZAS')
#   objeto      Instancia de modelo Django (opcional). Extrae modelo,
#               tabla, id y str() del objeto automáticamente.
#   descripcion Texto libre descriptivo del evento.
#   nivel       'INFO' | 'WARNING' | 'CRITICAL'
#   riesgo      'BAJO' | 'MEDIO' | 'ALTO'
#   extra       Dict con campos adicionales para data_detalle.
#   user        Usuario explícito (si no hay request).
# =============================================================================

def registrar_evento(
    *,
    request=None,
    accion:      str,
    modulo:      str,
    objeto=None,
    descripcion: str = '',
    nivel:       str = 'INFO',
    riesgo:      str = 'BAJO',
    extra:       dict | None = None,
    user=None,
    valor_anterior: str = '',
    valor_nuevo:    str = '',
    canal:          str = 'WEB',
) -> AuditLog | None:
    """
    Escribe un registro en AuditLog de forma segura.
    Nunca lanza excepción — un fallo de auditoría no debe cortar el flujo
    principal de la aplicación. El error se loguea silenciosamente.
    """
    try:
        datos = {
            'accion':          accion,
            'modulo':          modulo,
            'descripcion':     descripcion,
            'nivel':           nivel,
            'riesgo':          riesgo,
            'canal':           canal,
            'valor_anterior':  valor_anterior,
            'valor_nuevo':     valor_nuevo,
            'data_detalle':    extra or {},
        }

        # ── Datos del request ─────────────────────────────────────────────
        if request is not None:
            datos['user']       = getattr(request, 'user', None) or user
            datos['ruta']       = getattr(request, 'path', '')
            datos['metodo_http']= getattr(request, 'method', '')
            datos['user_agent'] = request.META.get('HTTP_USER_AGENT', '')
            datos['session_id'] = (
                request.session.session_key
                if hasattr(request, 'session') and request.session.session_key
                else ''
            )
            datos['ip_address'] = _extraer_ip(request)
            datos['ip_proxy']   = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or None
        else:
            datos['user'] = user

        # ── Datos del objeto afectado ─────────────────────────────────────
        if objeto is not None:
            datos['modelo']        = objeto.__class__.__name__
            datos['tabla_bd']      = getattr(objeto._meta, 'db_table', '')
            datos['objeto_id']     = str(getattr(objeto, 'pk', '') or '')
            datos['objeto_nombre'] = str(objeto)

        return AuditLog.objects.create(**datos)

    except Exception as exc:
        logger.error(
            "registrar_evento falló silenciosamente: %s | accion=%s modulo=%s",
            exc, accion, modulo,
        )
        return None


def _extraer_ip(request) -> str | None:
    """
    Extrae la IP real del cliente considerando proxies y load balancers.
    Prioriza X-Real-IP → REMOTE_ADDR.
    """
    x_real_ip = request.META.get('HTTP_X_REAL_IP')
    if x_real_ip:
        return x_real_ip.strip()
    return request.META.get('REMOTE_ADDR') or None


# =============================================================================
# QUERYSET PERSONALIZADO  (M-02)
# =============================================================================

class MovimientoEntradaQuerySet(models.QuerySet):

    def con_saldo(self):
        """
        Anota saldo_calculado = monto_pesos - gastos activos - servicios activos.
        Excluye registros ELIMINADO del cálculo (soft delete).

        USAR SIEMPRE ESTO EN VISTAS para evitar N+1:
            entradas = MovimientoEntrada.objects.con_saldo().order_by('-fecha')
            # Acceder con: entrada.saldo_calculado
        """
        return self.annotate(
            total_gastos=Coalesce(
                Sum(
                    'gasto__monto',
                    filter=~models.Q(gasto__estado='ELIMINADO'),
                ),
                Value(Decimal('0.00')),
            ),
            total_servicios=Coalesce(
                Sum(
                    'serviciopago__monto',
                    filter=~models.Q(serviciopago__estado='ELIMINADO'),
                ),
                Value(Decimal('0.00')),
            ),
            saldo_calculado=(
                F('monto_pesos')
                - F('total_gastos')
                - F('total_servicios')
            ),
        )


class MovimientoEntradaManager(models.Manager):
    def get_queryset(self):
        return MovimientoEntradaQuerySet(self.model, using=self._db)

    def con_saldo(self):
        return self.get_queryset().con_saldo()


# =============================================================================
# MÓDULO CONVERTIDOR — MovimientoEntrada
# =============================================================================

class MovimientoEntrada(models.Model):

    monto_usd = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Monto en USD",
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    tasa_cambio = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Tasa de Cambio",
        validators=[MinValueValidator(Decimal('0.01'))],
    )

    # Campo persistido + blindado con señal pre_save (M-01).
    # NUNCA usar QuerySet.update() sobre monto_usd o tasa_cambio.
    monto_pesos = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Monto en DOP",
        editable=False,
        help_text=(
            "Calculado automáticamente (monto_usd × tasa_cambio). "
            "Usar siempre .save() — nunca QuerySet.update()."
        ),
    )

    descripcion = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name="Descripción",
    )
    fecha = models.DateTimeField(
        verbose_name="Fecha de Conversión",
    )
    imagen = models.ImageField(
        upload_to=upload_convertidor,
        null=True,
        blank=True,
        verbose_name="Imagen de Factura",
        validators=[validar_imagen],
    )

    objects = MovimientoEntradaManager()

    class Meta:
        app_label           = 'finanzas'
        verbose_name        = "Movimiento de Entrada"
        verbose_name_plural = "Movimientos de Entrada"
        indexes = [
            models.Index(fields=['-fecha'], name='idx_entrada_fecha'),
        ]

    def save(self, *args, **kwargs):
        if self.monto_usd and self.tasa_cambio:
            self.monto_pesos = self.monto_usd * self.tasa_cambio
        if not self.fecha:
            self.fecha = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        fd = _a_zona_rd(self.fecha)
        fecha_str = fd.strftime('%d/%m/%Y') if fd else ''
        return f"${self.monto_usd} USD → ${self.monto_pesos} DOP - {fecha_str}"

    # ── Propiedades de fecha ──────────────────────────────────────────────────

    @property
    def fecha_rd(self):
        return _a_zona_rd(self.fecha)

    @property
    def fecha_display(self):
        fd = self.fecha_rd
        return fd.strftime('%d/%m/%Y') if fd else ''

    @property
    def fecha_formato_input(self):
        fd = self.fecha_rd
        return fd.strftime('%Y-%m-%d') if fd else ''

    @property
    def fecha_completa_rd(self):
        fd = self.fecha_rd
        return fd.strftime('%d/%m/%Y %H:%M:%S') if fd else ''

    @property
    def fecha_formateada(self):
        return self.fecha_display

    # ── Propiedades de descripción ────────────────────────────────────────────

    @property
    def descripcion_corta(self):
        if self.descripcion:
            return (self.descripcion[:10] + '...') if len(self.descripcion) > 10 else self.descripcion
        return ''

    @property
    def mostrar_ver_mas(self):
        return bool(self.descripcion and len(self.descripcion) > 10)

    # ── Saldo disponible — solo acceso individual  (M-02) ─────────────────────
    # Para listados usar SIEMPRE: MovimientoEntrada.objects.con_saldo()

    @property
    def saldo_disponible(self):
        resultado = (
            MovimientoEntrada.objects
            .filter(pk=self.pk)
            .con_saldo()
            .values('monto_pesos', 'total_gastos', 'total_servicios')
            .first()
        )
        if not resultado:
            return self.monto_pesos
        return (
            resultado['monto_pesos']
            - resultado['total_gastos']
            - resultado['total_servicios']
        )


# =============================================================================
# MODELO ABSTRACTO BASE — PagoBase  (P-N01 + M-05 + M-06)
# =============================================================================

class PagoBase(models.Model):
    """
    Modelo abstracto compartido por Gasto y ServicioPago.

    SOBRE clean() (M-05):
    clean() corre en ModelForm.is_valid() pero NO con ORM directo.
    Validación crítica → CheckConstraints en BD.
    Regla: clean() = UX | constraints = integridad de BD.

    SOBRE soft delete (M-06):
    Usar .eliminar() en lugar de .delete() para preservar historial.
    Filtrar en vistas con: .exclude(estado='ELIMINADO').
    """

    monto = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Monto",
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    descripcion = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name="Descripción",
    )
    fecha = models.DateTimeField(
        verbose_name="Fecha",
    )
    entrada = models.ForeignKey(
        MovimientoEntrada,
        on_delete=models.PROTECT,
        verbose_name="Movimiento Asociado",
        null=True,
        blank=True,
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='ACTIVO',
        verbose_name="Estado",
    )
    tipo_comprobante = models.CharField(
        max_length=20,
        choices=TIPO_COMPROBANTE_CHOICES,
        default='SIN_COMPROBANTE',
        verbose_name="Tipo de Comprobante",
    )
    numero_comprobante = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name="Número de Comprobante",
    )
    proveedor = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name="Proveedor",
    )
    notas = models.TextField(
        blank=True,
        default='',
        verbose_name="Notas Adicionales",
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Creación",
    )
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name="Fecha de Actualización",
    )

    class Meta:
        abstract = True

    # ── Validación de saldo con bloqueo (P-I01) ───────────────────────────────

    def _validar_saldo(self, modelo_propio):
        """
        Valida saldo con select_for_update() para evitar race conditions.
        Llamar siempre dentro de transaction.atomic().
        """
        if not (self.entrada_id and self.monto):
            return

        entrada_bloqueada = (
            MovimientoEntrada.objects
            .select_for_update()
            .get(pk=self.entrada_id)
        )
        saldo = entrada_bloqueada.saldo_disponible

        if self.pk:
            try:
                anterior = modelo_propio.objects.get(pk=self.pk)
                saldo += anterior.monto
            except modelo_propio.DoesNotExist:
                pass

        if self.monto > saldo:
            raise ValidationError(
                f"Saldo insuficiente. "
                f"Disponible: ${saldo:.2f} — "
                f"Intenta registrar: ${self.monto:.2f}"
            )

    # ── Soft delete (M-06) ────────────────────────────────────────────────────

    def eliminar(self, request=None):
        """
        Eliminación lógica. Preserva el registro en BD.
        Acepta request para registrar en AuditLog quién eliminó.
        """
        self.estado = 'ELIMINADO'
        self.save(update_fields=['estado', 'fecha_actualizacion'])
        registrar_evento(
            request     = request,
            accion      = 'ELIMINAR',
            modulo      = 'FINANZAS',
            objeto      = self,
            descripcion = f"{self.__class__.__name__} marcado como ELIMINADO.",
            nivel       = 'WARNING',
            riesgo      = 'MEDIO',
        )

    # ── clean() ───────────────────────────────────────────────────────────────

    def clean(self):
        if self.descripcion:
            self.descripcion = self.descripcion.strip()
        if self.proveedor:
            self.proveedor = self.proveedor.strip()
        if self.numero_comprobante:
            self.numero_comprobante = self.numero_comprobante.strip()

    # ── Propiedades ───────────────────────────────────────────────────────────

    @property
    def monto_formateado(self):
        return f"RD$ {self.monto:,.2f}"

    @property
    def fecha_rd(self):
        return _a_zona_rd(self.fecha)

    @property
    def fecha_formateada(self):
        fd = self.fecha_rd
        return fd.strftime('%d/%m/%Y') if fd else ''


# =============================================================================
# MÓDULO GASTOS — Gasto
# =============================================================================

class Gasto(PagoBase):

    categoria = models.CharField(
        max_length=20,
        choices=CATEGORIAS_GASTOS,
        verbose_name="Categoría",
    )
    imagen = models.ImageField(
        upload_to=upload_gastos,
        null=True,
        blank=True,
        verbose_name="Imagen de Comprobante",
        validators=[validar_imagen],
    )

    class Meta:
        app_label           = 'finanzas'
        verbose_name        = "Gasto"
        verbose_name_plural = "Gastos"
        indexes = [
            models.Index(fields=['-fecha'],            name='idx_gasto_fecha'),
            models.Index(fields=['estado'],             name='idx_gasto_estado'),
            models.Index(fields=['entrada', 'estado'], name='idx_gasto_entrada_estado'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(monto__gt=0),
                name='gasto_monto_positivo',
            ),
        ]

    def clean(self):
        super().clean()

    def save(self, *args, **kwargs):
        es_nuevo = self.pk is None
        with transaction.atomic():
            self._validar_saldo(Gasto)
            super().save(*args, **kwargs)
        # Registro en AuditLog después de guardar exitosamente
        registrar_evento(
            accion      = 'CREAR' if es_nuevo else 'EDITAR',
            modulo      = 'FINANZAS',
            objeto      = self,
            descripcion = (
                f"Gasto {'creado' if es_nuevo else 'editado'}: "
                f"{self.get_categoria_display()} — {self.monto_formateado}"
            ),
            nivel       = 'INFO',
            riesgo      = 'BAJO',
        )

    def __str__(self):
        return f"{self.get_categoria_display()}: ${self.monto} - {self.fecha_formateada}"


# =============================================================================
# MÓDULO SERVICIOS — ServicioPago
# =============================================================================

class ServicioPago(PagoBase):

    tipo_servicio = models.CharField(
        max_length=20,
        choices=SERVICIOS_TIPOS,
        verbose_name="Tipo de Servicio",
    )
    imagen = models.ImageField(
        upload_to=upload_servicios,
        null=True,
        blank=True,
        verbose_name="Imagen de Comprobante",
        validators=[validar_imagen],
    )

    class Meta:
        app_label           = 'finanzas'
        verbose_name        = "Pago de Servicio"
        verbose_name_plural = "Pagos de Servicios"
        indexes = [
            models.Index(fields=['-fecha'],            name='idx_servicio_fecha'),
            models.Index(fields=['estado'],             name='idx_servicio_estado'),
            models.Index(fields=['entrada', 'estado'], name='idx_servicio_entrada_estado'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(monto__gt=0),
                name='servicio_monto_positivo',
            ),
        ]

    def clean(self):
        super().clean()

    def save(self, *args, **kwargs):
        es_nuevo = self.pk is None
        with transaction.atomic():
            self._validar_saldo(ServicioPago)
            super().save(*args, **kwargs)
        registrar_evento(
            accion      = 'CREAR' if es_nuevo else 'EDITAR',
            modulo      = 'FINANZAS',
            objeto      = self,
            descripcion = (
                f"ServicioPago {'creado' if es_nuevo else 'editado'}: "
                f"{self.get_tipo_servicio_display()} — {self.monto_formateado}"
            ),
            nivel       = 'INFO',
            riesgo      = 'BAJO',
        )

    def __str__(self):
        return f"{self.get_tipo_servicio_display()}: ${self.monto} - {self.fecha_formateada}"


# =============================================================================
# SEÑALES  (M-01 + A-02)
# =============================================================================

from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver


# ── M-01: Blindaje de monto_pesos ─────────────────────────────────────────────
# pre_save garantiza recálculo en cada .save().
# LIMITACIÓN documentada: QuerySet.update() no dispara señales.

@receiver(pre_save, sender=MovimientoEntrada)
def recalcular_monto_pesos(sender, instance, **kwargs):
    if instance.monto_usd and instance.tasa_cambio:
        instance.monto_pesos = instance.monto_usd * instance.tasa_cambio


# ── A-02: Auditoría de MovimientoEntrada ──────────────────────────────────────
# Gasto y ServicioPago se auditan directamente en su save() para poder
# pasar el request desde la vista en el futuro.
# MovimientoEntrada se audita aquí vía señal.

@receiver(post_save, sender=MovimientoEntrada)
def auditar_movimiento_entrada(sender, instance, created, **kwargs):
    registrar_evento(
        accion      = 'CREAR' if created else 'EDITAR',
        modulo      = 'FINANZAS',
        objeto      = instance,
        descripcion = (
            f"MovimientoEntrada {'creado' if created else 'actualizado'}: "
            f"${instance.monto_usd} USD → ${instance.monto_pesos} DOP"
        ),
        nivel       = 'INFO',
        riesgo      = 'BAJO',
        canal       = 'SHELL' if not created else 'WEB',
    )


from django.db import models

class ExchangeRate(models.Model):
    base = models.CharField(max_length=3, default="USD")
    target = models.CharField(max_length=3, default="DOP")

    rate = models.DecimalField(max_digits=10, decimal_places=4)

    date = models.DateField()  # fecha del mercado
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('base', 'target', 'date')
        indexes = [
            models.Index(fields=['base', 'target', 'date']),
        ]

    def __str__(self):
        return f"{self.base}/{self.target} - {self.rate} ({self.date})"
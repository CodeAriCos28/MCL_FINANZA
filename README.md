# 📚 DOCUMENTACIÓN COMPLETA - MCL_FINANZA

## 📋 Información General del Proyecto

**Nombre del Proyecto:** MCL_FINANZA  
**Versión:** 2026.1.0.2  
**Tipo:** Aplicación Web de Gestión Financiera  
**Framework:** Django 4.2.20  
**Python:** 3.x  
**Base de Datos:** MySQL / PostgreSQL  
**Autor:** CodeAriCos28  
**Repositorio:** [GitHub](https://github.com/CodeAriCos28/MCL_FINANZA)  
**Demo:** [PythonAnywhere](https://codearicos.pythonanywhere.com/)

---

## 🎯 Descripción del Proyecto

MCL_FINANZA es una aplicación web completa de gestión financiera personal desarrollada en Django que permite a los usuarios dominicanos gestionar sus finanzas de manera eficiente. El sistema ofrece cuatro módulos principales interconectados que trabajan juntos para proporcionar una visión completa del estado financiero personal.

### 🎯 Objetivos Principales

1. **Gestión Integral de Finanzas Personales**: Centralizar todos los aspectos financieros en una sola plataforma
2. **Conversión de Moneda en Tiempo Real**: Convertir USD a DOP con tasas actualizadas
3. **Control de Gastos Detallado**: Categorizar y rastrear todos los gastos personales
4. **Administración de Servicios**: Gestionar pagos recurrentes y suscripciones
5. **Análisis y Reportes**: Visualizar datos financieros mediante dashboards y reportes PDF

---

## 🏗️ Arquitectura del Sistema

### Arquitectura General

```
┌─────────────────────────────────────────────────────────────┐
│                    CAPA DE PRESENTACIÓN                      │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                 INTERFAZ WEB (HTML/CSS/JS)              │ │
│  │  • Templates Django (.html)                            │ │
│  │  • CSS personalizado                                   │ │
│  │  • JavaScript (Chart.js, AJAX)                         │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                                 │
┌─────────────────────────────────────────────────────────────┐
│                   CAPA DE APLICACIÓN                        │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                 VISTAS DJANGO                           │ │
│  │  • Funciones de vista (views.py)                        │ │
│  │  • APIs REST (JSON)                                     │ │
│  │  • Generación de PDFs                                   │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                 MODELOS DJANGO                          │ │
│  │  • MovimientoEntrada                                    │ │
│  │  • Gasto                                               │ │
│  │  • ServicioPago                                        │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                                 │
┌─────────────────────────────────────────────────────────────┐
│                    CAPA DE DATOS                            │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                 BASE DE DATOS                           │ │
│  │  • MySQL / PostgreSQL                                  │ │
│  │  • Migraciones Django                                   │ │
│  │  • Archivos multimedia (imágenes)                       │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Arquitectura por Módulos

```
MCL_FINANZA/
├── 🔐 AUTENTICACIÓN
│   ├── Login/Logout
│   ├── Sesiones persistentes
│   └── Control de acceso
│
├── 💱 CONVERTIDOR
│   ├── Registro de conversiones USD→DOP
│   ├── Historial completo
│   ├── Reportes PDF
│   └── APIs REST
│
├── 💰 GASTOS
│   ├── CRUD completo de gastos
│   ├── Categorización automática
│   ├── Control de saldo disponible
│   ├── Reportes por período
│   └── APIs REST
│
├── 🏢 SERVICIOS
│   ├── Gestión de pagos recurrentes
│   ├── Control de proveedores
│   ├── Alertas de vencimiento
│   └── Reportes detallados
│
└── 📊 DASHBOARD
    ├── Visualización de datos
    ├── Gráficos interactivos
    ├── Estadísticas en tiempo real
    └── Reportes consolidados
```

---

## 🛠️ Tecnologías y Dependencias

### Tecnologías Core

| Tecnología | Versión | Propósito |
|------------|---------|-----------|
| **Python** | 3.x | Lenguaje de programación principal |
| **Django** | 4.2.20 | Framework web principal |
| **MySQL** | 8.x | Base de datos principal |
| **PostgreSQL** | 13+ | Base de datos alternativa |
| **HTML5** | - | Estructura de páginas web |
| **CSS3** | - | Estilos y diseño responsive |
| **JavaScript** | ES6+ | Interactividad del frontend |

### Dependencias Python (requirements.txt)

```txt
asgiref==3.11.0              # ASGI para Django
charset-normalizer==3.4.4    # Normalización de caracteres
Django==4.2.20               # Framework web
greenlet==3.2.4              # Concurrencia para SQLAlchemy
gunicorn==23.0.0             # Servidor WSGI para producción
mysqlclient==2.2.7           # Conector MySQL para Django
packaging==25.0              # Utilidades de empaquetado
pillow==12.0.0               # Procesamiento de imágenes
psycopg==3.3.2               # Conector PostgreSQL
psycopg-binary==3.3.2        # Binarios PostgreSQL
python-dotenv==1.2.1         # Variables de entorno
pytz==2025.2                 # Zonas horarias
reportlab==4.4.5             # Generación de PDFs
SQLAlchemy==2.0.44           # ORM alternativo
sqlparse==0.5.3              # Parser SQL para Django
typing_extensions==4.15.0    # Extensiones de tipado
tzdata==2025.2               # Datos de zonas horarias
whitenoise==6.11.0           # Servidor de archivos estáticos
```

### Tecnologías Frontend

| Tecnología | Versión | Propósito |
|------------|---------|-----------|
| **Chart.js** | CDN | Gráficos interactivos |
| **Font Awesome** | 6.4.0 | Iconos vectoriales |
| **Boxicons** | 2.1.4 | Iconos adicionales |
| **Session Timeout JS** | Custom | Control de sesiones |

---

## 📁 Estructura Completa del Proyecto

```
MLAN FINACE3/
├── 📄 README.md                           # Documentación básica
├── 📄 requirements.txt                     # Dependencias Python
├── 📄 financiera.sql                      # Script SQL de base de datos
├── 📄 manage.py                           # Comando Django
├── 📄 conapp.sh                           # Script de despliegue
├── 📄 versel.json                         # Configuración Vercel
│
├── 🗂️ core/                               # Configuración principal
│   ├── __init__.py
│   ├── asgi.py                           # Configuración ASGI
│   ├── settings/                         # Configuraciones Django
│   │   ├── __init__.py
│   │   ├── base.py                       # Configuración base
│   │   ├── dev.py                        # Configuración desarrollo
│   │   └── prod.py                       # Configuración producción
│   ├── urls.py                           # URLs principales
│   └── wsgi.py                           # Configuración WSGI
│
├── 🗂️ finanzas/                           # Aplicación principal
│   ├── __init__.py
│   ├── admin.py                          # Configuración admin Django
│   ├── apps.py                           # Configuración de la app
│   ├── models.py                         # Modelos de datos
│   ├── urls.py                           # URLs de la aplicación
│   ├── views.py                          # Lógica de negocio (6381 líneas)
│   ├── tests.py                          # Tests unitarios
│   └── migrations/                       # Migraciones de BD
│       ├── __init__.py
│       └── 0001_initial.py to 0007_*.py
│
├── 🗂️ templates/                          # Plantillas HTML
│   └── finanzas/
│       ├── index.html                    # Página de login
│       ├── convertidor.html              # Módulo convertidor
│       ├── convertidor_print.html        # Versión imprimible
│       ├── gastos.html                   # Módulo gastos
│       ├── gastos_print.html             # Versión imprimible gastos
│       ├── servicios.html                # Módulo servicios
│       ├── servicios_print.html          # Versión imprimible servicios
│       ├── dashboard.html                # Dashboard principal
│       └── dashboard_print.html          # Versión imprimible dashboard
│
├── 🗂️ static/                             # Archivos estáticos
│   ├── img/                              # Imágenes y logos
│   │   └── logo.ico
│   ├── js/                               # JavaScript
│   │   └── session_timeout.js
│   └── css/                              # Hojas de estilo (implícito)
│
├── 🗂️ media/                             # Archivos subidos por usuarios
│   ├── convertidor/                      # Imágenes de conversiones
│   ├── gastos/                           # Comprobantes de gastos
│   └── servicios/                        # Comprobantes de servicios
│
└── 🗂️ __pycache__/                       # Cache Python (ignorado)
```

---

## 🗄️ Modelos de Datos

### 1. MovimientoEntrada (Convertidor)

```python
class MovimientoEntrada(models.Model):
    # Campos básicos de conversión
    monto_usd = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        verbose_name="Monto en USD"
    )
    tasa_cambio = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        verbose_name="Tasa de Cambio"
    )
    monto_pesos = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        verbose_name="Monto en DOP", 
        editable=False
    )
    
    # Información adicional
    descripcion = models.CharField(
        max_length=200, 
        blank=True, 
        null=True, 
        verbose_name="Descripción"
    )
    fecha = models.DateTimeField(
        verbose_name="Fecha de Conversión"
    )
    
    # Archivos adjuntos
    imagen = models.ImageField(
        upload_to='convertidor/', 
        null=True, 
        blank=True, 
        verbose_name="Imagen de Factura"
    )
    
    # Campos de auditoría
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
```

**Campos Calculados:**
- `saldo_disponible`: Calcula el saldo restante después de gastos y servicios
- `fecha_display`: Fecha formateada para display (DD/MM/YYYY)
- `fecha_formato_input`: Fecha para inputs HTML (YYYY-MM-DD)
- `descripcion_corta`: Descripción truncada para vistas

**Métodos Importantes:**
- `save()`: Calcula automáticamente monto_pesos y maneja zona horaria
- `obtener_fecha_rd()`: Convierte fecha a zona horaria dominicana
- `clean()`: Validaciones personalizadas

### 2. Gasto

```python
class Gasto(models.Model):
    # Campos básicos
    categoria = models.CharField(
        max_length=20, 
        choices=CATEGORIAS_GASTOS, 
        verbose_name="Categoría"
    )
    monto = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        verbose_name="Monto del Gasto"
    )
    descripcion = models.CharField(
        max_length=200, 
        blank=True, 
        null=True, 
        verbose_name="Descripción del Gasto"
    )
    fecha = models.DateTimeField(verbose_name="Fecha del Gasto")
    
    # Relación con entrada financiera
    entrada = models.ForeignKey(
        MovimientoEntrada, 
        on_delete=models.CASCADE,
        verbose_name="Movimiento Asociado",
        null=True,
        blank=True
    )
    
    # Estado del gasto
    estado = models.CharField(
        max_length=20, 
        choices=ESTADO_CHOICES, 
        default='ACTIVO',
        verbose_name="Estado del Gasto"
    )
    
    # Información de comprobante
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
    notas = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Notas Adicionales"
    )
    imagen = models.ImageField(
        upload_to='gastos/', 
        null=True, 
        blank=True, 
        verbose_name="Imagen de Comprobante"
    )
    
    # Auditoría
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
```

**Categorías Disponibles:**
```python
CATEGORIAS_GASTOS = [
    ("ALIMENTACION", "Alimentación"),
    ("TRANSPORTE", "Transporte"),
    ("COMPRAS", "Compras"),
    ("SALUD", "Salud"),
    ("PERSONAL", "Gastos Personales"),
    ("OTROS", "Otros"),
]
```

**Estados del Gasto:**
```python
ESTADO_CHOICES = [
    ('ACTIVO', 'Activo'),
    ('EDITADO', 'Editado'), 
    ('ELIMINADO', 'Eliminado'),
    ('PENDIENTE', 'Pendiente'),
    ('APROBADO', 'Aprobado'),
    ('RECHAZADO', 'Rechazado'),
]
```

### 3. ServicioPago

```python
class ServicioPago(models.Model):
    # Campos básicos
    tipo_servicio = models.CharField(
        max_length=20, 
        choices=SERVICIOS_TIPOS, 
        verbose_name="Tipo de Servicio"
    )
    monto = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        verbose_name="Monto del Pago"
    )
    descripcion = models.CharField(
        max_length=200, 
        blank=True, 
        null=True, 
        verbose_name="Descripción del Pago"
    )
    fecha = models.DateTimeField(verbose_name="Fecha del Pago")
    
    # Relación con entrada financiera
    entrada = models.ForeignKey(
        MovimientoEntrada,
        on_delete=models.CASCADE,  
        verbose_name="Movimiento Asociado",
        null=True,
        blank=True
    )
    
    # Estado del pago
    estado = models.CharField(
        max_length=20, 
        choices=ESTADO_CHOICES, 
        default='ACTIVO',
        verbose_name="Estado del Pago"
    )
    
    # Información de comprobante
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
    notas = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Notas Adicionales"
    )
    imagen = models.ImageField(
        upload_to='servicios/', 
        null=True, 
        blank=True, 
        verbose_name="Imagen de Comprobante"
    )
    
    # Auditoría
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
```

**Tipos de Servicio Disponibles:**
```python
SERVICIOS_TIPOS = [
    ("LUZ", "Electricidad"),
    ("AGUA", "Agua"),
    ("INTERNET", "Internet"),
    ("TELEFONO", "Teléfono"),
    ("ALQUILER", "Alquiler"),
    ("OTRO", "Otro Servicio"),
]
```

---

## 🔗 URLs y Endpoints

### URLs Principales (core/urls.py)

```python
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('finanzas.urls')),
]

# Servir archivos multimedia en desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
```

### URLs de la Aplicación (finanzas/urls.py)

```python
urlpatterns = [
    # Autenticación
    path('', views.login, name='index'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # ==================================================
    # MÓDULO CONVERTIDOR - URLs
    # ==================================================
    path('convertidor/', views.convertidor_index, name='convertidor'),
    path('convertidor/registrar/', views.convertidor_registrar, name='convertidor_registrar'),
    path('convertidor/historial/', views.convertidor_historial, name='convertidor_historial'),
    path('convertidor/editar/<int:id>/', views.convertidor_editar, name='convertidor_editar'),
    path('convertidor/eliminar/<int:id>/', views.convertidor_eliminar, name='convertidor_eliminar'),
    path('convertidor/reporte-pdf/', views.convertidor_reporte_pdf, name='convertidor_reporte_pdf'),
    path('convertidor/reporte-detalle-pdf/<int:id>/', views.convertidor_reporte_detalle_pdf, name='convertidor_reporte_detalle_pdf'),
    path('api/convertidor/movimientos/', views.api_movimientos, name='api_movimientos'),
    path('api/convertidor/estadisticas/', views.api_estadisticas, name='api_estadisticas'),
    path('convertidor/imprimir-todo/', views.convertidor_imprimir_todo, name='convertidor_imprimir_todo'),
    
    # ==================================================
    # MÓDULO GASTOS - URLs
    # ==================================================
    path('gastos/', views.gastos_index, name='gastos'),
    path('gastos/crear/', views.gastos_crear, name='gastos_crear'),
    path('gastos/editar/<int:pk>/', views.gastos_editar, name='gastos_editar'),
    path('gastos/eliminar/<int:pk>/', views.gastos_eliminar, name='gastos_eliminar'),
    path('gastos/pdf/<int:pk>/', views.gastos_pdf, name='gastos_pdf'),
    path('gastos/pdf-historial/', views.gastos_pdf_historial, name='gastos_pdf_historial'),
    path('gastos/imprimir-historial/', views.gastos_imprimir_historial, name='gastos_imprimir_historial'),
    path('api/gastos/', views.api_gastos, name='api_gastos'),
    path('api/categorias/', views.api_categorias, name='api_categorias'),
    path('api/dashboard/', views.api_dashboard, name='api_dashboard'),
    path('api/gastos/<int:pk>/', views.gastos_editar, name='api_gastos_detail'),
    path('api/gastos/<int:pk>/delete/', views.gastos_eliminar, name='api_gastos_delete'),
    
    # ==================================================
    # MÓDULO SERVICIOS - URLs
    # ==================================================
    path('servicios/', views.servicios_index, name='servicios'),
    path('servicios/crear/', views.servicios_crear, name='servicios_crear'),
    path('servicios/editar/<int:pk>/', views.servicios_editar, name='servicios_editar'),
    path('servicios/eliminar/<int:pk>/', views.servicios_eliminar, name='servicios_eliminar'),
    path('servicios/pdf/<int:pk>/', views.servicios_pdf, name='servicios_pdf'),
    path('servicios/pdf-historial/', views.servicios_pdf_historial, name='servicios_pdf_historial'),
    path('servicios/imprimir-historial/', views.servicios_imprimir_historial, name='servicios_imprimir_historial'),
    path('servicios/tipos-servicio/', views.servicios_tipos, name='servicios_tipos'),
    path('servicios/proveedores/', views.servicios_proveedores, name='servicios_proveedores'),
    path('servicios/metodos-pago/', views.servicios_metodos_pago, name='servicios_metodos_pago'),
    
    # ==================================================
    # DASHBOARD - URLs
    # ==================================================
    path('dashboard/', views.dashboard_index, name='dashboard'),
    path('dashboard/api/', views.dashboard_api, name='dashboard_api'),
    path('reporte-movimiento/<str:tipo_movimiento>/<int:id>/', views.dashboard_reporte_detalle_pdf, name='dashboard_reporte_detalle_pdf'),
    path('dashboard/reporte-pdf/', views.dashboard_reporte_pdf, name='dashboard_reporte_pdf'),
    path('dashboard/imprimir/', views.dashboard_imprimir_historial, name='dashboard_imprimir'),
]
```

---

## ⚙️ Configuración del Sistema

### Configuración Base (core/settings/base.py)

#### Configuración de Base de Datos

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_NAME'),
        'USER': os.environ.get('DB_USER'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST'),
        'PORT': os.environ.get('DB_PORT'),
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        }
    }
}
```

#### Configuración de Internacionalización

```python
# Zona horaria
TIME_ZONE = 'UTC'  # Base UTC, conversiones locales en código
USE_TZ = True

# Idioma
LANGUAGE_CODE = 'en-us'
USE_I18N = True
USE_L10N = False

# Formatos de fecha personalizados
DATE_FORMAT = 'd/m/Y'
DATETIME_FORMAT = 'd/m/Y H:i:s'
```

#### Configuración de Archivos

```python
# Archivos estáticos
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Archivos multimedia
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'
```

#### Configuración de Sesiones

```python
# Configuración de sesiones
SESSION_COOKIE_AGE = 3600  # 1 hora
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
LOGIN_URL = 'index'
LOGIN_REDIRECT_URL = '/convertidor/'
LOGOUT_REDIRECT_URL = '/'
```

#### Configuración de Seguridad

```python
# Configuración de seguridad base
SECRET_KEY = os.environ.get('SECRET_KEY')
DEBUG = os.getenv("DEBUG", "False") == "True"

# Hosts permitidos (configurado en dev.py y prod.py)
ALLOWED_HOSTS = []

# CSRF
CSRF_TRUSTED_ORIGINS = []
CSRF_COOKIE_SECURE = False  # True en producción
CSRF_USE_SESSIONS = False
```

### Configuración de Desarrollo (dev.py)

```python
DEBUG = True
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'omega-neighbourless-sublabially.ngrok-free.dev']

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
```

### Configuración de Producción (prod.py)

```python
DEBUG = False
ALLOWED_HOSTS = ['midominio.com', 'www.midominio.com', 'mcl-finanza-1.onrender.com']

CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
```

---

## 🔐 Sistema de Autenticación

### Funcionalidades de Autenticación

1. **Login Seguro**: Autenticación basada en username/password
2. **Sesiones Persistentes**: Control de sesiones con timeout automático
3. **Logout Seguro**: Cierre de sesión con limpieza completa
4. **Protección CSRF**: Protección contra ataques CSRF en formularios
5. **Control de Acceso**: Decoradores `@login_required` en vistas protegidas

### Control de Sesiones (session_timeout.js)

```javascript
let timeout;

function resetTimer() {
    clearTimeout(timeout);
    
    // 600000 milisegundos = 10 minutos
    timeout = setTimeout(() => {
        // Alerta estética con SweetAlert2
        Swal.fire({
            title: '¡Sesión Expirada!',
            text: 'Has estado inactivo por demasiado tiempo.',
            icon: 'warning',
            confirmButtonColor: '#035087',
            confirmButtonText: 'Aceptar',
            allowOutsideClick: false
        }).then((result) => {
            if (result.isConfirmed) {
                window.location.href = "/logout/";
            }
        });

        // Redirección automática de respaldo
        setTimeout(() => {
            window.location.href = "/logout/";
        }, 5000);

    }, 3600000); // 1 hora en milisegundos
}

// Eventos que reinician el timer
window.onload = resetTimer;
window.onmousemove = resetTimer;
window.onmousedown = resetTimer;
window.onkeypress = resetTimer;
window.ontouchstart = resetTimer;
```

### Vistas de Autenticación

#### Login View

```python
@ensure_csrf_cookie
def login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            auth_login(request, user)
            messages.success(request, f'¡Bienvenido {user.username}!')
            return redirect('convertidor')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos')
            return render(request, 'finanzas/index.html')
    
    return render(request, 'finanzas/index.html')
```

#### Logout View

```python
def logout_view(request):
    logout(request)
    request.session.flush()
    messages.success(request, 'Sesión cerrada exitosamente')
    return redirect('index')
```

---

## 💱 Módulo Convertidor (USD → DOP)

### Funcionalidades Principales

1. **Registro de Conversiones**: Crear nuevas conversiones con tasa de cambio
2. **Historial Completo**: Ver todas las conversiones con filtros
3. **Edición de Registros**: Modificar conversiones existentes
4. **Eliminación Segura**: Eliminar solo si no hay gastos/servicios asociados
5. **Reportes PDF**: Generar reportes profesionales
6. **APIs REST**: Endpoints para integración con JavaScript
7. **Control de Imágenes**: Adjuntar comprobantes/facturas

### Vistas Principales

#### convertidor_index

**Propósito**: Página principal del módulo convertidor  
**URL**: `/convertidor/`  
**Método**: GET  
**Funcionalidades**:
- Mostrar últimas 5 conversiones
- Estadísticas generales (total USD, total DOP, cantidad)
- Formulario de filtros
- Enlaces a historial completo

#### convertidor_registrar

**Propósito**: Registrar nueva conversión  
**URL**: `/convertidor/registrar/`  
**Método**: POST  
**Validaciones**:
- Monto USD obligatorio y positivo
- Tasa de cambio obligatoria y positiva
- Fecha opcional (usa fecha actual si no se proporciona)
- Imagen opcional (solo imágenes válidas)

#### convertidor_historial

**Propósito**: Historial completo con filtros avanzados  
**URL**: `/convertidor/historial/`  
**Método**: GET  
**Filtros Disponibles**:
- Rango de fechas (inicio/fin)
- Descripción (búsqueda parcial)
- Monto mínimo en USD

### APIs del Convertidor

#### api_movimientos

**URL**: `/api/convertidor/movimientos/`  
**Método**: GET  
**Parámetros**: fecha_inicio, fecha_fin, descripcion, monto_min  
**Respuesta**: JSON con lista de movimientos

#### api_estadisticas

**URL**: `/api/convertidor/estadisticas/`  
**Método**: GET  
**Respuesta**: JSON con estadísticas calculadas

### Generación de PDFs

#### convertidor_reporte_pdf

**Propósito**: Reporte completo del historial  
**Características**:
- Logo de empresa
- Información del usuario y fecha
- Tabla detallada con todos los movimientos
- Totales calculados
- Observaciones automáticas
- Formato profesional A4

#### convertidor_reporte_detalle_pdf

**Propósito**: Reporte detallado de un movimiento específico  
**Características**:
- Información completa del movimiento
- Resumen financiero
- Detalle de conversión
- Observaciones personalizadas

---

## 💰 Módulo Gastos

### Funcionalidades Principales

1. **CRUD Completo**: Crear, leer, actualizar, eliminar gastos
2. **Categorización**: 6 categorías predefinidas
3. **Control de Saldo**: Validación automática de saldo disponible
4. **Comprobantes**: Adjuntar imágenes de comprobantes
5. **Estados**: Control de estados (Activo, Editado, Eliminado)
6. **Filtros Avanzados**: Por fecha, categoría, entrada asociada
7. **Reportes PDF**: Individuales y de historial
8. **APIs REST**: Integración completa con frontend

### Categorías de Gastos

```python
CATEGORIAS_GASTOS = [
    ("ALIMENTACION", "Alimentación"),
    ("TRANSPORTE", "Transporte"),
    ("COMPRAS", "Compras"),
    ("SALUD", "Salud"),
    ("PERSONAL", "Gastos Personales"),
    ("OTROS", "Otros"),
]
```

### Vistas Principales

#### gastos_index

**Propósito**: Dashboard de gastos con filtros  
**Funcionalidades**:
- Lista de gastos activos
- Estadísticas generales
- Formularios de filtro
- APIs para datos dinámicos

#### gastos_crear

**Propósito**: Crear nuevo gasto  
**Validaciones**:
- Saldo disponible en entrada asociada
- Campos obligatorios: fecha, monto, categoría, descripción
- Asociación opcional con movimiento de entrada

#### gastos_editar

**Propósito**: Editar gasto existente  
**Consideraciones**:
- Recalcular saldo disponible
- Mantener integridad referencial

### APIs de Gastos

#### api_gastos

**URL**: `/api/gastos/`  
**Funcionalidades**: Lista de gastos con filtros

#### api_categorias

**URL**: `/api/categorias/`  
**Funcionalidades**: Lista de categorías disponibles

#### api_dashboard

**URL**: `/api/dashboard/`  
**Funcionalidades**: Estadísticas generales del sistema

---

## 🏢 Módulo Servicios

### Funcionalidades Principales

1. **Gestión de Pagos Recurrentes**: Electricidad, agua, internet, etc.
2. **Control de Proveedores**: Registro de proveedores únicos
3. **Comprobantes Digitales**: Adjuntar imágenes de comprobantes
4. **Estados de Pago**: Seguimiento del estado de cada pago
5. **Filtros Avanzados**: Por tipo de servicio, proveedor, fecha
6. **Reportes Detallados**: PDFs individuales y de historial
7. **Validación de Saldos**: Control automático de fondos disponibles

### Tipos de Servicio

```python
SERVICIOS_TIPOS = [
    ("LUZ", "Electricidad"),
    ("AGUA", "Agua"),
    ("INTERNET", "Internet"),
    ("TELEFONO", "Teléfono"),
    ("ALQUILER", "Alquiler"),
    ("OTRO", "Otro Servicio"),
]
```

### Vistas Principales

#### servicios_index

**Propósito**: Dashboard principal de servicios  
**Características**:
- Lista de pagos activos
- Estadísticas por tipo de servicio
- Filtros dinámicos
- Soporte AJAX completo

#### servicios_crear

**Propósito**: Registrar nuevo pago de servicio  
**Validaciones**:
- Verificación de saldo disponible
- Asociación con movimiento de entrada
- Campos obligatorios: tipo_servicio, monto, proveedor

#### servicios_editar

**Propósito**: Modificar pago existente  
**Consideraciones**:
- Recalculo de saldos
- Mantenimiento de integridad

### APIs de Servicios

#### servicios_tipos

**URL**: `/servicios/tipos-servicio/`  
**Funcionalidades**: Lista de tipos de servicio disponibles

#### servicios_proveedores

**URL**: `/servicios/proveedores/`  
**Funcionalidades**: Lista de proveedores únicos

#### servicios_metodos_pago

**URL**: `/servicios/metodos-pago/`  
**Funcionalidades**: Métodos de pago disponibles

---

## 📊 Dashboard Financiero

### Funcionalidades Principales

1. **Visualización de Datos**: Gráficos interactivos con Chart.js
2. **Estadísticas en Tiempo Real**: Cálculos automáticos
3. **Análisis Mensual**: Tendencias por mes
4. **Análisis Diario**: Movimientos por día
5. **Balances por Entrada**: Saldo disponible por conversión
6. **Reportes Consolidados**: PDFs de todos los movimientos
7. **Filtros Dinámicos**: Por fechas, tipos, categorías

### APIs del Dashboard

#### dashboard_api

**URL**: `/dashboard/api/`  
**Respuesta**: JSON completo con todos los datos del dashboard

**Estructura de Respuesta**:
```json
{
  "totales": {
    "total_entradas": 15000.00,
    "total_gastos": 8500.00,
    "total_servicios": 3200.00,
    "total_gastado": 11700.00,
    "balance_general": 3300.00
  },
  "mensuales": {
    "entradas_mes": 2500.00,
    "gastos_mes": 1800.00,
    "servicios_mes": 600.00,
    "total_gastado_mes": 2400.00
  },
  "movimientos": {
    "ultimas_entradas": [...],
    "ultimos_gastos": [...],
    "ultimos_servicios": [...]
  },
  "estadisticas": {
    "gastos_por_categoria": [...],
    "servicios_por_tipo": [...],
    "entradas_por_mes": [...],
    "gastos_por_mes": [...],
    "servicios_por_mes": [...],
    "entradas_por_dia": [...],
    "gastos_por_dia": [...],
    "servicios_por_dia": [...]
  },
  "balances_por_entrada": [...]
}
```

### Funciones de Cálculo

#### get_totales_globales()

Calcula los totales generales del sistema:
- Total de todas las entradas (conversiones)
- Total de gastos activos
- Total de servicios activos
- Balance general = Entradas - Gastos - Servicios

#### get_totales_mensuales()

Calcula estadísticas del mes actual:
- Entradas del mes
- Gastos del mes
- Servicios del mes
- Total gastado del mes

#### get_movimientos_recientes(limit=10)

Obtiene los últimos movimientos de cada tipo:
- Últimas entradas
- Últimos gastos
- Últimos servicios

### Gráficos Disponibles

1. **Gráfico de Barras**: Entradas vs Gastos vs Servicios por mes
2. **Gráfico de Líneas**: Tendencia mensual
3. **Gráfico Circular**: Gastos por categoría
4. **Gráfico de Área**: Movimientos diarios
5. **Gráfico de Barras Apiladas**: Balance por entrada

---

## 📄 Generación de Reportes PDF

### Características Generales

1. **Formato Profesional**: Diseño consistente en todos los reportes
2. **Logo Corporativo**: Inclusión automática del logo
3. **Información del Usuario**: Usuario y fecha en cada reporte
4. **Zona Horaria Dominicana**: Fechas en hora local (UTC-4)
5. **Paginación Automática**: Manejo automático de páginas largas
6. **Tablas Profesionales**: Bordes, colores alternos, alineación
7. **Descargas Automáticas**: Nombres de archivo descriptivos

### Tipos de Reporte

#### 1. Reportes de Convertidor

**convertidor_reporte_pdf**: Historial completo de conversiones
**convertidor_reporte_detalle_pdf**: Detalle de una conversión específica
**convertidor_imprimir_todo**: Versión imprimible del historial

#### 2. Reportes de Gastos

**gastos_pdf**: Comprobante individual de gasto
**gastos_pdf_historial**: Historial completo de gastos
**gastos_imprimir_historial**: Versión imprimible

#### 3. Reportes de Servicios

**servicios_pdf**: Comprobante individual de servicio
**servicios_pdf_historial**: Historial completo de servicios
**servicios_imprimir_historial**: Versión imprimible

#### 4. Reportes de Dashboard

**dashboard_reporte_pdf**: Reporte consolidado de todos los movimientos
**dashboard_reporte_detalle_pdf**: Detalle de cualquier tipo de movimiento
**dashboard_imprimir_historial**: Versión imprimible del dashboard

### Estructura Común de Reportes

```
┌─────────────────────────────────────────┐
│ LOGO EMPRESA          MCL_FINANCE      │
│                                        │
│         TÍTULO DEL REPORTE             │
└─────────────────────────────────────────┘

FECHA DEL REPORTE: [fecha]
USUARIO: [usuario]

┌─────────────────────────────────────────┐
│         DATOS DEL REPORTE              │
│ Total registros: X                     │
│ Período: del XX/XX/XXXX al XX/XX/XXXX │
│ Filtros aplicados: [filtros]          │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│         DETALLE DE MOVIMIENTOS         │
│ ┌─────────────────────────────────────┐ │
│ │ N° │ FECHA │ DESCRIPCIÓN │ MONTO │ │
│ ├─────────────────────────────────────┤ │
│ │ 1 │ XX/XX │ XXXXXXXXXXX │ XXXX │ │
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│         RESUMEN FINAL                  │
│ Total entradas: RD$ XX,XXX.XX         │
│ Total gastos: RD$ XX,XXX.XX           │
│ Balance: RD$ XX,XXX.XX                │
└─────────────────────────────────────────┘

OBSERVACIONES:
[Observaciones automáticas]

Sistema de Gestión Financiera MLAN FINANCE
Generado el [fecha]
```

---

## 🎨 Interfaz de Usuario

### Diseño General

1. **Sidebar Izquierdo**: Navegación principal con iconos
2. **Header Superior**: Información del usuario y controles
3. **Contenido Principal**: Área de trabajo adaptable
4. **Paleta de Colores**: Azul profesional (#035087, #011b5c)
5. **Tipografía**: Inter font family
6. **Responsive**: Adaptable a móviles y tablets

### Componentes Reutilizables

#### Sidebar Navigation

```html
<div class="sidebar-left">
    <div class="sidebar-header">
        <h2><i class="fas fa-chart-line"></i> MCL_FINANZA</h2>
        <p>Sistema Financiero</p>
    </div>
    
    <nav class="sidebar-menu">
        <a href="/convertidor/" class="menu-item">
            <i class="fas fa-exchange-alt"></i>
            <span>Convertidor</span>
        </a>
        
        <a href="/gastos/" class="menu-item">
            <i class="fas fa-wallet"></i>
            <span>Gastos</span>
        </a>
        
        <a href="/servicios/" class="menu-item">
            <i class="fas fa-building"></i>
            <span>Servicios</span>
        </a>
        
        <a href="/dashboard/" class="menu-item active">
            <i class="fas fa-chart-bar"></i>
            <span>Dashboard</span>
        </a>
    </nav>
</div>
```

#### Cards de Estadísticas

```html
<div class="stats-grid">
    <div class="stat-card">
        <div class="stat-icon">
            <i class="fas fa-dollar-sign"></i>
        </div>
        <div class="stat-content">
            <h3>RD$ 15,000.00</h3>
            <p>Total Disponible</p>
        </div>
    </div>
    
    <div class="stat-card">
        <div class="stat-icon">
            <i class="fas fa-shopping-cart"></i>
        </div>
        <div class="stat-content">
            <h3>RD$ 8,500.00</h3>
            <p>Total Gastado</p>
        </div>
    </div>
    
    <div class="stat-card">
        <div class="stat-icon">
            <i class="fas fa-piggy-bank"></i>
        </div>
        <div class="stat-content">
            <h3>RD$ 6,500.00</h3>
            <p>Balance</p>
        </div>
    </div>
</div>
```

### JavaScript y AJAX

#### Carga Dinámica de Datos

```javascript
// Función para cargar gastos con filtros
function cargarGastos(filtros = {}) {
    $.ajax({
        url: '/api/gastos/',
        method: 'GET',
        data: filtros,
        success: function(response) {
            if (response.success) {
                actualizarTablaGastos(response.gastos);
                actualizarEstadisticas(response.dashboard);
            }
        },
        error: function(xhr, status, error) {
            console.error('Error al cargar gastos:', error);
        }
    });
}
```

#### Gráficos con Chart.js

```javascript
// Gráfico de gastos por categoría
function crearGraficoGastosPorCategoria(datos) {
    const ctx = document.getElementById('gastosCategoriaChart').getContext('2d');
    
    new Chart(ctx, {
        type: 'pie',
        data: {
            labels: datos.map(item => item.categoria),
            datasets: [{
                data: datos.map(item => item.total),
                backgroundColor: [
                    '#FF6384', '#36A2EB', '#FFCE56',
                    '#4BC0C0', '#9966FF', '#FF9F40'
                ]
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'bottom',
                }
            }
        }
    });
}
```

---

## 🔒 Seguridad del Sistema

### Medidas de Seguridad Implementadas

1. **Autenticación Obligatoria**: Todas las vistas protegidas requieren login
2. **Protección CSRF**: Tokens CSRF en todos los formularios
3. **Validación de Datos**: Validaciones en backend y frontend
4. **Control de Sesiones**: Timeout automático de sesiones
5. **Sanitización de Inputs**: Limpieza de datos de usuario
6. **Control de Acceso a Archivos**: Solo archivos de imagen permitidos
7. **HTTPS en Producción**: Configurado para entornos de producción

### Configuración de Seguridad

```python
# Configuración de sesiones seguras
SESSION_COOKIE_AGE = 3600  # 1 hora
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_HTTPONLY = True

# CSRF
CSRF_COOKIE_SECURE = True  # En producción
CSRF_USE_SESSIONS = False

# Headers de seguridad
SECURE_SSL_REDIRECT = True  # En producción
SECURE_HSTS_SECONDS = 31536000  # 1 año
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
```

### Validaciones de Seguridad

#### Validación de Imágenes

```python
def validar_imagen(imagen):
    """Valida que el archivo sea una imagen segura"""
    if not imagen:
        return True
    
    # Verificar tipo MIME
    if not imagen.content_type.startswith('image/'):
        return False
    
    # Verificar extensión
    extensiones_permitidas = ['.jpg', '.jpeg', '.png', '.gif']
    extension = os.path.splitext(imagen.name)[1].lower()
    
    if extension not in extensiones_permitidas:
        return False
    
    # Verificar tamaño (máximo 5MB)
    if imagen.size > 5 * 1024 * 1024:
        return False
    
    return True
```

---

## 🚀 Despliegue y Producción

### Entornos Soportados

1. **Desarrollo Local**: Configuración completa para desarrollo
2. **PythonAnywhere**: Despliegue gratuito con demo activa
3. **Render**: Plataforma de despliegue cloud
4. **Vercel**: Despliegue automático desde GitHub
5. **Servidores Dedicados**: Configuración para servidores propios

### Variables de Entorno Requeridas

```bash
# Base de datos
DB_NAME=financiera
DB_USER=usuario_db
DB_PASSWORD=contraseña_segura
DB_HOST=localhost
DB_PORT=3306

# Django
SECRET_KEY=clave-secreta-muy-larga-y-segura
DEBUG=False

# Email (opcional)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=tu-email@gmail.com
EMAIL_HOST_PASSWORD=tu-contraseña-app
```

### Proceso de Despliegue

#### 1. Preparación del Entorno

```bash
# Clonar repositorio
git clone https://github.com/CodeAriCos28/MCL_FINANZA.git
cd MCL_FINANZA

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o
venv\Scripts\activate     # Windows

# Instalar dependencias
pip install -r requirements.txt
```

#### 2. Configuración

```bash
# Variables de entorno
cp .env.example .env
# Editar .env con valores reales

# Migraciones de base de datos
python manage.py migrate

# Crear superusuario
python manage.py createsuperuser

# Recopilar archivos estáticos
python manage.py collectstatic --noinput
```

#### 3. Despliegue

```bash
# Ejecutar servidor
python manage.py runserver 0.0.0.0:8000

# O con Gunicorn (producción)
gunicorn core.wsgi:application --bind 0.0.0.0:8000
```

### Configuración de Nginx (Opcional)

```nginx
server {
    listen 80;
    server_name tu-dominio.com;
    
    location = /favicon.ico { access_log off; log_not_found off; }
    
    location /static/ {
        alias /ruta/a/tu/proyecto/staticfiles/;
    }
    
    location /media/ {
        alias /ruta/a/tu/proyecto/media/;
    }
    
    location / {
        include proxy_params;
        proxy_pass http://127.0.0.1:8000;
    }
}
```

---

## 🗄️ Base de Datos

### Estructura de Tablas

#### Tabla `finanzas_movimientoentrada`

```sql
CREATE TABLE `finanzas_movimientoentrada` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `monto_usd` decimal(12,2) NOT NULL,
  `tasa_cambio` decimal(12,2) NOT NULL,
  `monto_pesos` decimal(12,2) NOT NULL,
  `descripcion` varchar(200) DEFAULT NULL,
  `fecha` datetime(6) NOT NULL,
  `imagen` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### Tabla `finanzas_gasto`

```sql
CREATE TABLE `finanzas_gasto` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `categoria` varchar(20) NOT NULL,
  `monto` decimal(12,2) NOT NULL,
  `descripcion` varchar(200) DEFAULT NULL,
  `fecha` datetime(6) NOT NULL,
  `entrada_id` int(11) DEFAULT NULL,
  `estado` varchar(20) NOT NULL,
  `tipo_comprobante` varchar(20) NOT NULL,
  `numero_comprobante` varchar(100) DEFAULT NULL,
  `proveedor` varchar(200) DEFAULT NULL,
  `notas` longtext,
  `imagen` varchar(100) DEFAULT NULL,
  `fecha_creacion` datetime(6) NOT NULL,
  `fecha_actualizacion` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `finanzas_gasto_entrada_id` (`entrada_id`),
  CONSTRAINT `finanzas_gasto_entrada_id` FOREIGN KEY (`entrada_id`) REFERENCES `finanzas_movimientoentrada` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### Tabla `finanzas_serviciopago`

```sql
CREATE TABLE `finanzas_serviciopago` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `tipo_servicio` varchar(20) NOT NULL,
  `monto` decimal(12,2) NOT NULL,
  `descripcion` varchar(200) DEFAULT NULL,
  `fecha` datetime(6) NOT NULL,
  `entrada_id` int(11) DEFAULT NULL,
  `estado` varchar(20) NOT NULL,
  `tipo_comprobante` varchar(20) NOT NULL,
  `numero_comprobante` varchar(100) DEFAULT NULL,
  `proveedor` varchar(200) DEFAULT NULL,
  `notas` longtext,
  `imagen` varchar(100) DEFAULT NULL,
  `fecha_creacion` datetime(6) NOT NULL,
  `fecha_actualizacion` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `finanzas_serviciopago_entrada_id` (`entrada_id`),
  CONSTRAINT `finanzas_serviciopago_entrada_id` FOREIGN KEY (`entrada_id`) REFERENCES `finanzas_movimientoentrada` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### Migraciones Django

El proyecto incluye 7 migraciones que crean y modifican las tablas:

1. **0001_initial.py**: Creación inicial de todas las tablas
2. **0002_alter_movimientoentrada_fecha.py**: Modificación del campo fecha
3. **0003_alter_movimientoentrada_fecha.py**: Ajustes adicionales en fecha
4. **0004_alter_gasto_fecha_alter_gasto_fecha_creacion_and_more.py**: Campos de fecha en gastos
5. **0005_alter_gasto_fecha_actualizacion.py**: Campo fecha_actualizacion
6. **0006_alter_gasto_fecha_creacion.py**: Campo fecha_creacion
7. **0007_alter_gasto_fecha_actualizacion.py**: Ajustes finales

### Índices y Constraints

- **Primary Keys**: Autoincrementales en todas las tablas
- **Foreign Keys**: Relaciones entre gastos/servicios y movimientos de entrada
- **Índices**: En campos de fecha y claves foráneas para optimización
- **Constraints**: Restricciones de integridad referencial

---

## 🧪 Testing y Calidad

### Estrategia de Testing

1. **Tests Unitarios**: Para funciones individuales
2. **Tests de Integración**: Para flujos completos
3. **Tests de API**: Para endpoints REST
4. **Tests de UI**: Para funcionalidades frontend

### Tests Implementados

#### tests.py (finanzas/tests.py)

```python
from django.test import TestCase
from django.contrib.auth.models import User
from .models import MovimientoEntrada, Gasto, ServicioPago

class MovimientoEntradaTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', 
            password='testpass'
        )
        
    def test_crear_movimiento(self):
        movimiento = MovimientoEntrada.objects.create(
            monto_usd=100.00,
            tasa_cambio=58.50,
            descripcion='Test movimiento'
        )
        
        self.assertEqual(movimiento.monto_pesos, 5850.00)
        self.assertEqual(str(movimiento), '$100.00 USD → $5850.00 DOP - [fecha]')
```

### Ejecución de Tests

```bash
# Ejecutar todos los tests
python manage.py test

# Ejecutar tests de una app específica
python manage.py test finanzas

# Ejecutar un test específico
python manage.py test finanzas.tests.MovimientoEntradaTestCase.test_crear_movimiento

# Con cobertura
coverage run manage.py test
coverage report
```

---

## 📈 Rendimiento y Optimización

### Optimizaciones Implementadas

1. **Lazy Loading**: Queries optimizadas con select_related/prefetch_related
2. **Índices de Base de Datos**: En campos frecuentemente consultados
3. **Caching**: Archivos estáticos servidos eficientemente
4. **Compresión**: Gzip para respuestas HTTP
5. **Paginación**: Para listas grandes de datos

### Consultas Optimizadas

```python
# Ejemplo de query optimizada en gastos_index
gastos = Gasto.objects.filter(estado='ACTIVO').select_related('entrada')

# Con prefetch para relaciones inversas si fuera necesario
gastos = Gasto.objects.filter(estado='ACTIVO').prefetch_related('entrada')
```

### Configuración de Caché

```python
# Configuración de caché (opcional para producción)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/',
    }
}
```

---

## 🔧 Mantenimiento y Monitoreo

### Tareas de Mantenimiento

1. **Limpieza de Sesiones**: Eliminar sesiones expiradas
2. **Backup de Base de Datos**: Copias de seguridad regulares
3. **Limpieza de Archivos**: Eliminar archivos temporales
4. **Actualización de Dependencias**: Mantener versiones seguras
5. **Monitoreo de Logs**: Revisar logs de errores

### Logs del Sistema

```python
# Configuración de logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': 'logs/django_error.log',
        },
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
        },
        'django.request': {
            'handlers': ['file'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}
```

### Comandos de Mantenimiento

```bash
# Limpiar sesiones expiradas
python manage.py clearsessions

# Verificar integridad de la BD
python manage.py check

# Crear backup de datos
python manage.py dumpdata > backup.json

# Restaurar backup
python manage.py loaddata backup.json
```

---

## 📚 API Reference

### Endpoints Principales

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/api/convertidor/movimientos/` | GET | Lista movimientos convertidor |
| `/api/convertidor/estadisticas/` | GET | Estadísticas convertidor |
| `/api/gastos/` | GET | Lista de gastos |
| `/api/categorias/` | GET | Categorías de gastos |
| `/api/dashboard/` | GET | Datos del dashboard |
| `/servicios/tipos-servicio/` | GET | Tipos de servicio |
| `/servicios/proveedores/` | GET | Lista de proveedores |

### Formato de Respuesta API

```json
{
    "success": true,
    "data": [...],
    "total": 100,
    "filtros_aplicados": {
        "fecha_inicio": "2024-01-01",
        "categoria": "ALIMENTACION"
    }
}
```

---

## 🐛 Solución de Problemas

### Problemas Comunes

#### 1. Error de Conexión a Base de Datos

**Síntoma**: `django.db.utils.OperationalError`

**Solución**:
```bash
# Verificar variables de entorno
echo $DB_NAME
echo $DB_USER

# Probar conexión
python manage.py dbshell

# Verificar migraciones
python manage.py showmigrations
python manage.py migrate
```

#### 2. Error 500 en Producción

**Síntoma**: Internal Server Error

**Solución**:
```bash
# Revisar logs
tail -f logs/django_error.log

# Verificar archivos estáticos
python manage.py collectstatic --noinput

# Verificar permisos
chmod -R 755 media/
chmod -R 755 staticfiles/
```

#### 3. Problemas de Zona Horaria

**Síntoma**: Fechas incorrectas

**Solución**:
```python
# Verificar configuración
from django.utils import timezone
print(timezone.now())

# Forzar zona horaria
import pytz
tz_rd = pytz.timezone('America/Santo_Domingo')
fecha_rd = timezone.now().astimezone(tz_rd)
```

#### 4. Problemas de Memoria en PDFs

**Síntoma**: Error al generar PDFs grandes

**Solución**:
```python
# Implementar paginación
from django.core.paginator import Paginator

paginator = Paginator(movimientos, 100)  # 100 por página
for page_num in paginator.page_range:
    page = paginator.page(page_num)
    # Generar PDF por página
```

---

## 🚀 Roadmap y Mejoras Futuras

### Versión 2026.1.1 (Próxima)

1. **Notificaciones**: Sistema de alertas por email/SMS
2. **Presupuestos**: Control de presupuestos mensuales
3. **Inversiones**: Seguimiento de inversiones
4. **Reportes Avanzados**: Gráficos más complejos
5. **API REST Completa**: API documentada con Swagger
6. **Aplicación Móvil**: App React Native

### Mejoras Técnicas

1. **Microservicios**: Separar módulos en servicios independientes
2. **GraphQL**: API más flexible
3. **WebSockets**: Actualizaciones en tiempo real
4. **Machine Learning**: Predicciones financieras
5. **Blockchain**: Transacciones seguras

### Funcionalidades Planificadas

1. **Multimoneda**: Soporte para múltiples monedas
2. **Multiusuario**: Sistema multiusuario con roles
3. **Integraciones**: Conexión con bancos y fintech
4. **IA**: Asistente financiero inteligente
5. **Realidad Virtual**: Visualización 3D de datos

---

## 👥 Contribución

### Guía para Contribuidores

1. **Fork** el repositorio
2. **Crear** rama feature: `git checkout -b feature/nueva-funcionalidad`
3. **Commit** cambios: `git commit -m "Añade nueva funcionalidad"`
4. **Push** a rama: `git push origin feature/nueva-funcionalidad`
5. **Pull Request**: Crear PR con descripción detallada

### Estándares de Código

```python
# Ejemplo de función bien documentada
def calcular_total_gastos(fecha_inicio=None, fecha_fin=None):
    """
    Calcula el total de gastos en un período específico.
    
    Args:
        fecha_inicio (datetime, optional): Fecha de inicio del período
        fecha_fin (datetime, optional): Fecha de fin del período
    
    Returns:
        Decimal: Total de gastos en el período
    """
    queryset = Gasto.objects.filter(estado='ACTIVO')
    
    if fecha_inicio:
        queryset = queryset.filter(fecha__gte=fecha_inicio)
    if fecha_fin:
        queryset = queryset.filter(fecha__lte=fecha_fin)
    
    return queryset.aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
```

### Tests Requeridos

```python
def test_calcular_total_gastos(self):
    # Crear datos de prueba
    Gasto.objects.create(monto=100.00, estado='ACTIVO')
    Gasto.objects.create(monto=200.00, estado='ELIMINADO')
    
    # Probar función
    total = calcular_total_gastos()
    self.assertEqual(total, Decimal('100.00'))
```

---

## 📄 Licencia

Este proyecto está bajo la **Licencia MIT**.

```
MIT License

Copyright (c) 2026 CodeAriCos28

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 📞 Soporte y Contacto

### Autor
**CodeAriCos28**
- **GitHub**: [https://github.com/CodeAriCos28](https://github.com/CodeAriCos28)
- **Email**: [contacto@codearicos.com](mailto:contacto@codearicos.com)

### Demo en Línea
- **URL**: [https://codearicos.pythonanywhere.com/](https://codearicos.pythonanywhere.com/)
- **Estado**: Activo y funcional

### Canales de Soporte

1. **GitHub Issues**: Para reportar bugs y solicitar features
2. **GitHub Discussions**: Para preguntas generales
3. **Email**: Para soporte técnico directo

### Reportar un Bug

```markdown
## Título del Bug

### Descripción
[Descripción clara del problema]

### Pasos para Reproducir
1. Ir a '...'
2. Hacer click en '...'
3. Ver error

### Comportamiento Esperado
[Qué debería suceder]

### Comportamiento Actual
[Qué sucede en realidad]

### Información del Sistema
- OS: [Windows/Linux/Mac]
- Browser: [Chrome/Firefox/Safari]
- Versión: [2026 1.0.2]
```

---

## 🎉 Conclusión

MCL_FINANZA representa una solución completa y profesional para la gestión financiera personal en República Dominicana. El sistema combina las mejores prácticas de desarrollo Django con una interfaz intuitiva y funcionalidades avanzadas que permiten a los usuarios tener un control total sobre sus finanzas.

### Puntos Fuertes

✅ **Arquitectura Sólida**: Basada en Django con patrones de diseño probados  
✅ **Interfaz Moderna**: Diseño responsive con UX optimizada  
✅ **Funcionalidades Completas**: CRUD, reportes, APIs, validaciones  
✅ **Seguridad Robusta**: Autenticación, CSRF, validaciones  
✅ **Escalabilidad**: Preparado para crecimiento futuro  
✅ **Documentación Completa**: Esta documentación exhaustiva  

### Impacto

El proyecto no solo sirve como herramienta financiera práctica, sino también como ejemplo educativo de desarrollo web profesional con Django, demostrando cómo construir aplicaciones web complejas y mantenibles.

---

**¡Gracias por elegir MCL_FINANZA!** 💰📊

*Desarrollado con ❤️ por CodeAriCos28*

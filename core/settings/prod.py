# core/settings/prod.py

# Importa TODA la configuración del archivo base.py
import os
from .base import * # =========================================================
# AJUSTES DE PRODUCCIÓN
# =========================================================

# 1. Desactivar el modo de depuración (¡CRUCIAL por seguridad!)
DEBUG = False

# 2. Hosts permitidos (Reemplaza con tus dominios reales)
ALLOWED_HOSTS = ['midominio.com', 'www.midominio.com', 'mcl-finanza-1.onrender.com', '.vercel.app']

# 3. Clave secreta (Ya la cargamos desde .env en base.py)

# 4. Seguridad de la conexión (Recomendado para servidores)
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
# Más ajustes de seguridad como HSTS, etc.

# 5. Configuración de Archivos Estáticos (¡Cambia esto!)
# En producción, debes usar servicios como S3 o un CDN, 
# o servir archivos estáticos con un servidor como Nginx.
# STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')


# LOGGING['handlers']['file'] = {
#     'class': 'logging.handlers.RotatingFileHandler',
#     'filename': os.path.join(BASE_DIR, 'logs/django.log'),
#     'maxBytes': 1024*1024*5,  # 5 MB
#     'backupCount': 10,
#     'formatter': 'standard',
# }

# # LOGGING['loggers']['django']['handlers'] = ['file']
# LOGGING['loggers']['derej_clan']['handlers'] = ['file']
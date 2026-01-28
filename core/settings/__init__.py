# core/settings/__init__.py
import os

# Por defecto, carga la configuración de 'dev'
SETTINGS_MODULE = os.environ.get('DJANGO_ENV', 'dev')

if SETTINGS_MODULE == 'dev':
    from .dev import *
elif SETTINGS_MODULE == 'prod':
    from .prod import *
    
# Asegúrate de cargar la configuración base que es común a ambos
try:
    from .base import *
except ImportError:
    # Esto no debería pasar si la estructura está correcta
    print("FATAL: No se encontró la configuración base.")
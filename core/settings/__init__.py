# core/settings/__init__.py
from .base import *

import os
env = os.environ.get("DJANGO_ENV", "dev")

if env == "dev":
    from .dev import *
elif env == "prod":
    from .prod import *
    
# Asegúrate de cargar la configuración base que es común a ambos
try:
    from .base import *
except ImportError:
    # Esto no debería pasar si la estructura está correcta
    print("FATAL: No se encontró la configuración base.")
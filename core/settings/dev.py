# core/settings/dev.py
from .base import * # Importa toda la configuración del archivo base
# from dotenv import load_dotenv

# load_dotenv()
# =========================================================
# CONFIGURACIÓN ESPECÍFICA DE DESARROLLO (DEV)
# =========================================================

# 1. Modo de depuración (Debugging)
# DEBUG = True
# ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS')
# 2. Hosts permitidos
# ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'omega-neighbourless-sublabially.ngrok-free.dev']


# 3. Email (configurado para mostrar correos en la consola, no enviarlos)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# *Opcional: puedes definir una base de datos de desarrollo diferente aquí*
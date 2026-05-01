import os
import sys
import django
import datetime
import threading
import time
from pathlib import Path
from dotenv import load_dotenv
from django.core.management import call_command
from waitress import serve

# --- CONFIGURACIÓN DE RUTAS ---
if getattr(sys, 'frozen', False):
    # Si es el .exe, BASE_DIR es la carpeta donde vive el ejecutable
    BASE_DIR_EXE = Path(sys.executable).parent
else:
    # Si es desarrollo, es la carpeta donde está este script
    BASE_DIR_EXE = Path(__file__).resolve().parent

# Cargar variables de entorno (.env debe estar al lado del .exe o en la raíz)
load_dotenv(BASE_DIR_EXE / ".env")

def ejecutar_logica_tasa():
    """
    Verifica si ya se actualizó la tasa hoy después de las 9:00 AM.
    Si no, ejecuta el comando update_rates.
    """
    log_file = BASE_DIR_EXE / "last_rate_update.txt"
    ahora = datetime.datetime.now()
    hoy_9am = ahora.replace(hour=9, minute=0, second=0, microsecond=0)
    
    ultima_fecha = ""
    if log_file.exists():
        ultima_fecha = log_file.read_text().strip()

    # Condición: Son más de las 9 AM Y (no hay registro de hoy O nunca se ha actualizado)
    if ahora >= hoy_9am and ultima_fecha != ahora.strftime('%Y-%m-%d'):
        try:
            print(f"[*] [{ahora.strftime('%H:%M:%S')}] Iniciando actualización de tasas...")
            # 'update_rates' es el nombre de tu archivo sin el .py
            call_command('update_rates') 
            
            # Guardamos la fecha para no repetir hasta mañana
            log_file.write_text(ahora.strftime('%Y-%m-%d'))
            print("[✅] Tasas actualizadas con éxito.")
        except Exception as e:
            print(f"[⚠️] Error al actualizar tasas: {e}")

def monitor_de_tiempo():
    """
    Hilo infinito que revisa cada 30 minutos si es necesario actualizar.
    """
    while True:
        ejecutar_logica_tasa()
        time.sleep(1800) # Espera 30 minutos entre revisiones

def iniciar():
    # Establecer settings de Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
    
    try:
        django.setup()
    except Exception as e:
        print(f"[!] Error crítico en django.setup(): {e}")
        return

    # 🧵 LANZAR TAREA DE TASAS EN SEGUNDO PLANO
    # Se usa un hilo (Thread) para que el servidor suba rápido y Electron no espere.
    t = threading.Thread(target=monitor_de_tiempo, daemon=True)
    t.start()

    # Configurar y lanzar Waitress
    try:
        from core.wsgi import application
        
        # Prioridad a las variables que envía Node/Electron
        host = os.environ.get('SERVER_HOST', '127.0.0.1')
        port_env = os.environ.get('SERVER_PORT', '8000')
        port = int(port_env)

        print(f"[*] Servidor listo en http://{host}:{port}")
        serve(application, host=host, port=port)
        
    except Exception as e:
        print(f"[!] Error al iniciar Waitress: {e}")

if __name__ == '__main__':
    iniciar()
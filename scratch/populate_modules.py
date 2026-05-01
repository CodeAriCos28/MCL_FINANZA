import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.base')
django.setup()

from seguridad.models import Modulo

def populate_modules():
    modules_data = [
        {'nombre': 'Dashboard', 'slug': 'dashboard', 'icono': 'fas fa-chart-line', 'url_name': 'dashboard', 'orden': 1},
        {'nombre': 'Conversiones', 'slug': 'conversiones', 'icono': 'fas fa-exchange-alt', 'url_name': 'convertidor', 'orden': 2},
        {'nombre': 'Gestión Gastos', 'slug': 'gastos', 'icono': 'fas fa-wallet', 'url_name': 'gastos', 'orden': 3},
        {'nombre': 'Pago Servicios', 'slug': 'servicios', 'icono': 'fas fa-file-invoice-dollar', 'url_name': 'servicios', 'orden': 4},
        {'nombre': 'Seguridad', 'slug': 'seguridad', 'icono': 'fas fa-shield-halved', 'url_name': 'roles-index', 'orden': 5},
    ]

    for data in modules_data:
        modulo, created = Modulo.objects.get_or_create(
            slug=data['slug'],
            defaults={
                'nombre': data['nombre'],
                'icono': data['icono'],
                'url_name': data['url_name'],
                'orden': data['orden'],
                'activo': True
            }
        )
        if not created:
            modulo.nombre = data['nombre']
            modulo.icono = data['icono']
            modulo.url_name = data['url_name']
            modulo.orden = data['orden']
            modulo.save()
            print(f"Actualizado: {modulo.nombre}")
        else:
            print(f"Creado: {modulo.nombre}")

if __name__ == "__main__":
    populate_modules()

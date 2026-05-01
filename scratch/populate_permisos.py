import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.base')
django.setup()

from django.contrib.auth.models import Permission
from seguridad.models import Modulo, PermisoModulo

def populate_permissions():
    mappings = {
        'dashboard': [
            ('view_gasto', 'Ver Dashboard de Gastos'),
            ('view_serviciopago', 'Ver Dashboard de Servicios'),
            ('view_movimientoentrada', 'Ver Dashboard de Conversiones'),
        ],
        'conversiones': [
            ('view_movimientoentrada', 'Ver Conversiones'),
            ('add_movimientoentrada', 'Registrar Conversión'),
            ('change_movimientoentrada', 'Editar Conversión'),
            ('delete_movimientoentrada', 'Eliminar Conversión'),
        ],
        'gastos': [
            ('view_gasto', 'Ver Historial de Gastos'),
            ('add_gasto', 'Registrar Gasto'),
            ('change_gasto', 'Editar Gasto'),
            ('delete_gasto', 'Eliminar Gasto'),
        ],
        'servicios': [
            ('view_serviciopago', 'Ver Pagos de Servicios'),
            ('add_serviciopago', 'Registrar Pago de Servicio'),
            ('change_serviciopago', 'Editar Pago de Servicio'),
            ('delete_serviciopago', 'Eliminar Pago de Servicio'),
        ],
        'seguridad': [
            ('view_user', 'Ver Usuarios'),
            ('add_user', 'Crear Usuarios'),
            ('change_user', 'Editar Usuarios'),
            ('delete_user', 'Eliminar Usuarios'),
            ('view_group', 'Ver Roles'),
            ('add_group', 'Crear Roles'),
            ('change_group', 'Editar Roles'),
            ('delete_group', 'Eliminar Roles'),
            ('view_modulo', 'Gestionar Menú Lateral'),
        ]
    }

    for slug, perms in mappings.items():
        try:
            modulo = Modulo.objects.get(slug=slug)
            for codename, legible in perms:
                try:
                    permiso = Permission.objects.get(codename=codename)
                    pm, created = PermisoModulo.objects.get_or_create(
                        modulo=modulo,
                        permiso=permiso,
                        defaults={'nombre_legible': legible}
                    )
                    if created:
                        print(f"Creado enlace: {modulo.nombre} -> {legible}")
                    else:
                        pm.nombre_legible = legible
                        pm.save()
                        print(f"Actualizado enlace: {modulo.nombre} -> {legible}")
                except Permission.DoesNotExist:
                    print(f"ERROR: No existe el permiso {codename}")
        except Modulo.DoesNotExist:
            print(f"ERROR: No existe el módulo {slug}")

if __name__ == "__main__":
    populate_permissions()

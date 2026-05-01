# seguridad/backends.py
from django.contrib.auth.backends import ModelBackend
from .models import UserPermissionOverride


class SecurityLogicBackend(ModelBackend):
    """
    Prioridad:
      1. Override del usuario  → decide todo (True o False)
      2. Sin override          → decide el Rol/Grupo de Django
    """
    def has_perm(self, user_obj, perm, obj=None):
        if not user_obj.is_active:
            return False

        codename = perm.split('.')[-1]

        try:
            override = UserPermissionOverride.objects.get(
                usuario=user_obj,
                permiso__codename=codename
            )
            return override.tiene_acceso

        except UserPermissionOverride.DoesNotExist:
            pass

        return super().has_perm(user_obj, perm, obj)
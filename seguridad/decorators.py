from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps
from .models import UserPermissionOverride, PermisoModulo

def modulo_permission_required(modulo_slug):
    """
    Decorador que verifica si el usuario tiene permiso para acceder a un módulo específico.
    Considera permisos de Django y Overrides personalizados.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                return redirect('login')
            
            if user.is_superuser:
                return view_func(request, *args, **kwargs)

            # 1. Obtener los permisos vinculados a este módulo
            perms_modulo = PermisoModulo.objects.filter(modulo__slug=modulo_slug).select_related('permiso__content_type')
            
            if not perms_modulo.exists():
                # Si el módulo no tiene restricciones, permitimos acceso
                return view_func(request, *args, **kwargs)

            # 2. Verificar overrides y permisos estándar
            has_access = False
            user_perms = user.get_all_permissions()
            
            for pm in perms_modulo:
                codename = pm.permiso.codename
                app_label = pm.permiso.content_type.app_label
                full_perm = f"{app_label}.{codename}"

                # Prioridad 1: Overrides
                override = UserPermissionOverride.objects.filter(usuario=user, permiso__codename=codename).first()
                if override:
                    if override.tiene_acceso:
                        has_access = True
                        break
                    else:
                        continue # Bloqueado en este permiso, probar otros del módulo

                # Prioridad 2: Permisos de Django
                if full_perm in user_perms:
                    has_access = True
                    break
            
            if has_access:
                return view_func(request, *args, **kwargs)
            
            # Si no tiene acceso, redirigir con mensaje
            messages.error(request, f"No tienes permiso para acceder al módulo de {modulo_slug.capitalize()}.")
            return redirect('dashboard') # O a la página de inicio que prefieras
            
        return _wrapped_view
    return decorator

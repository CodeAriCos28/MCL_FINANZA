from .models import Modulo, UserPermissionOverride

def menu_modulos(request):
    """
    Proporciona los módulos activos al contexto global, filtrados por los permisos del usuario.
    """
    if not request.user.is_authenticated:
        return {'modulos_menu': []}

    user = request.user
    
    # Superusuario ve todo lo activo
    if user.is_superuser:
        return {
            'modulos_menu': Modulo.objects.filter(activo=True).order_by('orden')
        }

    # Para usuarios normales, obtenemos sus permisos y excepciones
    user_perms = user.get_all_permissions()
    overrides = {
        ov.permiso.codename: ov.tiene_acceso 
        for ov in UserPermissionOverride.objects.filter(usuario=user)
    }

    modulos_visibles = []
    # Usamos prefetch_related para evitar el problema N+1
    todos_los_modulos = Modulo.objects.filter(activo=True).prefetch_related('permisos__permiso__content_type').order_by('orden')

    for m in todos_los_modulos:
        has_access = False
        # Si un módulo no tiene permisos vinculados, lo mostramos por defecto (ej. Inicio)
        # o si el usuario tiene acceso a al menos uno de sus permisos.
        perms_modulo = m.permisos.all()
        
        if not perms_modulo:
            # Si no hay restricciones en PermisoModulo, es público para logueados
            has_access = True
        else:
            for pm in perms_modulo:
                codename = pm.permiso.codename
                app_label = pm.permiso.content_type.app_label
                full_perm = f"{app_label}.{codename}"

                # 1. Prioridad: Excepciones individuales (Overrides)
                if codename in overrides:
                    if overrides[codename]:
                        has_access = True
                        break
                    else:
                        continue # Bloqueado específicamente, probar con otro permiso del módulo

                # 2. Permisos estándar de Django (Grupos/Individuales)
                if full_perm in user_perms:
                    has_access = True
                    break
        
        if has_access:
            modulos_visibles.append(m)

    return {
        'modulos_menu': modulos_visibles
    }

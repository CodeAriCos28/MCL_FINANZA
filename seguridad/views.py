from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
# Create your views here.
# seguridad/views.py
import json
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group, Permission
from django.views.decorators.http import require_http_methods
from django.core.cache import cache
from .models import Modulo, PermisoModulo, UserPermissionOverride
from finanzas import VERSION


# ══════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════

def _es_admin(user):
    return user.is_active and (user.is_superuser or user.is_staff)


def _serializar_override(ov):
    modulo_nombre  = None
    modulo_slug    = None
    nombre_legible = ov.permiso.codename

    # modulo_info es ahora un ForeignKey (reverse relation)
    info = ov.permiso.modulo_info.first()
    if info:
        modulo_nombre  = info.modulo.nombre
        modulo_slug    = info.modulo.slug
        nombre_legible = info.nombre_legible

    return {
        'id':           ov.id,
        'permiso_id':   ov.permiso.id,
        'codename':     ov.permiso.codename,
        'nombre':       nombre_legible,
        'modulo':       modulo_nombre,
        'modulo_slug':  modulo_slug,
        'tiene_acceso': ov.tiene_acceso,
        'tipo':         'CONCEDE' if ov.tiene_acceso else 'BLOQUEA',
        'motivo':       ov.motivo,
        'creado_en':    ov.creado_en.strftime('%Y-%m-%d %H:%M'),
        'creado_por':   ov.creado_por.username if ov.creado_por else None,
    }


def _serializar_rol(group):
    permisos = []
    for perm in group.permissions.select_related('content_type').prefetch_related('modulo_info__modulo'):
        modulo_nombre  = None
        modulo_slug    = None
        nombre_legible = perm.name

        # modulo_info es ahora un ForeignKey, por lo que usamos .first()
        info = perm.modulo_info.first()
        if info:
            modulo_nombre  = info.modulo.nombre
            modulo_slug    = info.modulo.slug
            nombre_legible = info.nombre_legible

        permisos.append({
            'id':          perm.id,
            'codename':    perm.codename,
            'nombre':      nombre_legible,
            'modulo':      modulo_nombre,
            'modulo_slug': modulo_slug,
        })

    return {
        'id':               group.id,
        'nombre':           group.name,
        'total_usuarios':   group.user_set.count(),
        'permisos':         permisos,
    }


def _serializar_usuario(user):
    return {
        'id':         user.id,
        'username':   user.username,
        'first_name': user.first_name,
        'last_name':  user.last_name,
        'nombre':     f"{user.first_name} {user.last_name}".strip() or user.username,
        'email':      user.email,
        'roles':      list(user.groups.values('id', 'name')),
        'overrides': [
            _serializar_override(ov)
            for ov in user.overrides.select_related('permiso__content_type').prefetch_related('permiso__modulo_info__modulo')
        ],
    }


# ══════════════════════════════════════════════════════════════
#  CAPACIDADES — lo que usa el frontend del usuario logueado
# ══════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET"])
def obtener_capacidades(request):
    """
    GET /api/capacidades/
    Devuelve los módulos y acciones que el usuario puede ver/hacer.
    Resultado cacheado 5 min por usuario; se limpia automáticamente
    cuando cambia un override (via signals.py).
    """
    user      = request.user
    cache_key = f"caps_{user.id}"

    cached = cache.get(cache_key)
    if cached:
        response = JsonResponse(cached)
        response['Cache-Control'] = 'no-store, private'
        return response

    modulos = Modulo.objects.filter(activo=True).prefetch_related(
        'permisos__permiso__content_type'
    ).order_by('orden')

    menu = []
    for mod in modulos:
        acciones = []
        for pm in mod.permisos.all():
            perm_str = f"{pm.permiso.content_type.app_label}.{pm.permiso.codename}"
            if user.has_perm(perm_str):
                acciones.append({
                    'codename': pm.permiso.codename,
                    'label':    pm.nombre_legible,
                })
        if acciones:
            menu.append({
                'slug':     mod.slug,
                'nombre':   mod.nombre,
                'icono':    mod.icono,
                'acciones': acciones,
            })

    payload = {'menu': menu}
    cache.set(cache_key, payload, timeout=300)

    response = JsonResponse(payload)
    response['Cache-Control'] = 'no-store, private'
    return response


@login_required
@user_passes_test(_es_admin)
def roles_index(request):
    """
    Renders the main Roles and Permissions management page.
    """
    return render(request, 'seguridad/roles.html', {'version': VERSION})


# ══════════════════════════════════════════════════════════════
#  ROLES — gestión de Grupos de Django
# ══════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET", "POST"])
def lista_roles(request):
    """
    GET  /api/roles/  → lista todos los roles
    POST /api/roles/  → crea un rol nuevo
        body: { "nombre": "Cajero", "permiso_ids": [1, 2, 3] }
    """
    if not _es_admin(request.user):
        return JsonResponse({'error': 'Sin autorización'}, status=403)

    if request.method == 'GET':
        roles = Group.objects.prefetch_related(
            'permissions__content_type',
            'permissions__modulo_info__modulo'
        ).order_by('name')
        return JsonResponse({'roles': [_serializar_rol(r) for r in roles]})

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    nombre = body.get('nombre', '').strip()
    if not nombre:
        return JsonResponse({'error': 'El nombre del rol es requerido'}, status=400)

    if Group.objects.filter(name__iexact=nombre).exists():
        return JsonResponse(
            {'error': f'Ya existe un rol llamado "{nombre}"'}, status=400
        )

    rol = Group.objects.create(name=nombre)

    permiso_ids = body.get('permiso_ids', [])
    if permiso_ids:
        rol.permissions.set(Permission.objects.filter(id__in=permiso_ids))

    return JsonResponse({'rol': _serializar_rol(rol)}, status=201)


@login_required
@require_http_methods(["GET", "PUT", "DELETE"])
def detalle_rol(request, rol_id):
    """
    GET    /api/roles/<id>/  → detalle con permisos
    PUT    /api/roles/<id>/  → editar nombre y/o permisos
        body: { "nombre": "Nuevo nombre", "permiso_ids": [1,4,7] }
    DELETE /api/roles/<id>/  → eliminar (solo si no tiene usuarios)
    """
    if not _es_admin(request.user):
        return JsonResponse({'error': 'Sin autorización'}, status=403)

    try:
        rol = Group.objects.prefetch_related(
            'permissions__content_type',
            'permissions__modulo_info__modulo'
        ).get(id=rol_id)
    except Group.DoesNotExist:
        return JsonResponse({'error': 'Rol no encontrado'}, status=404)

    if request.method == 'GET':
        return JsonResponse({'rol': _serializar_rol(rol)})

    if request.method == 'PUT':
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON inválido'}, status=400)

        nuevo_nombre = body.get('nombre', '').strip()
        if nuevo_nombre and nuevo_nombre != rol.name:
            if Group.objects.filter(name__iexact=nuevo_nombre).exclude(id=rol_id).exists():
                return JsonResponse(
                    {'error': f'Ya existe otro rol llamado "{nuevo_nombre}"'}, status=400
                )
            rol.name = nuevo_nombre
            rol.save()

        if 'permiso_ids' in body:
            rol.permissions.set(Permission.objects.filter(id__in=body['permiso_ids']))
            # Refrescar para evitar problemas de prefetch cache
            rol = Group.objects.prefetch_related(
                'permissions__content_type',
                'permissions__modulo_info__modulo'
            ).get(id=rol_id)

        return JsonResponse({'rol': _serializar_rol(rol)})

    if request.method == 'DELETE':
        total = rol.user_set.count()
        if total > 0:
            return JsonResponse({
                'error': f'No se puede eliminar: {total} usuario(s) tienen este rol. '
                         'Reasígnalos primero.'
            }, status=400)
        nombre = rol.name
        rol.delete()
        return JsonResponse({'mensaje': f'Rol "{nombre}" eliminado'})


@login_required
@require_http_methods(["GET"])
def permisos_disponibles(request):
    """
    GET /api/roles/permisos-disponibles/
    Todos los permisos del sistema agrupados por módulo.
    Se usa para poblar el selector al crear/editar un rol.
    """
    if not _es_admin(request.user):
        return JsonResponse({'error': 'Sin autorización'}, status=403)

    items = PermisoModulo.objects.select_related(
        'permiso__content_type', 'modulo'
    ).order_by('modulo__orden', 'permiso__codename')

    modulos_dict = {}
    for pm in items:
        slug = pm.modulo.slug
        if slug not in modulos_dict:
            modulos_dict[slug] = {
                'modulo_id': pm.modulo.id,
                'nombre':    pm.modulo.nombre,
                'slug':      slug,
                'icono':     pm.modulo.icono,
                'permisos':  [],
            }
        modulos_dict[slug]['permisos'].append({
            'id':       pm.permiso.id,
            'codename': pm.permiso.codename,
            'nombre':   pm.nombre_legible,
        })

    return JsonResponse({'modulos': list(modulos_dict.values())})


@login_required
@require_http_methods(["GET"])
def usuarios_del_rol(request, rol_id):
    """
    GET /api/roles/<id>/usuarios/
    Lista los usuarios activos que tienen ese rol.
    """
    if not _es_admin(request.user):
        return JsonResponse({'error': 'Sin autorización'}, status=403)

    try:
        rol = Group.objects.get(id=rol_id)
    except Group.DoesNotExist:
        return JsonResponse({'error': 'Rol no encontrado'}, status=404)

    usuarios = rol.user_set.filter(is_active=True).values(
        'id', 'username', 'first_name', 'last_name', 'email'
    )
    return JsonResponse({'rol': rol.name, 'usuarios': list(usuarios)})


@login_required
@user_passes_test(_es_admin)
def lista_usuarios_api(request):
    """
    GET  /api/usuarios/  → lista todos los usuarios
    POST /api/usuarios/  → crea un usuario nuevo
        body: { "username": "...", "password": "...", "first_name": "...", "last_name": "...", "email": "...", "rol_ids": [1, 2] }
    """
    if request.method == 'GET':
        usuarios = User.objects.all().prefetch_related('groups', 'overrides').order_by('username')
        return JsonResponse({'usuarios': [_serializar_usuario(u) for u in usuarios]})

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    username = body.get('username', '').strip()
    password = body.get('password', '').strip()
    email    = body.get('email', '').strip()

    if not username or not password:
        return JsonResponse({'error': 'Username y password son requeridos'}, status=400)

    if User.objects.filter(username=username).exists():
        return JsonResponse({'error': f'El usuario "{username}" ya existe'}, status=400)

    user = User.objects.create_user(
        username=username,
        password=password,
        email=email,
        first_name=body.get('first_name', ''),
        last_name=body.get('last_name', '')
    )

    rol_ids = body.get('rol_ids', [])
    if rol_ids:
        # Business rule: solo un rol por usuario. Tomamos el primero.
        user.groups.set(Group.objects.filter(id__in=rol_ids[:1]))

    return JsonResponse({'usuario': _serializar_usuario(user)}, status=201)


@login_required
@user_passes_test(_es_admin)
def detalle_usuario_api(request, user_id):
    """
    GET    /api/usuarios/<id>/  → detalle
    PUT    /api/usuarios/<id>/  → editar (nombre, email, roles, password opcional)
    DELETE /api/usuarios/<id>/  → eliminar (o desactivar)
    """
    try:
        usuario = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({'error': 'Usuario no encontrado'}, status=404)

    if request.method == 'GET':
        return JsonResponse({'usuario': _serializar_usuario(usuario)})

    if request.method == 'PUT':
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON inválido'}, status=400)

        usuario.first_name = body.get('first_name', usuario.first_name)
        usuario.last_name  = body.get('last_name', usuario.last_name)
        usuario.email      = body.get('email', usuario.email)
        
        nuevo_pass = body.get('password', '').strip()
        if nuevo_pass:
            usuario.set_password(nuevo_pass)
            
        usuario.save()

        if 'rol_ids' in body:
            # Business rule: solo un rol por usuario.
            usuario.groups.set(Group.objects.filter(id__in=body['rol_ids'][:1]))

        return JsonResponse({'usuario': _serializar_usuario(usuario)})

    if request.method == 'DELETE':
        if usuario == request.user:
            return JsonResponse({'error': 'No puedes eliminarte a ti mismo'}, status=400)
        nombre = usuario.username
        usuario.delete()
        return JsonResponse({'mensaje': f'Usuario "{nombre}" eliminado'})


# ══════════════════════════════════════════════════════════════
#  OVERRIDES — excepciones individuales por usuario
# ══════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET"])
def lista_usuarios_con_overrides(request):
    """
    GET /api/overrides/usuarios/
    Todos los usuarios activos con sus overrides actuales.
    """
    if not _es_admin(request.user):
        return JsonResponse({'error': 'Sin autorización'}, status=403)

    usuarios = User.objects.filter(is_active=True).prefetch_related(
        'groups',
        'overrides__permiso__content_type',
        'overrides__permiso__modulo_info__modulo',
        'overrides__creado_por',
    ).order_by('username')

    return JsonResponse({
        'usuarios': [_serializar_usuario(u) for u in usuarios]
    })


@login_required
@require_http_methods(["GET"])
def detalle_usuario_overrides(request, user_id):
    """
    GET /api/overrides/usuario/<user_id>/
    Detalle de un usuario: sus roles + todos sus overrides.
    """
    if not _es_admin(request.user):
        return JsonResponse({'error': 'Sin autorización'}, status=403)

    try:
        usuario = User.objects.prefetch_related(
            'groups',
            'overrides__permiso__content_type',
            'overrides__permiso__modulo_info__modulo',
            'overrides__creado_por',
        ).get(id=user_id, is_active=True)
    except User.DoesNotExist:
        return JsonResponse({'error': 'Usuario no encontrado'}, status=404)

    return JsonResponse({'usuario': _serializar_usuario(usuario)})


@login_required
@require_http_methods(["POST"])
def crear_override(request, user_id):
    """
    POST /api/overrides/usuario/<user_id>/crear/
    Crea un override para ese usuario.
    body: {
        "permiso_id":   15,
        "tiene_acceso": true,
        "motivo":       "El cliente lo solicitó"
    }
    """
    if not _es_admin(request.user):
        return JsonResponse({'error': 'Sin autorización'}, status=403)

    try:
        usuario = User.objects.get(id=user_id, is_active=True)
    except User.DoesNotExist:
        return JsonResponse({'error': 'Usuario no encontrado'}, status=404)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    permiso_id   = body.get('permiso_id')
    tiene_acceso = body.get('tiene_acceso')
    motivo       = body.get('motivo', '').strip()

    if permiso_id is None:
        return JsonResponse({'error': 'permiso_id es requerido'}, status=400)
    if tiene_acceso is None:
        return JsonResponse({'error': 'tiene_acceso es requerido (true o false)'}, status=400)

    try:
        permiso = Permission.objects.select_related('content_type').prefetch_related('modulo_info__modulo').get(id=permiso_id)
    except Permission.DoesNotExist:
        return JsonResponse({'error': 'Permiso no encontrado'}, status=404)

    if UserPermissionOverride.objects.filter(usuario=usuario, permiso=permiso).exists():
        return JsonResponse({
            'error': f'Ya existe un override para "{usuario.username}" '
                     f'con "{permiso.codename}". Usa PUT para modificarlo.'
        }, status=400)

    override = UserPermissionOverride.objects.create(
        usuario      = usuario,
        permiso      = permiso,
        tiene_acceso = bool(tiene_acceso),
        motivo       = motivo,
        creado_por   = request.user,
    )

    return JsonResponse({'override': _serializar_override(override)}, status=201)


@login_required
@require_http_methods(["PUT", "DELETE"])
def modificar_override(request, override_id):
    """
    PUT    /api/overrides/<id>/  → cambia tiene_acceso o motivo
        body: { "tiene_acceso": false, "motivo": "Corrección" }
    DELETE /api/overrides/<id>/  → elimina override, usuario vuelve a depender del rol
    """
    if not _es_admin(request.user):
        return JsonResponse({'error': 'Sin autorización'}, status=403)

    try:
        override = UserPermissionOverride.objects.select_related(
            'creado_por',
            'usuario',
        ).prefetch_related(
            'permiso__content_type',
            'permiso__modulo_info__modulo',
        ).get(id=override_id)
    except UserPermissionOverride.DoesNotExist:
        return JsonResponse({'error': 'Override no encontrado'}, status=404)

    if request.method == 'PUT':
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON inválido'}, status=400)

        if 'tiene_acceso' in body:
            override.tiene_acceso = bool(body['tiene_acceso'])
        if 'motivo' in body:
            override.motivo = body['motivo'].strip()

        override.save()
        return JsonResponse({'override': _serializar_override(override)})

    if request.method == 'DELETE':
        info = {
            'usuario': override.usuario.username,
            'permiso': override.permiso.codename,
            'tipo':    'CONCEDE' if override.tiene_acceso else 'BLOQUEA',
        }
        override.delete()
        return JsonResponse({
            'mensaje': f'Override eliminado. "{info["usuario"]}" '
                       'vuelve a depender solo de su rol.',
            'detalle': info,
        })


@login_required
@require_http_methods(["GET"])
def permisos_disponibles_para_usuario(request, user_id):
    """
    GET /api/overrides/permisos-disponibles/<user_id>/
    Devuelve dos listas para el selector del formulario:
      puede_conceder → no está en su rol, se le puede dar extra
      puede_bloquear → sí está en su rol, se le puede quitar
    Los permisos que ya tienen override no aparecen.
    """
    if not _es_admin(request.user):
        return JsonResponse({'error': 'Sin autorización'}, status=403)

    try:
        usuario = User.objects.prefetch_related('groups__permissions').get(
            id=user_id, is_active=True
        )
    except User.DoesNotExist:
        return JsonResponse({'error': 'Usuario no encontrado'}, status=404)

    permisos_del_rol = {
        perm.id
        for group in usuario.groups.all()
        for perm in group.permissions.all()
    }

    overrides_existentes = set(
        UserPermissionOverride.objects.filter(usuario=usuario)
        .values_list('permiso_id', flat=True)
    )

    todos = PermisoModulo.objects.select_related(
        'permiso__content_type', 'modulo'
    ).order_by('modulo__orden', 'permiso__codename')

    puede_conceder = []
    puede_bloquear = []

    for pm in todos:
        if pm.permiso.id in overrides_existentes:
            continue

        entrada = {
            'permiso_id':  pm.permiso.id,
            'codename':    pm.permiso.codename,
            'nombre':      pm.nombre_legible,
            'modulo':      pm.modulo.nombre,
            'modulo_slug': pm.modulo.slug,
        }

        if pm.permiso.id in permisos_del_rol:
            puede_bloquear.append(entrada)
        else:
            puede_conceder.append(entrada)

    return JsonResponse({
        'usuario':        usuario.username,
        'puede_conceder': puede_conceder,
        'puede_bloquear': puede_bloquear,
    })
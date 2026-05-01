# seguridad/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Capacidades del usuario logueado
    path('api/capacidades/',                              views.obtener_capacidades,               name='capacidades'),

    path('roles/',                                        views.roles_index,                       name='roles-index'),

    # Roles
    path('api/roles/',                                    views.lista_roles,                       name='roles-lista'),
    path('api/roles/permisos-disponibles/',               views.permisos_disponibles,              name='roles-permisos'),
    path('api/roles/<int:rol_id>/',                       views.detalle_rol,                       name='roles-detalle'),
    path('api/roles/<int:rol_id>/usuarios/',              views.usuarios_del_rol,                  name='roles-usuarios'),

    # Overrides
    path('api/overrides/usuarios/',                       views.lista_usuarios_con_overrides,      name='overrides-usuarios'),
    path('api/overrides/usuario/<int:user_id>/',          views.detalle_usuario_overrides,         name='overrides-usuario'),
    path('api/overrides/usuario/<int:user_id>/crear/',    views.crear_override,                    name='overrides-crear'),
    path('api/overrides/permisos-disponibles/<int:user_id>/', views.permisos_disponibles_para_usuario, name='overrides-permisos'),
    path('api/overrides/<int:override_id>/',              views.modificar_override,                name='overrides-modificar'),

    # Usuarios (Gestión General)
    path('api/usuarios/',                                 views.lista_usuarios_api,                name='usuarios-lista'),
    path('api/usuarios/<int:user_id>/',                   views.detalle_usuario_api,               name='usuarios-detalle'),
]
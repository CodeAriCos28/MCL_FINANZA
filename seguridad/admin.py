from django.contrib import admin
from .models import Modulo, PermisoModulo, UserPermissionOverride

@admin.register(Modulo)
class ModuloAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'url_name', 'icono', 'orden', 'activo')
    list_editable = ('orden', 'activo')
    prepopulated_fields = {'slug': ('nombre',)}
    search_fields = ('nombre', 'url_name')
    ordering = ('orden',)

@admin.register(PermisoModulo)
class PermisoModuloAdmin(admin.ModelAdmin):
    list_display = ('nombre_legible', 'modulo', 'permiso')
    list_filter = ('modulo',)
    search_fields = ('nombre_legible', 'permiso__codename')

@admin.register(UserPermissionOverride)
class UserPermissionOverrideAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'permiso', 'tiene_acceso', 'creado_en')
    list_filter = ('tiene_acceso', 'usuario')
    search_fields = ('usuario__username', 'permiso__codename')
    readonly_fields = ('creado_en',)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)

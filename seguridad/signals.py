# seguridad/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import UserPermissionOverride


@receiver(post_save,   sender=UserPermissionOverride)
@receiver(post_delete, sender=UserPermissionOverride)
def invalidar_cache_usuario(sender, instance, **kwargs):
    cache.delete(f"caps_{instance.usuario_id}")
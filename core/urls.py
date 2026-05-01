"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
# from django.contrib import admin
# from django.urls import path

# urlpatterns = [
#     path('admin/', admin.site.urls),
# ]
from finanzas import views as finanza_views
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static, serve
from finanzas.views import *




urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('finanzas.urls')),
    path('', include('seguridad.urls')), 

]

# Servir archivos multimedia en desarrollo
if not settings.DEBUG: # O incluso sin el IF, ya que es para el EXE
    urlpatterns += [
        re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    ]


# handler400 = "finanzas.views.error_400"
# handler403 = "finanzas.views.error_403"
# handler404 = "finanzas.views.error_404"
# handler500 = "finanzas.views.error_500"

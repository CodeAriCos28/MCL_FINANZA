from django.urls import path
from django.contrib import admin
from . import views

urlpatterns = [
    path('', views.login, name='index'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout_view, name='logout'),
# ===============================================================================================================
#                                       MÓDULO CONVERTIDOR - URLs
# ================================================================================================================
    path('convertidor/', views.convertidor_index, name='convertidor'),
    path('convertidor/registrar/', views.convertidor_registrar, name='convertidor_registrar'),
    path('convertidor/historial/', views.convertidor_historial, name='convertidor_historial'),
    path('convertidor/editar/<int:id>/', views.convertidor_editar, name='convertidor_editar'),
    path('convertidor/eliminar/<int:id>/', views.convertidor_eliminar, name='convertidor_eliminar'),
    path('convertidor/reporte-pdf/', views.convertidor_reporte_pdf, name='convertidor_reporte_pdf'),
    path('convertidor/reporte-detalle-pdf/<int:id>/', views.convertidor_reporte_detalle_pdf, name='convertidor_reporte_detalle_pdf'),
    path('api/convertidor/movimientos/', views.api_movimientos, name='api_movimientos'),
    path('api/convertidor/estadisticas/', views.api_estadisticas, name='api_estadisticas'),
    
     # ============================================================================================================
    #                                   URLs PRINCIPALES DEL MÓDULO GASTOS
    # =============================================================================================================
    path('gastos/', views.gastos_index, name='gastos'),
    path('gastos/crear/', views.gastos_crear, name='gastos_crear'),
    path('gastos/editar/<int:pk>/', views.gastos_editar, name='gastos_editar'),
    path('gastos/eliminar/<int:pk>/', views.gastos_eliminar, name='gastos_eliminar'),
    path('gastos/pdf/<int:pk>/', views.gastos_pdf, name='gastos_pdf'),
    path('gastos/pdf-historial/', views.gastos_pdf_historial, name='gastos_pdf_historial'),
    path('gastos/imprimir/', views.gastos_imprimir_historial, name='gastos_imprimir_historial'),
    path('api/gastos/', views.api_gastos, name='api_gastos'),
    path('api/categorias/', views.api_categorias, name='api_categorias'),
    path('api/dashboard/', views.api_dashboard, name='api_dashboard'),
    path('api/gastos/<int:pk>/', views.gastos_editar, name='api_gastos_detail'),
    path('api/gastos/<int:pk>/delete/', views.gastos_eliminar, name='api_gastos_delete'),
    
    # =========================================================================
    # MÓDULO SERVICIOS - URLs
    # =========================================================================
    path('servicios/', views.servicios_index, name='servicios'),
    path('servicios/crear/', views.servicios_crear, name='servicios_crear'),
    path('servicios/editar/<int:pk>/', views.servicios_editar, name='servicios_editar'),
    path('servicios/eliminar/<int:pk>/', views.servicios_eliminar, name='servicios_eliminar'),
    path('servicios/pdf/<int:pk>/', views.servicios_pdf, name='servicios_pdf'),
    path('servicios/pdf-historial/', views.servicios_pdf_historial, name='servicios_pdf_historial'),
    path('servicios/imprimir-historial/', views.servicios_imprimir_historial, name='servicios_imprimir_historial'),
    path('servicios/tipos-servicio/', views.servicios_tipos, name='servicios_tipos'),  # Esta es importante
    path('servicios/proveedores/', views.servicios_proveedores, name='servicios_proveedores'),
    path('servicios/proveedores/', views.servicios_proveedores, name='servicios_proveedores'),
    path('servicios/metodos-pago/', views.servicios_metodos_pago, name='servicios_metodos_pago'),
    
    
 
    path('dashboard/', views.dashboard_index, name='dashboard'),
    path('dashboard/api/', views.dashboard_api, name='dashboard_api'), 
]
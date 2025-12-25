# ----------------------------------------------------------------------
# 1. IMPORTS DE LA BIBLIOTECA ESTÁNDAR (Standard Library)
# ----------------------------------------------------------------------
import os
import json
from decimal import Decimal
from datetime import datetime, timedelta
from finanzas import VERSION

# ----------------------------------------------------------------------
# 2. IMPORTS DE TERCEROS (Third-Party)
# ----------------------------------------------------------------------
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import Table, TableStyle
from reportlab.lib.pagesizes import letter, A4, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch, cm
from reportlab.platypus.flowables import HRFlowable, KeepTogether
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO

# ----------------------------------------------------------------------
# 3. IMPORTS DE DJANGO
# ----------------------------------------------------------------------
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Sum, Q, F, Count
from django.db.models.functions import Coalesce, TruncMonth, TruncDay
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib.messages import get_messages

# ----------------------------------------------------------------------
# 4. IMPORTS DE APLICACIONES LOCALES
# ----------------------------------------------------------------------
from finanzas.models import Gasto, MovimientoEntrada, ServicioPago, SERVICIOS_TIPOS

def login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # Autenticar usuario
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            # Login exitoso
            auth_login(request, user)
            messages.success(request, f'¡Bienvenido {user.username}!')
            return redirect('convertidor')  # Redirigir inmediatamente
        else:
            # Credenciales inválidas - mostrar error en la misma página
            messages.error(request, 'Usuario o contraseña incorrectos')
            return render(request, 'finanzas/index.html')
    
    # Si es GET, mostrar el formulario de login
    return render(request, 'finanzas/index.html')

def logout_view(request):
    """Vista para cerrar sesión"""
    from django.contrib.auth import logout
    logout(request)
    messages.success(request, 'Sesión cerrada exitosamente')
    return redirect('login')




# =============================================================================
# MÓDULO CONVERTIDOR - VISTAS
# =============================================================================

def convertidor_index(request):
    """
    Vista principal del módulo convertidor
    """
    # Obtener parámetros de filtro
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    descripcion = request.GET.get('descripcion')
    monto_min = request.GET.get('monto_min')
    
    # Aplicar filtros
    movimientos = MovimientoEntrada.objects.all()
    
    if fecha_inicio:
        movimientos = movimientos.filter(fecha__date__gte=fecha_inicio)
    if fecha_fin:
        movimientos = movimientos.filter(fecha__date__lte=fecha_fin)
    if descripcion:
        movimientos = movimientos.filter(descripcion__icontains=descripcion)
    if monto_min:
        movimientos = movimientos.filter(monto_usd__gte=monto_min)
    
    # Calcular estadísticas para las cards
    total_usd = movimientos.aggregate(total=Sum('monto_usd'))['total'] or 0
    total_rd = movimientos.aggregate(total=Sum('monto_pesos'))['total'] or 0
    total_movimientos = movimientos.count()
    
    # Obtener últimos 5 movimientos
    ultimos_movimientos = movimientos.order_by('-fecha')[:5]
    
    # Obtener mensajes y convertirlos a JSON seguro
    messages_data = []
    for message in get_messages(request):
        messages_data.append({
            'text': str(message),
            'tags': message.tags
        })
    
    # UN solo contexto con TODAS las variables
    context = {
        'user': request.user,
        'django_messages_json': json.dumps(messages_data),
        'movimientos': ultimos_movimientos,
        'total_usd': total_usd,
        'total_rd': total_rd,
        'total_movimientos': total_movimientos,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'descripcion': descripcion,
        'monto_min': monto_min,
        'version': VERSION,  # ← Aquí está la versión
    }
    
    return render(request, 'finanzas/convertidor.html', context)

# =============================================================================
# REGISTRAR MOVIMIENTO - CON MANEJO DE IMÁGENES
# =============================================================================

def convertidor_registrar(request):
    """
    Maneja el registro de nuevos movimientos de conversión - VERSIÓN CORREGIDA
    """
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            monto_usd = request.POST.get('monto_usd')
            tasa_cambio = request.POST.get('tasa_cambio')
            descripcion = request.POST.get('descripcion', '').strip()
            fecha = request.POST.get('fecha')
            imagen = request.FILES.get('imagen')  # Obtener la imagen

            print(f"Datos recibidos - USD: {monto_usd}, Tasa: {tasa_cambio}, Imagen: {imagen}")

            # Validaciones básicas
            if not monto_usd:
                return JsonResponse({
                    'success': False,
                    'error': 'Monto USD es obligatorio'
                })
            
            if not tasa_cambio:
                return JsonResponse({
                    'success': False,
                    'error': 'Tasa de Cambio es obligatoria'
                })

            # Convertir a decimal de forma segura
            try:
                from decimal import Decimal
                monto_usd_decimal = Decimal(str(monto_usd).replace(',', '.'))
                tasa_cambio_decimal = Decimal(str(tasa_cambio).replace(',', '.'))
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': f'Error en formato de números: {str(e)}'
                })

            # Crear nuevo movimiento
            movimiento = MovimientoEntrada(
                monto_usd=monto_usd_decimal,
                tasa_cambio=tasa_cambio_decimal,
                descripcion=descripcion if descripcion else None,
                imagen=imagen  # Asignar la imagen si existe
            )
            
            # Si se proporcionó fecha específica
            if fecha:
                try:
                    from django.utils import timezone
                    from datetime import datetime
                    # Parsear fecha de forma segura
                    fecha_dt = datetime.strptime(fecha, '%Y-%m-%d')
                    movimiento.fecha = timezone.make_aware(fecha_dt)
                except ValueError as e:
                    return JsonResponse({
                        'success': False,
                        'error': f'Formato de fecha inválido: {str(e)}'
                    })
            
            # Guardar el movimiento
            movimiento.save()
            
            print(f"Movimiento guardado exitosamente - ID: {movimiento.id}")
            
            return JsonResponse({
                'success': True,
                'message': f'Movimiento registrado exitosamente: ${movimiento.monto_usd} USD → ${movimiento.monto_pesos} DOP',
                'movimiento_id': movimiento.id
            })
            
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            print(f"ERROR COMPLETO en convertidor_registrar:")
            print(error_traceback)
            return JsonResponse({
                'success': False,
                'error': f'Error al registrar movimiento: {str(e)}',
                'debug_info': 'Revisa la consola del servidor para más detalles'
            })
    
    return JsonResponse({
        'success': False,
        'error': 'Método no permitido. Se requiere POST.'
    })
# =============================================================================
# HISTORIAL COMPLETO DEL CONVERTIDOR
# =============================================================================

def convertidor_historial(request):
    """
    Muestra el historial completo de movimientos con filtros aplicados
    """
    # Obtener parámetros de filtro
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    descripcion = request.GET.get('descripcion')
    monto_min = request.GET.get('monto_min')
    
    # Aplicar filtros
    movimientos = MovimientoEntrada.objects.all()
    
    if fecha_inicio:
        movimientos = movimientos.filter(fecha__date__gte=fecha_inicio)
    if fecha_fin:
        movimientos = movimientos.filter(fecha__date__lte=fecha_fin)
    if descripcion:
        movimientos = movimientos.filter(descripcion__icontains=descripcion)
    if monto_min:
        movimientos = movimientos.filter(monto_usd__gte=monto_min)
    
    # Ordenar por fecha descendente
    movimientos = movimientos.order_by('-fecha')
    
    # Calcular estadísticas con filtros aplicados
    total_usd = movimientos.aggregate(total=Sum('monto_usd'))['total'] or 0
    total_rd = movimientos.aggregate(total=Sum('monto_pesos'))['total'] or 0
    total_movimientos = movimientos.count()
    
    context = {
        'movimientos': movimientos,
        'total_usd': total_usd,
        'total_rd': total_rd,
        'total_movimientos': total_movimientos,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'descripcion': descripcion,
        'monto_min': monto_min,
        'es_historial_completo': True,
    }
    
    return render(request, 'finanzas/convertidor.html', context)

# =============================================================================
# EDITAR MOVIMIENTO  DEL  CONVERTIDOR
# =============================================================================

def convertidor_editar(request, id):
    """
    Edita un movimiento existente CON MANEJO DE IMÁGENES
    """
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'error': 'Método no permitido'
        })

    try:
        movimiento = get_object_or_404(MovimientoEntrada, id=id)
        
        monto_usd = request.POST.get('monto_usd')
        tasa_cambio = request.POST.get('tasa_cambio')
        descripcion = request.POST.get('descripcion', '').strip()
        fecha = request.POST.get('fecha')
        imagen = request.FILES.get('imagen')

        print(f"Editando movimiento {id} - Imagen: {imagen}")

        # Validaciones básicas
        if not monto_usd or not tasa_cambio:
            return JsonResponse({
                'success': False,
                'error': 'Monto USD y Tasa de Cambio son obligatorios'
            })

        try:
            monto_usd = float(monto_usd)
            tasa_cambio = float(tasa_cambio)
        except (TypeError, ValueError):
            return JsonResponse({
                'success': False,
                'error': 'Monto USD y Tasa de Cambio deben ser números válidos'
            })

        # Actualizar movimiento
        movimiento.monto_usd = monto_usd
        movimiento.tasa_cambio = tasa_cambio
        movimiento.descripcion = descripcion if descripcion else None

        # Manejo de imagen
        if imagen:
            # Validar tipo de archivo si es necesario
            if not imagen.content_type.startswith('image/'):
                return JsonResponse({
                    'success': False,
                    'error': 'El archivo debe ser una imagen válida'
                })
            
            # Eliminar imagen anterior si existe
            if movimiento.imagen:
                try:
                    if os.path.isfile(movimiento.imagen.path):
                        os.remove(movimiento.imagen.path)
                except Exception as e:
                    print(f"Error eliminando imagen anterior: {str(e)}")
                    # No fallar si no se puede eliminar la imagen anterior

            movimiento.imagen = imagen

        # Manejo de fecha
        if fecha:
            try:
                from django.utils import timezone
                from datetime import datetime
                movimiento.fecha = timezone.make_aware(
                    datetime.strptime(fecha, '%Y-%m-%d')
                )
            except ValueError:
                return JsonResponse({
                    'success': False,
                    'error': 'Formato de fecha inválido. Use YYYY-MM-DD'
                })

        movimiento.save()

        return JsonResponse({
            'success': True,
            'message': f'Movimiento actualizado exitosamente: ${movimiento.monto_usd} USD → ${movimiento.monto_pesos} DOP'
        })

    except MovimientoEntrada.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Movimiento no encontrado'
        })
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"Error completo al editar: {error_detail}")
        
        return JsonResponse({
            'success': False,
            'error': f'Error al actualizar movimiento: {str(e)}',
            'debug_detail': error_detail  # Solo para desarrollo, quitar en producción
        })

# =============================================================================
# ELIMINAR MOVIMIENTO - CON MANEJO DE IMÁGENES  DEL  CONVERTIDOR
# =============================================================================

def convertidor_eliminar(request, id):
    """
    Elimina un movimiento si no tiene gastos ni servicios asociados CON MANEJO DE IMÁGENES
    """
    if request.method == 'POST':
        try:
            movimiento = get_object_or_404(MovimientoEntrada, id=id)
            
            # Verificar si tiene gastos o servicios asociados
            tiene_gastos = Gasto.objects.filter(entrada=movimiento).exists()
            tiene_servicios = ServicioPago.objects.filter(entrada=movimiento).exists()
            
            if tiene_gastos or tiene_servicios:
                return JsonResponse({
                    'success': False,
                    'error': f'No se puede eliminar el movimiento porque tiene '
                            f'{"gastos" if tiene_gastos else ""} '
                            f'{"y " if tiene_gastos and tiene_servicios else ""}'
                            f'{"servicios" if tiene_servicios else ""} asociados.'
                })
            else:
                # Eliminar imagen física si existe
                if movimiento.imagen:
                    if os.path.isfile(movimiento.imagen.path):
                        os.remove(movimiento.imagen.path)
                
                movimiento.delete()
                return JsonResponse({
                    'success': True,
                    'message': 'Movimiento eliminado exitosamente'
                })
                
        except Exception as e:
            import traceback
            print(f"Error completo al eliminar: {traceback.format_exc()}")
            return JsonResponse({
                'success': False,
                'error': f'Error al eliminar movimiento: {str(e)}'
            })
    
    return JsonResponse({
        'success': False,
        'error': 'Método no permitido'
    })
# =============================================================================
# REPORTE PDF - HISTORIAL COMPLETO  DEL  CONVERTIDOR
# =============================================================================
def convertidor_reporte_pdf(request):
    """
    Genera reporte PDF profesional del historial completo de movimientos
    """
    # Aplicar filtros
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    descripcion = request.GET.get('descripcion')
    monto_min = request.GET.get('monto_min')

    movimientos = MovimientoEntrada.objects.all()

    if fecha_inicio:
        movimientos = movimientos.filter(fecha__date__gte=fecha_inicio)
    if fecha_fin:
        movimientos = movimientos.filter(fecha__date__lte=fecha_fin)
    if descripcion:
        movimientos = movimientos.filter(descripcion__icontains=descripcion)
    if monto_min:
        movimientos = movimientos.filter(monto_usd__gte=monto_min)
    
    movimientos = movimientos.order_by('-fecha')
    
    # Calcular totales
    total_movimientos = movimientos.count()
    total_usd = movimientos.aggregate(total=Sum('monto_usd'))['total'] or 0
    total_pesos = movimientos.aggregate(total=Sum('monto_pesos'))['total'] or 0
    
    # Formatear fechas para mostrar
    fecha_inicio_str = fecha_inicio if fecha_inicio else "No especificada"
    fecha_fin_str = fecha_fin if fecha_fin else "No especificada"
    
    # Si hay fechas, convertirlas al formato correcto (de YYYY-MM-DD a DD/MM/YYYY)
    if fecha_inicio:
        try:
            fecha_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d')
            fecha_inicio_str = fecha_obj.strftime('%d/%m/%Y')
        except:
            pass
    
    if fecha_fin:
        try:
            fecha_obj = datetime.strptime(fecha_fin, '%Y-%m-%d')
            fecha_fin_str = fecha_obj.strftime('%d/%m/%Y')
        except:
            pass
    
    # Crear buffer para el PDF
    buffer = BytesIO()
    
    # Crear documento en modo portrait (A4 vertical)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5*cm,
        leftMargin=1.5*cm,
        topMargin=2*cm,
        bottomMargin=1.5*cm,
        title="Reporte de Conversiones de Divisas"
    )
    
    # Estilos personalizados
    styles = getSampleStyleSheet()
    
    # Título principal - Estilo similar al reporte de la imagen
    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Title'],
        fontSize=16,
        textColor=colors.black,
        spaceAfter=12,
        alignment=1,  # Centrado
        fontName='Helvetica-Bold',
        leading=18
    )
    
    # Estilo para encabezados de sección
    section_style = ParagraphStyle(
        'SectionStyle',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.black,
        spaceAfter=8,
        fontName='Helvetica-Bold',
        alignment=0,  # Izquierda
        leading=14,
        leftIndent=0
    )
    
    # Estilo para información normal
    normal_style = ParagraphStyle(
        'NormalStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.black,
        spaceAfter=4,
        alignment=0,
        leading=12
    )
    
    # Estilo para tabla
    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.black,
        fontName='Helvetica-Bold',
        alignment=1,  # Centrado
        leading=10
    )
    
    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontSize=9,
        alignment=1,  # Centrado
        leading=10
    )
    
    table_cell_left_style = ParagraphStyle(
        'TableCellLeft',
        parent=styles['Normal'],
        fontSize=9,
        alignment=0,  # Izquierda
        leading=10
    )
    
    # Elementos del documento
    elements = []
    
    # Crear una tabla de encabezado con logo a la izquierda y título a la derecha
    header_table_data = []
    
    # Asegurarse de importar Image al inicio del archivo: from reportlab.platypus import Image
    try:
        # Intentar cargar el logo de la empresa
        # Cambia esta ruta por la ubicación real de tu logo
        logo_path = "static/img/logo.ico"  # Ajusta esta ruta según tu proyecto
        
        # Crear la imagen del logo
        logo = Image(logo_path, width=5*cm, height=3*cm)
        logo.hAlign = 'LEFT'
        
        # Crear celda con el logo
        logo_cell = logo
        
    except Exception as e:
        # Si no se puede cargar el logo, usar texto alternativo
        logo_cell = Paragraph("LOGO EMPRESA", ParagraphStyle(
            'LogoPlaceholder',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.gray,
            alignment=1,
            fontName='Helvetica-Bold'
        ))
    
    # Crear celda con los títulos
    titles_cell = [
        Paragraph("SISTEMA DE CONVERSIÓN DE DIVISAS", title_style),
        Spacer(1, 4),
        Paragraph("REPORTE HISTÓRICO DE CONVERSIONES", 
                  ParagraphStyle(
                      'SubtitleStyle',
                      parent=styles['Title'],
                      fontSize=14,
                      textColor=colors.black,
                      spaceAfter=0,
                      alignment=1,
                      fontName='Helvetica-Bold',
                      leading=16
                  ))
    ]
    
    # Crear la fila de la tabla: logo a la izquierda, títulos a la derecha
    header_table_data.append([logo_cell, titles_cell])
    
    # Crear la tabla de encabezado
    header_table = Table(header_table_data, colWidths=[4*cm, 11*cm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    
    elements.append(header_table)
    elements.append(Spacer(1, 12))
    
    # Fecha del reporte - Similar al formato de la imagen
    fecha_table_data = [
        ["Fecha del Reporte:", datetime.now().strftime('%d/%m/%Y %I:%M')]
    ]
    
    fecha_table = Table(fecha_table_data, colWidths=[4*cm, 11*cm])
    fecha_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('PADDING', (0, 0), (-1, -1), (4, 6)),
    ]))
    
    elements.append(fecha_table)
    elements.append(Spacer(1, 16))
    
    # DATOS DEL REPORTE (similar a "Datos del Cliente" en la imagen)
    elements.append(Paragraph("DATOS DEL REPORTE", section_style))
    elements.append(Spacer(1, 6))
    
    # Construir datos del reporte dinámicamente
    datos_reporte = []
    datos_reporte.append(["Usuario Encargado:", request.user.get_full_name() or request.user.username])
    datos_reporte.append(["Total de registros:", str(total_movimientos)])
    
    # Solo agregar filtros si se aplicaron
    if fecha_inicio or fecha_fin:
        datos_reporte.append(["Período del reporte:", f"Del {fecha_inicio_str} al {fecha_fin_str}"])
    
    if descripcion:
        datos_reporte.append(["Descripción filtrada:", descripcion])
    
    if monto_min:
        datos_reporte.append(["Monto mínimo (USD):", f"${monto_min}"])
    
    # Agregar información de totales
    datos_reporte.append(["Total USD:", f"$ {total_usd:,.2f}"])
    datos_reporte.append(["Total Pesos:", f"$ {total_pesos:,.2f}"])
    
    datos_table = Table(datos_reporte, colWidths=[5*cm, 10*cm])
    datos_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('PADDING', (0, 0), (-1, -1), (4, 6)),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
    ]))
    
    elements.append(datos_table)
    elements.append(Spacer(1, 16))
    
    # RESÚMENES TOTALES (similar a la tabla de componentes en la imagen)
    if movimientos.exists():
        elements.append(Paragraph("DETALLE DE CONVERSIONES", section_style))
        elements.append(Spacer(1, 6))
        
        # Preparar datos de la tabla
        table_data = []
        
        # Encabezados - similar al reporte de la imagen
        headers = [
            Paragraph("Nº", table_header_style),
            Paragraph("FECHA", table_header_style),
            Paragraph("DESCRIPCIÓN", table_header_style),
            Paragraph("USD", table_header_style),
            Paragraph("TASA", table_header_style),
            Paragraph("PESOS", table_header_style),
            Paragraph("ESTADO", table_header_style)
        ]
        table_data.append(headers)
        
        # Agregar filas de datos
        for idx, mov in enumerate(movimientos, 1):
            # Formatear fecha usando el método del modelo
            fecha_formateada = mov.fecha_formateada if hasattr(mov, 'fecha_formateada') else mov.fecha.strftime('%d/%m/%Y')
            
            descripcion_text = mov.descripcion or 'Sin descripción'
            if len(descripcion_text) > 25:
                descripcion_text = descripcion_text[:22] + "..."
            
            row = [
                Paragraph(str(idx), table_cell_style),
                Paragraph(fecha_formateada, table_cell_style),
                Paragraph(descripcion_text, table_cell_left_style),
                Paragraph(f"$ {mov.monto_usd:,.2f}", table_cell_style),
                Paragraph(f"$ {mov.tasa_cambio:,.2f}", table_cell_style),
                Paragraph(f"$ {mov.monto_pesos:,.2f}", table_cell_style),
                Paragraph("Completado", table_cell_style)
            ]
            table_data.append(row)
        
        # Anchos de columna
        col_widths = [1.2*cm, 2.5*cm, 4.5*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm]
        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        
        # Estilos de la tabla - similar al reporte de la imagen
        table_style = TableStyle([
            # Encabezado
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f0f0')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
            
            # Bordes - similares al reporte de la imagen
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            
            # Alineación
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),
            ('ALIGN', (1, 1), (1, -1), 'CENTER'),
            ('ALIGN', (2, 1), (2, -1), 'LEFT'),
            ('ALIGN', (3, 1), (5, -1), 'RIGHT'),
            ('ALIGN', (6, 1), (6, -1), 'CENTER'),
            
            # Padding
            ('PADDING', (0, 0), (-1, -1), (4, 4)),
            
            # Filas alternas
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ])
        
        # Alternar colores de fila
        for i in range(1, len(table_data)):
            if i % 2 == 0:
                table_style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor('#f8f8f8'))
        
        table.setStyle(table_style)
        elements.append(table)
    else:
        # Mensaje cuando no hay datos
        no_data_style = ParagraphStyle(
            'NoData',
            parent=styles['Normal'],
            fontSize=12,
            textColor=colors.black,
            spaceAfter=15,
            alignment=1,
            fontName='Helvetica-Bold',
            leading=14
        )
        elements.append(Spacer(1, 20))
        elements.append(Paragraph("NO SE ENCONTRARON MOVIMIENTOS", no_data_style))
        elements.append(Spacer(1, 15))
    
    elements.append(Spacer(1, 20))
    
    # OBSERVACIONES (similar a la sección de observaciones en la imagen)
    elements.append(Paragraph("OBSERVACIONES", section_style))
    elements.append(Spacer(1, 6))
    
    # Crear observaciones dinámicas
    observaciones_text = "Reporte generado automáticamente por el sistema. "
    if total_movimientos > 0:
        observaciones_text += f"Se encontraron {total_movimientos} conversiones. "
        observaciones_text += f"Total convertido: ${total_usd:,.2f} USD → ${total_pesos:,.2f} DOP. "
    
    if fecha_inicio or fecha_fin:
        observaciones_text += f"Período del reporte: {fecha_inicio_str} al {fecha_fin_str}. "
    
    observaciones_style = ParagraphStyle(
        'Observaciones',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.black,
        spaceAfter=8,
        alignment=0,
        leading=12,
        leftIndent=0,
        borderWidth=1,
        borderColor=colors.black,
        padding=6
    )
    
    elements.append(Paragraph(observaciones_text, observaciones_style))
    elements.append(Spacer(1, 20))
    
    # Información del sistema (pie de página)
    footer_style = ParagraphStyle(
        'FooterStyle',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#666666'),
        spaceAfter=0,
        alignment=1,
        leading=10
    )
    
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"Sistema de Conversión de Divisas - Generado el {datetime.now().strftime('%d/%m/%Y %I:%M')}", footer_style))
    elements.append(Paragraph("Reporte válido como documentación del sistema", footer_style))
    
    # Construir el PDF
    doc.build(elements)
    
    # Obtener el valor del buffer
    pdf = buffer.getvalue()
    buffer.close()
    
    # Crear respuesta HTTP
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="reporte_conversiones_{datetime.now().strftime("%d%m%Y_%I%M%S")}.pdf"'
    response.write(pdf)
    
    return response

# =============================================================================
# REPORTE PDF - DETALLE DE MOVIMIENTO (CORREGIDO)  DEL  CONVERTIDOR
# =============================================================================
def convertidor_reporte_detalle_pdf(request, id):
    """
    Genera reporte PDF profesional de un movimiento específico
    """
    movimiento = get_object_or_404(MovimientoEntrada, id=id)
    
    # Crear buffer para el PDF
    buffer = BytesIO()
    
    # Crear documento en modo portrait (A4 vertical)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5*cm,
        leftMargin=1.5*cm,
        topMargin=1.2*cm,  # Reducido para que el logo esté más arriba
        bottomMargin=1.5*cm,
        title=f"Reporte Movimiento {id}"
    )
    
    # Estilos personalizados - MISMOS QUE EL REPORTE HISTÓRICO
    styles = getSampleStyleSheet()
    
    # Título principal - Estilo similar al reporte de la imagen
    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Title'],
        fontSize=16,
        textColor=colors.black,
        spaceAfter=12,
        alignment=1,  # Centrado
        fontName='Helvetica-Bold',
        leading=18
    )
    
    # Estilo para encabezados de sección
    section_style = ParagraphStyle(
        'SectionStyle',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.black,
        spaceAfter=8,
        fontName='Helvetica-Bold',
        alignment=0,  # Izquierda
        leading=14,
        leftIndent=0
    )
    
    # Estilo para información normal
    normal_style = ParagraphStyle(
        'NormalStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.black,
        spaceAfter=4,
        alignment=0,
        leading=12
    )
    
    # Estilo para tabla
    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.black,
        fontName='Helvetica-Bold',
        alignment=1,  # Centrado
        leading=10
    )
    
    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontSize=9,
        alignment=1,  # Centrado
        leading=10
    )
    
    table_cell_left_style = ParagraphStyle(
        'TableCellLeft',
        parent=styles['Normal'],
        fontSize=9,
        alignment=0,  # Izquierda
        leading=10
    )
    
    # Elementos del documento
    elements = []
    
    # Crear una tabla de encabezado con logo a la izquierda y título a la derecha
    header_table_data = []
    
    # Intentar cargar el logo de la empresa - MISMA RUTA QUE EL REPORTE HISTÓRICO
    try:
        logo_path = "static/img/logo.ico"  # MISMA RUTA QUE EL REPORTE HISTÓRICO
        
        # Crear la imagen del logo - TAMAÑO AJUSTADO
        logo = Image(logo_path, width=3.5*cm, height=2.5*cm)
        logo.hAlign = 'LEFT'
        
        # Crear celda con el logo
        logo_cell = logo
        
    except Exception as e:
        # Si no se puede cargar el logo, usar texto alternativo
        logo_cell = Paragraph("LOGO EMPRESA", ParagraphStyle(
            'LogoPlaceholder',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.gray,
            alignment=1,
            fontName='Helvetica-Bold'
        ))
    
    # Crear celda con los títulos - MISMO FORMATO QUE EL REPORTE HISTÓRICO
    titles_cell = [
        Paragraph("SISTEMA DE CONVERSIÓN DE DIVISAS", title_style),
        Spacer(1, 4),
        Paragraph(f"REPORTE DETALLADO - MOVIMIENTO #{id}", 
                  ParagraphStyle(
                      'SubtitleStyle',
                      parent=styles['Title'],
                      fontSize=14,
                      textColor=colors.black,
                      spaceAfter=0,
                      alignment=1,
                      fontName='Helvetica-Bold',
                      leading=16
                  ))
    ]
    
    # Crear la fila de la tabla: logo a la izquierda, títulos a la derecha
    header_table_data.append([logo_cell, titles_cell])
    
    # Crear la tabla de encabezado - AJUSTADO PARA LOGO MÁS ARRIBA
    header_table = Table(header_table_data, colWidths=[4*cm, 11*cm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('TOPPADDING', (0, 0), (0, 0), -10),  # NEGATIVO PARA SUBIR EL LOGO MÁS
        ('TOPPADDING', (1, 0), (1, 0), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    
    elements.append(header_table)
    elements.append(Spacer(1, 10))
    
    # Fecha del reporte - MISMO FORMATO QUE EL REPORTE HISTÓRICO
    fecha_table_data = [
        ["Fecha del Reporte:", datetime.now().strftime('%d/%m/%Y %I:%M')]
    ]
    
    fecha_table = Table(fecha_table_data, colWidths=[4*cm, 11*cm])
    fecha_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('PADDING', (0, 0), (-1, -1), (4, 6)),
    ]))
    
    elements.append(fecha_table)
    elements.append(Spacer(1, 12))
    
    # DATOS DEL MOVIMIENTO (similar a "Datos del Reporte" en el histórico)
    elements.append(Paragraph("DATOS DEL MOVIMIENTO", section_style))
    elements.append(Spacer(1, 6))
    
    # Construir datos del movimiento dinámicamente
    datos_movimiento = []
    datos_movimiento.append(["ID del Movimiento:", f"#{id}"])
    datos_movimiento.append(["Fecha de Conversión:", movimiento.fecha.strftime('%d/%m/%Y %I:%M')])
    datos_movimiento.append(["Usuario Encargado:", request.user.get_full_name() or request.user.username])
    datos_movimiento.append(["Estado:", "Completado"])
    
    # Agregar descripción si existe
    if movimiento.descripcion:
        descripcion_text = movimiento.descripcion
        if len(descripcion_text) > 40:
            descripcion_text = descripcion_text[:37] + "..."
        datos_movimiento.append(["Descripción:", descripcion_text])
    
    datos_table = Table(datos_movimiento, colWidths=[5*cm, 10*cm])
    datos_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('PADDING', (0, 0), (-1, -1), (4, 6)),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
    ]))
    
    elements.append(datos_table)
    elements.append(Spacer(1, 16))
    
    # RESUMEN DE CONVERSIÓN (similar a "Resúmenes Totales" en el histórico)
    elements.append(Paragraph("RESUMEN DE CONVERSIÓN", section_style))
    elements.append(Spacer(1, 6))
    
    resumen_data = [
        ["Descripción", "Monto", "Estado"],
        ["Monto en USD", f"$ {movimiento.monto_usd:,.2f}", "Verificado"],
        ["Tasa de Cambio", f"$ {movimiento.tasa_cambio:,.2f}", "Aplicada"],
        ["Monto en Pesos", f"$ {movimiento.monto_pesos:,.2f}", "Calculado"],
    ]
    
    resumen_table = Table(resumen_data, colWidths=[8*cm, 4*cm, 3*cm])
    resumen_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e0e0e0')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('PADDING', (0, 0), (-1, -1), (4, 6)),
    ]))
    
    elements.append(resumen_table)
    elements.append(Spacer(1, 16))
    
    # DETALLE DE CONVERSIÓN (similar a "Detalle de Conversiones" en el histórico)
    elements.append(Paragraph("DETALLE DE CONVERSIÓN", section_style))
    elements.append(Spacer(1, 6))
    
    # Preparar datos de la tabla - MISMA ESTRUCTURA QUE EL HISTÓRICO
    table_data = []
    
    # Encabezados - igual al reporte histórico
    headers = [
        Paragraph("Nº", table_header_style),
        Paragraph("FECHA", table_header_style),
        Paragraph("DESCRIPCIÓN", table_header_style),
        Paragraph("USD", table_header_style),
        Paragraph("TASA", table_header_style),
        Paragraph("PESOS", table_header_style),
        Paragraph("ESTADO", table_header_style)
    ]
    table_data.append(headers)
    
    # Agregar fila del movimiento
    fecha_formateada = movimiento.fecha_formateada if hasattr(movimiento, 'fecha_formateada') else movimiento.fecha.strftime('%d/%m/%Y')
    
    descripcion_text = movimiento.descripcion or 'Sin descripción'
    if len(descripcion_text) > 25:
        descripcion_text = descripcion_text[:22] + "..."
    
    row = [
        Paragraph("1", table_cell_style),
        Paragraph(fecha_formateada, table_cell_style),
        Paragraph(descripcion_text, table_cell_left_style),
        Paragraph(f"$ {movimiento.monto_usd:,.2f}", table_cell_style),
        Paragraph(f"$ {movimiento.tasa_cambio:,.2f}", table_cell_style),
        Paragraph(f"$ {movimiento.monto_pesos:,.2f}", table_cell_style),
        Paragraph("Completado", table_cell_style)
    ]
    table_data.append(row)
    
    # Anchos de columna - igual al reporte histórico
    col_widths = [1.2*cm, 2.5*cm, 4.5*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm]
    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    
    # Estilos de la tabla - igual al reporte histórico
    table_style = TableStyle([
        # Encabezado
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f0f0')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        
        # Bordes
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        
        # Alineación
        ('ALIGN', (0, 1), (0, -1), 'CENTER'),
        ('ALIGN', (1, 1), (1, -1), 'CENTER'),
        ('ALIGN', (2, 1), (2, -1), 'LEFT'),
        ('ALIGN', (3, 1), (5, -1), 'RIGHT'),
        ('ALIGN', (6, 1), (6, -1), 'CENTER'),
        
        # Padding
        ('PADDING', (0, 0), (-1, -1), (4, 4)),
        
        # Fila de datos
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#f8f8f8')),
    ])
    
    table.setStyle(table_style)
    elements.append(table)
    elements.append(Spacer(1, 20))
    
    # OBSERVACIONES (igual al reporte histórico)
    elements.append(Paragraph("OBSERVACIONES", section_style))
    elements.append(Spacer(1, 6))
    
    # Crear observaciones dinámicas
    observaciones_text = "Reporte detallado de movimiento individual. "
    observaciones_text += f"Conversión realizada el {movimiento.fecha.strftime('%d/%m/%Y')}. "
    observaciones_text += f"Monto convertido: ${movimiento.monto_usd:,.2f} USD → ${movimiento.monto_pesos:,.2f} DOP."
    
    if movimiento.descripcion:
        observaciones_text += f" Notas: {movimiento.descripcion}"
    
    observaciones_style = ParagraphStyle(
        'Observaciones',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.black,
        spaceAfter=8,
        alignment=0,
        leading=12,
        leftIndent=0,
        borderWidth=1,
        borderColor=colors.black,
        padding=6
    )
    
    elements.append(Paragraph(observaciones_text, observaciones_style))
    elements.append(Spacer(1, 20))
    
    # Información del sistema (pie de página) - igual al reporte histórico
    footer_style = ParagraphStyle(
        'FooterStyle',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#666666'),
        spaceAfter=0,
        alignment=1,
        leading=10
    )
    
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"Sistema de Conversión de Divisas - Generado el {datetime.now().strftime('%d/%m/%Y %I:%M')}", footer_style))
    elements.append(Paragraph("Reporte válido como documentación del sistema", footer_style))
    
    # Construir el PDF
    doc.build(elements)
    
    # Obtener el valor del buffer
    pdf = buffer.getvalue()
    buffer.close()
    
    # Crear respuesta HTTP
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="movimiento_{id}_{datetime.now().strftime("%d%m%Y_%I%M%S")}.pdf"'
    response.write(pdf)
    
    return response
# =============================================================================
# FUNCIÓN PARA IMPRIMIR (VERSIÓN PARA IMPRESORA)
# =============================================================================
def convertidor_imprimir_todo(request):
    """
    Genera versión optimizada para impresión del historial completo
    """
    # Aplicar filtros
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    descripcion = request.GET.get('descripcion')
    monto_min = request.GET.get('monto_min')
    
    movimientos = MovimientoEntrada.objects.all()
    
    if fecha_inicio:
        movimientos = movimientos.filter(fecha__date__gte=fecha_inicio)
    if fecha_fin:
        movimientos = movimientos.filter(fecha__date__lte=fecha_fin)
    if descripcion:
        movimientos = movimientos.filter(descripcion__icontains=descripcion)
    if monto_min:
        movimientos = movimientos.filter(monto_usd__gte=monto_min)
    
    movimientos = movimientos.order_by('-fecha')
    
    # Calcular totales
    total_movimientos = movimientos.count()
    total_usd = movimientos.aggregate(total=Sum('monto_usd'))['total'] or 0
    total_pesos = movimientos.aggregate(total=Sum('monto_pesos'))['total'] or 0
    
    # Formatear fechas para mostrar
    fecha_inicio_str = fecha_inicio if fecha_inicio else "No especificada"
    fecha_fin_str = fecha_fin if fecha_fin else "No especificada"
    
    # Si hay fechas, convertirlas al formato correcto (de YYYY-MM-DD a DD/MM/YYYY)
    if fecha_inicio:
        try:
            fecha_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d')
            fecha_inicio_str = fecha_obj.strftime('%d/%m/%Y')
        except:
            pass
    
    if fecha_fin:
        try:
            fecha_obj = datetime.strptime(fecha_fin, '%Y-%m-%d')
            fecha_fin_str = fecha_obj.strftime('%d/%m/%Y')
        except:
            pass
    
    # Crear buffer para el PDF
    buffer = BytesIO()
    
    # Crear documento en modo portrait (A4 vertical)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5*cm,
        leftMargin=1.5*cm,
        topMargin=1.2*cm,  # Reducido para que el logo esté más arriba
        bottomMargin=1.5*cm,
        title="Impresión de Conversiones de Divisas"
    )
    
    # Estilos personalizados
    styles = getSampleStyleSheet()
    
    # Título principal - Estilo similar al reporte de la imagen
    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Title'],
        fontSize=16,
        textColor=colors.black,
        spaceAfter=12,
        alignment=1,  # Centrado
        fontName='Helvetica-Bold',
        leading=18
    )
    
    # Estilo para encabezados de sección
    section_style = ParagraphStyle(
        'SectionStyle',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.black,
        spaceAfter=8,
        fontName='Helvetica-Bold',
        alignment=0,  # Izquierda
        leading=14,
        leftIndent=0
    )
    
    # Estilo para información normal
    normal_style = ParagraphStyle(
        'NormalStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.black,
        spaceAfter=4,
        alignment=0,
        leading=12
    )
    
    # Estilo para tabla
    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.black,
        fontName='Helvetica-Bold',
        alignment=1,  # Centrado
        leading=10
    )
    
    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontSize=9,
        alignment=1,  # Centrado
        leading=10
    )
    
    table_cell_left_style = ParagraphStyle(
        'TableCellLeft',
        parent=styles['Normal'],
        fontSize=9,
        alignment=0,  # Izquierda
        leading=10
    )
    
    # Elementos del documento
    elements = []
    
    # Crear una tabla de encabezado con logo a la izquierda y título a la derecha
    header_table_data = []
    
    # Intentar cargar el logo de la empresa - logo más arriba y a la izquierda
    try:
        # Ruta del logo - ajusta según tu proyecto
        # Intenta varias rutas posibles
        logo_paths = ["static/img/logo.png"]
        
        logo = None
        for path in logo_paths:
            try:
                logo = Image(path, width=2.8*cm, height=2.8*cm)  # Tamaño ligeramente reducido
                break
            except:
                continue
        
        if logo:
            logo_cell = logo
        else:
            raise Exception("Logo no encontrado")
            
    except Exception as e:
        # Si no se puede cargar el logo, usar texto alternativo
        logo_cell = Paragraph("LOGO EMPRESA", ParagraphStyle(
            'LogoPlaceholder',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.gray,
            alignment=1,
            fontName='Helvetica-Bold'
        ))
    
    # Crear celda con los títulos
    titles_cell = [
        Paragraph("SISTEMA DE CONVERSIÓN DE DIVISAS", title_style),
        Spacer(1, 4),
        Paragraph("REPORTE PARA IMPRESIÓN", 
                  ParagraphStyle(
                      'SubtitleStyle',
                      parent=styles['Title'],
                      fontSize=14,
                      textColor=colors.black,
                      spaceAfter=0,
                      alignment=1,
                      fontName='Helvetica-Bold',
                      leading=16
                  ))
    ]
    
    # Crear la fila de la tabla: logo a la izquierda, títulos a la derecha
    header_table_data.append([logo_cell, titles_cell])
    
    # Crear la tabla de encabezado - ajustada para que el logo esté más arriba
    header_table = Table(header_table_data, colWidths=[3.5*cm, 11.5*cm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('TOPPADDING', (0, 0), (0, 0), -5),  # Negativo para subir el logo
        ('TOPPADDING', (1, 0), (1, 0), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    
    elements.append(header_table)
    elements.append(Spacer(1, 8))  # Menos espacio después del encabezado
    
    # Fecha del reporte
    fecha_table_data = [
        ["Fecha del Reporte:", datetime.now().strftime('%d/%m/%Y %I:%M')]
    ]
    
    fecha_table = Table(fecha_table_data, colWidths=[4*cm, 11*cm])
    fecha_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),  # Reducido
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),  # Reducido
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('PADDING', (0, 0), (-1, -1), (4, 6)),
    ]))
    
    elements.append(fecha_table)
    elements.append(Spacer(1, 12))  # Menos espacio
    
    # DATOS DEL REPORTE
    elements.append(Paragraph("DATOS DEL REPORTE", section_style))
    elements.append(Spacer(1, 4))  # Menos espacio
    
    # Construir datos del reporte dinámicamente
    datos_reporte = []
    datos_reporte.append(["Usuario Encargado:", request.user.get_full_name() or request.user.username])
    datos_reporte.append(["Total de registros:", str(total_movimientos)])
    
    # Solo agregar filtros si se aplicaron
    if fecha_inicio or fecha_fin:
        datos_reporte.append(["Período del reporte:", f"Del {fecha_inicio_str} al {fecha_fin_str}"])
    
    if descripcion:
        datos_reporte.append(["Descripción filtrada:", descripcion])
    
    if monto_min:
        datos_reporte.append(["Monto mínimo (USD):", f"${monto_min}"])
    
    # Agregar información de totales
    datos_reporte.append(["Total USD:", f"$ {total_usd:,.2f}"])
    datos_reporte.append(["Total Pesos:", f"$ {total_pesos:,.2f}"])
    
    datos_table = Table(datos_reporte, colWidths=[5*cm, 10*cm])
    datos_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('PADDING', (0, 0), (-1, -1), (4, 6)),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
    ]))
    
    elements.append(datos_table)
    elements.append(Spacer(1, 12))  # Menos espacio
    
    # DETALLE DE CONVERSIONES
    if movimientos.exists():
        elements.append(Paragraph("DETALLE DE CONVERSIONES", section_style))
        elements.append(Spacer(1, 4))  # Menos espacio
        
        # Preparar datos de la tabla
        table_data = []
        
        # Encabezados - similar al reporte de la imagen
        headers = [
            Paragraph("Nº", table_header_style),
            Paragraph("FECHA", table_header_style),
            Paragraph("DESCRIPCIÓN", table_header_style),
            Paragraph("USD", table_header_style),
            Paragraph("TASA", table_header_style),
            Paragraph("PESOS", table_header_style),
            Paragraph("ESTADO", table_header_style)
        ]
        table_data.append(headers)
        
        # Agregar filas de datos
        for idx, mov in enumerate(movimientos, 1):
            # Formatear fecha usando el método del modelo
            fecha_formateada = mov.fecha_formateada if hasattr(mov, 'fecha_formateada') else mov.fecha.strftime('%d/%m/%Y')
            
            descripcion_text = mov.descripcion or 'Sin descripción'
            if len(descripcion_text) > 25:
                descripcion_text = descripcion_text[:22] + "..."
            
            row = [
                Paragraph(str(idx), table_cell_style),
                Paragraph(fecha_formateada, table_cell_style),
                Paragraph(descripcion_text, table_cell_left_style),
                Paragraph(f"$ {mov.monto_usd:,.2f}", table_cell_style),
                Paragraph(f"$ {mov.tasa_cambio:,.2f}", table_cell_style),
                Paragraph(f"$ {mov.monto_pesos:,.2f}", table_cell_style),
                Paragraph("Completado", table_cell_style)
            ]
            table_data.append(row)
        
        # Anchos de columna
        col_widths = [1.2*cm, 2.5*cm, 4.5*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm]
        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        
        # Estilos de la tabla - similar al reporte de la imagen
        table_style = TableStyle([
            # Encabezado
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f0f0')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
            
            # Bordes - similares al reporte de la imagen
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            
            # Alineación
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),
            ('ALIGN', (1, 1), (1, -1), 'CENTER'),
            ('ALIGN', (2, 1), (2, -1), 'LEFT'),
            ('ALIGN', (3, 1), (5, -1), 'RIGHT'),
            ('ALIGN', (6, 1), (6, -1), 'CENTER'),
            
            # Padding
            ('PADDING', (0, 0), (-1, -1), (4, 4)),
            
            # Filas alternas
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ])
        
        # Alternar colores de fila
        for i in range(1, len(table_data)):
            if i % 2 == 0:
                table_style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor('#f8f8f8'))
        
        table.setStyle(table_style)
        elements.append(table)
    else:
        # Mensaje cuando no hay datos
        no_data_style = ParagraphStyle(
            'NoData',
            parent=styles['Normal'],
            fontSize=12,
            textColor=colors.black,
            spaceAfter=15,
            alignment=1,
            fontName='Helvetica-Bold',
            leading=14
        )
        elements.append(Spacer(1, 20))
        elements.append(Paragraph("NO SE ENCONTRARON MOVIMIENTOS", no_data_style))
        elements.append(Spacer(1, 15))
    
    elements.append(Spacer(1, 15))  # Menos espacio
    
    # OBSERVACIONES
    elements.append(Paragraph("OBSERVACIONES", section_style))
    elements.append(Spacer(1, 4))  # Menos espacio
    
    # Crear observaciones dinámicas
    observaciones_text = "Reporte generado automáticamente por el sistema. "
    if total_movimientos > 0:
        observaciones_text += f"Se encontraron {total_movimientos} conversiones. "
        observaciones_text += f"Total convertido: ${total_usd:,.2f} USD → ${total_pesos:,.2f} DOP. "
    
    if fecha_inicio or fecha_fin:
        observaciones_text += f"Período del reporte: {fecha_inicio_str} al {fecha_fin_str}. "
    
    observaciones_style = ParagraphStyle(
        'Observaciones',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.black,
        spaceAfter=8,
        alignment=0,
        leading=12,
        leftIndent=0,
        borderWidth=1,
        borderColor=colors.black,
        padding=6
    )
    
    elements.append(Paragraph(observaciones_text, observaciones_style))
    elements.append(Spacer(1, 15))  # Menos espacio
    
    # Información del sistema (pie de página)
    footer_style = ParagraphStyle(
        'FooterStyle',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#666666'),
        spaceAfter=0,
        alignment=1,
        leading=10
    )
    
    elements.append(Spacer(1, 8))  # Menos espacio
    elements.append(Paragraph(f"Sistema de Conversión de Divisas - Generado el {datetime.now().strftime('%d/%m/%Y %I:%M')}", footer_style))
    elements.append(Paragraph("Reporte válido como documentación del sistema", footer_style))
    
    # Construir el PDF
    doc.build(elements)
    
    # Obtener el valor del buffer
    pdf = buffer.getvalue()
    buffer.close()
    
    # Crear respuesta HTTP
    response = HttpResponse(content_type='application/pdf')
    # Para impresión, usar 'inline' para que se abra directamente en el navegador
    response['Content-Disposition'] = f'inline; filename="impresion_conversiones_{datetime.now().strftime("%d%m%Y_%I%M%S")}.pdf"'
    response.write(pdf)
    
    return response
# =============================================================================
# APIs PARA JAVASCRIPT  DEL  CONVERTIDOR
# =============================================================================

def api_movimientos(request):
    """
    API para obtener movimientos con filtros - CON IMÁGENES
    """
    try:
        # Obtener parámetros de filtro
        fecha_inicio = request.GET.get('fecha_inicio', '')
        fecha_fin = request.GET.get('fecha_fin', '')
        descripcion = request.GET.get('descripcion', '')
        monto_min = request.GET.get('monto_min', '')
        
        # Aplicar filtros
        movimientos = MovimientoEntrada.objects.all()
        
        if fecha_inicio:
            movimientos = movimientos.filter(fecha__date__gte=fecha_inicio)
        if fecha_fin:
            movimientos = movimientos.filter(fecha__date__lte=fecha_fin)
        if descripcion:
            movimientos = movimientos.filter(descripcion__icontains=descripcion)
        if monto_min:
            movimientos = movimientos.filter(monto_usd__gte=float(monto_min))
        
        # Ordenar por fecha descendente
        movimientos = movimientos.order_by('-fecha')
        
        # Formatear datos para el frontend
        movimientos_data = []
        for mov in movimientos:
            # Determinar URL de imagen
            if mov.imagen and hasattr(mov.imagen, 'url'):
                imagen_url = mov.imagen.url
            else:
                # Usar placeholder SVG base64
                imagen_url = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAwIiBoZWlnaHQ9IjEwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwIiBoZWlnaHQ9IjEwMCIgZmlsbD0iI2Y1ZjVmNSIvPjx0ZXh0IHg9IjUwIiB5PSI1MCIgZm9udC1mYW1pbHk9IkFyaWFsIiBmb250LXNpemU9IjgiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGZpbGw9IiNjY2MiPk5vIEltYWdlPC90ZXh0Pjwvc3ZnPg=='
            
            movimientos_data.append({
                'id': mov.id,
                'fecha': mov.fecha.strftime('%Y-%m-%d'),
                'fecha_display': mov.fecha.strftime('%d/%m/%Y'),
                'monto_usd': float(mov.monto_usd),
                'tasa_cambio': float(mov.tasa_cambio),
                'monto_pesos': float(mov.monto_pesos),
                'descripcion': mov.descripcion or '',
                'imagen_url': imagen_url,
                'tiene_imagen': bool(mov.imagen),
                'tiene_notas': bool(mov.descripcion and mov.descripcion.strip()),
                'notas': mov.descripcion or ''
            })
        
        return JsonResponse({
            'success': True,
            'movimientos': movimientos_data,
            'total': len(movimientos_data)
        })
        
    except Exception as e:
        import traceback
        print(f"Error en api_movimientos: {traceback.format_exc()}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

def api_estadisticas(request):
    """
    API para obtener estadísticas con filtros
    """
    try:
        # Obtener parámetros de filtro
        fecha_inicio = request.GET.get('fecha_inicio', '')
        fecha_fin = request.GET.get('fecha_fin', '')
        descripcion = request.GET.get('descripcion', '')
        monto_min = request.GET.get('monto_min', '')
        
        # Aplicar mismos filtros que en movimientos
        movimientos = MovimientoEntrada.objects.all()
        
        if fecha_inicio:
            movimientos = movimientos.filter(fecha__date__gte=fecha_inicio)
        if fecha_fin:
            movimientos = movimientos.filter(fecha__date__lte=fecha_fin)
        if descripcion:
            movimientos = movimientos.filter(descripcion__icontains=descripcion)
        if monto_min:
            movimientos = movimientos.filter(monto_usd__gte=float(monto_min))
        
        # Calcular estadísticas
        total_movimientos = movimientos.count()
        total_usd = movimientos.aggregate(total=Sum('monto_usd'))['total'] or 0
        total_pesos = movimientos.aggregate(total=Sum('monto_pesos'))['total'] or 0
        
        return JsonResponse({
            'success': True,
            'estadisticas': {
                'total_conversiones': total_movimientos,
                'total_usd': float(total_usd),
                'total_pesos': float(total_pesos),
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

def api_estadisticas(request):
    """
    API para obtener estadísticas con filtros - CORREGIDA
    """
    try:
        # Obtener parámetros de filtro
        fecha_inicio = request.GET.get('fecha_inicio', '')
        fecha_fin = request.GET.get('fecha_fin', '')
        descripcion = request.GET.get('descripcion', '')
        monto_min = request.GET.get('monto_min', '')
        
        # Aplicar mismos filtros que en movimientos
        movimientos = MovimientoEntrada.objects.all()
        
        if fecha_inicio:
            movimientos = movimientos.filter(fecha__date__gte=fecha_inicio)
        if fecha_fin:
            movimientos = movimientos.filter(fecha__date__lte=fecha_fin)
        if descripcion:
            movimientos = movimientos.filter(descripcion__icontains=descripcion)
        if monto_min:
            movimientos = movimientos.filter(monto_usd__gte=float(monto_min))
        
        # Calcular estadísticas
        total_movimientos = movimientos.count()
        total_usd = movimientos.aggregate(total=Sum('monto_usd'))['total'] or 0
        total_pesos = movimientos.aggregate(total=Sum('monto_pesos'))['total'] or 0
        
        return JsonResponse({
            'success': True,
            'estadisticas': {
                'total_conversiones': total_movimientos,
                'total_usd': float(total_usd),
                'total_pesos': float(total_pesos),
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

def api_estadisticas(request):
    """
    API para obtener estadísticas con filtros - usada por JavaScript
    """
    try:
        # Obtener parámetros de filtro
        fecha_inicio = request.GET.get('fecha_inicio', '')
        fecha_fin = request.GET.get('fecha_fin', '')
        descripcion = request.GET.get('descripcion', '')
        monto_min = request.GET.get('monto_min', '')
        
        # Aplicar mismos filtros que en movimientos
        movimientos = MovimientoEntrada.objects.all()
        
        if fecha_inicio:
            movimientos = movimientos.filter(fecha__date__gte=fecha_inicio)
        if fecha_fin:
            movimientos = movimientos.filter(fecha__date__lte=fecha_fin)
        if descripcion:
            movimientos = movimientos.filter(descripcion__icontains=descripcion)
        if monto_min:
            movimientos = movimientos.filter(monto_usd__gte=float(monto_min))
        
        # Calcular estadísticas
        total_movimientos = movimientos.count()
        total_usd = movimientos.aggregate(total=Sum('monto_usd'))['total'] or 0
        total_pesos = movimientos.aggregate(total=Sum('monto_pesos'))['total'] or 0
        
        # Calcular totales de gastos y servicios (placeholders por ahora)
        total_gastos = 0
        total_servicios = 0
        
        # Si hay movimientos, calcular gastos y servicios asociados
        if total_movimientos > 0:
            from .models import Gasto, ServicioPago
            total_gastos = Gasto.objects.filter(entrada__in=movimientos).aggregate(total=Sum('monto'))['total'] or 0
            total_servicios = ServicioPago.objects.filter(entrada__in=movimientos).aggregate(total=Sum('monto'))['total'] or 0
        
        return JsonResponse({
            'success': True,
            'estadisticas': {
                'total_conversiones': total_movimientos,
                'total_usd': float(total_usd),
                'total_pesos': float(total_pesos),
                'total_gastos': float(total_gastos),
                'total_servicios': float(total_servicios),
                'balance_disponible': float(total_pesos - total_gastos - total_servicios)
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)





# =============================================================================
# MÓDULO GASTOS - VISTAS
# =============================================================================
def _to_decimal(value):
    """Convierte valores a Decimal de forma segura"""
    if value is None or value == '':
        return Decimal('0.00')
    try:
        return Decimal(str(value))
    except:
        return Decimal('0.00')
# =============================================================================
# VISTAS PRINCIPALES - VERSIÓN CORREGIDA DEL GASTOS
# =============================================================================
def gastos_index(request):
    """
    Vista principal del módulo de gastos - VERSIÓN CORREGIDA
    """
    try:
        # Obtener parámetros de filtro
        fecha_desde = request.GET.get('fecha_desde', '')
        fecha_hasta = request.GET.get('fecha_hasta', '')
        categoria = request.GET.get('categoria', '')
        
        # Construir queryset base - SOLO gastos ACTIVOS
        gastos = Gasto.objects.filter(estado='ACTIVO')
        
        # Aplicar filtros
        filters = Q()
        if fecha_desde:
            filters &= Q(fecha__gte=fecha_desde)
        if fecha_hasta:
            filters &= Q(fecha__lte=fecha_hasta)
        if categoria:
            filters &= Q(categoria=categoria)
            
        gastos = gastos.filter(filters)
        
        # Obtener todas las entradas activas
        entradas = MovimientoEntrada.objects.all()
        
        # Calcular totales
        totales = calcular_totales()
        
        # Preparar datos para el template
        gastos_data = []
        for gasto in gastos:
            gastos_data.append({
                'id': gasto.id,
                'fecha': gasto.fecha.strftime('%Y-%m-%d'),
                'fecha_display': gasto.fecha.strftime('%d/%m/%Y'),
                'monto': float(gasto.monto),
                'monto_display': f"RD$ {gasto.monto:,.2f}",
                'categoria': gasto.get_categoria_display(),
                'categoria_id': gasto.categoria,
                'descripcion': gasto.descripcion,
                'notas': gasto.notas,
                'registrado_por': 'Maria Lantigua',
                'estado': gasto.estado,
                'tipo_comprobante': gasto.tipo_comprobante,
                'numero_comprobante': gasto.numero_comprobante,
                'proveedor': gasto.proveedor,
                'imagen_url': gasto.imagen.url if gasto.imagen else None,
                'tiene_imagen': bool(gasto.imagen)
            })
        
        # Obtener categorías para filtros - CORREGIDO
        from finanzas.models import CATEGORIAS_GASTOS
        categorias = CATEGORIAS_GASTOS
        
        # Obtener mensajes Django
        messages_data = []
        from django.contrib.messages import get_messages
        for message in get_messages(request):
            messages_data.append({
                'text': str(message),
                'tags': message.tags
            })
        
        # CONTEXTO CON VERSIÓN
        context = {
            'user': request.user,
            'gastos': gastos_data,
            'categorias': categorias,
            'entradas': entradas,
            'totales': totales,
            'filtros': {
                'fecha_desde': fecha_desde,
                'fecha_hasta': fecha_hasta,
                'categoria': categoria,
            },
            'django_messages_json': json.dumps(messages_data),
            'version': VERSION,  # ← AÑADIR AQUÍ LA VERSIÓN
        }
        
        # Si es una petición AJAX, retornar JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'gastos': gastos_data,
                'dashboard': totales
            })
        
        return render(request, 'finanzas/gastos.html', context)
        
    except Exception as e:
        print(f"Error en gastos_index: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': str(e)})
        # En caso de error, mostrar template con datos vacíos
        from finanzas.models import CATEGORIAS_GASTOS
        return render(request, 'finanzas/gastos.html', {
            'gastos': [],
            'categorias': CATEGORIAS_GASTOS,
            'entradas': [],
            'totales': calcular_totales(),
            'filtros': {},
            'version': VERSION,  # ← VERSIÓN TAMBIÉN EN CASO DE ERROR
        })
def calcular_saldo_entrada(entrada):
    """Calcula el saldo disponible de una entrada - VERSIÓN CORREGIDA"""
    if not entrada:
        return Decimal('0.00')
    
    try:
        gastos_activos = Gasto.objects.filter(
            entrada=entrada, 
            estado='ACTIVO'
        ).aggregate(total=Sum('monto'))
        total_gastos = gastos_activos['total'] or Decimal('0.00')
        

        return entrada.monto_pesos - total_gastos
    except Exception as e:
        print(f"Error calculando saldo: {str(e)}")
        return Decimal('0.00')

def calcular_totales():
    """Calcula los totales generales del sistema - VERSIÓN CORREGIDA"""
    try:
        # Total de todas las entradas
        total_entradas = MovimientoEntrada.objects.aggregate(
            total=Sum('monto_pesos')
        )['total'] or Decimal('0.00')
        
        # Total de gastos activos
        total_gastos = Gasto.objects.filter(estado='ACTIVO').aggregate(
            total=Sum('monto')
        )['total'] or Decimal('0.00')
        
        # Total de servicios activos
        total_servicios = ServicioPago.objects.filter(
            estado='ACTIVO'
        ).aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
        
        # Balance restante = Entradas - Gastos - Servicios
        balance = total_entradas - total_gastos - total_servicios 
        
        return {
            'total_disponible': total_entradas,
            'total_gastado': total_gastos,
            'total_servicios': total_servicios,  # Opcional: si quieres mostrar este valor
            'balance_restante': balance
        }
    except Exception as e:
        print(f"Error calculando totales: {str(e)}")
        return {
            'total_disponible': Decimal('0.00'),
            'total_gastado': Decimal('0.00'),
            'total_servicios': Decimal('0.00'),
            'balance_restante': Decimal('0.00')
        }
def gastos_crear(request):
    """
    Crear un nuevo gasto - VERSIÓN CORREGIDA
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'})
    
    try:
        with transaction.atomic():
            # Obtener datos del formulario - NOMBRES CORREGIDOS
            fecha = request.POST.get('date')  # ❌ 'fecha' → ✅ 'date'
            monto = _to_decimal(request.POST.get('amount'))
            categoria = request.POST.get('category')
            descripcion = request.POST.get('description', '').strip()
            
            # Campos opcionales
            notas = request.POST.get('notas', '').strip()
            entrada_id = request.POST.get('entrada_id')
            tipo_comprobante = request.POST.get('tipo_comprobante', 'SIN_COMPROBANTE')
            numero_comprobante = request.POST.get('numeroComprobante', '').strip()  # ❌ 'numero_comprobante' → ✅ 'numeroComprobante'
            proveedor = request.POST.get('proveedor', '').strip()
            
            # Depuración: Ver qué datos están llegando
            print("Datos recibidos:")
            print(f"Fecha: {fecha}")
            print(f"Monto: {monto}")
            print(f"Categoría: {categoria}")
            print(f"Descripción: {descripcion}")
            print(f"Tipo Comprobante: {tipo_comprobante}")
            print(f"Número Comprobante: {numero_comprobante}")
            print(f"Proveedor: {proveedor}")
            
            # Validaciones básicas
            if not all([fecha, monto, categoria, descripcion]):
                missing_fields = []
                if not fecha: missing_fields.append("fecha")
                if not monto: missing_fields.append("monto")
                if not categoria: missing_fields.append("categoría")
                if not descripcion: missing_fields.append("descripción")
                
                return JsonResponse({
                    'success': False, 
                    'error': f'Faltan campos obligatorios: {", ".join(missing_fields)}'
                })
            
            if monto <= Decimal('0.00'):
                return JsonResponse({
                    'success': False, 
                    'error': 'El monto debe ser mayor a cero'
                })
            
            # Buscar entrada asociada
            entrada = None
            if entrada_id:
                entrada = get_object_or_404(MovimientoEntrada, id=entrada_id)
                
                # Verificar saldo disponible
                saldo_disponible = calcular_saldo_entrada(entrada)
                if monto > saldo_disponible:
                    return JsonResponse({
                        'success': False,
                        'error': f'Saldo insuficiente. Disponible: RD$ {saldo_disponible:,.2f}'
                    })
            
            # Manejar imagen si se proporciona
            imagen = None
            if 'imagen' in request.FILES:
                imagen = request.FILES['imagen']
            
            # Crear el gasto
            gasto = Gasto(
                fecha=fecha,
                monto=monto,
                categoria=categoria,
                descripcion=descripcion,
                notas=notas,
                entrada=entrada,
                estado='ACTIVO',
                tipo_comprobante=tipo_comprobante,
                numero_comprobante=numero_comprobante,
                proveedor=proveedor
            )
            
            # Asignar imagen si se proporciona
            if imagen:
                gasto.imagen = imagen
            
            gasto.save()
            
            # Respuesta exitosa
            response_data = {
                'success': True,
                'message': 'Gasto creado exitosamente',
                'gasto_id': gasto.id
            }
            
            # Si no es AJAX, agregar mensaje flash
            if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                messages.success(request, 'Gasto creado exitosamente')
                return redirect('gastos_index')
            
            return JsonResponse(response_data)
            
    except Exception as e:
        error_msg = f'Error al crear el gasto: {str(e)}'
        print(f"Error en gastos_crear: {error_msg}")  # Para depuración
        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            messages.error(request, error_msg)
            return redirect('gastos_index')
        return JsonResponse({'success': False, 'error': error_msg})

def gastos_editar(request, pk):
    """
    Editar un gasto existente - VERSIÓN CORREGIDA
    """
    gasto = get_object_or_404(Gasto, id=pk)
    
    if request.method == 'GET':
        # Retornar datos del gasto para edición
        gasto_data = {
            'id': gasto.id,
            'fecha': gasto.fecha.strftime('%Y-%m-%d'),
            'monto': float(gasto.monto),
            'categoria': gasto.categoria,
            'descripcion': gasto.descripcion,
            'notas': gasto.notas,
            'entrada_id': gasto.entrada.id if gasto.entrada else None,
            'tipo_comprobante': gasto.tipo_comprobante,
            'numero_comprobante': gasto.numero_comprobante,
            'proveedor': gasto.proveedor
        }
        return JsonResponse({'success': True, 'gasto': gasto_data})
    
    elif request.method == 'POST':
        try:
            with transaction.atomic():
                # Obtener datos del formulario - NOMBRES CORRECTOS
                fecha = request.POST.get('date')
                monto = _to_decimal(request.POST.get('amount'))
                categoria = request.POST.get('category')
                descripcion = request.POST.get('description', '').strip()
                notas = request.POST.get('notas', '').strip()
                tipo_comprobante = request.POST.get('tipoComprobante', 'SIN_COMPROBANTE')
                numero_comprobante = request.POST.get('numeroComprobante', '').strip()
                proveedor = request.POST.get('proveedor', '').strip()
                
                # Depuración
                print("Datos recibidos en edición:")
                print(f"Fecha: {fecha}, Monto: {monto}, Categoría: {categoria}")
                print(f"Descripción: {descripcion}")
                print(f"Tipo Comprobante: {tipo_comprobante}")
                print(f"Número Comprobante: {numero_comprobante}")
                print(f"Proveedor: {proveedor}")
                
                # Validaciones básicas
                if not all([fecha, monto, categoria, descripcion]):
                    missing_fields = []
                    if not fecha: missing_fields.append("fecha")
                    if not monto: missing_fields.append("monto")
                    if not categoria: missing_fields.append("categoría")
                    if not descripcion: missing_fields.append("descripción")
                    
                    return JsonResponse({
                        'success': False, 
                        'error': f'Faltan campos obligatorios: {", ".join(missing_fields)}'
                    })
                
                if monto <= Decimal('0.00'):
                    return JsonResponse({
                        'success': False, 
                        'error': 'El monto debe ser mayor a cero'
                    })
                
                # Verificar saldo disponible (considerando el monto actual)
                if gasto.entrada:
                    saldo_disponible = calcular_saldo_entrada(gasto.entrada) + gasto.monto
                    if monto > saldo_disponible:
                        return JsonResponse({
                            'success': False,
                            'error': f'Saldo insuficiente. Disponible: RD$ {saldo_disponible:,.2f}'
                        })
                
                # Actualizar el gasto
                gasto.fecha = fecha
                gasto.monto = monto
                gasto.categoria = categoria
                gasto.descripcion = descripcion
                gasto.notas = notas
                gasto.estado = 'ACTIVO'  # Cambiado de 'EDITADO' a 'ACTIVO'
                gasto.tipo_comprobante = tipo_comprobante
                gasto.numero_comprobante = numero_comprobante
                gasto.proveedor = proveedor
                
                # Manejar nueva imagen si se proporciona
                if 'imagen' in request.FILES:
                    gasto.imagen = request.FILES['imagen']
                
                gasto.save()
                
                # Respuesta exitosa
                response_data = {
                    'success': True,
                    'message': 'Gasto actualizado exitosamente'
                }
                
                # Si no es AJAX, agregar mensaje flash
                if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    messages.success(request, 'Gasto actualizado exitosamente')
                    return redirect('gastos_index')
                
                return JsonResponse(response_data)
                
        except Exception as e:
            error_msg = f'Error al actualizar el gasto: {str(e)}'
            print(f"Error en gastos_editar: {error_msg}")
            import traceback
            traceback.print_exc()  # Esto mostrará el traceback completo
            
            if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                messages.error(request, error_msg)
                return redirect('gastos_index')
            return JsonResponse({'success': False, 'error': error_msg})
    
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

def gastos_eliminar(request, pk):
    """
    Eliminación lógica de un gasto
    """
    gasto = get_object_or_404(Gasto, id=pk)
    
    if request.method == 'POST':
        try:
            gasto.estado = 'ELIMINADO'
            gasto.save()
            
            response_data = {
                'success': True,
                'message': 'Gasto eliminado exitosamente'
            }
            
            # Si no es AJAX, agregar mensaje flash
            if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                messages.success(request, 'Gasto eliminado exitosamente')
                return redirect('gastos_index')
            
            return JsonResponse(response_data)
            
        except Exception as e:
            error_msg = f'Error al eliminar el gasto: {str(e)}'
            if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                messages.error(request, error_msg)
                return redirect('gastos_index')
            return JsonResponse({'success': False, 'error': error_msg})
    
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

def gastos_pdf(request, pk):
    """
    Generar PDF de un gasto individual
    """
    gasto = get_object_or_404(Gasto, id=pk)
    
    # Crear respuesta HTTP con tipo PDF
    response = HttpResponse(content_type='application/pdf')
    filename = f'gasto_{gasto.id}_{gasto.fecha.strftime("%Y%m%d")}.pdf'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    # Crear el PDF
    p = canvas.Canvas(response, pagesize=letter)
    width, height = letter
    
    # Configuración inicial
    p.setTitle(f"Comprobante de Gasto #{gasto.id}")
    
    # Encabezado
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, height - 100, "COMPROBANTE DE GASTO")
    p.setFont("Helvetica", 10)
    p.drawString(100, height - 120, f"Emitido el: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    
    # Línea separadora
    p.line(100, height - 130, width - 100, height - 130)
    
    # Información del gasto
    y_position = height - 160
    
    p.setFont("Helvetica-Bold", 12)
    p.drawString(100, y_position, "Información del Gasto:")
    p.setFont("Helvetica", 10)
    
    # Datos básicos
    datos = [
        (f"ID del Gasto: #{gasto.id}", 100, y_position - 30),
        (f"Fecha: {gasto.fecha.strftime('%d/%m/%Y')}", 100, y_position - 50),
        (f"Monto: RD$ {gasto.monto:,.2f}", 100, y_position - 70),
        (f"Categoría: {gasto.get_categoria_display()}", 100, y_position - 90),
        (f"Estado: {gasto.estado}", 100, y_position - 110),
    ]
    
    for texto, x, y in datos:
        p.drawString(x, y, texto)
    
    # Descripción
    p.drawString(100, y_position - 140, "Descripción:")
    # Dividir descripción en líneas si es muy larga
    descripcion = gasto.descripcion
    line_height = 15
    max_width = 400
    lines = []
    
    words = descripcion.split()
    current_line = []
    
    for word in words:
        test_line = ' '.join(current_line + [word])
        if p.stringWidth(test_line, "Helvetica", 10) <= max_width:
            current_line.append(word)
        else:
            lines.append(' '.join(current_line))
            current_line = [word]
    
    if current_line:
        lines.append(' '.join(current_line))
    
    # Dibujar líneas de descripción
    desc_y = y_position - 160
    for line in lines[:5]:  # Máximo 5 líneas
        p.drawString(120, desc_y, line)
        desc_y -= line_height
    
    # Notas (si existen)
    if gasto.notas:
        p.drawString(100, desc_y - 20, "Notas Adicionales:")
        notas_lines = []
        words = gasto.notas.split()
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            if p.stringWidth(test_line, "Helvetica", 10) <= max_width:
                current_line.append(word)
            else:
                notas_lines.append(' '.join(current_line))
                current_line = [word]
        
        if current_line:
            notas_lines.append(' '.join(current_line))
        
        notas_y = desc_y - 40
        for line in notas_lines[:3]:  # Máximo 3 líneas
            p.drawString(120, notas_y, line)
            notas_y -= line_height
    
    # Información de entrada asociada (si existe)
    if gasto.entrada:
        p.drawString(100, 200, f"Entrada Asociada: #{gasto.entrada.id}")
        p.drawString(100, 180, f"Monto Original: RD$ {gasto.entrada.monto_pesos:,.2f}")
    
    # Pie de página
    p.setFont("Helvetica-Oblique", 8)
    p.drawString(100, 50, "Sistema MLAN Finance - Comprobante generado automáticamente")
    
    p.showPage()
    p.save()
    
    return response

def gastos_pdf_historial(request):
    """
    Generar PDF con el historial completo de gastos
    """
    # Aplicar mismos filtros que en gastos_index
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    categoria = request.GET.get('categoria', '')
    entrada_id = request.GET.get('entrada_id', '')
    
    gastos = Gasto.objects.filter(estado='ACTIVO')
    
    if fecha_desde:
        gastos = gastos.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        gastos = gastos.filter(fecha__lte=fecha_hasta)
    if categoria:
        gastos = gastos.filter(categoria=categoria)
    if entrada_id:
        gastos = gastos.filter(entrada_id=entrada_id)
    
    # Calcular totales
    total_gastado = gastos.aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    
    # Crear respuesta HTTP con tipo PDF
    response = HttpResponse(content_type='application/pdf')
    filename = f'historial_gastos_{datetime.now().strftime("%Y%m%d")}.pdf'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    # Crear el PDF
    p = canvas.Canvas(response, pagesize=letter)
    width, height = letter
    
    # Configuración inicial
    p.setTitle("Historial de Gastos")
    
    # Encabezado
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, height - 100, "HISTORIAL DE GASTOS")
    p.setFont("Helvetica", 10)
    p.drawString(100, height - 120, f"Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    
    # Información de filtros aplicados
    filtros_texto = "Filtros aplicados: "
    filtros = []
    if fecha_desde:
        filtros.append(f"Desde: {fecha_desde}")
    if fecha_hasta:
        filtros.append(f"Hasta: {fecha_hasta}")
    if categoria:
        categoria_display = dict(Gasto.CATEGORIAS_GASTOS).get(categoria, categoria)
        filtros.append(f"Categoría: {categoria_display}")
    
    if filtros:
        filtros_texto += ", ".join(filtros)
    else:
        filtros_texto += "Todos los gastos"
    
    p.drawString(100, height - 140, filtros_texto)
    
    # Línea separadora
    p.line(100, height - 150, width - 100, height - 150)
    
    # Encabezados de tabla
    y_position = height - 180
    p.setFont("Helvetica-Bold", 10)
    
    columnas = [
        ("Fecha", 100),
        ("Categoría", 150),
        ("Descripción", 220),
        ("Monto", 400),
        ("Estado", 470)
    ]
    
    for texto, x in columnas:
        p.drawString(x, y_position, texto)
    
    p.line(100, y_position - 5, width - 100, y_position - 5)
    
    # Datos de la tabla
    p.setFont("Helvetica", 8)
    y_position -= 20
    
    for gasto in gastos:
        if y_position < 100:  # Nueva página si se acaba el espacio
            p.showPage()
            y_position = height - 100
            # Redibujar encabezados de tabla en nueva página
            p.setFont("Helvetica-Bold", 10)
            for texto, x in columnas:
                p.drawString(x, y_position, texto)
            p.line(100, y_position - 5, width - 100, y_position - 5)
            p.setFont("Helvetica", 8)
            y_position -= 20
        
        # Truncar descripción si es muy larga
        descripcion = gasto.descripcion
        if len(descripcion) > 40:
            descripcion = descripcion[:37] + "..."
        
        # Dibujar fila
        p.drawString(100, y_position, gasto.fecha.strftime('%d/%m/%Y'))
        p.drawString(150, y_position, gasto.get_categoria_display()[:20])
        p.drawString(220, y_position, descripcion)
        p.drawString(400, y_position, f"RD$ {gasto.monto:,.2f}")
        p.drawString(470, y_position, gasto.estado)
        
        y_position -= 15
    
    # Total al final
    p.setFont("Helvetica-Bold", 10)
    p.drawString(400, y_position - 20, f"TOTAL GASTADO:")
    p.drawString(470, y_position - 20, f"RD$ {total_gastado:,.2f}")
    
    # Pie de página
    p.setFont("Helvetica-Oblique", 8)
    p.drawString(100, 50, f"Sistema MLAN Finance - Total de gastos: {gastos.count()} registros")
    
    p.showPage()
    p.save()
    
    return response

def gastos_imprimir_historial(request):
    """
    Vista para imprimir el historial de gastos
    """
    # Aplicar mismos filtros que en gastos_index
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    categoria = request.GET.get('categoria', '')
    entrada_id = request.GET.get('entrada_id', '')
    
    gastos = Gasto.objects.filter(estado='ACTIVO')
    
    if fecha_desde:
        gastos = gastos.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        gastos = gastos.filter(fecha__lte=fecha_hasta)
    if categoria:
        gastos = gastos.filter(categoria=categoria)
    if entrada_id:
        gastos = gastos.filter(entrada_id=entrada_id)
    
    # Preparar datos para el template
    gastos_data = []
    for gasto in gastos:
        gastos_data.append({
            'id': gasto.id,
            'fecha': gasto.fecha.strftime('%d/%m/%Y'),
            'monto': f"RD$ {gasto.monto:,.2f}",
            'categoria': gasto.get_categoria_display(),
            'descripcion': gasto.descripcion,
            'entrada_id': gasto.entrada.id if gasto.entrada else 'N/A',
            'estado': gasto.estado
        })
    
    # Calcular totales
    total_gastado = gastos.aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    
    context = {
        'gastos': gastos_data,
        'total_gastado': f"RD$ {total_gastado:,.2f}",
        'total_registros': len(gastos_data),
        'fecha_generacion': datetime.now().strftime('%d/%m/%Y %H:%M'),
        'filtros': {
            'fecha_desde': fecha_desde,
            'fecha_hasta': fecha_hasta,
            'categoria': categoria,
            'entrada_id': entrada_id
        }
    }
    
    return render(request, 'finanzas/gastos_print.html', context)

# =============================================================================
# VISTAS API PARA EL TEMPLATE GASTOS.HTML
# =============================================================================
def api_gastos(request):
    """
    API para obtener gastos (usado por gastos.html)
    """
    try:
        # Obtener parámetros de filtro
        fecha_desde = request.GET.get('fecha_desde', '')
        fecha_hasta = request.GET.get('fecha_hasta', '')
        categoria = request.GET.get('categoria', '')
        
        # Construir queryset
        gastos = Gasto.objects.filter(estado='ACTIVO')
        
        if fecha_desde:
            gastos = gastos.filter(fecha__gte=fecha_desde)
        if fecha_hasta:
            gastos = gastos.filter(fecha__lte=fecha_hasta)
        if categoria:
            gastos = gastos.filter(categoria=categoria)
        
        # Preparar datos para JSON
        gastos_data = []
        for gasto in gastos:
            gastos_data.append({
                'id': gasto.id,
                'fecha': gasto.fecha.strftime('%Y-%m-%d'),
                'fecha_display': gasto.fecha.strftime('%d/%m/%Y'),
                'monto': float(gasto.monto),
                'monto_display': f"RD$ {gasto.monto:,.2f}",
                'categoria': gasto.get_categoria_display(),
                'categoria_id': gasto.categoria,
                'descripcion': gasto.descripcion,
                'registrado_por': getattr(gasto.entrada, 'descripcion', 'Sistema') if gasto.entrada else 'Sistema',
                'estado': gasto.estado,
                'tipo_comprobante': getattr(gasto, 'tipo_comprobante', 'SIN_COMPROBANTE'),
                'numero_comprobante': getattr(gasto, 'numero_comprobante', ''),
                'proveedor': getattr(gasto, 'proveedor', ''),
                'imagen_url': gasto.imagen.url if gasto.imagen else None,
                'tiene_imagen': bool(gasto.imagen)
            })
        
        return JsonResponse({
            'success': True,
            'gastos': gastos_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

def api_categorias(request):
    """
    API para obtener categorías (usado por gastos.html)
    """
    try:
        categorias = [
            {'id': cat[0], 'nombre': cat[1]} 
            for cat in Gasto.CATEGORIAS_GASTOS
        ]
        
        return JsonResponse({
            'success': True,
            'categorias': categorias
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

def api_dashboard(request):
    """
    API para obtener datos del dashboard (usado por gastos.html) - VERSIÓN CORREGIDA
    """
    try:
        # Obtener parámetros de filtro
        fecha_desde = request.GET.get('fecha_desde', '')
        fecha_hasta = request.GET.get('fecha_hasta', '')
        categoria = request.GET.get('categoria', '')

        # 1. Total de todas las entradas (sin filtrar por fecha)
        total_entradas = MovimientoEntrada.objects.aggregate(
            total=Sum('monto_pesos')
        )['total'] or Decimal('0.00')

        # 2. Total de gastos activos (con filtros si existen)
        gastos = Gasto.objects.filter(estado='ACTIVO')
        
        if fecha_desde:
            gastos = gastos.filter(fecha__gte=fecha_desde)
        if fecha_hasta:
            gastos = gastos.filter(fecha__lte=fecha_hasta)
        if categoria:
            gastos = gastos.filter(categoria=categoria)
            
        total_gastos = gastos.aggregate(total=Sum('monto'))['total'] or Decimal('0.00')

        # 3. Total de servicios activos (con filtros si existen)
        servicios = ServicioPago.objects.filter(estado='ACTIVO')
        
        if fecha_desde:
            servicios = servicios.filter(fecha__gte=fecha_desde)
        if fecha_hasta:
            servicios = servicios.filter(fecha__lte=fecha_hasta)
            
        total_servicios = servicios.aggregate(total=Sum('monto'))['total'] or Decimal('0.00')

        # 4. Calcular balance: Entradas - Gastos - Servicios
        balance = total_entradas - total_gastos - total_servicios

        # Asegurarse de que el balance no sea negativo
        if balance < Decimal('0.00'):
            balance = Decimal('0.00')

        dashboard_data = {
            'total_disponible': float(total_entradas),
            'total_gastado': float(total_gastos),
            'total_servicios': float(total_servicios),
            'balance_restante': float(balance)
        }

        return JsonResponse({
            'success': True,
            'dashboard': dashboard_data
        })

    except Exception as e:
        print(f"Error en api_dashboard: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
def api_categorias(request):
    """
    API para obtener categorías (usado por gastos.html) - CORREGIDO
    """
    try:
        from finanzas.models import CATEGORIAS_GASTOS
        categorias = [
            {'id': cat[0], 'nombre': cat[1]} 
            for cat in CATEGORIAS_GASTOS
        ]
        
        return JsonResponse({
            'success': True,
            'categorias': categorias
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })





# =============================================================================
# MÓDULO SERVICIOS - VISTAS COMPLETAS
# =============================================================================

def _to_decimal(value):
    """Convierte seguro a Decimal"""
    if value is None or value == '':
        return Decimal('0.00')
    try:
        return Decimal(str(value))
    except:
        return Decimal('0.00')

def calcular_saldo_entrada_servicios(entrada):
    """Calcula saldo disponible para servicios en una entrada específica"""
    total_servicios = ServicioPago.objects.filter(
        entrada=entrada,
        estado='ACTIVO'
    ).aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    
    return entrada.monto_pesos - total_servicios

def calcular_totales_servicios():
    """Calcula totales generales del módulo servicios"""
    # Total de todas las entradas
    total_entradas = MovimientoEntrada.objects.aggregate(
        total=Sum('monto_pesos')
    )['total'] or Decimal('0.00')
    
    # Total de todos los servicios activos
    total_servicios = ServicioPago.objects.filter(
        estado='ACTIVO'
    ).aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    
    # Total de todos los gastos activos
    total_gastos = Gasto.objects.filter(
        estado='ACTIVO'
    ).aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    
    # Balance = Total Entradas - Total Servicios - Total Gastos
    balance = total_entradas - total_servicios - total_gastos
    
    return {
        'total_entradas': total_entradas,
        'total_servicios': total_servicios,
        'total_gastos': total_gastos,
        'balance': balance
    }

def servicios_tipos(request):
    """API para obtener los tipos de servicio disponibles"""
    try:
        from .models import SERVICIOS_TIPOS
        tipos_servicio = SERVICIOS_TIPOS
        return JsonResponse({
            'tipos_servicio': tipos_servicio
        })
    except Exception as e:
        print(f"Error en servicios_tipos: {str(e)}")
        # Fallback a valores por defecto
        tipos_servicio = [
            ("LUZ", "Electricidad"),
            ("AGUA", "Agua"),
            ("INTERNET", "Internet"),
            ("TELEFONO", "Teléfono"),
            ("ALQUILER", "Alquiler"),
            ("OTRO", "Otro Servicio"),
        ]
        return JsonResponse({
            'tipos_servicio': tipos_servicio
        })

def servicios_metodos_pago(request):
    """API para obtener los métodos de pago disponibles"""
    try:
        # Importar los choices del modelo
        from .models import TIPO_COMPROBANTE_CHOICES
        
        print("=== SERVICIOS_METODOS_PAGO LLAMADA ===")
        print(f"TIPO_COMPROBANTE_CHOICES: {TIPO_COMPROBANTE_CHOICES}")
        
        return JsonResponse({
            'metodos_pago': TIPO_COMPROBANTE_CHOICES,
            'success': True
        })
        
    except Exception as e:
        print(f"Error en servicios_metodos_pago: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Fallback a valores por defecto
        metodos_pago = [
            ("SIN_COMPROBANTE", "Sin Comprobante"),
            ("FACTURA", "Factura"),
            ("RECIBO", "Recibo"),
            ("TICKET", "Ticket"),
            ("TRANSFERENCIA", "Transferencia"),
        ]
        
        return JsonResponse({
            'metodos_pago': metodos_pago,
            'success': False,
            'error': str(e)
        })
def servicios_proveedores(request):
    """API para obtener los proveedores únicos"""
    try:
        proveedores = ServicioPago.objects.exclude(
            estado='ELIMINADO'
        ).exclude(
            proveedor__isnull=True
        ).exclude(
            proveedor__exact=''
        ).values_list('proveedor', flat=True).distinct().order_by('proveedor')
        
        return JsonResponse({
            'proveedores': list(proveedores)
        })
    except Exception as e:
        print(f"Error en servicios_proveedores: {str(e)}")
        return JsonResponse({
            'error': str(e),
            'proveedores': []
        }, status=500)

def servicios_index(request):
    """Vista principal del módulo servicios - Soporta AJAX"""
    try:
        # Obtener parámetros de filtro
        fecha_desde = request.GET.get('fecha_desde', '')
        fecha_hasta = request.GET.get('fecha_hasta', '')
        tipo_servicio = request.GET.get('tipo_servicio', '')
        proveedor = request.GET.get('proveedor', '')
        estado = request.GET.get('estado', '')  # Cambiado: por defecto vacío para incluir todos
        
        # Consulta base - excluir SOLO eliminados
        servicios = ServicioPago.objects.exclude(estado='ELIMINADO')
        
        # Si no se especifica estado, incluir ACTIVO y EDITADO
        if not estado:
            servicios = servicios.filter(estado__in=['ACTIVO', 'EDITADO'])
        else:
            servicios = servicios.filter(estado=estado)
        
        # Aplicar filtros
        if fecha_desde:
            servicios = servicios.filter(fecha__gte=fecha_desde)
        if fecha_hasta:
            servicios = servicios.filter(fecha__lte=fecha_hasta)
        if tipo_servicio:
            servicios = servicios.filter(tipo_servicio=tipo_servicio)
        if proveedor:
            servicios = servicios.filter(proveedor=proveedor)
        
        # Ordenar por fecha más reciente primero
        servicios = servicios.order_by('-fecha')
        
        # DETECCIÓN MEJORADA DE PETICIONES AJAX
        is_ajax = (
            request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
            request.GET.get('format') == 'json' or
            request.content_type == 'application/json'
        )
        
        # Si es petición AJAX, devolver JSON (NO incluir versión en JSON)
        if is_ajax:
            servicios_data = []
            for servicio in servicios:
                servicios_data.append({
                    'id': servicio.id,
                    'fecha': servicio.fecha.isoformat(),
                    'tipo_servicio': servicio.tipo_servicio,
                    'monto': float(servicio.monto),
                    'tipo_comprobante': servicio.tipo_comprobante,
                    'proveedor': servicio.proveedor or '',
                    'descripcion': servicio.descripcion or '',
                    'notas': servicio.notas or '',
                    'entrada_descripcion': servicio.entrada.descripcion if servicio.entrada else '',
                    'entrada_id': servicio.entrada.id if servicio.entrada else None
                })
            
            totales = calcular_totales_servicios()
            
            response_data = {
                'servicios': servicios_data,
                'totales': {
                    'total_servicios': float(totales['total_servicios']),
                    'balance': float(totales['balance'])
                }
            }
            
            return JsonResponse(response_data)
        
        # Para peticiones normales, renderizar template
        entradas = MovimientoEntrada.objects.all().order_by('-fecha')
        totales = calcular_totales_servicios()
        
        # Obtener tipos de servicio
        try:
            from .models import SERVICIOS_TIPOS
            tipos_servicio = SERVICIOS_TIPOS
        except:
            tipos_servicio = ServicioPago._meta.get_field('tipo_servicio').choices
        
        # Obtener proveedores únicos
        proveedores = ServicioPago.objects.exclude(
            estado='ELIMINADO'
        ).exclude(
            proveedor__isnull=True
        ).exclude(
            proveedor__exact=''
        ).values_list('proveedor', flat=True).distinct().order_by('proveedor')
        
        # Obtener mensajes Django
        from django.contrib.messages import get_messages
        messages_data = []
        for message in get_messages(request):
            messages_data.append({
                'text': str(message),
                'tags': message.tags
            })
        
        # CONTEXTO CON VERSIÓN
        context = {
            'user': request.user,
            'servicios': servicios,
            'tipos_servicio': tipos_servicio,
            'proveedores': proveedores,
            'entradas': entradas,
            'totales': totales,
            'filtros': {
                'fecha_desde': fecha_desde,
                'fecha_hasta': fecha_hasta,
                'tipo_servicio': tipo_servicio,
                'proveedor': proveedor,
                'estado': estado,
            },
            'django_messages_json': json.dumps(messages_data),
            'version': VERSION,  # ← AÑADIR AQUÍ LA VERSIÓN
        }
        
        return render(request, 'finanzas/servicios.html', context)
    
    except Exception as e:
        print(f"Error en servicios_index: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Si es AJAX, devolver error en JSON
        if (request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 
            request.GET.get('format') == 'json'):
            return JsonResponse({
                'error': str(e),
                'servicios': [],
                'totales': {'total_servicios': 0, 'balance': 0}
            }, status=500)
        
        # En caso de error, mostrar template con datos vacíos pero con versión
        try:
            from .models import SERVICIOS_TIPOS
            tipos_servicio = SERVICIOS_TIPOS
        except:
            tipos_servicio = []
        
        return render(request, 'finanzas/servicios.html', {
            'servicios': [],
            'tipos_servicio': tipos_servicio,
            'proveedores': [],
            'entradas': [],
            'totales': {'total_servicios': 0, 'balance': 0},
            'filtros': {},
            'version': VERSION,  # ← VERSIÓN TAMBIÉN EN CASO DE ERROR
        })
@transaction.atomic
def servicios_crear(request):
    """Crear nuevo pago de servicio - Soporta AJAX"""
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            fecha = request.POST.get('date')
            monto = _to_decimal(request.POST.get('amount'))
            tipo_servicio = request.POST.get('serviceType')
            tipo_comprobante = request.POST.get('paymentMethod', 'SIN_COMPROBANTE')
            proveedor = request.POST.get('registrar', '')
            descripcion = request.POST.get('notes', '')
            
            print(f"Datos recibidos: fecha={fecha}, monto={monto}, tipo_servicio={tipo_servicio}, proveedor={proveedor}")
            
            # Validar campos obligatorios
            if not all([fecha, monto, tipo_servicio, proveedor]):
                missing = []
                if not fecha: missing.append('fecha')
                if not monto: missing.append('monto')
                if not tipo_servicio: missing.append('tipo_servicio')
                if not proveedor: missing.append('proveedor')
                
                error_msg = f'Campos obligatorios faltantes: {", ".join(missing)}'
                print(f"ERROR: {error_msg}")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': error_msg
                    }, status=400)
                messages.error(request, error_msg)
                return redirect('servicios_index')
            
            # Buscar una entrada disponible
            entradas = MovimientoEntrada.objects.all()
            entrada_disponible = None
            
            for entrada in entradas:
                # Calcular saldo disponible manualmente
                total_servicios_entrada = ServicioPago.objects.filter(
                    entrada=entrada,
                    estado='ACTIVO'
                ).aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
                
                saldo_disponible = entrada.monto_pesos - total_servicios_entrada
                
                if saldo_disponible >= monto:
                    entrada_disponible = entrada
                    break
            
            if not entrada_disponible:
                error_msg = f'No hay entradas disponibles con saldo suficiente. Monto requerido: RD$ {monto:.2f}'
                print(f"ERROR: {error_msg}")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': error_msg
                    }, status=400)
                messages.error(request, error_msg)
                return redirect('servicios_index')
            
            # Manejar archivo de comprobante
            imagen = None
            if 'receipt' in request.FILES:
                imagen = request.FILES['receipt']
            
            # Crear servicio
            servicio = ServicioPago(
                fecha=fecha,
                monto=monto,
                tipo_servicio=tipo_servicio,
                tipo_comprobante=tipo_comprobante,
                proveedor=proveedor,
                descripcion=descripcion,
                entrada=entrada_disponible,
                imagen=imagen,
                estado='ACTIVO'
            )
            
            servicio.save()
            
            print(f"Servicio creado exitosamente: ID {servicio.id}")
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Pago de servicio registrado exitosamente'
                })
            messages.success(request, 'Pago de servicio registrado exitosamente')
            
        except Exception as e:
            error_msg = f'Error al crear servicio: {str(e)}'
            print(f"Error en servicios_crear: {error_msg}")
            import traceback
            traceback.print_exc()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': error_msg
                }, status=500)
            messages.error(request, error_msg)
    
    return redirect('servicios_index')

@transaction.atomic
def servicios_editar(request, pk):
    """Editar pago de servicio existente - Soporta AJAX"""
    servicio = get_object_or_404(ServicioPago, pk=pk)
    
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            fecha = request.POST.get('date')
            monto = _to_decimal(request.POST.get('amount'))
            tipo_servicio = request.POST.get('serviceType')
            tipo_comprobante = request.POST.get('paymentMethod', 'SIN_COMPROBANTE')
            proveedor = request.POST.get('registrar', '')
            descripcion = request.POST.get('notes', '')
            
            print(f"Editando servicio {pk}: fecha={fecha}, monto={monto}, tipo_servicio={tipo_servicio}")
            
            # Validar campos obligatorios
            if not all([fecha, monto, tipo_servicio, proveedor]):
                missing = []
                if not fecha: missing.append('fecha')
                if not monto: missing.append('monto')
                if not tipo_servicio: missing.append('tipo_servicio')
                if not proveedor: missing.append('proveedor')
                
                error_msg = f'Campos obligatorios faltantes: {", ".join(missing)}'
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': error_msg
                    }, status=400)
                messages.error(request, error_msg)
                return redirect('servicios_index')
            
            # Verificar si cambió el monto
            if monto != servicio.monto:
                # Buscar entradas disponibles manualmente
                entradas = MovimientoEntrada.objects.all()
                entrada_disponible = None
                diferencia = monto - servicio.monto
                
                for entrada in entradas:
                    # Calcular saldo disponible manualmente
                    total_servicios_entrada = ServicioPago.objects.filter(
                        entrada=entrada,
                        estado='ACTIVO'
                    ).aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
                    
                    saldo_disponible = entrada.monto_pesos - total_servicios_entrada
                    
                    if saldo_disponible >= diferencia:
                        entrada_disponible = entrada
                        break
                
                if not entrada_disponible and (monto > servicio.monto):
                    error_msg = f'No hay entradas disponibles para cubrir el aumento de monto. Diferencia: RD$ {diferencia:.2f}'
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': False,
                            'message': error_msg
                        }, status=400)
                    messages.error(request, error_msg)
                    return redirect('servicios_index')
            
            # Actualizar servicio - ¡NO CAMBIAR EL ESTADO!
            servicio.fecha = fecha
            servicio.monto = monto
            servicio.tipo_servicio = tipo_servicio
            servicio.tipo_comprobante = tipo_comprobante
            servicio.proveedor = proveedor
            servicio.descripcion = descripcion
            # NO CAMBIES EL ESTADO: servicio.estado = 'EDITADO'
            
            # Manejar archivo de comprobante si se proporciona uno nuevo
            if 'receipt' in request.FILES:
                servicio.imagen = request.FILES['receipt']
            
            servicio.save()
            
            print(f"Servicio {pk} actualizado exitosamente")
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Pago de servicio actualizado exitosamente'
                })
            else:
                messages.success(request, 'Pago de servicio actualizado exitosamente')
                
        except Exception as e:
            error_msg = f'Error al editar servicio: {str(e)}'
            print(f"Error en servicios_editar: {error_msg}")
            import traceback
            traceback.print_exc()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': error_msg
                }, status=500)
            else:
                messages.error(request, error_msg)
    
    return redirect('servicios_index')

def servicios_metodos_pago(request):
    """API para obtener los métodos de pago disponibles"""
    try:
        # Importar los choices del modelo
        from .models import TIPO_COMPROBANTE_CHOICES
        
        print("=== SERVICIOS_METODOS_PAGO LLAMADA ===")
        print(f"TIPO_COMPROBANTE_CHOICES: {TIPO_COMPROBANTE_CHOICES}")
        
        return JsonResponse({
            'metodos_pago': TIPO_COMPROBANTE_CHOICES,
            'success': True
        })
        
    except Exception as e:
        print(f"Error en servicios_metodos_pago: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Fallback a valores por defecto
        metodos_pago = [
            ("SIN_COMPROBANTE", "Sin Comprobante"),
            ("FACTURA", "Factura"),
            ("RECIBO", "Recibo"),
            ("TICKET", "Ticket"),
            ("TRANSFERENCIA", "Transferencia"),
        ]
        
        return JsonResponse({
            'metodos_pago': metodos_pago,
            'success': False,
            'error': str(e)
        })

@transaction.atomic
def servicios_eliminar(request, pk):
    """Eliminar lógicamente un pago de servicio - Soporta AJAX"""
    servicio = get_object_or_404(ServicioPago, pk=pk)
    
    try:
        servicio.estado = 'ELIMINADO'
        servicio.save()
        
        print(f"Servicio {pk} eliminado exitosamente")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Pago de servicio eliminado exitosamente'
            })
        else:
            messages.success(request, 'Pago de servicio eliminado exitosamente')
            
    except Exception as e:
        error_msg = f'Error al eliminar servicio: {str(e)}'
        print(f"Error en servicios_eliminar: {error_msg}")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': error_msg
            }, status=500)
        else:
            messages.error(request, error_msg)
    
    return redirect('servicios_index')

def servicios_pdf(request, pk):
    """Generar PDF individual del servicio"""
    servicio = get_object_or_404(ServicioPago, pk=pk)
    
    # Crear respuesta HTTP con tipo PDF
    response = HttpResponse(content_type='application/pdf')
    filename = f'servicio_{servicio.id}_{servicio.fecha.strftime("%Y%m%d")}.pdf'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    # Crear PDF
    p = canvas.Canvas(response, pagesize=letter)
    width, height = letter
    
    # Encabezado
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, height - 100, "COMPROBANTE DE PAGO DE SERVICIO")
    p.line(100, height - 105, width - 100, height - 105)
    
    # Información del servicio
    p.setFont("Helvetica", 12)
    y = height - 140
    
    # Fecha
    p.drawString(100, y, f"Fecha: {servicio.fecha.strftime('%d/%m/%Y')}")
    y -= 25
    
    # Tipo de servicio
    p.drawString(100, y, f"Servicio: {servicio.get_tipo_servicio_display()}")
    y -= 25
    
    # Monto
    p.drawString(100, y, f"Monto: RD$ {servicio.monto:,.2f}")
    y -= 25
    
    # Método de pago
    p.drawString(100, y, f"Método de pago: {servicio.tipo_comprobante}")
    y -= 25
    
    # Proveedor/Registrado por
    p.drawString(100, y, f"Registrado por: {servicio.proveedor}")
    y -= 25
    
    # Entrada asociada
    if servicio.entrada:
        p.drawString(100, y, f"Entrada Asociada: #{servicio.entrada.id}")
        y -= 25
        p.drawString(100, y, f"Monto Entrada: RD$ {servicio.entrada.monto_pesos:,.2f}")
        y -= 25
    
    # Descripción
    if servicio.descripcion:
        # Manejar descripción larga
        descripcion = servicio.descripcion
        if len(descripcion) > 80:
            # Dividir en líneas
            lines = []
            while len(descripcion) > 80:
                space_index = descripcion[:80].rfind(' ')
                if space_index == -1:
                    space_index = 80
                lines.append(descripcion[:space_index])
                descripcion = descripcion[space_index:].strip()
            lines.append(descripcion)
            
            p.drawString(100, y, "Descripción:")
            y -= 20
            for line in lines:
                if y < 100:  # Nueva página si es necesario
                    p.showPage()
                    p.setFont("Helvetica", 12)
                    y = height - 100
                p.drawString(120, y, line)
                y -= 20
        else:
            p.drawString(100, y, f"Descripción: {servicio.descripcion}")
            y -= 25
    
    # Estado
    p.drawString(100, y, f"Estado: {servicio.get_estado_display()}")
    
    # Pie de página
    p.setFont("Helvetica-Oblique", 10)
    p.drawString(100, 50, f"Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    
    p.showPage()
    p.save()
    
    return response

def servicios_pdf_historial(request):
    """Generar PDF del historial completo de servicios"""
    # Obtener filtros
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    tipo_servicio = request.GET.get('tipo_servicio', '')
    proveedor = request.GET.get('proveedor', '')
    
    # Aplicar mismos filtros que en la vista principal
    servicios = ServicioPago.objects.exclude(estado='ELIMINADO')
    
    if fecha_desde:
        servicios = servicios.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        servicios = servicios.filter(fecha__lte=fecha_hasta)
    if tipo_servicio:
        servicios = servicios.filter(tipo_servicio=tipo_servicio)
    if proveedor:
        servicios = servicios.filter(proveedor=proveedor)
    
    servicios = servicios.order_by('-fecha')
    
    # Calcular total
    total_servicios = servicios.aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    
    # Crear respuesta HTTP con tipo PDF
    response = HttpResponse(content_type='application/pdf')
    filename = f'historial_servicios_{datetime.now().strftime("%Y%m%d")}.pdf'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    # Crear PDF
    p = canvas.Canvas(response, pagesize=letter)
    width, height = letter
    
    # Encabezado
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, height - 100, "HISTORIAL DE PAGOS DE SERVICIOS")
    p.line(100, height - 105, width - 100, height - 105)
    
    # Información del reporte
    p.setFont("Helvetica", 10)
    p.drawString(100, height - 130, f"Fecha de generación: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    p.drawString(100, height - 145, f"Total de registros: {servicios.count()}")
    
    # Filtros aplicados
    y = height - 170
    if fecha_desde or fecha_hasta or tipo_servicio or proveedor:
        p.drawString(100, y, "Filtros aplicados:")
        y -= 15
        if fecha_desde:
            p.drawString(120, y, f"Desde: {fecha_desde}")
            y -= 15
        if fecha_hasta:
            p.drawString(120, y, f"Hasta: {fecha_hasta}")
            y -= 15
        if tipo_servicio:
            p.drawString(120, y, f"Tipo de servicio: {tipo_servicio}")
            y -= 15
        if proveedor:
            p.drawString(120, y, f"Proveedor: {proveedor}")
            y -= 15
    
    # Tabla de servicios
    y -= 10
    p.setFont("Helvetica-Bold", 10)
    
    # Encabezados de tabla
    p.drawString(50, y, "Fecha")
    p.drawString(120, y, "Servicio")
    p.drawString(200, y, "Monto")
    p.drawString(280, y, "Método")
    p.drawString(350, y, "Registrado por")
    p.line(50, y-2, width-50, y-2)
    
    y -= 20
    p.setFont("Helvetica", 9)
    
    # Filas de datos
    for servicio in servicios:
        if y < 100:  # Nueva página si es necesario
            p.showPage()
            p.setFont("Helvetica", 9)
            y = height - 100
            
            # Volver a dibujar encabezados
            p.setFont("Helvetica-Bold", 10)
            p.drawString(50, y, "Fecha")
            p.drawString(120, y, "Servicio")
            p.drawString(200, y, "Monto")
            p.drawString(280, y, "Método")
            p.drawString(350, y, "Registrado por")
            p.line(50, y-2, width-50, y-2)
            y -= 20
            p.setFont("Helvetica", 9)
        
        # Datos del servicio
        p.drawString(50, y, servicio.fecha.strftime('%d/%m/%Y'))
        p.drawString(120, y, servicio.get_tipo_servicio_display()[:15])
        p.drawString(200, y, f"RD$ {servicio.monto:,.2f}")
        p.drawString(280, y, servicio.tipo_comprobante[:10])
        p.drawString(350, y, servicio.proveedor[:15] if servicio.proveedor else "N/A")
        
        y -= 15
    
    # Total
    y -= 10
    p.setFont("Helvetica-Bold", 10)
    p.drawString(200, y, f"TOTAL: RD$ {total_servicios:,.2f}")
    
    p.showPage()
    p.save()
    
    return response

def servicios_imprimir_historial(request):
    """Vista para imprimir historial de servicios"""
    # Obtener filtros (misma lógica que servicios_index)
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    tipo_servicio = request.GET.get('tipo_servicio', '')
    proveedor = request.GET.get('proveedor', '')
    estado = request.GET.get('estado', 'ACTIVO')
    
    servicios = ServicioPago.objects.exclude(estado='ELIMINADO')
    
    if fecha_desde:
        servicios = servicios.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        servicios = servicios.filter(fecha__lte=fecha_hasta)
    if tipo_servicio:
        servicios = servicios.filter(tipo_servicio=tipo_servicio)
    if proveedor:
        servicios = servicios.filter(proveedor=proveedor)
    if estado:
        servicios = servicios.filter(estado=estado)
    
    servicios = servicios.order_by('-fecha')
    
    # Calcular totales
    total_servicios = servicios.aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    totales = calcular_totales_servicios()
    
    context = {
        'servicios': servicios,
        'total_servicios': total_servicios,
        'totales': totales,
        'fecha_generacion': datetime.now(),
        'filtros': {
            'fecha_desde': fecha_desde,
            'fecha_hasta': fecha_hasta,
            'tipo_servicio': tipo_servicio,
            'proveedor': proveedor,
            'estado': estado,
        }
    }
    
    return render(request, 'finanzas/servicios_print.html', context)



# =============================================================================
# VISTA PRINCIPAL DEL DASHBOARD
# =============================================================================

def dashboard_index(request):
    """
    Renderiza la plantilla del dashboard sin datos
    Los datos se obtienen via API desde JavaScript
    """
    # Obtener mensajes Django
    from django.contrib.messages import get_messages
    messages_data = []
    for message in get_messages(request):
        messages_data.append({
            'text': str(message),
            'tags': message.tags
        })
    
    context = {
        'user': request.user,
        'django_messages_json': json.dumps(messages_data),
        'version': VERSION,  # ← AÑADIR AQUÍ LA VERSIÓN
    }
    
    return render(request, "finanzas/dashboard.html", context)
# =============================================================================
# API ENDPOINT PARA DATOS DEL DASHBOARD
# =============================================================================

def dashboard_api(request):
    """
    Endpoint API que devuelve todos los datos del dashboard en formato JSON
    """
    try:
        data = {
            "totales": get_totales_globales(),
            "mensuales": get_totales_mensuales(),
            "movimientos": get_movimientos_recientes(limit=10),
            "estadisticas": {
                "gastos_por_categoria": get_gastos_por_categoria(),
                "servicios_por_tipo": get_servicios_por_tipo(),
                # Datos para gráfico de resumen mensual (por mes)
                "entradas_por_mes": get_entradas_por_mes(),
                "gastos_por_mes": get_gastos_por_mes(),
                "servicios_por_mes": get_servicios_por_mes(),
                # Datos para gráfico de movilidad (por día)
                "entradas_por_dia": get_entradas_por_dia(),
                "gastos_por_dia": get_gastos_por_dia(),
                "servicios_por_dia": get_servicios_por_dia(),
            },
            "balances_por_entrada": get_totales_por_entrada()
        }
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

# =============================================================================
# FUNCIONES AUXILIARES CORREGIDAS
# =============================================================================

def get_totales_globales():
    """
    Calcula los totales globales del sistema
    """
    # Total de entradas (convertidor)
    total_entradas = MovimientoEntrada.objects.aggregate(
        total=Sum('monto_pesos')
    )['total'] or Decimal('0.00')
    
    # Total de gastos (solo activos)
    total_gastos = Gasto.objects.filter(estado='ACTIVO').aggregate(
        total=Sum('monto')
    )['total'] or Decimal('0.00')
    
    # Total de servicios (solo activos)
    total_servicios = ServicioPago.objects.filter(estado='ACTIVO').aggregate(
        total=Sum('monto')
    )['total'] or Decimal('0.00')
    
    # Total gastado (gastos + servicios)
    total_gastado = total_gastos + total_servicios
    
    # Balance general
    balance_general = total_entradas - total_gastado
    
    return {
        "total_entradas": float(total_entradas),
        "total_gastos": float(total_gastos),
        "total_servicios": float(total_servicios),
        "total_gastado": float(total_gastado),
        "balance_general": float(balance_general)
    }

def get_totales_mensuales():
    """
    Calcula los totales del mes actual
    """
    # Fechas para el mes actual usando timezone
    hoy = timezone.now()
    inicio_mes = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    fin_mes = hoy.replace(day=1, month=hoy.month+1 if hoy.month < 12 else 1, 
                         year=hoy.year+1 if hoy.month == 12 else hoy.year,
                         hour=23, minute=59, second=59, microsecond=999999)
    fin_mes = fin_mes - timedelta(days=1)
    
    # Entradas del mes
    entradas_mes = MovimientoEntrada.objects.filter(
        fecha__gte=inicio_mes,
        fecha__lte=fin_mes
    ).aggregate(total=Sum('monto_pesos'))['total'] or Decimal('0.00')
    
    # Gastos del mes (solo activos)
    gastos_mes = Gasto.objects.filter(
        estado='ACTIVO',
        fecha__gte=inicio_mes,
        fecha__lte=fin_mes
    ).aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    
    # Servicios del mes (solo activos)
    servicios_mes = ServicioPago.objects.filter(
        estado='ACTIVO',
        fecha__gte=inicio_mes,
        fecha__lte=fin_mes
    ).aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    
    # Total gastado del mes (gastos + servicios)
    total_gastado_mes = gastos_mes + servicios_mes
    
    return {
        "entradas_mes": float(entradas_mes),
        "gastos_mes": float(gastos_mes),
        "servicios_mes": float(servicios_mes),
        "total_gastado_mes": float(total_gastado_mes),
    }

def get_movimientos_recientes(limit=10):
    """
    Obtiene los movimientos más recientes de cada tipo
    Incluye proveedor para gastos y servicios
    CORREGIDO: Usar timezone para manejar correctamente las fechas
    """
    # Últimas entradas
    ultimas_entradas = list(MovimientoEntrada.objects.all().order_by('-fecha')[:limit].values(
        'id', 'monto_usd', 'tasa_cambio', 'monto_pesos', 'descripcion', 'fecha'
    ))
    
    # Últimos gastos (solo activos) - INCLUYE PROVEEDOR
    ultimos_gastos = list(Gasto.objects.filter(estado='ACTIVO').order_by('-fecha')[:limit].values(
        'id', 'categoria', 'monto', 'descripcion', 'fecha', 'entrada_id', 'proveedor'
    ))
    
    # Últimos servicios (solo activos) - INCLUYE PROVEEDOR
    ultimos_servicios = list(ServicioPago.objects.filter(estado='ACTIVO').order_by('-fecha')[:limit].values(
        'id', 'tipo_servicio', 'monto', 'descripcion', 'fecha', 'entrada_id', 'proveedor'
    ))
    
    # Convertir Decimal a float para JSON y formatear fechas correctamente
    for entrada in ultimas_entradas:
        entrada['monto_usd'] = float(entrada['monto_usd'])
        entrada['tasa_cambio'] = float(entrada['tasa_cambio'])
        entrada['monto_pesos'] = float(entrada['monto_pesos'])
        # CORREGIDO: Usar ISO format con timezone
        fecha_obj = entrada['fecha']
        if isinstance(fecha_obj, datetime):
            entrada['fecha'] = fecha_obj.isoformat()
        else:
            entrada['fecha'] = str(fecha_obj)
    
    for gasto in ultimos_gastos:
        gasto['monto'] = float(gasto['monto'])
        # CORREGIDO: Usar ISO format con timezone
        fecha_obj = gasto['fecha']
        if isinstance(fecha_obj, datetime):
            gasto['fecha'] = fecha_obj.isoformat()
        else:
            gasto['fecha'] = str(fecha_obj)
        if not gasto['proveedor']:
            gasto['proveedor'] = "No especificado"
    
    for servicio in ultimos_servicios:
        servicio['monto'] = float(servicio['monto'])
        # CORREGIDO: Usar ISO format con timezone
        fecha_obj = servicio['fecha']
        if isinstance(fecha_obj, datetime):
            servicio['fecha'] = fecha_obj.isoformat()
        else:
            servicio['fecha'] = str(fecha_obj)
        if not servicio['proveedor']:
            servicio['proveedor'] = "No especificado"
    
    return {
        "ultimas_entradas": ultimas_entradas,
        "ultimos_gastos": ultimos_gastos,
        "ultimos_servicios": ultimos_servicios
    }

def get_gastos_por_categoria():
    """
    Agrupa los gastos por categoría (solo activos)
    """
    gastos_por_categoria = Gasto.objects.filter(estado='ACTIVO').values(
        'categoria'
    ).annotate(
        total=Sum('monto'),
        cantidad=Count('id')
    ).order_by('-total')
    
    resultado = []
    for item in gastos_por_categoria:
        resultado.append({
            "categoria": item['categoria'],
            "total": float(item['total']),
            "cantidad": item['cantidad']
        })
    
    return resultado

def get_servicios_por_tipo():
    """
    Agrupa los servicios por tipo (solo activos)
    """
    servicios_por_tipo = ServicioPago.objects.filter(estado='ACTIVO').values(
        'tipo_servicio'
    ).annotate(
        total=Sum('monto'),
        cantidad=Count('id')
    ).order_by('-total')
    
    resultado = []
    for item in servicios_por_tipo:
        resultado.append({
            "tipo_servicio": item['tipo_servicio'],
            "total": float(item['total']),
            "cantidad": item['cantidad']
        })
    
    return resultado

def get_entradas_por_mes():
    """
    Agrupa las entradas por mes (últimos 6 meses)
    """
    # Últimos 6 meses
    seis_meses_atras = timezone.now() - timedelta(days=180)
    
    entradas_por_mes = MovimientoEntrada.objects.filter(
        fecha__gte=seis_meses_atras
    ).annotate(
        mes=TruncMonth('fecha')
    ).values('mes').annotate(
        total=Sum('monto_pesos')
    ).order_by('mes')
    
    resultado = []
    for item in entradas_por_mes:
        resultado.append({
            "mes": item['mes'].strftime('%Y-%m'),
            "total": float(item['total'])
        })
    
    return resultado

def get_gastos_por_mes():
    """
    Agrupa los gastos por mes (solo activos, últimos 6 meses)
    """
    # Últimos 6 meses
    seis_meses_atras = timezone.now() - timedelta(days=180)
    
    gastos_por_mes = Gasto.objects.filter(
        estado='ACTIVO',
        fecha__gte=seis_meses_atras
    ).annotate(
        mes=TruncMonth('fecha')
    ).values('mes').annotate(
        total=Sum('monto')
    ).order_by('mes')
    
    resultado = []
    for item in gastos_por_mes:
        resultado.append({
            "mes": item['mes'].strftime('%Y-%m'),
            "total": float(item['total'])
        })
    
    return resultado

def get_servicios_por_mes():
    """
    Agrupa los servicios por mes (solo activos, últimos 6 meses)
    """
    # Últimos 6 meses
    seis_meses_atras = timezone.now() - timedelta(days=180)
    
    servicios_por_mes = ServicioPago.objects.filter(
        estado='ACTIVO',
        fecha__gte=seis_meses_atras
    ).annotate(
        mes=TruncMonth('fecha')
    ).values('mes').annotate(
        total=Sum('monto')
    ).order_by('mes')
    
    resultado = []
    for item in servicios_por_mes:
        resultado.append({
            "mes": item['mes'].strftime('%Y-%m'),
            "total": float(item['total'])
        })
    
    return resultado

def get_entradas_por_dia():
    """
    Agrupa las entradas por día (últimos 30 días)
    """
    # Últimos 30 días
    treinta_dias_atras = timezone.now() - timedelta(days=30)
    
    entradas_por_dia = MovimientoEntrada.objects.filter(
        fecha__gte=treinta_dias_atras
    ).annotate(
        dia=TruncDay('fecha')
    ).values('dia').annotate(
        total=Sum('monto_pesos')
    ).order_by('dia')
    
    resultado = []
    for item in entradas_por_dia:
        resultado.append({
            "dia": item['dia'].strftime('%Y-%m-%d'),
            "total": float(item['total'])
        })
    
    return resultado

def get_gastos_por_dia():
    """
    Agrupa los gastos por día (solo activos, últimos 30 días)
    """
    # Últimos 30 días
    treinta_dias_atras = timezone.now() - timedelta(days=30)
    
    gastos_por_dia = Gasto.objects.filter(
        estado='ACTIVO',
        fecha__gte=treinta_dias_atras
    ).annotate(
        dia=TruncDay('fecha')
    ).values('dia').annotate(
        total=Sum('monto')
    ).order_by('dia')
    
    resultado = []
    for item in gastos_por_dia:
        resultado.append({
            "dia": item['dia'].strftime('%Y-%m-%d'),
            "total": float(item['total'])
        })
    
    return resultado

def get_servicios_por_dia():
    """
    Agrupa los servicios por día (solo activos, últimos 30 días)
    """
    # Últimos 30 días
    treinta_dias_atras = timezone.now() - timedelta(days=30)
    
    servicios_por_dia = ServicioPago.objects.filter(
        estado='ACTIVO',
        fecha__gte=treinta_dias_atras
    ).annotate(
        dia=TruncDay('fecha')
    ).values('dia').annotate(
        total=Sum('monto')
    ).order_by('dia')
    
    resultado = []
    for item in servicios_por_dia:
        resultado.append({
            "dia": item['dia'].strftime('%Y-%m-%d'),
            "total": float(item['total'])
        })
    
    return resultado

def get_totales_por_entrada():
    """
    Calcula el balance por cada entrada individual
    """
    entradas = MovimientoEntrada.objects.all().order_by('-fecha')
    balances = []
    
    for entrada in entradas:
        # Total gastado en esta entrada
        gastado = Gasto.objects.filter(
            entrada=entrada,
            estado='ACTIVO'
        ).aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
        
        # Total servicios en esta entrada
        servicios = ServicioPago.objects.filter(
            entrada=entrada,
            estado='ACTIVO'
        ).aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
        
        # Total gastado (gastos + servicios)
        total_gastado = gastado + servicios
        
        # Saldo disponible
        saldo = entrada.monto_pesos - total_gastado
        
        balances.append({
            "entrada_id": entrada.id,
            "descripcion": entrada.descripcion or "Sin descripción",
            "monto_pesos": float(entrada.monto_pesos),
            "gastado": float(gastado),
            "servicios": float(servicios),
            "total_gastado": float(total_gastado),
            "saldo": float(saldo),
            "fecha": entrada.fecha.isoformat()
        })
    
    return balances
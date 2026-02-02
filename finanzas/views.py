# ----------------------------------------------------------------------
# 1. IMPORTS DE LA BIBLIOTECA ESTÁNDAR (Standard Library)
# ----------------------------------------------------------------------
import pytz
from datetime import datetime
from decimal import Decimal
from django.http import JsonResponse
import os
import calendar
import pytz
import json
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta

# ----------------------------------------------------------------------
# 2. IMPORTS DE TERCEROS (Third-Party)
# ----------------------------------------------------------------------
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from reportlab.lib.pagesizes import letter, A4, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch, cm
from reportlab.platypus.flowables import HRFlowable, KeepTogether
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO

# ----------------------------------------------------------------------
# 3. IMPORTS DE DJANGO
# ----------------------------------------------------------------------
from django.contrib import messages
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from django.contrib.auth import authenticate, logout, login as auth_login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Sum, Q, F, Count
from django.db.models.functions import Coalesce, TruncMonth, TruncDay
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib.messages import get_messages
from django.views import View
from django.views.decorators.cache import never_cache

# ----------------------------------------------------------------------
# 4. IMPORTS DE APLICACIONES LOCALES
# ----------------------------------------------------------------------
from finanzas import VERSION
from finanzas.models import Gasto, MovimientoEntrada, ServicioPago, SERVICIOS_TIPOS


#==========#=============#==========#======#============#===============#==================#=================#
#==========#=============#==========#======#============#===============#==================#=================#


#==============================================================================
# VISTA DE LOGIN
#==============================================================================
@ensure_csrf_cookie
def login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        # Autenticar usuario
        user = authenticate(request, username=username, password=password)
        # Obtener mensajes y convertirlos a JSON seguro
        messages_data = []
        for message in get_messages(request):
            messages_data.append({
                'text': str(message),
                'tags': message.tags
            })

        context = {
            'django_messages_json': json.dumps(messages_data),
        }

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

#==============================================================================
# CERRAR SESIÓN
#==============================================================================
def logout_view(request):
    """Vista para cerrar sesión"""
    logout(request)
    request.session.flush()
    messages.success(request, 'Sesión cerrada exitosamente')
    return redirect('index')


#==========#=============#==========#======#============#===============#==================#=================#
#==========#=============#==========#======#============#===============#==================#=================#


# =============================================================================
# MÓDULO CONVERTIDOR - VISTAS
# =============================================================================
@login_required
@never_cache
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
@transaction.atomic
@never_cache
def convertidor_registrar(request):
    """
    Maneja el registro de nuevos movimientos de conversión - VERSIÓN CORREGIDA
    Con manejo correcto de zona horaria para República Dominicana
    """
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            monto_usd = request.POST.get('monto_usd')
            tasa_cambio = request.POST.get('tasa_cambio')
            descripcion = request.POST.get('descripcion', '').strip()
            fecha = request.POST.get('fecha')
            imagen = request.FILES.get('imagen')  # Obtener la imagen

            print(
                f"Datos recibidos - USD: {monto_usd}, Tasa: {tasa_cambio}, Fecha: {fecha}, Imagen: {imagen}")

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
                monto_usd_decimal = Decimal(str(monto_usd).replace(',', '.'))
                tasa_cambio_decimal = Decimal(
                    str(tasa_cambio).replace(',', '.'))
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
                    # Parsear fecha de forma segura
                    fecha_dt = datetime.strptime(fecha, '%Y-%m-%d')

                    # Configurar zona horaria de República Dominicana (AST, UTC-4)
                    tz_rd = pytz.timezone('America/Santo_Domingo')

                    # SOLUCIÓN: Establecer la hora a mediodía (12:00 PM) en la zona horaria local
                    # Esto evita el problema del desfase de 4 horas
                    fecha_dt = fecha_dt.replace(
                        hour=12, minute=0, second=0, microsecond=0)

                    # Localizar la fecha en la zona horaria de República Dominicana
                    movimiento.fecha = tz_rd.localize(fecha_dt)

                    print(f"Fecha procesada correctamente: {movimiento.fecha}")

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
@never_cache
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
@transaction.atomic
@never_cache
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
@transaction.atomic
@never_cache
def convertidor_eliminar(request, id):
    """
    Elimina un movimiento si no tiene gastos ni servicios asociados CON MANEJO DE IMÁGENES
    """
    if request.method == 'POST':
        try:
            movimiento = get_object_or_404(MovimientoEntrada, id=id)

            # Verificar si tiene gastos o servicios asociados
            tiene_gastos = Gasto.objects.filter(entrada=movimiento).exists()
            tiene_servicios = ServicioPago.objects.filter(
                entrada=movimiento).exists()

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

#=============================================================================
# REPORTE PDF - HISTORIAL COMPLETO  DEL  CONVERTIDOR
#=============================================================================
@never_cache
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
        Paragraph("MLAN FINANCE Sistema de Reportes Financieros", title_style),
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
    datos_reporte.append(
        ["Usuario Encargado:", request.user.get_full_name() or request.user.username])
    datos_reporte.append(["Total de registros:", str(total_movimientos)])

    # Solo agregar filtros si se aplicaron
    if fecha_inicio or fecha_fin:
        datos_reporte.append(
            ["Período del reporte:", f"Del {fecha_inicio_str} al {fecha_fin_str}"])

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
            fecha_formateada = mov.fecha_formateada if hasattr(
                mov, 'fecha_formateada') else mov.fecha.strftime('%d/%m/%Y')

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
                table_style.add('BACKGROUND', (0, i), (-1, i),
                                colors.HexColor('#f8f8f8'))

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
        elements.append(
            Paragraph("NO SE ENCONTRARON MOVIMIENTOS", no_data_style))
        elements.append(Spacer(1, 15))

    elements.append(Spacer(1, 20))

    # OBSERVACIONES (similar a la sección de observaciones en la imagen)
    elements.append(Paragraph("OBSERVACIONES", section_style))
    elements.append(Spacer(1, 6))

    # Crear observaciones dinámicas
    observaciones_text = "Reporte generado automáticamente por el sistema. "
    if total_movimientos > 0:
        observaciones_text += f"Se encontraron {total_movimientos} conversiones (Regiastros). "
        observaciones_text += f"Total convertido: ${total_usd:,.2f} USD (Dolores) → ${total_pesos:,.2f} DOP (Peso Dominicano). "

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
    elements.append(Paragraph(
        f"Sistema de Conversión de Divisas  MLAN FINANCE | Generado el {datetime.now().strftime('%d/%m/%Y %I:%M')}", footer_style))
    elements.append(Paragraph(
        "Este reporte constituye documentación oficial del sistema", footer_style))

    # Construir el PDF
    doc.build(elements)

    # Obtener el valor del buffer
    pdf = buffer.getvalue()
    buffer.close()

    # Crear respuesta HTTP
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="reporte_conversiones_{datetime.now().strftime("%d/%m/%Y_%I:%M:%S")}.pdf"'
    response.write(pdf)

    return response

#=============================================================================
# REPORTE PDF - DETALLE ESPECÍFICO  DEL  CONVERTIDOR
#=============================================================================
@never_cache
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
        Paragraph("MLAN FINANCE Sistema de Reportes Financieros", title_style),
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
    datos_movimiento.append(
        ["Fecha de Conversión:", movimiento.fecha.strftime('%d/%m/%Y %I:%M')])
    datos_movimiento.append(
        ["Usuario Encargado:", request.user.get_full_name() or request.user.username])
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
    fecha_formateada = movimiento.fecha_formateada if hasattr(
        movimiento, 'fecha_formateada') else movimiento.fecha.strftime('%d/%m/%Y')

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
    elements.append(Paragraph(
        f"Sistema de Conversión de Divisas MLAN FINANCE | Generado el {datetime.now().strftime('%d/%m/%Y %I:%M')}", footer_style))
    elements.append(Paragraph(
        "Este reporte constituye documentación oficial del sistema", footer_style))

    # Construir el PDF
    doc.build(elements)

    # Obtener el valor del buffer
    pdf = buffer.getvalue()
    buffer.close()

    # Crear respuesta HTTP
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="movimiento_{id}_{datetime.now().strftime("%d/%m/%Y/%I:%M:%S")}.pdf"'
    response.write(pdf)

    return response

#=============================================================================
# VISTA PARA IMPRIMIR TODO EL HISTORIAL DE CONVERSIONES
#=============================================================================
@never_cache
def convertidor_imprimir_todo(request):
    """
    Vista para imprimir todo el historial de conversiones (MovimientoEntrada)
    """
    # Obtener filtros del request
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')
    descripcion = request.GET.get('descripcion', '')
    monto_min_usd = request.GET.get('monto_min', '')

    # Filtrar movimientos de entrada
    conversiones = MovimientoEntrada.objects.all()

    # Aplicar filtros
    if fecha_inicio:
        try:
            # Convertir a datetime para comparación
            fecha_inicio_dt = datetime.strptime(fecha_inicio, '%Y-%m-%d')
            conversiones = conversiones.filter(fecha__gte=fecha_inicio_dt)
        except ValueError:
            pass

    if fecha_fin:
        try:
            # Convertir a datetime y agregar un día para incluir todo el día
            fecha_fin_dt = datetime.strptime(
                fecha_fin, '%Y-%m-%d') + timedelta(days=1)
            conversiones = conversiones.filter(fecha__lt=fecha_fin_dt)
        except ValueError:
            pass

    if descripcion:
        conversiones = conversiones.filter(descripcion__icontains=descripcion)

    if monto_min_usd:
        try:
            monto_min_decimal = Decimal(monto_min_usd)
            conversiones = conversiones.filter(
                monto_usd__gte=monto_min_decimal)
        except (ValueError, InvalidOperation):
            pass

    # Ordenar por fecha descendente (más reciente primero)
    conversiones = conversiones.order_by('-fecha')

    # Obtener la fecha de la primera y última conversión
    primera_fecha = None
    ultima_fecha = None

    if conversiones.exists():
        # Obtener la fecha más antigua
        try:
            primera_fecha_conv = conversiones.last()  # Última en orden ascendente
            primera_fecha = primera_fecha_conv.fecha_display
        except Exception:
            pass

        # Obtener la fecha más reciente
        try:
            ultima_fecha_conv = conversiones.first()  # Primera en orden descendente
            ultima_fecha = ultima_fecha_conv.fecha_display
        except Exception:
            pass

    # Preparar datos para el template
    conversiones_data = []
    for idx, conversion in enumerate(conversiones, 1):
        # Usar monto_pesos ya calculado en el modelo
        monto_pesos = conversion.monto_pesos

        conversiones_data.append({
            'numero': idx,
            'fecha': conversion.fecha_display,
            'fecha_completa': conversion.fecha_completa_rd,
            'monto_usd': f"${conversion.monto_usd:,.2f}",
            'tasa_cambio': f"{conversion.tasa_cambio:,.2f}",
            'monto_pesos': f"RD$ {monto_pesos:,.2f}",
            'descripcion': conversion.descripcion or 'Sin descripción',
            'descripcion_corta': conversion.descripcion_corta,
            'tiene_imagen': bool(conversion.imagen),
            'mostrar_ver_mas': conversion.mostrar_ver_mas,
        })

    # Calcular totales
    total_conversiones = conversiones.count()

    total_usd_result = conversiones.aggregate(
        total=Sum('monto_usd')
    )
    total_usd = total_usd_result['total'] or Decimal('0.00')

    total_pesos_result = conversiones.aggregate(
        total=Sum('monto_pesos')
    )
    total_pesos = total_pesos_result['total'] or Decimal('0.00')

    # Calcular tasa promedio ponderada
    tasa_promedio = "N/A"
    if total_usd > 0:
        try:
            tasa_promedio = f"{total_pesos / total_usd:,.2f}"
        except (ZeroDivisionError, InvalidOperation):
            tasa_promedio = "N/A"

    # Si no hay filtros de fecha, usar las fechas del primer y último registro
    fecha_inicio_mostrar = fecha_inicio if fecha_inicio else primera_fecha
    fecha_fin_mostrar = fecha_fin if fecha_fin else ultima_fecha

    # Formatear fechas para mostrar si están en formato YYYY-MM-DD
    try:
        if fecha_inicio_mostrar and '-' in fecha_inicio_mostrar:
            fecha_obj = datetime.strptime(fecha_inicio_mostrar, '%Y-%m-%d')
            fecha_inicio_mostrar = fecha_obj.strftime('%d/%m/%Y')
    except ValueError:
        pass

    try:
        if fecha_fin_mostrar and '-' in fecha_fin_mostrar:
            fecha_obj = datetime.strptime(fecha_fin_mostrar, '%Y-%m-%d')
            fecha_fin_mostrar = fecha_obj.strftime('%d/%m/%Y')
    except ValueError:
        pass

    context = {
        'conversiones': conversiones_data,
        'total_conversiones': total_conversiones,
        'total_usd': f"${total_usd:,.2f}",
        'total_pesos': f"RD$ {total_pesos:,.2f}",
        'fecha_generacion': datetime.now().strftime('%d/%m/%Y %I:%M %p'),
        'filtros': {
            'fecha_inicio': fecha_inicio_mostrar,
            'fecha_fin': fecha_fin_mostrar,
            'descripcion': descripcion,
            'monto_min': monto_min_usd,
        },
        'primera_fecha': primera_fecha,
        'ultima_fecha': ultima_fecha,
        'tasa_promedio': tasa_promedio,
    }

    return render(request, 'finanzas/convertidor_print.html', context)

#===========================================================================
#API PARA OBTENER MOVIMIENTOS CON FILTROS
#===========================================================================
@never_cache
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
            movimientos = movimientos.filter(
                descripcion__icontains=descripcion)
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

#===========================================================================
#API PARA OBTENER ESTADÍSTICAS CON FILTROS
#===========================================================================
@never_cache
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
            movimientos = movimientos.filter(
                descripcion__icontains=descripcion)
        if monto_min:
            movimientos = movimientos.filter(monto_usd__gte=float(monto_min))

        # Calcular estadísticas
        total_movimientos = movimientos.count()
        total_usd = movimientos.aggregate(total=Sum('monto_usd'))['total'] or 0
        total_pesos = movimientos.aggregate(
            total=Sum('monto_pesos'))['total'] or 0

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

#===========================================================================
#API PARA OBTENER ESTADÍSTICAS CON FILTROS - CORREGIDA
#===========================================================================
@never_cache
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
            movimientos = movimientos.filter(
                descripcion__icontains=descripcion)
        if monto_min:
            movimientos = movimientos.filter(monto_usd__gte=float(monto_min))

        # Calcular estadísticas
        total_movimientos = movimientos.count()
        total_usd = movimientos.aggregate(total=Sum('monto_usd'))['total'] or 0
        total_pesos = movimientos.aggregate(
            total=Sum('monto_pesos'))['total'] or 0

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

#===========================================================================
#API PARA OBTENER ESTADÍSTICAS CON GASTOS Y SERVICIOS ASOCIADOS - CORREGIDA
#===========================================================================
@never_cache
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
            movimientos = movimientos.filter(
                descripcion__icontains=descripcion)
        if monto_min:
            movimientos = movimientos.filter(monto_usd__gte=float(monto_min))

        # Calcular estadísticas
        total_movimientos = movimientos.count()
        total_usd = movimientos.aggregate(total=Sum('monto_usd'))['total'] or 0
        total_pesos = movimientos.aggregate(
            total=Sum('monto_pesos'))['total'] or 0

        # Calcular totales de gastos y servicios (placeholders por ahora)
        total_gastos = 0
        total_servicios = 0

        # Si hay movimientos, calcular gastos y servicios asociados
        if total_movimientos > 0:
            from .models import Gasto, ServicioPago
            total_gastos = Gasto.objects.filter(entrada__in=movimientos).aggregate(
                total=Sum('monto'))['total'] or 0
            total_servicios = ServicioPago.objects.filter(
                entrada__in=movimientos).aggregate(total=Sum('monto'))['total'] or 0

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


#==========#=============#==========#======#============#===============#==================#=================#
#==========#=============#==========#======#============#===============#==================#=================#


# =============================================================================
# VISTAS PRINCIPALES - VERSIÓN CORREGIDA DEL GASTOS
# =============================================================================
@login_required
@never_cache
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
    
#==============================================================================
# CÁLCULO DE SALDO DE ENTRADA - VERSIÓN CORREGIDA
#==============================================================================
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

#==============================================================================
# CÁLCULO DE TOTALES GENERALES - VERSIÓN CORREGIDA
#==============================================================================
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

#==============================================================================
# CREACIÓN DE GASTOS - VERSIÓN CORREGIDA
#==============================================================================
@transaction.atomic
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
            tipo_comprobante = request.POST.get(
                'tipo_comprobante', 'SIN_COMPROBANTE')
            # ❌ 'numero_comprobante' → ✅ 'numeroComprobante'
            numero_comprobante = request.POST.get(
                'numeroComprobante', '').strip()
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
                if not fecha:
                    missing_fields.append("fecha")
                if not monto:
                    missing_fields.append("monto")
                if not categoria:
                    missing_fields.append("categoría")
                if not descripcion:
                    missing_fields.append("descripción")

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

#==============================================================================
# EDICIÓN DE GASTOS - VERSIÓN CORREGIDA
#==============================================================================
@transaction.atomic
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
                tipo_comprobante = request.POST.get(
                    'tipoComprobante', 'SIN_COMPROBANTE')
                numero_comprobante = request.POST.get(
                    'numeroComprobante', '').strip()
                proveedor = request.POST.get('proveedor', '').strip()

                # Depuración
                print("Datos recibidos en edición:")
                print(
                    f"Fecha: {fecha}, Monto: {monto}, Categoría: {categoria}")
                print(f"Descripción: {descripcion}")
                print(f"Tipo Comprobante: {tipo_comprobante}")
                print(f"Número Comprobante: {numero_comprobante}")
                print(f"Proveedor: {proveedor}")

                # Validaciones básicas
                if not all([fecha, monto, categoria, descripcion]):
                    missing_fields = []
                    if not fecha:
                        missing_fields.append("fecha")
                    if not monto:
                        missing_fields.append("monto")
                    if not categoria:
                        missing_fields.append("categoría")
                    if not descripcion:
                        missing_fields.append("descripción")

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
                    saldo_disponible = calcular_saldo_entrada(
                        gasto.entrada) + gasto.monto
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

#==============================================================================
# ELIMINACIÓN LÓGICA DE GASTOS - VERSIÓN CORREGIDA
#==============================================================================
@transaction.atomic
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

#==============================================================================
# REPORTE PDF PROFESIONAL DE GASTOS - MISMO FORMATO QUE EL REPORTE DE CONVERSIÓN
#==============================================================================
def gastos_pdf(request, pk):
    """
    Genera reporte PDF profesional de un gasto específico
    """
    gasto = get_object_or_404(Gasto, id=pk)

    # Crear buffer para el PDF
    buffer = BytesIO()

    # Crear documento en modo portrait (A4 vertical)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5*cm,
        leftMargin=1.5*cm,
        topMargin=1.2*cm,
        bottomMargin=1.5*cm,
        title=f"Reporte Gasto {pk}"
    )

    # Estilos personalizados - MISMO FORMATO QUE EL REPORTE DE CONVERSIÓN
    styles = getSampleStyleSheet()

    # Título principal
    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Title'],
        fontSize=16,
        textColor=colors.black,
        spaceAfter=12,
        alignment=1,
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
        alignment=0,
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
        alignment=1,
        leading=10
    )

    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontSize=9,
        alignment=1,
        leading=10
    )

    table_cell_left_style = ParagraphStyle(
        'TableCellLeft',
        parent=styles['Normal'],
        fontSize=9,
        alignment=0,
        leading=10
    )

    # Elementos del documento
    elements = []

    # Crear una tabla de encabezado con logo a la izquierda y título a la derecha
    header_table_data = []

    # Intentar cargar el logo de la empresa - MISMA RUTA QUE EL REPORTE DE CONVERSIÓN
    try:
        logo_path = "static/img/logo.ico"
        logo = Image(logo_path, width=3.5*cm, height=2.5*cm)
        logo.hAlign = 'LEFT'
        logo_cell = logo
    except Exception as e:
        logo_cell = Paragraph("MLAN FINANCE", ParagraphStyle(
            'LogoPlaceholder',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.gray,
            alignment=1,
            fontName='Helvetica-Bold'
        ))

    # Crear celda con los títulos - MISMO FORMATO
    titles_cell = [
        Paragraph("MLAN FINANCE Sistema de Gestión Financiera", title_style),
        Spacer(1, 4),
        Paragraph(f"COMPROBANTE DE GASTO #{pk}",
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
        ('TOPPADDING', (0, 0), (0, 0), -10),
        ('TOPPADDING', (1, 0), (1, 0), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))

    elements.append(header_table)
    elements.append(Spacer(1, 10))

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
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('PADDING', (0, 0), (-1, -1), (4, 6)),
    ]))

    elements.append(fecha_table)
    elements.append(Spacer(1, 12))

    # DATOS DEL GASTO
    elements.append(Paragraph("DATOS DEL GASTO", section_style))
    elements.append(Spacer(1, 6))

    # Construir datos del gasto
    datos_gasto = []
    datos_gasto.append(["ID del Gasto:", f"#{pk}"])
    datos_gasto.append(["Fecha del Gasto:", gasto.fecha.strftime('%d/%m/%Y')])
    datos_gasto.append(["Usuario Registró:", gasto.usuario.get_full_name() if hasattr(
        gasto, 'usuario') else request.user.get_full_name() or request.user.username])

    # Estado con colores según el estado
    estado_text = gasto.estado
    estado_color = colors.black
    if gasto.estado.upper() in ['APROBADO', 'ACTIVO']:
        estado_color = colors.HexColor('#2e7d32')  # Verde
    elif gasto.estado.upper() in ['PENDIENTE', 'EDITADO']:
        estado_color = colors.HexColor('#f57c00')  # Naranja
    elif gasto.estado.upper() == 'RECHAZADO':
        estado_color = colors.HexColor('#c62828')  # Rojo

    estado_style = ParagraphStyle(
        'EstadoStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=estado_color,
        fontName='Helvetica-Bold',
        alignment=0,
        leading=12
    )

    datos_gasto.append(["Estado:", Paragraph(estado_text, estado_style)])

    # Agregar proveedor si existe
    if hasattr(gasto, 'proveedor') and gasto.proveedor:
        datos_gasto.append(["Proveedor:", gasto.proveedor])

    # Agregar tipo de comprobante si existe
    if hasattr(gasto, 'tipo_comprobante') and gasto.tipo_comprobante:
        tipo_comprobante = gasto.get_tipo_comprobante_display() if hasattr(
            gasto, 'get_tipo_comprobante_display') else gasto.tipo_comprobante
        datos_gasto.append(["Tipo Comprobante:", tipo_comprobante])

    datos_table = Table(datos_gasto, colWidths=[5*cm, 10*cm])
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

    # RESUMEN FINANCIERO
    elements.append(Paragraph("RESUMEN FINANCIERO", section_style))
    elements.append(Spacer(1, 6))

    resumen_data = [
        ["Descripción", "Monto", "Estado"],
        ["Monto del Gasto", f"RD$ {gasto.monto:,.2f}", "Registrado"],
        ["Categoría", gasto.get_categoria_display() if hasattr(
            gasto, 'get_categoria_display') else gasto.categoria, "Asignada"],
    ]

    # Agregar información de saldo si está disponible en el modelo
    if hasattr(gasto, 'saldo_disponible_antes'):
        resumen_data.append(
            ["Saldo Antes", f"RD$ {gasto.saldo_disponible_antes:,.2f}", "Disponible"])
        resumen_data.append(
            ["Saldo Después", f"RD$ {gasto.saldo_disponible_despues:,.2f}", "Calculado"])

    resumen_table = Table(resumen_data, colWidths=[8*cm, 4*cm, 3*cm])
    resumen_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e0e0e0')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('PADDING', (0, 0), (-1, -1), (4, 6)),
        ('TEXTCOLOR', (1, 1), (1, 1), colors.HexColor(
            '#c62828')),  # Rojo para monto del gasto
    ]))

    elements.append(resumen_table)
    elements.append(Spacer(1, 16))

    # DETALLE DEL GASTO
    elements.append(Paragraph("DETALLE DEL GASTO", section_style))
    elements.append(Spacer(1, 6))

    # Preparar datos de la tabla
    table_data = []

    # Encabezados
    headers = [
        Paragraph("Nº", table_header_style),
        Paragraph("FECHA", table_header_style),
        Paragraph("CATEGORÍA", table_header_style),
        Paragraph("DESCRIPCIÓN", table_header_style),
        Paragraph("MONTO", table_header_style),
        Paragraph("ESTADO", table_header_style)
    ]
    table_data.append(headers)

    # Agregar fila del gasto
    fecha_formateada = gasto.fecha.strftime('%d/%m/%Y')

    descripcion_text = gasto.descripcion or 'Sin descripción'
    if len(descripcion_text) > 25:
        descripcion_text = descripcion_text[:22] + "..."

    # Determinar color para el estado en la tabla
    estado_table_color = colors.black
    if gasto.estado.upper() in ['APROBADO', 'ACTIVO']:
        estado_table_color = colors.HexColor('#2e7d32')
    elif gasto.estado.upper() in ['PENDIENTE', 'EDITADO']:
        estado_table_color = colors.HexColor('#f57c00')
    elif gasto.estado.upper() == 'RECHAZADO':
        estado_table_color = colors.HexColor('#c62828')

    estado_table_style = ParagraphStyle(
        'EstadoTableCell',
        parent=table_cell_style,
        textColor=estado_table_color,
        fontName='Helvetica-Bold'
    )

    row = [
        Paragraph("1", table_cell_style),
        Paragraph(fecha_formateada, table_cell_style),
        Paragraph(gasto.get_categoria_display() if hasattr(
            gasto, 'get_categoria_display') else gasto.categoria, table_cell_style),
        Paragraph(descripcion_text, table_cell_left_style),
        Paragraph(f"RD$ {gasto.monto:,.2f}", table_cell_style),
        Paragraph(gasto.estado, estado_table_style)
    ]
    table_data.append(row)

    # Anchos de columna
    col_widths = [1.2*cm, 2.5*cm, 3.0*cm, 5.0*cm, 2.5*cm, 2.5*cm]
    table = Table(table_data, colWidths=col_widths, repeatRows=1)

    # Estilos de la tabla
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
        ('ALIGN', (2, 1), (2, -1), 'CENTER'),
        ('ALIGN', (3, 1), (3, -1), 'LEFT'),
        ('ALIGN', (4, 1), (4, -1), 'RIGHT'),
        ('ALIGN', (5, 1), (5, -1), 'CENTER'),

        # Padding
        ('PADDING', (0, 0), (-1, -1), (4, 4)),

        # Fila de datos
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#f8f8f8')),
        ('TEXTCOLOR', (4, 1), (4, 1), colors.HexColor(
            '#c62828')),  # Rojo para el monto
    ])

    table.setStyle(table_style)
    elements.append(table)
    elements.append(Spacer(1, 20))

    # OBSERVACIONES Y NOTAS
    elements.append(Paragraph("OBSERVACIONES Y NOTAS", section_style))
    elements.append(Spacer(1, 6))

    # Crear observaciones dinámicas
    observaciones_text = f"Comprobante de gasto registrado el {gasto.fecha.strftime('%d/%m/%Y')}. "
    observaciones_text += f"Monto: RD$ {gasto.monto:,.2f}. "
    observaciones_text += f"Categoría: {gasto.get_categoria_display() if hasattr(gasto, 'get_categoria_display') else gasto.categoria}. "
    observaciones_text += f"Estado: {gasto.estado}."

    # Agregar descripción completa si existe
    if gasto.descripcion and len(gasto.descripcion) > 100:
        observaciones_text += f"\n\nDescripción completa: {gasto.descripcion}"

    # Agregar notas adicionales si existen
    if hasattr(gasto, 'notas') and gasto.notas:
        observaciones_text += f"\n\nNotas adicionales: {gasto.notas}"

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
    elements.append(Paragraph(
        f"Sistema de Gestión de Gastos MLAN FINANCE | Generado el {datetime.now().strftime('%d/%m/%Y %I:%M')}", footer_style))
    elements.append(Paragraph(
        "Este comprobante constituye documentación oficial del sistema financiero", footer_style))

    # Construir el PDF
    doc.build(elements)

    # Obtener el valor del buffer
    pdf = buffer.getvalue()
    buffer.close()

    # Crear respuesta HTTP
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="gasto_{pk}_{datetime.now().strftime("%d-%m-%Y")}.pdf"'
    response.write(pdf)

    return response

#===========================================================================
# REPORTE PDF HISTORIAL COMPLETO DE GASTOS
#===========================================================================
def gastos_pdf_historial(request):
    """
    Genera reporte PDF profesional del historial completo de gastos
    """
    # Aplicar filtros
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

    gastos = gastos.order_by('-fecha')

    # Calcular totales
    total_gastos = gastos.count()
    total_gastado = gastos.aggregate(total=Sum('monto'))[
        'total'] or Decimal('0.00')

    # Formatear fechas para mostrar
    fecha_desde_str = fecha_desde if fecha_desde else "No especificada"
    fecha_hasta_str = fecha_hasta if fecha_hasta else "No especificada"

    # Si hay fechas, convertirlas al formato correcto (de YYYY-MM-DD a DD/MM/YYYY)
    if fecha_desde:
        try:
            fecha_obj = datetime.strptime(fecha_desde, '%Y-%m-%d')
            fecha_desde_str = fecha_obj.strftime('%d/%m/%Y')
        except:
            pass

    if fecha_hasta:
        try:
            fecha_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d')
            fecha_hasta_str = fecha_obj.strftime('%d/%m/%Y')
        except:
            pass

    # Formatear categoría para mostrar
    categoria_display = ""
    if categoria:
        categoria_display = dict(
            Gasto.CATEGORIAS_GASTOS).get(categoria, categoria)

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
        title="Reporte de Gastos"
    )

    # Estilos personalizados
    styles = getSampleStyleSheet()

    # Título principal
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

    # Intentar cargar el logo de la empresa
    try:
        logo_path = "static/img/logo.ico"
        logo = Image(logo_path, width=5*cm, height=3*cm)
        logo.hAlign = 'LEFT'
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
        Paragraph("MLAN FINANCE Sistema de Reportes Financieros", title_style),
        Spacer(1, 4),
        Paragraph("REPORTE HISTÓRICO DE GASTOS",
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

    # Fecha del reporte
    fecha_table_data = [
        ["Fecha del Reporte:", datetime.now().strftime('%d/%m/%Y %I:%M %p')]
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

    # DATOS DEL REPORTE
    elements.append(Paragraph("DATOS DEL REPORTE", section_style))
    elements.append(Spacer(1, 6))

    # Construir datos del reporte dinámicamente
    datos_reporte = []
    datos_reporte.append(
        ["Usuario Encargado:", request.user.get_full_name() or request.user.username])
    datos_reporte.append(["Total de registros:", str(total_gastos)])
    datos_reporte.append(["Estado de gastos:", "ACTIVO"])

    # Solo agregar filtros si se aplicaron
    if fecha_desde or fecha_hasta:
        datos_reporte.append(
            ["Período del reporte:", f"Del {fecha_desde_str} al {fecha_hasta_str}"])

    if categoria:
        datos_reporte.append(["Categoría filtrada:", categoria_display])

    if entrada_id:
        datos_reporte.append(["ID de Entrada:", entrada_id])

    # Agregar información de totales
    datos_reporte.append(["Total Gastado:", f"RD$ {total_gastado:,.2f}"])

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

    # DETALLE DE GASTOS
    if gastos.exists():
        elements.append(Paragraph("DETALLE DE GASTOS", section_style))
        elements.append(Spacer(1, 6))

        # Preparar datos de la tabla
        table_data = []

        # Encabezados
        headers = [
            Paragraph("Nº", table_header_style),
            Paragraph("FECHA", table_header_style),
            Paragraph("CATEGORÍA", table_header_style),
            Paragraph("DESCRIPCIÓN", table_header_style),
            Paragraph("MONTO", table_header_style),
            Paragraph("ESTADO", table_header_style)
        ]
        table_data.append(headers)

        # Agregar filas de datos
        for idx, gasto in enumerate(gastos, 1):
            # Formatear fecha
            fecha_formateada = gasto.fecha.strftime('%d/%m/%Y')

            # Obtener categoría
            categoria_gasto = gasto.get_categoria_display()[:20]

            # Truncar descripción si es muy larga
            descripcion_text = gasto.descripcion or 'Sin descripción'
            if len(descripcion_text) > 35:
                descripcion_text = descripcion_text[:32] + "..."

            row = [
                Paragraph(str(idx), table_cell_style),
                Paragraph(fecha_formateada, table_cell_style),
                Paragraph(categoria_gasto, table_cell_left_style),
                Paragraph(descripcion_text, table_cell_left_style),
                Paragraph(f"RD$ {gasto.monto:,.2f}", table_cell_style),
                Paragraph(gasto.estado, table_cell_style)
            ]
            table_data.append(row)

        # Anchos de columna
        col_widths = [1.2*cm, 2.5*cm, 3*cm, 5.5*cm, 3*cm, 2*cm]
        table = Table(table_data, colWidths=col_widths, repeatRows=1)

        # Estilos de la tabla
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
            ('ALIGN', (2, 1), (3, -1), 'LEFT'),
            ('ALIGN', (4, 1), (4, -1), 'RIGHT'),
            ('ALIGN', (5, 1), (5, -1), 'CENTER'),

            # Padding
            ('PADDING', (0, 0), (-1, -1), (4, 4)),

            # Filas alternas
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ])

        # Alternar colores de fila
        for i in range(1, len(table_data)):
            if i % 2 == 0:
                table_style.add('BACKGROUND', (0, i), (-1, i),
                                colors.HexColor('#f8f8f8'))

        table.setStyle(table_style)
        elements.append(table)

        # RESUMEN DE TOTALES
        elements.append(Spacer(1, 20))

        # Crear tabla de resumen
        resumen_data = [
            ["RESUMEN DE GASTOS", ""],
            ["Total de gastos registrados:", f"{total_gastos}"],
            ["Monto total gastado:", f"RD$ {total_gastado:,.2f}"],
        ]

        resumen_table = Table(resumen_data, colWidths=[8*cm, 7*cm])
        resumen_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('ALIGN', (0, 0), (1, 0), 'CENTER'),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (1, 0), 0.5, colors.black),
            ('GRID', (0, 1), (-1, -1), 0.5, colors.black),
            ('PADDING', (0, 0), (-1, -1), (6, 8)),
            ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#e0e0e0')),
            ('TEXTCOLOR', (0, 0), (1, 0), colors.black),
        ]))

        elements.append(resumen_table)

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
        elements.append(
            Paragraph("NO SE ENCONTRARON GASTOS REGISTRADOS", no_data_style))
        elements.append(Spacer(1, 15))

    elements.append(Spacer(1, 20))

    # OBSERVACIONES
    elements.append(Paragraph("OBSERVACIONES", section_style))
    elements.append(Spacer(1, 6))

    # Crear observaciones dinámicas
    observaciones_text = "Reporte generado automáticamente por el sistema MLAN FINANCE. "
    if total_gastos > 0:
        observaciones_text += f"Se encontraron {total_gastos} gastos registrados. "
        observaciones_text += f"Total gastado: RD$ {total_gastado:,.2f} (Peso Dominicano). "

    if fecha_desde or fecha_hasta:
        observaciones_text += f"Período del reporte: {fecha_desde_str} al {fecha_hasta_str}. "

    if categoria:
        observaciones_text += f"Filtrado por categoría: {categoria_display}. "

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
    elements.append(Paragraph(
        f"Sistema de Control de Gastos MLAN FINANCE | Generado el {datetime.now().strftime('%d/%m/%Y %I:%M %p')}", footer_style))
    elements.append(Paragraph(
        "Este reporte constituye documentación oficial del sistema", footer_style))

    # Construir el PDF
    doc.build(elements)

    # Obtener el valor del buffer
    pdf = buffer.getvalue()
    buffer.close()

    # Crear respuesta HTTP
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="reporte_gastos_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf"'
    response.write(pdf)

    return response

#=============================================================================
# VISTA PARA IMPRIMIR EL HISTORIAL DE GASTOS
#=============================================================================
def gastos_imprimir_historial(request):
    """
    Vista para imprimir el historial de gastos
    """
    # Aplicar mismos filtros que en gastos_index
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    categoria = request.GET.get('categoria', '')
    entrada_id = request.GET.get('entrada_id', '')
    proveedor = request.GET.get('proveedor', '')

    gastos = Gasto.objects.filter(estado='ACTIVO')

    if fecha_desde:
        gastos = gastos.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        gastos = gastos.filter(fecha__lte=fecha_hasta)
    if categoria:
        gastos = gastos.filter(categoria=categoria)
    if proveedor:
        gastos = gastos.filter(proveedor=proveedor)
    if entrada_id:
        gastos = gastos.filter(entrada_id=entrada_id)

    gastos = gastos.order_by('id')

    # Obtener la fecha del primer y último gasto para mostrar cuando no hay filtros
    primera_fecha = None
    ultima_fecha = None

    if gastos.exists():
        # Obtener la primera fecha (más antigua)
        primera_fecha_gasto = gastos.earliest('fecha')
        primera_fecha = primera_fecha_gasto.fecha.strftime('%d/%m/%Y')

        # Obtener la última fecha (más reciente)
        ultima_fecha_gasto = gastos.latest('fecha')
        ultima_fecha = ultima_fecha_gasto.fecha.strftime('%d/%m/%Y')

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
            'estado': gasto.estado,
            'proveedor': gasto.proveedor if gasto.proveedor else 'N/A',

        })

    # Calcular totales
    total_gastado = gastos.aggregate(total=Sum('monto'))[
        'total'] or Decimal('0.00')

    # Si no hay filtros de fecha, usar las fechas del primer y último registro
    fecha_desde_mostrar = fecha_desde if fecha_desde else primera_fecha
    fecha_hasta_mostrar = fecha_hasta if fecha_hasta else ultima_fecha

    context = {
        'gastos': gastos_data,
        'total_gastado': f"RD$ {total_gastado:,.2f}",
        'total_registros': len(gastos_data),
        'fecha_generacion': datetime.now().strftime('%d/%m/%Y %I:%M'),
        'filtros': {
            'fecha_desde': fecha_desde_mostrar,
            'fecha_hasta': fecha_hasta_mostrar,
            'categoria': categoria,
            'entrada_id': entrada_id
        },
        'primera_fecha': primera_fecha,
        'ultima_fecha': ultima_fecha
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

#=============================================================================
# API PARA OBTENER CATEGORÍAS
#=============================================================================
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

#=============================================================================
# API PARA OBTENER DATOS DEL DASHBOARD - VERSIÓN CORREGIDA
#=============================================================================
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

        total_gastos = gastos.aggregate(total=Sum('monto'))[
            'total'] or Decimal('0.00')

        # 3. Total de servicios activos (con filtros si existen)
        servicios = ServicioPago.objects.filter(estado='ACTIVO')

        if fecha_desde:
            servicios = servicios.filter(fecha__gte=fecha_desde)
        if fecha_hasta:
            servicios = servicios.filter(fecha__lte=fecha_hasta)

        total_servicios = servicios.aggregate(total=Sum('monto'))[
            'total'] or Decimal('0.00')

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

#=============================================================================
# API PARA OBTENER CATEGORÍAS - VERSIÓN CORREGIDA
#=============================================================================
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


#==========#=============#==========#======#============#===============#==================#=================#
#==========#=============#==========#======#============#===============#==================#=================#


# ==============================================================================
# VISTA PRINCIPAL DEL MÓDULO SERVICIOS
# ==============================================================================
@login_required
@never_cache
def servicios_index(request):
    """Vista principal del módulo servicios - Soporta AJAX"""
    try:
        # Obtener parámetros de filtro
        fecha_desde = request.GET.get('fecha_desde', '')
        fecha_hasta = request.GET.get('fecha_hasta', '')
        tipo_servicio = request.GET.get('tipo_servicio', '')
        proveedor = request.GET.get('proveedor', '')
        # Cambiado: por defecto vacío para incluir todos
        estado = request.GET.get('estado', '')

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
                # ✅ SOLUCIÓN: Convertir fecha a string YYYY-MM-DD para evitar problemas de zona horaria
                fecha_str = servicio.fecha.strftime(
                    '%Y-%m-%d') if servicio.fecha else None

                # Obtener URL de la imagen si existe
                imagen_url = None
                if servicio.imagen:
                    try:
                        # Construir URL absoluta usando request
                        imagen_url = request.build_absolute_uri(
                            servicio.imagen.url)
                    except Exception as img_error:
                        print(
                            f"Error construyendo URL de imagen para servicio {servicio.id}: {img_error}")
                        # En caso de error, intentar construir URL manualmente
                        if servicio.imagen.url.startswith('/'):
                            imagen_url = f"{request.scheme}://{request.get_host()}{servicio.imagen.url}"
                        else:
                            imagen_url = servicio.imagen.url

                servicios_data.append({
                    'id': servicio.id,
                    'fecha': fecha_str,  # ✅ USAR STRING EN LUGAR DE isoformat()
                    'tipo_servicio': servicio.tipo_servicio,
                    'monto': float(servicio.monto),
                    'tipo_comprobante': servicio.tipo_comprobante,
                    'proveedor': servicio.proveedor or '',
                    'descripcion': servicio.descripcion or '',
                    'notas': servicio.notas or '',
                    'entrada_descripcion': servicio.entrada.descripcion if servicio.entrada else '',
                    'entrada_id': servicio.entrada.id if servicio.entrada else None,
                    # AGREGAR CAMPOS DE IMAGEN
                    'imagen': imagen_url,
                    'comprobante_url': imagen_url,  # Para compatibilidad con frontend
                    'comprobante': imagen_url,      # Para compatibilidad con frontend
                    'estado': servicio.estado,      # Agregar estado también
                })

            totales = calcular_totales_servicios()

            response_data = {
                'servicios': servicios_data,
                'totales': {
                    'total_servicios': float(totales['total_servicios']),
                    'balance': float(totales['balance'])
                }
            }

            # LOG para depuración
            print(f"Total servicios serializados: {len(servicios_data)}")
            # Mostrar solo los primeros 3 para no saturar
            for i, s in enumerate(servicios_data[:3]):
                print(
                    f"Servicio {i+1} - ID: {s['id']}, Fecha: {s['fecha']}, Imagen URL: {s.get('imagen', 'NO TIENE')}")

            return JsonResponse(response_data)

        # Para peticiones normales, renderizar template
        entradas = MovimientoEntrada.objects.all().order_by('-fecha')
        totales = calcular_totales_servicios()

        # Obtener tipos de servicio
        try:
            from .models import SERVICIOS_TIPOS
            tipos_servicio = SERVICIOS_TIPOS
        except:
            tipos_servicio = ServicioPago._meta.get_field(
                'tipo_servicio').choices

        # Obtener proveedores únicos
        proveedores = ServicioPago.objects.exclude(
            estado='ELIMINADO'
        ).exclude(
            proveedor__isnull=True
        ).exclude(
            proveedor__exact=''
        ).values_list('proveedor', flat=True).distinct().order_by('proveedor')

        # Obtener métodos de pago (TIPO_COMPROBANTE_CHOICES)
        try:
            from .models import TIPO_COMPROBANTE_CHOICES
            metodos_pago = TIPO_COMPROBANTE_CHOICES
        except:
            metodos_pago = ServicioPago._meta.get_field(
                'tipo_comprobante').choices

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
            'metodos_pago': metodos_pago,  # Agregar métodos de pago al contexto
            'filtros': {
                'fecha_desde': fecha_desde,
                'fecha_hasta': fecha_hasta,
                'tipo_servicio': tipo_servicio,
                'proveedor': proveedor,
                'estado': estado,
            },
            'django_messages_json': json.dumps(messages_data),
            'version': VERSION,
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

        try:
            from .models import TIPO_COMPROBANTE_CHOICES
            metodos_pago = TIPO_COMPROBANTE_CHOICES
        except:
            metodos_pago = []

        return render(request, 'finanzas/servicios.html', {
            'servicios': [],
            'tipos_servicio': tipos_servicio,
            'proveedores': [],
            'entradas': [],
            'metodos_pago': metodos_pago,
            'totales': {'total_servicios': 0, 'balance': 0},
            'filtros': {},
            'version': VERSION,
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

#=============================================================================
# FUNCIONES AUXILIARES PARA CÁLCULO DE SALDOS EN SERVICIOS
#=============================================================================
def calcular_saldo_entrada_servicios(entrada):
    """Calcula saldo disponible para servicios en una entrada específica"""
    total_servicios = ServicioPago.objects.filter(
        entrada=entrada,
        estado='ACTIVO'
    ).aggregate(total=Sum('monto'))['total'] or Decimal('0.00')

    return entrada.monto_pesos - total_servicios

#=============================================================================
# FUNCIONES AUXILIARES PARA CÁLCULO DE TOTALES EN SERVIC
#=============================================================================
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

#=============================================================================
# # API PARA OBTENER TIPOS DE SERVICIO
#=============================================================================
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

#=============================================================================
# # API PARA OBTENER MÉTODOS DE PAGO EN SERVICIOS
#=============================================================================
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

#==============================================================================
# API PARA OBTENER PROVEEDORES ÚNICOS EN SERVICIOS
#==============================================================================
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

#=============================================================================
# CREAR SERVICIO
#=============================================================================
@transaction.atomic
def servicios_crear(request):
    """Crear nuevo pago de servicio - Soporta AJAX"""
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            fecha = request.POST.get('date')
            monto = _to_decimal(request.POST.get('amount'))
            tipo_servicio = request.POST.get('serviceType')
            tipo_comprobante = request.POST.get(
                'paymentMethod', 'SIN_COMPROBANTE')
            proveedor = request.POST.get('registrar', '')
            descripcion = request.POST.get('notes', '')

            print(
                f"Datos recibidos: fecha={fecha}, monto={monto}, tipo_servicio={tipo_servicio}, proveedor={proveedor}")

            # Validar campos obligatorios
            if not all([fecha, monto, tipo_servicio, proveedor]):
                missing = []
                if not fecha:
                    missing.append('fecha')
                if not monto:
                    missing.append('monto')
                if not tipo_servicio:
                    missing.append('tipo_servicio')
                if not proveedor:
                    missing.append('proveedor')

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
            messages.success(
                request, 'Pago de servicio registrado exitosamente')

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

#==============================================================================
# EDITAR SERVICIO
#=============================================================================
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
            tipo_comprobante = request.POST.get(
                'paymentMethod', 'SIN_COMPROBANTE')
            proveedor = request.POST.get('registrar', '')
            descripcion = request.POST.get('notes', '')

            print(
                f"Editando servicio {pk}: fecha={fecha}, monto={monto}, tipo_servicio={tipo_servicio}")

            # Validar campos obligatorios
            if not all([fecha, monto, tipo_servicio, proveedor]):
                missing = []
                if not fecha:
                    missing.append('fecha')
                if not monto:
                    missing.append('monto')
                if not tipo_servicio:
                    missing.append('tipo_servicio')
                if not proveedor:
                    missing.append('proveedor')

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
                messages.success(
                    request, 'Pago de servicio actualizado exitosamente')

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

#==============================================================================
# ELIMINAR SERVICIO
#=============================================================================
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
            messages.success(
                request, 'Pago de servicio eliminado exitosamente')

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

# =============================================================================
# REPORTE PDF PROFESIONAL DE SERVICIOS
# =============================================================================
def servicios_pdf(request, pk):
    """
    Genera reporte PDF profesional de un pago de servicio específico
    Mismo formato que convertidor_reporte_detalle_pdf
    """
    servicio = get_object_or_404(ServicioPago, pk=pk)

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
        title=f"Reporte Pago de Servicio {pk}"
    )

    # Estilos personalizados - MISMO FORMATO QUE EL REPORTE DE CONVERSIÓN
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
        logo_cell = Paragraph("MLAN FINANCE", ParagraphStyle(
            'LogoPlaceholder',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.gray,
            alignment=1,
            fontName='Helvetica-Bold'
        ))

    # Crear celda con los títulos - MISMO FORMATO QUE EL REPORTE HISTÓRICO
    titles_cell = [
        Paragraph("MLAN FINANCE Sistema de Reportes Financieros", title_style),
        Spacer(1, 4),
        Paragraph(f"COMPROBANTE DE PAGO DE SERVICIO #{pk}",
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

    # DATOS DEL SERVICIO (similar a "Datos del Reporte" en el histórico)
    elements.append(Paragraph("DATOS DEL SERVICIO", section_style))
    elements.append(Spacer(1, 6))

    # Construir datos del servicio dinámicamente
    datos_servicio = []
    datos_servicio.append(["ID del Servicio:", f"#{pk}"])
    datos_servicio.append(
        ["Fecha del Pago:", servicio.fecha.strftime('%d/%m/%Y')])

    # Usuario que registró (si está disponible)
    if hasattr(servicio, 'usuario'):
        datos_servicio.append(
            ["Usuario Registró:", servicio.usuario.get_full_name()])
    else:
        datos_servicio.append(
            ["Usuario Registró:", request.user.get_full_name() or request.user.username])

    # Proveedor/Registrado por
    datos_servicio.append(["Proveedor/Registrado por:", servicio.proveedor])

    # Estado con colores según el estado
    estado_text = servicio.estado
    estado_color = colors.black
    if servicio.estado.upper() in ['APROBADO', 'ACTIVO']:
        estado_color = colors.HexColor('#2e7d32')  # Verde
    elif servicio.estado.upper() in ['PENDIENTE', 'EDITADO']:
        estado_color = colors.HexColor('#f57c00')  # Naranja
    elif servicio.estado.upper() == 'RECHAZADO':
        estado_color = colors.HexColor('#c62828')  # Rojo

    estado_style = ParagraphStyle(
        'EstadoStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=estado_color,
        fontName='Helvetica-Bold',
        alignment=0,
        leading=12
    )

    datos_servicio.append(["Estado:", Paragraph(estado_text, estado_style)])

    # Entrada asociada si existe
    if servicio.entrada:
        datos_servicio.append(["Entrada Asociada:", f"#{servicio.entrada.id}"])
        datos_servicio.append(
            ["Monto Entrada:", f"RD$ {servicio.entrada.monto_pesos:,.2f}"])

    # Descripción si existe
    if servicio.descripcion:
        descripcion_text = servicio.descripcion
        if len(descripcion_text) > 40:
            descripcion_text = descripcion_text[:37] + "..."
        datos_servicio.append(["Descripción:", descripcion_text])

    datos_table = Table(datos_servicio, colWidths=[5*cm, 10*cm])
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

    # RESUMEN DEL PAGO (similar a "Resúmenes Totales" en el histórico)
    elements.append(Paragraph("RESUMEN DEL PAGO", section_style))
    elements.append(Spacer(1, 6))

    # Obtener el tipo de servicio como texto descriptivo
    tipo_servicio_text = servicio.get_tipo_servicio_display() if hasattr(
        servicio, 'get_tipo_servicio_display') else servicio.tipo_servicio

    # Obtener el tipo de comprobante como texto descriptivo
    tipo_comprobante_text = servicio.get_tipo_comprobante_display() if hasattr(
        servicio, 'get_tipo_comprobante_display') else servicio.tipo_comprobante

    resumen_data = [
        ["Descripción", "Monto", "Estado"],
        ["Tipo de Servicio", tipo_servicio_text, "Registrado"],
        ["Monto del Servicio", f"RD$ {servicio.monto:,.2f}", "Pagado"],
        ["Método de Pago", tipo_comprobante_text, "Verificado"],
    ]

    # Agregar información de saldo si está disponible en el modelo
    if servicio.entrada:
        # Calcular saldo disponible antes y después
        saldo_antes = servicio.entrada.monto_pesos
        saldo_despues = saldo_antes - servicio.monto

        resumen_data.append(
            ["Saldo Entrada Inicial", f"RD$ {saldo_antes:,.2f}", "Disponible"])
        resumen_data.append(
            ["Saldo Después del Pago", f"RD$ {saldo_despues:,.2f}", "Calculado"])

    resumen_table = Table(resumen_data, colWidths=[8*cm, 4*cm, 3*cm])
    resumen_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e0e0e0')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('PADDING', (0, 0), (-1, -1), (4, 6)),
        ('TEXTCOLOR', (1, 2), (1, 2), colors.HexColor(
            '#2e7d32')),  # Verde para monto pagado
    ]))

    elements.append(resumen_table)
    elements.append(Spacer(1, 16))

    # DETALLE DEL PAGO (similar a "Detalle de Conversiones" en el histórico)
    elements.append(Paragraph("DETALLE DEL PAGO", section_style))
    elements.append(Spacer(1, 6))

    # Preparar datos de la tabla - MISMA ESTRUCTURA QUE EL HISTÓRICO
    table_data = []

    # Encabezados - adaptados para servicios
    headers = [
        Paragraph("Nº", table_header_style),
        Paragraph("FECHA", table_header_style),
        Paragraph("SERVICIO", table_header_style),
        Paragraph("PROVEEDOR", table_header_style),
        Paragraph("MONTO", table_header_style),
        Paragraph("MÉTODO", table_header_style),
        Paragraph("ESTADO", table_header_style)
    ]
    table_data.append(headers)

    # Agregar fila del servicio
    fecha_formateada = servicio.fecha.strftime('%d/%m/%Y')

    # Truncar descripción si es muy larga
    descripcion_text = servicio.descripcion or 'Sin descripción'
    if len(descripcion_text) > 25:
        descripcion_text = descripcion_text[:22] + "..."

    # Determinar color para el estado en la tabla
    estado_table_color = colors.black
    if servicio.estado.upper() in ['APROBADO', 'ACTIVO']:
        estado_table_color = colors.HexColor('#2e7d32')
    elif servicio.estado.upper() in ['PENDIENTE', 'EDITADO']:
        estado_table_color = colors.HexColor('#f57c00')
    elif servicio.estado.upper() == 'RECHAZADO':
        estado_table_color = colors.HexColor('#c62828')

    estado_table_style = ParagraphStyle(
        'EstadoTableCell',
        parent=table_cell_style,
        textColor=estado_table_color,
        fontName='Helvetica-Bold'
    )

    row = [
        Paragraph("1", table_cell_style),
        Paragraph(fecha_formateada, table_cell_style),
        Paragraph(tipo_servicio_text, table_cell_left_style),
        Paragraph(servicio.proveedor, table_cell_left_style),
        Paragraph(f"RD$ {servicio.monto:,.2f}", table_cell_style),
        Paragraph(tipo_comprobante_text, table_cell_style),
        Paragraph(servicio.estado, estado_table_style)
    ]
    table_data.append(row)

    # Anchos de columna - ajustados para servicios
    col_widths = [1.2*cm, 2.5*cm, 3.0*cm, 3.5*cm, 2.5*cm, 2.5*cm, 2.5*cm]
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
        ('ALIGN', (2, 1), (3, -1), 'LEFT'),
        ('ALIGN', (4, 1), (5, -1), 'RIGHT'),
        ('ALIGN', (6, 1), (6, -1), 'CENTER'),

        # Padding
        ('PADDING', (0, 0), (-1, -1), (4, 4)),

        # Fila de datos
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#f8f8f8')),
        ('TEXTCOLOR', (4, 1), (4, 1), colors.HexColor(
            '#2e7d32')),  # Verde para el monto
    ])

    table.setStyle(table_style)
    elements.append(table)
    elements.append(Spacer(1, 20))

    # OBSERVACIONES (igual al reporte histórico)
    elements.append(Paragraph("OBSERVACIONES", section_style))
    elements.append(Spacer(1, 6))

    # Crear observaciones dinámicas
    observaciones_text = f"Comprobante de pago de servicio registrado el {servicio.fecha.strftime('%d/%m/%Y')}. "
    observaciones_text += f"Servicio: {tipo_servicio_text}. "
    observaciones_text += f"Monto pagado: RD$ {servicio.monto:,.2f}. "
    observaciones_text += f"Método de pago: {tipo_comprobante_text}. "
    observaciones_text += f"Proveedor: {servicio.proveedor}. "
    observaciones_text += f"Estado: {servicio.estado}."

    if servicio.entrada:
        observaciones_text += f" Entrada asociada: #{servicio.entrada.id}."

    if servicio.descripcion:
        observaciones_text += f" Notas: {servicio.descripcion}"

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
    elements.append(Paragraph(
        f"Sistema de Pago de Servicios MLAN FINANCE | Generado el {datetime.now().strftime('%d/%m/%Y %I:%M')}", footer_style))
    elements.append(Paragraph(
        "Este reporte constituye documentación oficial del sistema", footer_style))

    # Construir el PDF
    doc.build(elements)

    # Obtener el valor del buffer
    pdf = buffer.getvalue()
    buffer.close()

    # Crear respuesta HTTP
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="servicio_{pk}_{datetime.now().strftime("%d-%m-%Y_%I-%M")}.pdf"'
    response.write(pdf)

    return response

#============================================================================
# Generar reporte PDF profesional del historial completo de pagos de servicios
#============================================================================
def servicios_pdf_historial(request):
    """
    Genera reporte PDF profesional del historial completo de pagos de servicios
    Mismo formato que convertidor_reporte_pdf
    """
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

    # Calcular totales
    total_servicios = servicios.count()
    total_monto = servicios.aggregate(total=Sum('monto'))[
        'total'] or Decimal('0.00')

    # Formatear fechas para mostrar
    fecha_desde_str = fecha_desde if fecha_desde else "No especificada"
    fecha_hasta_str = fecha_hasta if fecha_hasta else "No especificada"

    # Si hay fechas, convertirlas al formato correcto (de YYYY-MM-DD a DD/MM/YYYY)
    if fecha_desde:
        try:
            fecha_obj = datetime.strptime(fecha_desde, '%Y-%m-%d')
            fecha_desde_str = fecha_obj.strftime('%d/%m/%Y')
        except:
            pass

    if fecha_hasta:
        try:
            fecha_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d')
            fecha_hasta_str = fecha_obj.strftime('%d/%m/%Y')
        except:
            pass

    # Formatear tipo de servicio para mostrar
    tipo_servicio_display = ""
    if tipo_servicio:
        # Buscar el display name del tipo de servicio
        from .models import SERVICIOS_TIPOS
        for codigo, nombre in SERVICIOS_TIPOS:
            if codigo == tipo_servicio:
                tipo_servicio_display = nombre
                break

    # Crear buffer para el PDF
    buffer = BytesIO()

    # Crear documento en modo portrait (A4 vertical)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5*cm,
        leftMargin=1.5*cm,
        topMargin=1.2*cm,
        bottomMargin=1.5*cm,
        title="Reporte Histórico de Pagos de Servicios"
    )

    # Estilos personalizados - MISMO FORMATO QUE EL REPORTE DE CONVERSIONES
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
        logo_path = "static/img/logo.ico"

        # Crear la imagen del logo
        logo = Image(logo_path, width=3.5*cm, height=2.5*cm)
        logo.hAlign = 'LEFT'

        # Crear celda con el logo
        logo_cell = logo

    except Exception as e:
        # Si no se puede cargar el logo, usar texto alternativo
        logo_cell = Paragraph("MLAN FINANCE", ParagraphStyle(
            'LogoPlaceholder',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.gray,
            alignment=1,
            fontName='Helvetica-Bold'
        ))

    # Crear celda con los títulos - MISMO FORMATO
    titles_cell = [
        Paragraph("MLAN FINANCE Sistema de Reportes Financieros", title_style),
        Spacer(1, 4),
        Paragraph("REPORTE HISTÓRICO DE PAGOS DE SERVICIOS",
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
        ('TOPPADDING', (0, 0), (0, 0), -10),
        ('TOPPADDING', (1, 0), (1, 0), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))

    elements.append(header_table)
    elements.append(Spacer(1, 10))

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
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('PADDING', (0, 0), (-1, -1), (4, 6)),
    ]))

    elements.append(fecha_table)
    elements.append(Spacer(1, 12))

    # DATOS DEL REPORTE
    elements.append(Paragraph("DATOS DEL REPORTE", section_style))
    elements.append(Spacer(1, 6))

    # Construir datos del reporte dinámicamente
    datos_reporte = []
    datos_reporte.append(
        ["Usuario Encargado:", request.user.get_full_name() or request.user.username])
    datos_reporte.append(["Total de registros:", str(total_servicios)])
    datos_reporte.append(["Estado de servicios:", "ACTIVO"])

    # Solo agregar filtros si se aplicaron
    if fecha_desde or fecha_hasta:
        datos_reporte.append(
            ["Período del reporte:", f"Del {fecha_desde_str} al {fecha_hasta_str}"])

    if tipo_servicio:
        datos_reporte.append(
            ["Tipo de servicio filtrado:", tipo_servicio_display or tipo_servicio])

    if proveedor:
        datos_reporte.append(["Proveedor filtrado:", proveedor])

    # Agregar información de totales
    datos_reporte.append(
        ["Total Pagado en Servicios:", f"RD$ {total_monto:,.2f}"])

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

    # DETALLE DE PAGOS DE SERVICIOS
    if servicios.exists():
        elements.append(
            Paragraph("DETALLE DE PAGOS DE SERVICIOS", section_style))
        elements.append(Spacer(1, 6))

        # Preparar datos de la tabla
        table_data = []

        # Encabezados - adaptados para servicios
        headers = [
            Paragraph("Nº", table_header_style),
            Paragraph("FECHA", table_header_style),
            Paragraph("SERVICIO", table_header_style),
            Paragraph("PROVEEDOR", table_header_style),
            Paragraph("MONTO", table_header_style),
            Paragraph("MÉTODO", table_header_style),
            Paragraph("ESTADO", table_header_style)
        ]
        table_data.append(headers)

        # Agregar filas de datos
        for idx, servicio in enumerate(servicios, 1):
            # Formatear fecha
            fecha_formateada = servicio.fecha.strftime('%d/%m/%Y')

            # Obtener tipo de servicio como texto descriptivo
            tipo_servicio_text = servicio.get_tipo_servicio_display() if hasattr(
                servicio, 'get_tipo_servicio_display') else servicio.tipo_servicio
            if len(tipo_servicio_text) > 20:
                tipo_servicio_text = tipo_servicio_text[:17] + "..."

            # Obtener proveedor
            proveedor_text = servicio.proveedor or 'N/A'
            if len(proveedor_text) > 20:
                proveedor_text = proveedor_text[:17] + "..."

            # Obtener método de pago como texto descriptivo
            metodo_text = servicio.get_tipo_comprobante_display() if hasattr(
                servicio, 'get_tipo_comprobante_display') else servicio.tipo_comprobante
            if len(metodo_text) > 15:
                metodo_text = metodo_text[:12] + "..."

            # Determinar color para el estado en la tabla
            estado_table_color = colors.black
            if servicio.estado.upper() in ['APROBADO', 'ACTIVO']:
                estado_table_color = colors.HexColor('#2e7d32')
            elif servicio.estado.upper() in ['PENDIENTE', 'EDITADO']:
                estado_table_color = colors.HexColor('#f57c00')
            elif servicio.estado.upper() == 'RECHAZADO':
                estado_table_color = colors.HexColor('#c62828')

            estado_table_style = ParagraphStyle(
                'EstadoTableCell',
                parent=table_cell_style,
                textColor=estado_table_color,
                fontName='Helvetica-Bold'
            )

            row = [
                Paragraph(str(idx), table_cell_style),
                Paragraph(fecha_formateada, table_cell_style),
                Paragraph(tipo_servicio_text, table_cell_left_style),
                Paragraph(proveedor_text, table_cell_left_style),
                Paragraph(f"RD$ {servicio.monto:,.2f}", table_cell_style),
                Paragraph(metodo_text, table_cell_style),
                Paragraph(servicio.estado, estado_table_style)
            ]
            table_data.append(row)

        # Anchos de columna
        col_widths = [1.2*cm, 2.5*cm, 3.0*cm, 3.5*cm, 2.5*cm, 2.5*cm, 2.5*cm]
        table = Table(table_data, colWidths=col_widths, repeatRows=1)

        # Estilos de la tabla
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
            ('ALIGN', (2, 1), (3, -1), 'LEFT'),
            ('ALIGN', (4, 1), (5, -1), 'RIGHT'),
            ('ALIGN', (6, 1), (6, -1), 'CENTER'),

            # Padding
            ('PADDING', (0, 0), (-1, -1), (4, 4)),

            # Filas alternas
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ])

        # Alternar colores de fila
        for i in range(1, len(table_data)):
            if i % 2 == 0:
                table_style.add('BACKGROUND', (0, i), (-1, i),
                                colors.HexColor('#f8f8f8'))

        table.setStyle(table_style)
        elements.append(table)

        # RESUMEN DE TOTALES
        elements.append(Spacer(1, 20))

        # Crear tabla de resumen
        resumen_data = [
            ["RESUMEN DE PAGOS DE SERVICIOS", ""],
            ["Total de servicios registrados:", f"{total_servicios}"],
            ["Monto total pagado en servicios:", f"RD$ {total_monto:,.2f}"],
        ]

        resumen_table = Table(resumen_data, colWidths=[8*cm, 7*cm])
        resumen_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('ALIGN', (0, 0), (1, 0), 'CENTER'),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (1, 0), 0.5, colors.black),
            ('GRID', (0, 1), (-1, -1), 0.5, colors.black),
            ('PADDING', (0, 0), (-1, -1), (6, 8)),
            ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#e0e0e0')),
            ('TEXTCOLOR', (0, 0), (1, 0), colors.black),
            ('TEXTCOLOR', (1, 2), (1, 2), colors.HexColor(
                '#2e7d32')),  # Verde para monto total
        ]))

        elements.append(resumen_table)

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
        elements.append(
            Paragraph("NO SE ENCONTRARON PAGOS DE SERVICIOS REGISTRADOS", no_data_style))
        elements.append(Spacer(1, 15))

    elements.append(Spacer(1, 20))

    # OBSERVACIONES
    elements.append(Paragraph("OBSERVACIONES", section_style))
    elements.append(Spacer(1, 6))

    # Crear observaciones dinámicas
    observaciones_text = "Reporte generado automáticamente por el sistema MLAN FINANCE. "
    if total_servicios > 0:
        observaciones_text += f"Se encontraron {total_servicios} pagos de servicios registrados. "
        observaciones_text += f"Total pagado en servicios: RD$ {total_monto:,.2f} (Peso Dominicano). "

    if fecha_desde or fecha_hasta:
        observaciones_text += f"Período del reporte: {fecha_desde_str} al {fecha_hasta_str}. "

    if tipo_servicio:
        observaciones_text += f"Filtrado por tipo de servicio: {tipo_servicio_display or tipo_servicio}. "

    if proveedor:
        observaciones_text += f"Filtrado por proveedor: {proveedor}. "

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
    elements.append(Paragraph(
        f"Sistema de Pago de Servicios MLAN FINANCE | Generado el {datetime.now().strftime('%d/%m/%Y %I:%M')}", footer_style))
    elements.append(Paragraph(
        "Este reporte constituye documentación oficial del sistema", footer_style))

    # Construir el PDF
    doc.build(elements)

    # Obtener el valor del buffer
    pdf = buffer.getvalue()
    buffer.close()

    # Crear respuesta HTTP
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="reporte_servicios_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf"'
    response.write(pdf)

    return response

#=============================================================================
# VISTA PARA IMPRIMIR HISTORIAL DE SERVICIOS
#=============================================================================
def servicios_imprimir_historial(request):
    """Vista para imprimir historial de servicios"""

    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    tipo_servicio = request.GET.get('tipo_servicio', '')
    proveedor = request.GET.get('proveedor', '')
    estado = request.GET.get('estado', 'ACTIVO')

    servicios = ServicioPago.objects.exclude(estado='ELIMINADO')

    # Aplicar filtros solo si vienen por GET
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

    servicios = servicios.order_by('id')

    # 🔹 Obtener fechas reales si no hay filtros
    primera_fecha = servicios.first().fecha if servicios.exists() else None
    ultima_fecha = servicios.last().fecha if servicios.exists() else None

    fecha_desde_mostrar = fecha_desde or (
        primera_fecha.strftime('%d-%m-%Y') if primera_fecha else None)
    fecha_hasta_mostrar = fecha_hasta or (
        ultima_fecha.strftime('%d-%m-%Y') if ultima_fecha else None)

    # Totales
    total_servicios = servicios.aggregate(total=Sum('monto'))[
        'total'] or Decimal('0.00')
    totales = calcular_totales_servicios()

    context = {
        'servicios': servicios,
        'total_servicios': total_servicios,
        'totales': totales,
        'fecha_generacion': datetime.now().strftime('%d/%m/%Y %I:%M'),
        'filtros': {
            'fecha_desde': fecha_desde_mostrar,
            'fecha_hasta': fecha_hasta_mostrar,
            'tipo_servicio': tipo_servicio,
            'proveedor': proveedor,
            'estado': estado,
        }
    }

    return render(request, 'finanzas/servicios_print.html', context)


#==========#=============#==========#======#============#===============#==================#=================#
#==========#=============#==========#======#============#===============#==================#=================#

# =============================================================================
# VISTA PRINCIPAL DEL DASHBOARD
# =============================================================================
@login_required
@never_cache
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
        'version': VERSION,
    }

    return render(request, "finanzas/dashboard.html", context)

# =============================================================================
# API ENDPOINT PARA DATOS DEL DASHBOARD
# =============================================================================
@login_required
@never_cache
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
        # FUNCIONES AUXILIARES CORREGIDAS
        return JsonResponse({"error": str(e)}, status=500)

# =============================================================================
# TOTALES GLOBALES
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

# =============================================================================
# TOTALES MENSUALES
# =============================================================================
def get_totales_mensuales():
    """
    Calcula los totales del mes actual - CORREGIDO
    """
    # Obtener la fecha actual en la zona horaria del proyecto
    hoy = timezone.localtime(timezone.now())

    # Inicio del mes: primer día a las 00:00:00
    inicio_mes = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Fin del mes: calcular el primer día del próximo mes y restar 1 microsegundo
    if hoy.month == 12:
        proximo_mes = hoy.replace(
            year=hoy.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        proximo_mes = hoy.replace(
            month=hoy.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)

    # Fin del mes es 1 microsegundo antes del próximo mes
    fin_mes = proximo_mes - timedelta(microseconds=1)

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

# =============================================================================
# MOVIMIENTOS RECIENTES AUXILIAR
# =============================================================================
def formatear_fecha_para_json(fecha_obj):
    """
    Convierte un objeto fecha/datetime a string ISO manteniendo la fecha local
    EVITA que se reste un día por problemas de timezone
    """
    if fecha_obj is None:
        return None

    # Si es un datetime con timezone
    if isinstance(fecha_obj, datetime):
        # Convertir a hora local para evitar problemas de zona horaria
        if timezone.is_aware(fecha_obj):
            fecha_obj = timezone.localtime(fecha_obj)

        # Retornar en formato ISO pero solo la parte de fecha (YYYY-MM-DD)
        # Esto evita problemas de conversión en JavaScript
        return fecha_obj.strftime('%Y-%m-%d')

    # Si es solo un objeto date
    return str(fecha_obj)

# =============================================================================
# MOVIMIENTOS RECIENTES
# =============================================================================
def get_movimientos_recientes(limit=10):
    """
    Obtiene los movimientos más recientes de cada tipo
    CORREGIDO: Manejo correcto de fechas sin pérdida de días
    """
    # Últimas entradas
    ultimas_entradas = list(MovimientoEntrada.objects.all().order_by('-fecha')[:limit].values(
        'id', 'monto_usd', 'tasa_cambio', 'monto_pesos', 'descripcion', 'fecha'
    ))

    # Últimos gastos (solo activos)
    ultimos_gastos = list(Gasto.objects.filter(estado='ACTIVO').order_by('-fecha')[:limit].values(
        'id', 'categoria', 'monto', 'descripcion', 'fecha', 'entrada_id', 'proveedor'
    ))

    # Últimos servicios (solo activos)
    ultimos_servicios = list(ServicioPago.objects.filter(estado='ACTIVO').order_by('-fecha')[:limit].values(
        'id', 'tipo_servicio', 'monto', 'descripcion', 'fecha', 'entrada_id', 'proveedor'
    ))

    # Convertir Decimal a float y formatear fechas CORRECTAMENTE
    for entrada in ultimas_entradas:
        entrada['monto_usd'] = float(entrada['monto_usd'])
        entrada['tasa_cambio'] = float(entrada['tasa_cambio'])
        entrada['monto_pesos'] = float(entrada['monto_pesos'])
        entrada['fecha'] = formatear_fecha_para_json(entrada['fecha'])

    for gasto in ultimos_gastos:
        gasto['monto'] = float(gasto['monto'])
        gasto['fecha'] = formatear_fecha_para_json(gasto['fecha'])
        if not gasto['proveedor']:
            gasto['proveedor'] = "No especificado"

    for servicio in ultimos_servicios:
        servicio['monto'] = float(servicio['monto'])
        servicio['fecha'] = formatear_fecha_para_json(servicio['fecha'])
        if not servicio['proveedor']:
            servicio['proveedor'] = "No especificado"

    return {
        "ultimas_entradas": ultimas_entradas,
        "ultimos_gastos": ultimos_gastos,
        "ultimos_servicios": ultimos_servicios
    }

# =============================================================================
# GASTOS POR CATEGORÍA
# =============================================================================
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

# =============================================================================
# SERVICIOS POR TIPO
# =============================================================================
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

# =============================================================================
# ENTRADAS POR MES
# =============================================================================
def get_entradas_por_mes():
    """
    Agrupa las entradas por mes (últimos 6 meses) - CORREGIDO
    """
    # Obtener fecha actual en hora local
    hoy = timezone.localtime(timezone.now())
    seis_meses_atras = hoy - timedelta(days=180)

    entradas_por_mes = MovimientoEntrada.objects.filter(
        fecha__gte=seis_meses_atras
    ).annotate(
        mes=TruncMonth('fecha')
    ).values('mes').annotate(
        total=Sum('monto_pesos')
    ).order_by('mes')

    resultado = []
    for item in entradas_por_mes:
        # Convertir a hora local antes de formatear
        mes_local = timezone.localtime(item['mes']) if timezone.is_aware(
            item['mes']) else item['mes']
        resultado.append({
            "mes": mes_local.strftime('%Y-%m'),
            "total": float(item['total'])
        })

    return resultado

# =============================================================================
# GASTOS POR MES
# =============================================================================
def get_gastos_por_mes():
    """
    Agrupa los gastos por mes (solo activos, últimos 6 meses) - CORREGIDO
    """
    hoy = timezone.localtime(timezone.now())
    seis_meses_atras = hoy - timedelta(days=180)

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
        mes_local = timezone.localtime(item['mes']) if timezone.is_aware(
            item['mes']) else item['mes']
        resultado.append({
            "mes": mes_local.strftime('%Y-%m'),
            "total": float(item['total'])
        })

    return resultado

# =============================================================================
# SERVICIOS POR MES
# =============================================================================
def get_servicios_por_mes():
    """
    Agrupa los servicios por mes (solo activos, últimos 6 meses) - CORREGIDO
    """
    hoy = timezone.localtime(timezone.now())
    seis_meses_atras = hoy - timedelta(days=180)

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
        mes_local = timezone.localtime(item['mes']) if timezone.is_aware(
            item['mes']) else item['mes']
        resultado.append({
            "mes": mes_local.strftime('%Y-%m'),
            "total": float(item['total'])
        })

    return resultado

# =============================================================================
# ENTRADAS POR DÍA
# =============================================================================
def get_entradas_por_dia():
    """
    Agrupa las entradas por día (últimos 30 días) - CORREGIDO
    """
    hoy = timezone.localtime(timezone.now())
    treinta_dias_atras = hoy - timedelta(days=30)

    entradas_por_dia = MovimientoEntrada.objects.filter(
        fecha__gte=treinta_dias_atras
    ).annotate(
        dia=TruncDay('fecha')
    ).values('dia').annotate(
        total=Sum('monto_pesos')
    ).order_by('dia')

    resultado = []
    for item in entradas_por_dia:
        dia_local = timezone.localtime(item['dia']) if timezone.is_aware(
            item['dia']) else item['dia']
        resultado.append({
            "dia": dia_local.strftime('%Y-%m-%d'),
            "total": float(item['total'])
        })

    return resultado

# =============================================================================
# GASTOS POR DÍA
# =============================================================================
def get_gastos_por_dia():
    """
    Agrupa los gastos por día (solo activos, últimos 30 días) - CORREGIDO
    """
    hoy = timezone.localtime(timezone.now())
    treinta_dias_atras = hoy - timedelta(days=30)

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
        dia_local = timezone.localtime(item['dia']) if timezone.is_aware(
            item['dia']) else item['dia']
        resultado.append({
            "dia": dia_local.strftime('%Y-%m-%d'),
            "total": float(item['total'])
        })

    return resultado

# =============================================================================
# SERVICIOS POR DÍA
# =============================================================================
def get_servicios_por_dia():
    """
    Agrupa los servicios por día (solo activos, últimos 30 días) - CORREGIDO
    """
    hoy = timezone.localtime(timezone.now())
    treinta_dias_atras = hoy - timedelta(days=30)

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
        dia_local = timezone.localtime(item['dia']) if timezone.is_aware(
            item['dia']) else item['dia']
        resultado.append({
            "dia": dia_local.strftime('%Y-%m-%d'),
            "total": float(item['total'])
        })

    return resultado

# =============================================================================
# BALANCE POR CADA ENTRADA INDIVIDUAL
# =============================================================================
def get_totales_por_entrada():
    """
    Calcula el balance por cada entrada individual - CORREGIDO
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
            "fecha": formatear_fecha_para_json(entrada.fecha)
        })

    return balances

# =============================================================================
# REPORTE PDF - DETALLE DE MOVIMIENTOS  DEL  DASHBOARD (REPORTE INDIVIDUAL REGISTROS)
# =============================================================================
def dashboard_reporte_detalle_pdf(request, tipo_movimiento, id):
    """
    Genera reporte PDF profesional para cualquier tipo de movimiento del dashboard
    tipo_movimiento: 'entrada', 'gasto', 'servicio'
    """
    # Obtener el movimiento según el tipo
    movimiento = None
    tipo_label = ""

    if tipo_movimiento == 'entrada':
        movimiento = get_object_or_404(MovimientoEntrada, id=id)
        tipo_label = "Entrada Financiera"
    elif tipo_movimiento == 'gasto':
        # Cambiado de MovimientoGasto a Gasto
        movimiento = get_object_or_404(Gasto, id=id)
        tipo_label = "Registro de Gasto"
    elif tipo_movimiento == 'servicio':
        # Cambiado de MovimientoServicio a ServicioPago
        movimiento = get_object_or_404(ServicioPago, id=id)
        tipo_label = "Pago de Servicio"
    else:
        return HttpResponse("Tipo de movimiento no válido", status=400)

    # Crear buffer para el PDF
    buffer = BytesIO()

    # Crear documento en modo portrait (A4 vertical)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5*cm,
        leftMargin=1.5*cm,
        topMargin=1.2*cm,
        bottomMargin=1.5*cm,
        title=f"Reporte {tipo_label} #{id}"
    )

    # Estilos personalizados
    styles = getSampleStyleSheet()

    # Título principal
    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Title'],
        fontSize=16,
        textColor=colors.black,
        spaceAfter=12,
        alignment=1,
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
        alignment=0,
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
        alignment=1,
        leading=10
    )
# Estilo para celdas de tabla
    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontSize=9,
        alignment=1,
        leading=10
    )

    table_cell_left_style = ParagraphStyle(
        'TableCellLeft',
        parent=styles['Normal'],
        fontSize=9,
        alignment=0,
        leading=10
    )

    # Elementos del documento
    elements = []

    # Crear una tabla de encabezado con logo
    header_table_data = []

    # Intentar cargar el logo de la empresa
    try:
        logo_path = "static/img/logo.ico"
        logo = Image(logo_path, width=3.5*cm, height=2.5*cm)
        logo.hAlign = 'LEFT'
        logo_cell = logo
    except Exception as e:
        logo_cell = Paragraph("MLAN FINANCE", ParagraphStyle(
            'LogoPlaceholder',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.gray,
            alignment=1,
            fontName='Helvetica-Bold'
        ))

    # Crear celda con los títulos
    titles_cell = [
        Paragraph("MLAN FINANCE Sistema de Reportes Financieros", title_style),
        Spacer(1, 4),
        Paragraph(f"REPORTE DETALLADO - {tipo_label.upper()} #{id}",
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
        ('TOPPADDING', (0, 0), (0, 0), -10),
        ('TOPPADDING', (1, 0), (1, 0), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))

    elements.append(header_table)
    elements.append(Spacer(1, 10))

    # Fecha del reporte
    fecha_table_data = [
        ["Fecha del Reporte:", datetime.now().strftime('%d/%m/%Y %I:%M %p')]
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

    # INFORMACIÓN GENERAL DEL MOVIMIENTO
    elements.append(Paragraph("INFORMACIÓN GENERAL", section_style))
    elements.append(Spacer(1, 6))

    # Construir información general según el tipo de movimiento
    info_general = []
    info_general.append(["ID del Movimiento:", f"#{id}"])
    info_general.append(["Tipo de Movimiento:", tipo_label])

    # Formatear fecha según el modelo
    fecha_movimiento = ""
    if hasattr(movimiento, 'fecha_formateada'):
        fecha_movimiento = movimiento.fecha_formateada
    elif hasattr(movimiento, 'fecha'):
        fecha_movimiento = movimiento.fecha.strftime('%d/%m/%Y %I:%M %p')

    info_general.append(["Fecha del Movimiento:", fecha_movimiento])
    info_general.append(
        ["Usuario Registrador:", request.user.get_full_name() or request.user.username])

    # Información específica según el tipo
    if tipo_movimiento == 'entrada':
        info_general.append(["Proveedor/Cliente:", "Maria DC Lantigua"])
        info_general.append(["Tipo de Entrada:", "Conversión USD a DOP"])
    elif tipo_movimiento == 'gasto':
        proveedor = movimiento.proveedor or "No especificado"
        categoria = movimiento.get_categoria_display(
        ) if movimiento.categoria else "Sin categoría"
        info_general.append(["Proveedor:", proveedor])
        info_general.append(["Categoría:", categoria])
    elif tipo_movimiento == 'servicio':
        proveedor = movimiento.proveedor or "No especificado"
        tipo_servicio = movimiento.get_tipo_servicio_display(
        ) if movimiento.tipo_servicio else "General"
        info_general.append(["Proveedor del Servicio:", proveedor])
        info_general.append(["Tipo de Servicio:", tipo_servicio])

    info_general_table = Table(info_general, colWidths=[5*cm, 10*cm])
    info_general_table.setStyle(TableStyle([
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

    elements.append(info_general_table)
    elements.append(Spacer(1, 16))

    # RESUMEN FINANCIERO
    elements.append(Paragraph("RESUMEN FINANCIERO", section_style))
    elements.append(Spacer(1, 6))

    # Construir resumen según el tipo
    resumen_data = []

    if tipo_movimiento == 'entrada':
        resumen_data = [
            ["Concepto", "Monto", "Detalles"],
            ["Monto en USD",
                f"$ {movimiento.monto_usd:,.2f}", "Monto original"],
            ["Tasa de Cambio",
                f"$ {movimiento.tasa_cambio:,.2f}", "Tasa aplicada"],
            ["Monto en Pesos",
                f"$ {movimiento.monto_pesos:,.2f}", "Total convertido"],
            ["Ganancia/Comisión", "Incluida", "Según tasa"],
        ]
    elif tipo_movimiento == 'gasto':
        categoria_display = movimiento.get_categoria_display(
        ) if movimiento.categoria else "Sin categoría"
        metodo_pago = movimiento.tipo_comprobante if hasattr(
            movimiento, 'tipo_comprobante') else "No especificado"
        resumen_data = [
            ["Concepto", "Monto", "Detalles"],
            ["Monto del Gasto", f"$ {movimiento.monto:,.2f}", "Total gastado"],
            ["Categoría", categoria_display, "Clasificación"],
            ["Método de Pago", metodo_pago, "Forma de pago"],
            ["Estado", movimiento.estado if hasattr(
                movimiento, 'estado') else "Completado", "Estado del gasto"],
        ]
    elif tipo_movimiento == 'servicio':
        tipo_servicio_display = movimiento.get_tipo_servicio_display(
        ) if movimiento.tipo_servicio else "General"
        metodo_pago = movimiento.tipo_comprobante if hasattr(
            movimiento, 'tipo_comprobante') else "No especificado"
        resumen_data = [
            ["Concepto", "Monto", "Detalles"],
            ["Monto del Servicio",
                f"$ {movimiento.monto:,.2f}", "Total pagado"],
            ["Tipo de Servicio", tipo_servicio_display, "Clasificación"],
            ["Método de Pago", metodo_pago, "Forma de pago"],
            ["Estado", movimiento.estado if hasattr(
                movimiento, 'estado') else "Pagado", "Estado del pago"],
        ]

    resumen_table = Table(resumen_data, colWidths=[6*cm, 4*cm, 5*cm])
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

    # DETALLE COMPLETO DEL MOVIMIENTO
    elements.append(Paragraph("DETALLE COMPLETO", section_style))
    elements.append(Spacer(1, 6))

    # Tabla de detalle con formato específico según el tipo
    table_data = []

    if tipo_movimiento == 'entrada':
        headers = [
            Paragraph("ITEM", table_header_style),
            Paragraph("FECHA", table_header_style),
            Paragraph("DESCRIPCIÓN", table_header_style),
            Paragraph("USD", table_header_style),
            Paragraph("TASA", table_header_style),
            Paragraph("DOP", table_header_style),
            Paragraph("ESTADO", table_header_style)
        ]
        table_data.append(headers)

        fecha_formateada = movimiento.fecha_formateada if hasattr(
            movimiento, 'fecha_formateada') else movimiento.fecha.strftime('%d/%m/%Y')
        descripcion = movimiento.descripcion or "Conversión de divisas"

        row = [
            Paragraph("1", table_cell_style),
            Paragraph(fecha_formateada, table_cell_style),
            Paragraph(descripcion[:40] + "..." if len(descripcion)
                      > 40 else descripcion, table_cell_left_style),
            Paragraph(f"$ {movimiento.monto_usd:,.2f}", table_cell_style),
            Paragraph(f"$ {movimiento.tasa_cambio:,.2f}", table_cell_style),
            Paragraph(f"$ {movimiento.monto_pesos:,.2f}", table_cell_style),
            Paragraph("Completado", table_cell_style)
        ]
        table_data.append(row)

        col_widths = [1.2*cm, 2.2*cm, 4.5*cm, 2.2*cm, 2.2*cm, 2.2*cm, 2.2*cm]

    elif tipo_movimiento == 'gasto':
        headers = [
            Paragraph("ITEM", table_header_style),
            Paragraph("FECHA", table_header_style),
            Paragraph("PROVEEDOR", table_header_style),
            Paragraph("CATEGORÍA", table_header_style),
            Paragraph("MONTO", table_header_style),
            Paragraph("COMPROBANTE", table_header_style),
            Paragraph("ESTADO", table_header_style)
        ]
        table_data.append(headers)

        fecha_formateada = movimiento.fecha_formateada if hasattr(
            movimiento, 'fecha_formateada') else movimiento.fecha.strftime('%d/%m/%Y')
        proveedor = movimiento.proveedor or "No especificado"
        categoria = movimiento.get_categoria_display(
        ) if movimiento.categoria else "Sin categoría"
        comprobante = movimiento.tipo_comprobante if hasattr(
            movimiento, 'tipo_comprobante') else "Sin comprobante"

        row = [
            Paragraph("1", table_cell_style),
            Paragraph(fecha_formateada, table_cell_style),
            Paragraph(proveedor[:25] + "..." if len(proveedor)
                      > 25 else proveedor, table_cell_left_style),
            Paragraph(categoria, table_cell_style),
            Paragraph(f"$ {movimiento.monto:,.2f}", table_cell_style),
            Paragraph(comprobante, table_cell_style),
            Paragraph(movimiento.estado if hasattr(
                movimiento, 'estado') else "Completado", table_cell_style)
        ]
        table_data.append(row)

        col_widths = [1.2*cm, 2.2*cm, 3.5*cm, 2.2*cm, 2.2*cm, 2.2*cm, 2.2*cm]

    elif tipo_movimiento == 'servicio':
        headers = [
            Paragraph("ITEM", table_header_style),
            Paragraph("FECHA", table_header_style),
            Paragraph("SERVICIO", table_header_style),
            Paragraph("PROVEEDOR", table_header_style),
            Paragraph("MONTO", table_header_style),
            Paragraph("COMPROBANTE", table_header_style),
            Paragraph("ESTADO", table_header_style)
        ]
        table_data.append(headers)

        fecha_formateada = movimiento.fecha_formateada if hasattr(
            movimiento, 'fecha_formateada') else movimiento.fecha.strftime('%d/%m/%Y')
        servicio = movimiento.get_tipo_servicio_display(
        ) if movimiento.tipo_servicio else "Servicio"
        proveedor = movimiento.proveedor or "No especificado"
        comprobante = movimiento.tipo_comprobante if hasattr(
            movimiento, 'tipo_comprobante') else "Sin comprobante"

        row = [
            Paragraph("1", table_cell_style),
            Paragraph(fecha_formateada, table_cell_style),
            Paragraph(servicio, table_cell_style),
            Paragraph(proveedor[:25] + "..." if len(proveedor)
                      > 25 else proveedor, table_cell_left_style),
            Paragraph(f"$ {movimiento.monto:,.2f}", table_cell_style),
            Paragraph(comprobante, table_cell_style),
            Paragraph(movimiento.estado if hasattr(
                movimiento, 'estado') else "Pagado", table_cell_style)
        ]
        table_data.append(row)

        col_widths = [1.2*cm, 2.2*cm, 2.2*cm, 3.2*cm, 2.2*cm, 2.2*cm, 2.2*cm]

    # Crear la tabla
    table = Table(table_data, colWidths=col_widths, repeatRows=1)

    # Estilos de la tabla
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
        ('ALIGN', (3, 1), (5, -1), 'CENTER'),
        ('ALIGN', (6, 1), (6, -1), 'CENTER'),

        # Padding
        ('PADDING', (0, 0), (-1, -1), (4, 4)),

        # Fila de datos
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#f8f8f8')),
    ])

    table.setStyle(table_style)
    elements.append(table)
    elements.append(Spacer(1, 20))

    # OBSERVACIONES ADICIONALES
    elements.append(Paragraph("OBSERVACIONES ADICIONALES", section_style))
    elements.append(Spacer(1, 6))

    # Crear observaciones dinámicas
    observaciones_text = ""

    if tipo_movimiento == 'entrada':
        observaciones_text = f"Reporte detallado de entrada financiera por conversión de divisas. "
        observaciones_text += f"Operación realizada el {movimiento.fecha.strftime('%d/%m/%Y')} a las {movimiento.fecha.strftime('%I:%M %p')}. "
        observaciones_text += f"Monto convertido: ${movimiento.monto_usd:,.2f} USD a ${movimiento.monto_pesos:,.2f} DOP con tasa de cambio de ${movimiento.tasa_cambio:,.2f}."

    elif tipo_movimiento == 'gasto':
        observaciones_text = f"Reporte detallado de gasto registrado en el sistema. "
        observaciones_text += f"Gasto realizado el {movimiento.fecha.strftime('%d/%m/%Y')}. "
        observaciones_text += f"Monto: ${movimiento.monto:,.2f} DOP. "
        observaciones_text += f"Categoría: {movimiento.get_categoria_display() if movimiento.categoria else 'Sin categoría'}. "
        if hasattr(movimiento, 'descripcion') and movimiento.descripcion:
            observaciones_text += f"Motivo: {movimiento.descripcion}"
        if hasattr(movimiento, 'notas') and movimiento.notas:
            observaciones_text += f" Notas: {movimiento.notas}"

    elif tipo_movimiento == 'servicio':
        observaciones_text = f"Reporte detallado de pago de servicio. "
        observaciones_text += f"Servicio pagado el {movimiento.fecha.strftime('%d/%m/%Y')}. "
        observaciones_text += f"Monto pagado: ${movimiento.monto:,.2f} DOP. "
        observaciones_text += f"Tipo de servicio: {movimiento.get_tipo_servicio_display() if movimiento.tipo_servicio else 'General'}. "
        if hasattr(movimiento, 'descripcion') and movimiento.descripcion:
            observaciones_text += f"Detalles: {movimiento.descripcion}"
        if hasattr(movimiento, 'notas') and movimiento.notas:
            observaciones_text += f" Notas: {movimiento.notas}"

    # Agregar descripción general si existe
    if hasattr(movimiento, 'descripcion') and movimiento.descripcion and tipo_movimiento != 'gasto' and tipo_movimiento != 'servicio':
        observaciones_text += f" Notas adicionales: {movimiento.descripcion}"

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
    elements.append(Paragraph(
        f"Sistema de Gestión Financiera MLAN FINANCE | Generado el {datetime.now().strftime('%d/%m/%Y %I:%M %p')}", footer_style))
    elements.append(Paragraph(
        "Este reporte constituye documentación oficial del sistema financiero", footer_style))
    elements.append(Paragraph(
        f"Tipo de movimiento: {tipo_label} | ID: {id} | Usuario: {request.user.get_full_name() or request.user.username}", footer_style))

    # Construir el PDF
    doc.build(elements)

    # Obtener el valor del buffer
    pdf = buffer.getvalue()
    buffer.close()

    # Crear nombre de archivo dinámico
    filename = f"{tipo_movimiento}_{id}_reporte_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    # Crear respuesta HTTP
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write(pdf)

    return response

# =============================================================================
# REPORTE PDF - RESUMEN DE MOVIMIENTOS DEL DASHBOARD (EXPORTADOR)
# =============================================================================
@never_cache
def dashboard_reporte_pdf(request):
    """
    Genera reporte PDF profesional del resumen completo de movimientos del dashboard
    Incluye Entradas, Gastos y Servicios en un solo reporte - VERSIÓN CORREGIDA
    """
    # Obtener parámetros de filtro (si existen)
    fecha_inicio = request.GET.get('date_from')
    fecha_fin = request.GET.get('date_to')
    tipo_movimiento = request.GET.get('type')
    categoria = request.GET.get('category')
    usuario = request.GET.get('user')

    # Inicializar todas las listas
    all_movements = []
    total_entradas = 0
    total_gastos = 0
    total_servicios = 0

    # =========================================================================
    # 1. OBTENER ENTRADAS (CONVERSIONES USD-DOP) - CORREGIDO
    # =========================================================================
    entradas = MovimientoEntrada.objects.all()

    # Aplicar filtros si existen
    if fecha_inicio:
        # Convertir string a objeto date para comparación
        try:
            fecha_inicio_obj = datetime.strptime(
                fecha_inicio, '%Y-%m-%d').date()
            entradas = entradas.filter(fecha__date__gte=fecha_inicio_obj)
        except:
            pass

    if fecha_fin:
        try:
            fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
            entradas = entradas.filter(fecha__date__lte=fecha_fin_obj)
        except:
            pass

    # Ordenar por fecha descendente
    entradas = entradas.order_by('-fecha')

    # Agregar a la lista general
    for entrada in entradas:
        all_movements.append({
            'fecha': entrada.fecha,
            'tipo': 'Entrada',
            'tipo_movimiento': 'entrada',
            'descripcion': entrada.descripcion or 'Conversión USD a DOP',
            'monto': entrada.monto_pesos,
            'monto_usd': entrada.monto_usd,
            'tasa_cambio': entrada.tasa_cambio,
            'categoria': 'Conversión USD-DOP',
            'responsable': 'Maria DC Lantigua',
            # Usar descripción como observaciones
            'observaciones': entrada.descripcion or '',
            'id': entrada.id,
            'proveedor': 'Sistema de Conversión'
        })
        total_entradas += float(entrada.monto_pesos)

    # =========================================================================
    # 2. OBTENER GASTOS - CORREGIDO
    # =========================================================================
    gastos = Gasto.objects.filter(estado__in=['ACTIVO', 'EDITADO'])

    # Aplicar filtros si existen
    if fecha_inicio:
        try:
            fecha_inicio_obj = datetime.strptime(
                fecha_inicio, '%Y-%m-%d').date()
            gastos = gastos.filter(fecha__date__gte=fecha_inicio_obj)
        except:
            pass

    if fecha_fin:
        try:
            fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
            gastos = gastos.filter(fecha__date__lte=fecha_fin_obj)
        except:
            pass

    if categoria:
        gastos = gastos.filter(categoria=categoria)

    if tipo_movimiento and tipo_movimiento == 'expense':
        # Si específicamente se filtra por gastos
        pass
    elif tipo_movimiento and tipo_movimiento != 'expense':
        gastos = Gasto.objects.none()

    # Ordenar por fecha descendente
    gastos = gastos.order_by('-fecha')

    # Mapeo de categorías a español
    categorias_map = {
        'ALIMENTACION': 'Alimentación',
        'TRANSPORTE': 'Transporte',
        'COMPRAS': 'Compras',
        'SALUD': 'Salud',
        'PERSONAL': 'Gastos Personales',
        'OTROS': 'Otros'
    }

    for gasto in gastos:
        categoria_display = categorias_map.get(
            gasto.categoria, gasto.categoria)
        all_movements.append({
            'fecha': gasto.fecha,
            'tipo': 'Gasto',
            'tipo_movimiento': 'gasto',
            'descripcion': gasto.descripcion or 'Gasto sin descripción',
            'monto': gasto.monto,
            'monto_usd': None,
            'tasa_cambio': None,
            'categoria': categoria_display,
            'responsable': gasto.proveedor or 'No especificado',
            'observaciones': gasto.notas or '',  # Usar campo 'notas' correcto
            'id': gasto.id,
            'proveedor': gasto.proveedor or 'No especificado'
        })
        total_gastos += float(gasto.monto)

    # =========================================================================
    # 3. OBTENER SERVICIOS - COMPLETAMENTE CORREGIDO
    # =========================================================================
    servicios = ServicioPago.objects.filter(estado__in=['ACTIVO', 'EDITADO'])

    # Aplicar filtros si existen - USAR 'fecha' NO 'fecha_pago'
    if fecha_inicio:
        try:
            fecha_inicio_obj = datetime.strptime(
                fecha_inicio, '%Y-%m-%d').date()
            servicios = servicios.filter(
                fecha__date__gte=fecha_inicio_obj)  # CORREGIDO
        except:
            pass

    if fecha_fin:
        try:
            fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
            servicios = servicios.filter(
                fecha__date__lte=fecha_fin_obj)  # CORREGIDO
        except:
            pass

    if tipo_movimiento and tipo_movimiento == 'service':
        # Si específicamente se filtra por servicios
        pass
    elif tipo_movimiento and tipo_movimiento != 'service':
        servicios = ServicioPago.objects.none()

    # Ordenar por fecha descendente - USAR 'fecha' NO 'fecha_pago'
    servicios = servicios.order_by('-fecha')  # CORREGIDO

    # Mapeo de tipos de servicio a español
    tipos_servicio_map = {
        'LUZ': 'Electricidad',
        'AGUA': 'Agua',
        'INTERNET': 'Internet',
        'TELEFONO': 'Teléfono',
        'ALQUILER': 'Alquiler',
        'OTRO': 'Otro Servicio'
    }

    for servicio in servicios:
        tipo_display = tipos_servicio_map.get(
            servicio.tipo_servicio, servicio.tipo_servicio)
        all_movements.append({
            'fecha': servicio.fecha,  # CORREGIDO: usar servicio.fecha
            'tipo': 'Servicio',
            'tipo_movimiento': 'servicio',
            'descripcion': servicio.descripcion or 'Pago de servicio sin descripción',
            'monto': servicio.monto,
            'monto_usd': None,
            'tasa_cambio': None,
            'categoria': tipo_display,
            'responsable': servicio.proveedor or 'No especificado',
            'observaciones': servicio.notas or '',  # CORREGIDO: usar 'notas'
            'id': servicio.id,
            'proveedor': servicio.proveedor or 'No especificado'
        })
        total_servicios += float(servicio.monto)

    # =========================================================================
    # 4. ORDENAR TODOS LOS MOVIMIENTOS POR FECHA (Más reciente primero)
    # =========================================================================
    all_movements.sort(key=lambda x: x['fecha'], reverse=True)

    # Calcular totales generales
    total_movimientos = len(all_movements)
    total_general = total_entradas - total_gastos - total_servicios

    # Formatear fechas para mostrar
    fecha_inicio_str = fecha_inicio if fecha_inicio else "No especificada"
    fecha_fin_str = fecha_fin if fecha_fin else "No especificada"

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

    # =========================================================================
    # 5. GENERAR PDF
    # =========================================================================
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
        title="Reporte Completo de Movimientos - Dashboard"
    )

    # Estilos personalizados
    styles = getSampleStyleSheet()

    # Título principal
    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Title'],
        fontSize=16,
        textColor=colors.black,
        spaceAfter=12,
        alignment=1,
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
        alignment=0,
        leading=14,
        leftIndent=0
    )

    # Estilo para tabla
    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.black,
        fontName='Helvetica-Bold',
        alignment=1,
        leading=10
    )

    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontSize=9,
        alignment=1,
        leading=10
    )

    table_cell_left_style = ParagraphStyle(
        'TableCellLeft',
        parent=styles['Normal'],
        fontSize=9,
        alignment=0,
        leading=10
    )

    # Elementos del documento
    elements = []

    # =========================================================================
    # 6. ENCABEZADO DEL REPORTE
    # =========================================================================
    header_table_data = []

    try:
        # Intentar cargar el logo
        logo_path = "static/img/logo.ico"
        logo = Image(logo_path, width=5*cm, height=3*cm)
        logo.hAlign = 'LEFT'
        logo_cell = logo
    except Exception as e:
        # Si no se puede cargar el logo, usar texto alternativo
        logo_cell = Paragraph("MLAN FINANCE", ParagraphStyle(
            'LogoPlaceholder',
            parent=styles['Normal'],
            fontSize=12,
            textColor=colors.HexColor('#035087'),
            alignment=1,
            fontName='Helvetica-Bold'
        ))

    # Crear celda con los títulos
    titles_cell = [
        Paragraph("MLAN FINANCE - Sistema de Gestión Financiera", title_style),
        Spacer(1, 4),
        Paragraph("REPORTE COMPLETO DE MOVIMIENTOS - DASHBOARD",
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

    # Fecha del reporte
    fecha_table_data = [
        ["Fecha del Reporte:", datetime.now().strftime('%d/%m/%Y %I:%M %p')],
        ["Usuario Encargado:", request.user.get_full_name() or request.user.username]
    ]

    fecha_table = Table(fecha_table_data, colWidths=[4*cm, 11*cm])
    fecha_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('PADDING', (0, 0), (-1, -1), (4, 6)),
    ]))

    elements.append(fecha_table)
    elements.append(Spacer(1, 16))

    # =========================================================================
    # 7. DATOS DEL REPORTE
    # =========================================================================
    elements.append(Paragraph("DATOS DEL REPORTE", section_style))
    elements.append(Spacer(1, 6))

    datos_reporte = []
    datos_reporte.append(["Total de registros:", str(total_movimientos)])

    # Solo agregar filtros si se aplicaron
    if fecha_inicio or fecha_fin:
        datos_reporte.append(
            ["Período del reporte:", f"Del {fecha_inicio_str} al {fecha_fin_str}"])

    if tipo_movimiento:
        tipo_display = {
            'income': 'Entradas',
            'expense': 'Gastos',
            'service': 'Servicios'
        }.get(tipo_movimiento, tipo_movimiento)
        datos_reporte.append(["Tipo de movimiento filtrado:", tipo_display])

    if categoria:
        datos_reporte.append(["Categoría filtrada:", categoria])

    if usuario:
        datos_reporte.append(["Usuario filtrado:", usuario])

    # Agregar información de totales
    datos_reporte.append(["Total Entradas:", f"RD$ {total_entradas:,.2f}"])
    datos_reporte.append(["Total Gastos:", f"RD$ {total_gastos:,.2f}"])
    datos_reporte.append(["Total Servicios:", f"RD$ {total_servicios:,.2f}"])
    datos_reporte.append(["Balance General:", f"RD$ {total_general:,.2f}"])

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

    # =========================================================================
    # 8. TABLA DETALLADA DE MOVIMIENTOS
    # =========================================================================
    if all_movements:
        elements.append(Paragraph("DETALLE DE MOVIMIENTOS", section_style))
        elements.append(Spacer(1, 6))

        # Preparar datos de la tabla
        table_data = []

        # Encabezados
        headers = [
            Paragraph("Nº", table_header_style),
            Paragraph("FECHA", table_header_style),
            Paragraph("TIPO", table_header_style),
            Paragraph("DESCRIPCIÓN", table_header_style),
            Paragraph("MONTO (RD$)", table_header_style),
            Paragraph("CATEGORÍA", table_header_style),
            Paragraph("RESPONSABLE", table_header_style)
        ]
        table_data.append(headers)

        # Agregar filas de datos
        for idx, mov in enumerate(all_movements, 1):
            # Formatear fecha
            if hasattr(mov['fecha'], 'strftime'):
                fecha_formateada = mov['fecha'].strftime('%d/%m/%Y')
            else:
                # Si no es datetime, intentar convertir
                try:
                    fecha_formateada = mov['fecha'].split('T')[0]
                except:
                    fecha_formateada = str(mov['fecha'])

            # Truncar descripción si es muy larga
            descripcion_text = mov['descripcion'] or 'Sin descripción'
            if len(descripcion_text) > 30:
                descripcion_text = descripcion_text[:27] + "..."

            # Determinar color del tipo
            tipo_color = {
                'Entrada': colors.HexColor('#2e7d32'),  # Verde
                'Gasto': colors.HexColor('#c62828'),    # Rojo
                'Servicio': colors.HexColor('#ef6c00')  # Naranja
            }.get(mov['tipo'], colors.black)

            # Crear celda de tipo con color
            tipo_cell = Paragraph(
                f"<font color='{tipo_color}'>{mov['tipo']}</font>",
                ParagraphStyle(
                    'TipoCell',
                    parent=styles['Normal'],
                    fontSize=9,
                    alignment=1,
                    leading=10,
                    textColor=tipo_color
                )
            )

            # Formatear monto
            try:
                monto_formateado = f"RD$ {float(mov['monto']):,.2f}"
            except:
                monto_formateado = f"RD$ {mov['monto']:,.2f}"

            row = [
                Paragraph(str(idx), table_cell_style),
                Paragraph(fecha_formateada, table_cell_style),
                tipo_cell,
                Paragraph(descripcion_text, table_cell_left_style),
                Paragraph(monto_formateado, table_cell_style),
                Paragraph(mov['categoria'], table_cell_style),
                Paragraph(mov['responsable'], table_cell_style)
            ]
            table_data.append(row)

        # Anchos de columna
        col_widths = [1.0*cm, 2.0*cm, 1.8*cm, 4.5*cm, 3.0*cm, 3.0*cm, 3.0*cm]
        table = Table(table_data, colWidths=col_widths, repeatRows=1)

        # Estilos de la tabla
        table_style = TableStyle([
            # Encabezado
            ('BACKGROUND', (0, 0), (-1, 0),
             colors.HexColor("#F7FAFC")),  # Azul del sidebar
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),

            # Bordes
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),

            # Alineación
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),
            ('ALIGN', (1, 1), (1, -1), 'CENTER'),
            ('ALIGN', (2, 1), (2, -1), 'CENTER'),
            ('ALIGN', (3, 1), (3, -1), 'LEFT'),
            ('ALIGN', (4, 1), (4, -1), 'RIGHT'),
            ('ALIGN', (5, 1), (6, -1), 'CENTER'),

            # Padding
            ('PADDING', (0, 0), (-1, -1), (4, 4)),

            # Fondo base
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ])

        # Alternar colores de fila
        for i in range(1, len(table_data)):
            if i % 2 == 0:
                table_style.add('BACKGROUND', (0, i), (-1, i),
                                colors.HexColor('#f8f8f8'))

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
        elements.append(
            Paragraph("NO SE ENCONTRARON MOVIMIENTOS", no_data_style))
        elements.append(Spacer(1, 15))

    elements.append(Spacer(1, 20))

    # =========================================================================
    # 9. RESUMEN FINAL
    # =========================================================================
    elements.append(Paragraph("RESUMEN FINAL", section_style))
    elements.append(Spacer(1, 6))

    resumen_data = [
        ["TOTAL ENTRADAS:", f"RD$ {total_entradas:,.2f}"],
        ["TOTAL GASTOS:", f"RD$ {total_gastos:,.2f}"],
        ["TOTAL SERVICIOS:", f"RD$ {total_servicios:,.2f}"],
        ["", ""],
        ["BALANCE FINAL:", f"RD$ {total_general:,.2f}"]
    ]

    resumen_table = Table(resumen_data, colWidths=[5*cm, 5*cm])
    resumen_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -2), 0.5, colors.black),
        ('GRID', (0, 4), (1, 4), 1, colors.black),
        ('PADDING', (0, 0), (-1, -1), (6, 8)),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
        ('BACKGROUND', (1, 4), (1, 4), colors.HexColor('#e3f2fd')),
        ('FONTSIZE', (0, 4), (1, 4), 11),
        ('FONTNAME', (0, 4), (1, 4), 'Helvetica-Bold'),
    ]))

    elements.append(resumen_table)
    elements.append(Spacer(1, 20))

    # =========================================================================
    # 10. PIE DE PÁGINA
    # =========================================================================
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
    elements.append(Paragraph(
        f"Sistema de Gestión Financiera - MLAN FINANCE | Generado el {datetime.now().strftime('%d/%m/%Y %I:%M %p')}", footer_style))
    elements.append(Paragraph(
        "Este reporte constituye documentación oficial del sistema", footer_style))

    # Construir el PDF
    try:
        doc.build(elements)
    except Exception as e:
        # En caso de error, devolver un error simple
        error_response = HttpResponse(
            f"Error al generar PDF: {str(e)}", content_type='text/plain')
        return error_response

    # Obtener el valor del buffer
    pdf = buffer.getvalue()
    buffer.close()

    # Crear respuesta HTTP
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="reporte_movimientos_completo_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf"'
    response.write(pdf)

    return response

#=============================================================================
# REPORTE IMPRIMIBLE - DASHBOARD FINANCIERO (EXPORTADOR)
#=============================================================================
@never_cache
def dashboard_imprimir_historial(request):
    """
    Vista para generar un reporte imprimible del dashboard financiero
    CON ZONA HORARIA CORRECTA PARA REPÚBLICA DOMINICANA (UTC-4)
    """
    # Configurar zona horaria de República Dominicana
    RD_TZ = pytz.timezone('America/Santo_Domingo')

    # Obtener parámetros de filtro del GET
    date_from_str = request.GET.get('date_from')
    date_to_str = request.GET.get('date_to')
    tipo_filtro = request.GET.get('type')
    categoria_filtro = request.GET.get('category')
    usuario_filtro = request.GET.get('user')

    # Si hay fechas en los parámetros, usarlas; de lo contrario, usar valores por defecto
    if date_from_str and date_to_str:
        try:
            # Parsear fechas y aplicar zona horaria de RD
            fecha_inicio_naive = timezone.datetime.strptime(
                date_from_str, '%Y-%m-%d')
            fecha_fin_naive = timezone.datetime.strptime(
                date_to_str, '%Y-%m-%d')

            # Hacer las fechas aware con zona horaria de RD
            fecha_inicio = RD_TZ.localize(fecha_inicio_naive.replace(
                hour=0, minute=0, second=0, microsecond=0
            ))
            fecha_fin = RD_TZ.localize(fecha_fin_naive.replace(
                hour=23, minute=59, second=59, microsecond=999999
            ))

        except ValueError:
            # Si hay error en el formato, usar valores por defecto
            hoy = timezone.now().astimezone(RD_TZ)
            primer_dia_mes_actual = hoy.replace(
                day=1, hour=0, minute=0, second=0, microsecond=0)
            fecha_inicio = primer_dia_mes_actual - timedelta(days=15)
            fecha_fin = hoy.replace(
                hour=23, minute=59, second=59, microsecond=999999)
    else:
        # Valores por defecto: mes actual + 15 días anteriores
        hoy = timezone.now().astimezone(RD_TZ)
        primer_dia_mes_actual = hoy.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0)
        fecha_inicio = primer_dia_mes_actual - timedelta(days=15)
        fecha_fin = hoy.replace(
            hour=23, minute=59, second=59, microsecond=999999)

    # ==========================================
    # OBTENER DATOS CON FILTROS
    # ==========================================

    # Base querysets
    entradas_qs = MovimientoEntrada.objects.filter(
        fecha__gte=fecha_inicio,
        fecha__lte=fecha_fin
    )

    gastos_qs = Gasto.objects.filter(
        fecha__gte=fecha_inicio,
        fecha__lte=fecha_fin
    )

    servicios_qs = ServicioPago.objects.filter(
        fecha__gte=fecha_inicio,
        fecha__lte=fecha_fin
    )

    # Aplicar filtros adicionales si existen
    if tipo_filtro:
        if tipo_filtro == 'income':
            gastos_qs = gastos_qs.none()
            servicios_qs = servicios_qs.none()
        elif tipo_filtro == 'expense':
            entradas_qs = entradas_qs.none()
            servicios_qs = servicios_qs.none()
        elif tipo_filtro == 'service':
            entradas_qs = entradas_qs.none()
            gastos_qs = gastos_qs.none()

    if categoria_filtro:
        gastos_qs = gastos_qs.filter(categoria__icontains=categoria_filtro)

    # ==========================================
    # CALCULAR TOTALES
    # ==========================================

    entradas_periodo = entradas_qs.aggregate(
        total=Sum('monto_pesos'))['total'] or 0
    gastos_periodo = gastos_qs.aggregate(total=Sum('monto'))['total'] or 0
    servicios_periodo = servicios_qs.aggregate(
        total=Sum('monto'))['total'] or 0

    total_gastado_periodo = gastos_periodo + servicios_periodo
    balance_periodo = entradas_periodo - total_gastado_periodo

    # ==========================================
    # OBTENER MOVIMIENTOS
    # ==========================================

    # Combinar todos los movimientos para la tabla
    movimientos_combinados = []

    # Agregar entradas
    for entrada in entradas_qs.order_by('-fecha')[:100]:
        # Convertir fecha a zona horaria de RD para mostrar
        fecha_rd = entrada.fecha.astimezone(RD_TZ) if timezone.is_aware(
            entrada.fecha) else RD_TZ.localize(entrada.fecha)

        movimientos_combinados.append({
            'tipo': 'Entrada',
            'fecha': fecha_rd,
            'descripcion': entrada.descripcion or 'Conversión USD-DOP',
            'monto': entrada.monto_pesos,
            'categoria': 'Conversión USD-DOP',
            'responsable': 'Maria DC Lantigua',
            'tipo_movimiento': 'entrada',
            'usd': entrada.monto_usd,
            'tasa_cambio': entrada.tasa_cambio,
            'id': entrada.id,
            'moneda': 'USD',
            'simbolo': 'US$'
        })

    # Agregar gastos
    for gasto in gastos_qs.order_by('-fecha')[:100]:
        # Convertir fecha a zona horaria de RD
        fecha_rd = gasto.fecha.astimezone(RD_TZ) if timezone.is_aware(
            gasto.fecha) else RD_TZ.localize(gasto.fecha)

        movimientos_combinados.append({
            'tipo': 'Gasto',
            'fecha': fecha_rd,
            'descripcion': gasto.descripcion or 'Gasto registrado',
            'monto': gasto.monto,
            'categoria': gasto.categoria,
            'responsable': gasto.proveedor or 'No especificado',
            'tipo_movimiento': 'gasto',
            'id': gasto.id
        })

    # Agregar servicios
    for servicio in servicios_qs.order_by('-fecha')[:100]:
        # Convertir fecha a zona horaria de RD
        fecha_rd = servicio.fecha.astimezone(RD_TZ) if timezone.is_aware(
            servicio.fecha) else RD_TZ.localize(servicio.fecha)

        movimientos_combinados.append({
            'tipo': 'Servicio',
            'fecha': fecha_rd,
            'descripcion': servicio.descripcion or 'Pago de servicio',
            'monto': servicio.monto,
            'categoria': servicio.tipo_servicio,
            'responsable': servicio.proveedor or 'No especificado',
            'tipo_movimiento': 'servicio',
            'id': servicio.id
        })

    # Ordenar movimientos por fecha (más reciente primero)
    movimientos_combinados.sort(key=lambda x: x['fecha'], reverse=True)

    # ==========================================
    # PREPARAR CONTEXTO
    # ==========================================

    # Fecha actual en zona horaria de RD
    fecha_reporte_rd = timezone.now().astimezone(RD_TZ)

    context = {
        'empresa_nombre': 'MLAN FINANCE',
        'titulo_reporte': 'Dashboard Financiero - Reporte de Movimientos',
        'fecha_reporte': fecha_reporte_rd.strftime('%d/%m/%Y %I:%M:%S'),

        'periodo': {
            'inicio': fecha_inicio.strftime('%d/%m/%Y'),
            'fin': fecha_fin.strftime('%d/%m/%Y'),
            'mes_actual': fecha_inicio.strftime('%B %Y').capitalize()
        },

        'totales': {
            'balance_general': balance_periodo,
            'entradas_mes_actual': entradas_periodo,
            'gastos_mes_actual': gastos_periodo,
            'servicios_mes_actual': servicios_periodo,
            'total_gastado_mes_actual': total_gastado_periodo,
            'cantidad_servicios': servicios_qs.count(),
        },

        'movimientos': movimientos_combinados,

        'estadisticas': {
            'gastos_por_categoria': gastos_qs.values('categoria').annotate(
                total=Sum('monto')
            ).order_by('-total'),
            'total_movimientos': len(movimientos_combinados),
            'total_entradas_periodo': entradas_qs.count(),
            'total_gastos_periodo': gastos_qs.count(),
            'total_servicios_periodo': servicios_qs.count(),
        },

        'usuario': {
            'nombre': request.user.get_full_name() if request.user.is_authenticated else 'Usuario',
            'username': request.user.username if request.user.is_authenticated else 'No autenticado'
        }
    }
    return render(request, 'finanzas/dashboard_print.html', context)


#==========#=============#==========#======#============#===============#==================#=================#
#==========#=============#==========#======#============#===============#==================#=================#


#=============================================================================
# VISTAS DE ERROR PERSONALIZADAS
#=============================================================================
def error_400(request, exception):
    return render(request, "errors/400.html", status=400)
def error_403(request, exception):
    return render(request, "errors/403.html", status=403)
def error_404(request, exception):
    return render(request, "errors/404.html", status=404)
def error_500(request):
    return render(request, "errors/500.html", status=500)

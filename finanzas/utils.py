from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from django.utils import timezone
from datetime import datetime

def generar_pdf_conversion(conversion):
    """Generar PDF para una conversión individual"""
    buffer = BytesIO()
    
    # Crear documento
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch)
    elements = []
    
    # Estilos
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30,
        alignment=1  # Centrado
    )
    
    # Título
    title = Paragraph("COMPROBANTE DE CONVERSIÓN", title_style)
    elements.append(title)
    
    # Información de la conversión
    data = [
        ['Número de Conversión:', f"CONV-{conversion.id:06d}"],
        ['Fecha de Conversión:', conversion.fecha_conversion.strftime('%d/%m/%Y')],
        ['Fecha de Registro:', conversion.fecha_registro.strftime('%d/%m/%Y %H:%M')],
        ['', ''],
        ['MONTO EN DÓLARES:', f"${conversion.monto_usd:,.2f} USD"],
        ['TASA DE CAMBIO:', f"{conversion.tasa_cambio:.4f}"],
        ['MONTO EN PESOS:', f"RD$ {conversion.monto_pesos:,.2f}"],
        ['', ''],
        ['REPRESENTANTE:', conversion.rep_nombre],
        ['ESTADO:', conversion.get_estado_display()],
    ]
    
    if conversion.rep_identificacion:
        data.insert(8, ['Identificación:', conversion.rep_identificacion])
    
    # Crear tabla
    table = Table(data, colWidths=[2.5*inch, 3*inch])
    table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, -1), 'Helvetica', 10),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8f9fa')),
        ('BACKGROUND', (0, 4), (0, 6), colors.HexColor('#e3f2fd')),
        ('BACKGROUND', (0, 8), (0, -1), colors.HexColor('#f3e5f5')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONT', (1, 0), (1, -1), 'Helvetica-Bold', 10),
        ('FONT', (1, 4), (1, 6), 'Helvetica-Bold', 12),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.black),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#fafafa')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Notas si existen
    if conversion.notas and conversion.notas.strip():
        notes_style = ParagraphStyle(
            'NotesStyle',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.darkblue,
            backColor=colors.HexColor('#fff9c4'),
            borderPadding=10,
            borderColor=colors.orange,
            borderWidth=1
        )
        notes_title = Paragraph("<b>NOTAS ADICIONALES:</b>", styles['Heading3'])
        elements.append(notes_title)
        notes_content = Paragraph(conversion.notas, notes_style)
        elements.append(notes_content)
    
    # Pie de página
    footer_style = ParagraphStyle(
        'FooterStyle',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey,
        alignment=1
    )
    elements.append(Spacer(1, 0.5*inch))
    footer = Paragraph(
        f"Generado el {timezone.now().strftime('%d/%m/%Y a las %H:%M')} - MLAN Finance System",
        footer_style
    )
    elements.append(footer)
    
    # Construir PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer

def generar_pdf_historial(conversiones, usuario):
    """Generar PDF del historial de conversiones"""
    buffer = BytesIO()
    
    # Crear documento
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch)
    elements = []
    
    # Estilos
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=1
    )
    
    # Título y información del reporte
    title = Paragraph("HISTORIAL DE CONVERSIONES", title_style)
    elements.append(title)
    
    info_style = ParagraphStyle(
        'InfoStyle',
        parent=styles['Normal'],
        fontSize=10,
        alignment=1
    )
    
    user_info = Paragraph(
        f"Usuario: {usuario.get_full_name() or usuario.username} | "
        f"Email: {usuario.email}",
        info_style
    )
    elements.append(user_info)
    
    date_info = Paragraph(
        f"Reporte generado el: {timezone.now().strftime('%d/%m/%Y a las %H:%M')}",
        info_style
    )
    elements.append(date_info)
    
    elements.append(Spacer(1, 0.3*inch))
    
    # Estadísticas resumen
    total_usd = sum(conv.monto_usd for conv in conversiones)
    total_pesos = sum(conv.monto_pesos for conv in conversiones)
    
    stats_data = [
        ['TOTAL CONVERSIONES:', len(conversiones)],
        ['TOTAL USD:', f"${total_usd:,.2f}"],
        ['TOTAL RD$:', f"RD$ {total_pesos:,.2f}"],
    ]
    
    stats_table = Table(stats_data, colWidths=[2.5*inch, 2*inch])
    stats_table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, -1), 'Helvetica-Bold', 11),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#e3f2fd')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    elements.append(stats_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Tabla de conversiones
    if conversiones:
        # Encabezados de la tabla
        headers = ['Fecha', 'USD', 'Tasa', 'RD$', 'Representante', 'Estado']
        
        # Datos de la tabla
        table_data = [headers]
        for conv in conversiones:
            row = [
                conv.fecha_conversion.strftime('%d/%m/%Y'),
                f"${conv.monto_usd:,.2f}",
                f"{conv.tasa_cambio:.4f}",
                f"RD$ {conv.monto_pesos:,.2f}",
                conv.rep_nombre,
                conv.get_estado_display()
            ]
            table_data.append(row)
        
        # Crear tabla
        table = Table(table_data, repeatRows=1)
        table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 9),  # Encabezados
            ('FONT', (0, 1), (-1, -1), 'Helvetica', 8),      # Datos
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#035087')),  # Fondo encabezado
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),    # Texto encabezado blanco
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(table)
    else:
        no_data = Paragraph(
            "<b>No hay conversiones para mostrar en el período seleccionado</b>",
            styles['Heading3']
        )
        elements.append(no_data)
    
    # Pie de página
    elements.append(Spacer(1, 0.5*inch))
    footer_style = ParagraphStyle(
        'FooterStyle',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey,
        alignment=1
    )
    footer = Paragraph(
        "MLAN Finance System - Sistema de Gestión de Conversiones",
        footer_style
    )
    elements.append(footer)
    
    # Construir PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer
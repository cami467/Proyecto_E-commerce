import os
from reportlab.platypus import Image
from datetime import datetime
from decimal import Decimal
from io import BytesIO

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
)


def _gs(valor) -> str:
    """
    Formatea un valor monetario como string en Guaraníes.
    Ejemplo: 135000 -> '135.000'
    """
    numero = int(Decimal(str(valor or 0)))
    return f"{numero:,}".replace(",", ".")


def _numero_factura_display(orden) -> str:
    """
    Genera un número de factura con formato paraguayo estándar
    001-001-NNNNNNN a partir de un contador secuencial.

    Usa los últimos 7 dígitos numéricos derivados del número de
    orden interno para mantener unicidad sin necesitar una tabla
    de numeración fiscal separada (que se podría agregar a futuro
    si el negocio crece y se gestiona ante la SET).
    """
    numero_secuencial = abs(hash(str(orden.id))) % 9_999_999
    return f"001-001-{numero_secuencial:07d}"


def generar_factura_pdf(orden) -> BytesIO:
    """
    Genera el PDF de una factura legal paraguaya a partir de una
    instancia de Orden, replicando el formato estándar de factura
    impresa: encabezado con timbrado y RUC, datos del cliente,
    tabla de ítems con columnas separadas por tasa de IVA (5%/10%/
    Exentas), y liquidación del IVA al pie.

    El PDF se genera completamente en memoria (BytesIO), nunca se
    escribe a disco.

    Args:
        orden: instancia de Orden con sus items prefetcheados.
               Se recomienda pasar una orden con
               .prefetch_related("items") para evitar N+1.

    Returns:
        BytesIO: buffer del PDF listo para ser leído desde el inicio.
    """
    buffer = BytesIO()

    documento = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
    )

    estilos = getSampleStyleSheet()
    estilo_empresa = ParagraphStyle(
        "Empresa",
        parent=estilos["Normal"],
        fontSize=9,
        leading=12,
    )
    estilo_factura_titulo = ParagraphStyle(
        "FacturaTitulo",
        parent=estilos["Normal"],
        fontSize=13,
        fontName="Helvetica-Bold",
        alignment=1,  # centrado
    )
    estilo_factura_dato = ParagraphStyle(
        "FacturaDato",
        parent=estilos["Normal"],
        fontSize=9,
        alignment=1,
    )
    estilo_seccion = ParagraphStyle(
        "Seccion",
        parent=estilos["Normal"],
        fontSize=9,
        fontName="Helvetica-Bold",
        spaceBefore=8,
        spaceAfter=4,
    )

    elementos = []
    
    # ------------------------------------------------------------------
    # LOGOS DE LA EMPRESA
    # ------------------------------------------------------------------
    def _cargar_logo(nombre_archivo, ancho=1.0 * cm, alto=1.4 * cm):
        """
        Carga un logo desde static/facturas/ como imagen de ReportLab.
        Si el archivo no existe, retorna None en lugar de fallar,
        para que la factura siga generándose aunque falte un logo.
        """
        ruta = os.path.join(settings.BASE_DIR, "static", "facturas", nombre_archivo)
        if not os.path.exists(ruta):
            return None
        return Image(ruta, width=ancho, height=alto)

    logo_eimek = _cargar_logo("logo_eimek.jpg")
    logo_ecp = _cargar_logo("ecp.jpg")
    logo_good = _cargar_logo("good_of_pizz.jpg")

    logos_disponibles = [logo for logo in (logo_eimek, logo_ecp, logo_good) if logo is not None]

    if logos_disponibles:
        fila_logos = Table(
            [logos_disponibles],
            colWidths=[1.1 * cm] * len(logos_disponibles),
        )
        fila_logos.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (1, 0), (-1, -1), 4),
        ]))
    else:
        fila_logos = Paragraph("", estilos["Normal"])

    # ------------------------------------------------------------------
    # ENCABEZADO: DATOS DE LA EMPRESA + RECUADRO DE FACTURA
    # ------------------------------------------------------------------
    datos_empresa = Paragraph(
        f"<b>{settings.EMPRESA_RAZON_SOCIAL}</b><br/>"
        f"{settings.EMPRESA_ACTIVIDAD}<br/>"
        f"{settings.EMPRESA_DIRECCION}<br/>"
        f"Tel: {settings.EMPRESA_TELEFONO}",
        estilo_empresa,
    )
    
    bloque_empresa = Table(
        [[fila_logos, datos_empresa]],
        colWidths=[3.6 * cm if logos_disponibles else 0.1 * cm, 6.8 * cm],
    )
    bloque_empresa.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))

    numero_factura = _numero_factura_display(orden)
    recuadro_factura = Table(
        [
            [Paragraph("FACTURA", estilo_factura_titulo)],
            [Paragraph(f"N° {numero_factura}", estilo_factura_dato)],
            [Paragraph(f"TIMBRADO N°: {settings.EMPRESA_TIMBRADO}", estilo_factura_dato)],
            [Paragraph(f"R.U.C.: {settings.EMPRESA_RUC}", estilo_factura_dato)],
            [Paragraph(
                f"Vigencia: {settings.EMPRESA_TIMBRADO_VIGENCIA_INICIO} - "
                f"{settings.EMPRESA_TIMBRADO_VIGENCIA_FIN}",
                estilo_factura_dato,
            )],
        ],
        colWidths=[7 * cm],
    )
    recuadro_factura.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1.2, colors.black),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
    ]))

    tabla_encabezado = Table(
        [[bloque_empresa, recuadro_factura]],
        colWidths=[10.5 * cm, 7 * cm],
    )
    tabla_encabezado.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elementos.append(tabla_encabezado)
    elementos.append(Spacer(1, 0.5 * cm))

    # ------------------------------------------------------------------
    # DATOS DEL CLIENTE
    # ------------------------------------------------------------------
    fecha_emision = orden.fecha_creacion.strftime("%d/%m/%Y")
    nombre_cliente = orden.usuario.get_full_name() or orden.usuario.username
    condicion_venta = "CONTADO"  # El proyecto solo maneja ventas al contado por ahora

    datos_cliente = [
        ["Fecha de emisión:", fecha_emision, "Condición de venta:", condicion_venta],
        ["Nombre o Razón Social:", nombre_cliente, "RUC o C.I. N°:", "-"],
        ["Dirección:", "-", "Teléfono:", "-"],
    ]
    tabla_cliente = Table(
        datos_cliente,
        colWidths=[4.2 * cm, 6.3 * cm, 3.8 * cm, 3.2 * cm],
    )
    tabla_cliente.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.black),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elementos.append(tabla_cliente)
    elementos.append(Spacer(1, 0.4 * cm))

    # ------------------------------------------------------------------
    # TABLA DE ÍTEMS — separados por tasa de IVA (5% / 10% / Exentas)
    # ------------------------------------------------------------------
    encabezado_items = [
        "Cant.", "Descripción", "Precio Unitario",
        "Exentas", "5%", "10%",
    ]
    filas_items = [encabezado_items]

    total_exentas = Decimal("0")
    total_cinco = Decimal("0")
    total_diez = Decimal("0")
    iva_cinco = Decimal("0")
    iva_diez = Decimal("0")

    for item in orden.items.all():
        fila = [str(item.cantidad), f"{item.nombre_producto} - {item.nombre_variante}", _gs(item.precio_unitario)]

        if item.tasa_iva == "0":
            total_exentas += item.subtotal
            fila += [_gs(item.subtotal), "", ""]
        elif item.tasa_iva == "5":
            total_cinco += item.subtotal
            iva_cinco += item.monto_iva
            fila += ["", _gs(item.subtotal), ""]
        else:  # 10%
            total_diez += item.subtotal
            iva_diez += item.monto_iva
            fila += ["", "", _gs(item.subtotal)]

        filas_items.append(fila)

    # Rellena filas vacías hasta un mínimo de 8, como en la factura impresa
    while len(filas_items) < 9:
        filas_items.append(["", "", "", "", "", ""])

    tabla_items = Table(
        filas_items,
        colWidths=[1.3 * cm, 7.2 * cm, 2.8 * cm, 2.2 * cm, 1.8 * cm, 2.2 * cm],
        repeatRows=1,
    )
    tabla_items.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c2c2c")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("BOX", (0, 0), (-1, -1), 1, colors.black),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elementos.append(tabla_items)
    elementos.append(Spacer(1, 0.4 * cm))

    # ------------------------------------------------------------------
    # LIQUIDACIÓN DEL IVA Y TOTALES
    # ------------------------------------------------------------------
    iva_total = iva_cinco + iva_diez
    valor_venta_total = total_exentas + total_cinco + total_diez

    filas_liquidacion = [
        ["Subtotales:", _gs(valor_venta_total)],
        ["Total a pagar en Guaraníes:", _gs(orden.total)],
        ["", ""],
        ["Liquidación del IVA", ""],
        ["(5%) Gravado:", _gs(total_cinco)],
        ["(10%) Gravado:", _gs(total_diez)],
        ["Exentas:", _gs(total_exentas)],
        ["IVA (5%):", _gs(iva_cinco)],
        ["IVA (10%):", _gs(iva_diez)],
        ["Total IVA:", _gs(iva_total)],
    ]

    tabla_liquidacion = Table(filas_liquidacion, colWidths=[12 * cm, 5.5 * cm])
    tabla_liquidacion.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, 1), 11),
        ("FONTNAME", (0, 3), (-1, 3), "Helvetica-Bold"),
        ("LINEABOVE", (0, 1), (-1, 1), 1, colors.black),
        ("LINEBELOW", (0, 1), (-1, 1), 1, colors.black),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.black),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elementos.append(tabla_liquidacion)

    # ------------------------------------------------------------------
    # NOTAS Y PIE
    # ------------------------------------------------------------------
    if orden.notas:
        elementos.append(Spacer(1, 0.5 * cm))
        elementos.append(Paragraph("Notas:", estilo_seccion))
        elementos.append(Paragraph(orden.notas, estilos["Normal"]))

    elementos.append(Spacer(1, 0.8 * cm))
    elementos.append(
        Paragraph(
            "Original: Cliente - Duplicado: Archivo Tributario",
            ParagraphStyle("Pie", parent=estilos["Normal"], fontSize=7.5, textColor=colors.grey),
        )
    )

    documento.build(elementos)
    buffer.seek(0)
    return buffer
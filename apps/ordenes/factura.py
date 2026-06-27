import os
import hashlib
from decimal import Decimal
from io import BytesIO

import qrcode
from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    Image,
)

from core.numeros_en_letras import numero_a_letras

NEGRO = colors.black
GRIS = colors.HexColor("#555555")
GRIS_CLARO = colors.HexColor("#f4f4f4")


def _gs(valor) -> str:
    """Formatea un valor monetario en Guaraníes. Ej: 135000 -> '135.000'"""
    numero = int(Decimal(str(valor or 0)))
    return f"{numero:,}".replace(",", ".")


def _numero_factura_display(orden) -> str:
    """
    Genera un número de factura con formato paraguayo estándar
    001-001-NNNNNNN a partir de un hash determinístico del UUID
    de la orden.
    """
    hash_bytes = hashlib.sha256(str(orden.id).encode()).hexdigest()
    numero_secuencial = int(hash_bytes, 16) % 9_999_999
    return f"001-001-{numero_secuencial:07d}"


def _generar_imagen_qr(orden) -> BytesIO:
    """Genera un código QR en memoria que apunta al detalle de la orden."""
    url_verificacion = f"{settings.URL_BASE_SISTEMA}/api/ordenes/{orden.id}/"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=4,
        border=1,
    )
    qr.add_data(url_verificacion)
    qr.make(fit=True)
    imagen_qr = qr.make_image(fill_color="black", back_color="white")

    buffer_qr = BytesIO()
    imagen_qr.save(buffer_qr, format="PNG")
    buffer_qr.seek(0)
    return buffer_qr


# ==============================================================================
# ESTILOS NATIVOS CONTROLADOS
# ==============================================================================
ESTILO_RAZON_SOCIAL = ParagraphStyle(
    "RazonSocial", fontName="Helvetica-Bold", fontSize=13,
    leading=15, textColor=NEGRO, alignment=TA_LEFT,
)
ESTILO_ACTIVIDAD = ParagraphStyle(
    "Actividad", fontName="Helvetica", fontSize=7,
    leading=9, textColor=NEGRO, alignment=TA_LEFT,
)
ESTILO_FACTURA_TITULO = ParagraphStyle(
    "FacturaTitulo", fontName="Helvetica-Bold", fontSize=11,
    leading=13, textColor=NEGRO, alignment=TA_CENTER,
)
ESTILO_FACTURA_DATO = ParagraphStyle(
    "FacturaDato", fontName="Helvetica", fontSize=8,
    leading=11, textColor=NEGRO, alignment=TA_CENTER,
)
ESTILO_CELDA = ParagraphStyle(
    "Celda", fontName="Helvetica", fontSize=7.5,
    leading=9, textColor=NEGRO, alignment=TA_LEFT,
)
ESTILO_CELDA_CENTRO = ParagraphStyle(
    "CeldaCentro", fontName="Helvetica", fontSize=7.5,
    leading=9, textColor=NEGRO, alignment=TA_CENTER,
)
ESTILO_CELDA_BOLD = ParagraphStyle(
    "CeldaBold", fontName="Helvetica-Bold", fontSize=7.5,
    leading=9, textColor=NEGRO, alignment=TA_LEFT,
)
ESTILO_CELDA_BOLD_CENTRO = ParagraphStyle(
    "CeldaBoldCentro", fontName="Helvetica-Bold", fontSize=7,
    leading=8.5, textColor=NEGRO, alignment=TA_CENTER, wordWrap=None,
)
ESTILO_CELDA_DER = ParagraphStyle(
    "CeldaDer", fontName="Helvetica", fontSize=7.5,
    leading=9, textColor=NEGRO, alignment=TA_RIGHT, wordWrap=None,
)
ESTILO_CELDA_BOLD_DER = ParagraphStyle(
    "CeldaBoldDer", fontName="Helvetica-Bold", fontSize=7.5,
    leading=9, textColor=NEGRO, alignment=TA_RIGHT, wordWrap=None,
)
ESTILO_NOTAS = ParagraphStyle(
    "Notas", fontName="Helvetica", fontSize=8, textColor=NEGRO,
)
ESTILO_PIE = ParagraphStyle(
    "Pie", fontName="Helvetica", fontSize=7, textColor=GRIS,
)


def generar_factura_pdf(orden) -> BytesIO:
    """
    Genera el PDF de la factura unificando ítems y totales en una sola tabla
    continua y cerrada, igual al formato digital de UniNorte.
    """
    buffer = BytesIO()

    documento = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=0.8 * cm,
        bottomMargin=0.8 * cm,
        leftMargin=0.8 * cm,
        rightMargin=0.8 * cm,
    )

    ANCHO_PAGINA = 19.4 * cm

    elementos = []
    p = lambda txt: Paragraph(str(txt), ESTILO_CELDA)
    pc = lambda txt: Paragraph(str(txt), ESTILO_CELDA_CENTRO)
    pb = lambda txt: Paragraph(str(txt), ESTILO_CELDA_BOLD)
    pbc = lambda txt: Paragraph(str(txt), ESTILO_CELDA_BOLD_CENTRO)
    pd = lambda txt: Paragraph(str(txt), ESTILO_CELDA_DER)
    pbd = lambda txt: Paragraph(str(txt), ESTILO_CELDA_BOLD_DER)

    # ------------------------------------------------------------------
    # ENCABEZADO FISCAL Y LOGOS
    # ------------------------------------------------------------------
    def _cargar_logo(nombre_archivo, ancho=1.1 * cm, alto=1.1 * cm):
        ruta = os.path.join(settings.BASE_DIR, "static", "facturas", nombre_archivo)
        if not os.path.exists(ruta):
            return None
        return Image(ruta, width=ancho, height=alto)

    logos = [
        logo for logo in (
            _cargar_logo("logo_eimek.jpg"),
            _cargar_logo("ecp.jpg"),
            _cargar_logo("good_of_pizz.jpg"),
        ) if logo is not None
    ]

    ANCHO_MARCA = 12.0 * cm
    ANCHO_FISCAL = ANCHO_PAGINA - ANCHO_MARCA

    if logos:
        fila_logos = Table([logos], colWidths=[1.2 * cm] * len(logos))
        fila_logos.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        ancho_logos = 1.2 * cm * len(logos) + 0.1 * cm
    else:
        fila_logos = Paragraph("", ESTILO_CELDA)
        ancho_logos = 0.1 * cm

    bloque_marca = Table(
        [[
            fila_logos,
            Table(
                [
                    [Paragraph(settings.EMPRESA_RAZON_SOCIAL, ESTILO_RAZON_SOCIAL)],
                    [Paragraph(settings.EMPRESA_ACTIVIDAD, ESTILO_ACTIVIDAD)],
                ],
                colWidths=[ANCHO_MARCA - ancho_logos],
            ),
        ]],
        colWidths=[ancho_logos, ANCHO_MARCA - ancho_logos],
    )
    bloque_marca.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    numero_factura = _numero_factura_display(orden)
    bloque_fiscal = Table(
        [
            [Paragraph("FACTURA ELECTRÓNICA", ESTILO_FACTURA_TITULO)],
            [Paragraph(f"N° {numero_factura}", ESTILO_FACTURA_DATO)],
            [Paragraph(f"Timbrado N°: {settings.EMPRESA_TIMBRADO}", ESTILO_FACTURA_DATO)],
            [Paragraph(f"R.U.C.: {settings.EMPRESA_RUC}", ESTILO_FACTURA_DATO)],
            [Paragraph(
                f"Vigencia: {settings.EMPRESA_TIMBRADO_VIGENCIA_INICIO} - "
                f"{settings.EMPRESA_TIMBRADO_VIGENCIA_FIN}",
                ESTILO_FACTURA_DATO,
            )],
        ],
        colWidths=[ANCHO_FISCAL],
    )
    bloque_fiscal.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    texto_pie_marca = Paragraph(
        f"{settings.EMPRESA_DIRECCION}  -  Tel: {settings.EMPRESA_TELEFONO}",
        ESTILO_ACTIVIDAD,
    )

    bloque_marca_completo = Table(
        [[bloque_marca], [texto_pie_marca]],
        colWidths=[ANCHO_MARCA],
    )
    bloque_marca_completo.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))

    tabla_encabezado = Table(
        [[bloque_marca_completo, bloque_fiscal]],
        colWidths=[ANCHO_MARCA, ANCHO_FISCAL],
    )
    tabla_encabezado.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, NEGRO),
        ("LINEAFTER", (0, 0), (0, 0), 0.8, NEGRO),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ]))
    elementos.append(tabla_encabezado)
    elementos.append(Spacer(1, 0.25 * cm))

    # ------------------------------------------------------------------
    # DATOS DEL CLIENTE
    # ------------------------------------------------------------------
    fecha_emision = orden.fecha_creacion.strftime("%d/%m/%Y")
    hora_emision = orden.fecha_creacion.strftime("%H:%M:%S")
    nombre_cliente = orden.usuario.get_full_name() or orden.usuario.username
    correo_cliente = str(orden.usuario.email or "-")

    filas_grilla = [
        [pb("Fecha y hora de emisión:"), p(f"{fecha_emision} {hora_emision}"), pb("Moneda:"), p("GUARANÍ")],
        [pb("N° de Orden / Ref:"), p(orden.numero_orden_display), pb("Condición Venta:"), p("Contado  ( X )   Crédito  (   )")],
        [pb("Nombre o Razón Social:"), p(nombre_cliente), pb("Teléfono:"), p("-")],
        [pb("Correo Electrónico:"), p(correo_cliente), pb("RUC / C.I. N°:"), p("-")],
    ]

    tabla_grilla = Table(
        filas_grilla,
        colWidths=[3.6 * cm, ANCHO_PAGINA - 3.6 * cm - 3.2 * cm - 5.3 * cm, 3.2 * cm, 5.3 * cm],
    )
    tabla_grilla.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, NEGRO),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, NEGRO),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ]))
    elementos.append(tabla_grilla)
    elementos.append(Spacer(1, 0.3 * cm))

    # ------------------------------------------------------------------
    # ESTRUCTURA DE ÍTEMS Y TOTALES UNIFICADA (UN SOLO CUADRO CONTINUO)
    # ------------------------------------------------------------------
    COL_COD = 1.4 * cm
    COL_DESC = 6.4 * cm
    COL_UNI = 1.1 * cm
    COL_CANT = 1.1 * cm
    COL_PRECIO = 2.3 * cm
    COL_DESC_MONTO = 2.0 * cm
    COL_IVA = (ANCHO_PAGINA - COL_COD - COL_DESC - COL_UNI - COL_CANT - COL_PRECIO - COL_DESC_MONTO) / 3

    ANCHOS_ITEMS = [COL_COD, COL_DESC, COL_UNI, COL_CANT, COL_PRECIO, COL_DESC_MONTO, COL_IVA, COL_IVA, COL_IVA]

    filas_items = [
        [pc(""), pc(""), pc(""), pc(""), pc(""), pc(""), pbc("Valor de Venta"), pbc(""), pbc("")],
        [pbc("Cód."), pbc("Descripción"), pbc("Unid."), pbc("Cant."), pbc("Precio Unit."), pbc("Descuento"), pbc("Exentas"), pbc("5%"), pbc("10%")]
    ]

    total_exentas = Decimal("0")
    total_cinco = Decimal("0")
    total_diez = Decimal("0")
    iva_cinco = Decimal("0")
    iva_diez = Decimal("0")

    items_orden = list(orden.items.all())

    # Prorratea el descuento total proporcionalmente al subtotal de
    # cada item, no en partes iguales. Dividir 100.000 Gs en 3 items
    # iguales daria 33.333 x 3 = 99.999 (no cierra). El prorrateo
    # proporcional respeta el peso real de cada item en la compra,
    # y el ultimo item se ajusta para que la suma sea exacta.
    descuentos_por_item = []
    if orden.monto_descuento and orden.monto_descuento > 0:
        subtotal_general = sum(item.subtotal for item in items_orden)
        descuento_acumulado = Decimal("0")
        for i, item in enumerate(items_orden):
            if i == len(items_orden) - 1:
                # Ultimo item: se ajusta para que la suma cierre exacto
                descuento_item = orden.monto_descuento - descuento_acumulado
            else:
                proporcion = item.subtotal / subtotal_general
                descuento_item = (orden.monto_descuento * proporcion).quantize(Decimal("1"))
            descuentos_por_item.append(descuento_item)
            descuento_acumulado += descuento_item
    else:
        descuentos_por_item = [Decimal("0")] * len(items_orden)

    for idx, (item, descuento_item) in enumerate(zip(items_orden, descuentos_por_item), start=1):
        descripcion = f"{item.nombre_producto} - {item.nombre_variante}"
        desc_display = _gs(descuento_item)

        fila = [pc(idx), p(descripcion), pc("UNI"), pc(item.cantidad), pd(_gs(item.precio_unitario)), pd(desc_display)]
        if item.tasa_iva == "0":
            total_exentas += item.subtotal
            fila += [pd(_gs(item.subtotal)), pd(""), pd("")]
        elif item.tasa_iva == "5":
            total_cinco += item.subtotal
            iva_cinco += item.monto_iva
            fila += [pd(""), pd(_gs(item.subtotal)), pd("")]
        else:
            total_diez += item.subtotal
            iva_diez += item.monto_iva
            fila += [pd(""), pd(""), pd(_gs(item.subtotal))]
        filas_items.append(fila)

    # Relleno de filas visibles vacías (espacio "aireado" como UniNorte)
    fila_inicio_blancos = len(filas_items)
    MINIMO_FILAS_VISIBLES = 6
    while len(filas_items) - 2 < MINIMO_FILAS_VISIBLES:
        filas_items.append([p(""), p(""), p(""), p(""), p(""), p(""), p(""), p(""), p("")])

    fila_fin_items_idx = len(filas_items) - 1

    # Cálculo final
    valor_venta_total = total_exentas + total_cinco + total_diez
    iva_total = iva_cinco + iva_diez

    # Fila Subtotal
    filas_items.append([
        pb("SUBTOTAL:"), pb(""), pb(""), pb(""), pb(""), pb(""),
        pbd(_gs(total_exentas)), pbd(_gs(total_cinco)), pbd(_gs(total_diez)),
    ])
    fila_subtotal_idx = len(filas_items) - 1

    # Fila Total de la Operación
    monto_operacion_en_letras = numero_a_letras(valor_venta_total)
    filas_items.append([
        pb(f"TOTAL DE LA OPERACIÓN: GUARANÍES {monto_operacion_en_letras} ==="),
        pb(""), pb(""), pb(""), pb(""), pb(""), pb(""), pb(""), pbd(_gs(valor_venta_total)),
    ])
    fila_total_op_idx = len(filas_items) - 1

    indices_spans_totales = []

    cupon_texto = f" ({orden.codigo_cupon})" if (orden.monto_descuento and orden.codigo_cupon) else ""
    if orden.monto_descuento and orden.monto_descuento > 0:
        filas_items.append([
            pb(f"DESCUENTO COMPUESTO{cupon_texto}:"), pb(""), pb(""), pb(""), pb(""), pb(""), pb(""), pb(""),
            pbd(f"- {_gs(orden.monto_descuento)}"),
        ])
        indices_spans_totales.append(len(filas_items) - 1)

    if orden.costo_envio and orden.costo_envio > 0:
        filas_items.append([
            pb("COSTO DE SERVICIO / ENVÍO:"), pb(""), pb(""), pb(""), pb(""), pb(""), pb(""), pb(""), pbd(_gs(orden.costo_envio)),
        ])
        indices_spans_totales.append(len(filas_items) - 1)

    # Fila Total a Pagar
    # Fila Total a Pagar — incluye el monto en letras del TOTAL
    # FINAL (orden.total), que es el numero que realmente se muestra
    # a la derecha de esta fila.
    monto_pagar_en_letras = numero_a_letras(orden.total)
    filas_items.append([
        pb(f"TOTAL A PAGAR EN GUARANÍES: {monto_pagar_en_letras} ==="),
        pb(""), pb(""), pb(""), pb(""), pb(""), pb(""), pb(""), pbd(_gs(orden.total)),
    ])
    fila_total_pagar_idx = len(filas_items) - 1
    indices_spans_totales.append(fila_total_pagar_idx)

    # Fila Liquidación IVA
    filas_items.append([
        pb("LIQUIDACIÓN DEL IVA:"), pb(""), pb(""),
        pc("5%:"), pd(_gs(iva_cinco)),
        pc("10%:"), pd(_gs(iva_diez)),
        pb("TOTAL IVA:"), pbd(_gs(iva_total)),
    ])
    fila_iva_idx = len(filas_items) - 1

    # Construcción de la tabla completa
    tabla_items = Table(filas_items, colWidths=ANCHOS_ITEMS, repeatRows=2)

    estilo_tabla = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),

        # Aire visual en las filas vacías, como en UniNorte
        ("TOPPADDING", (0, fila_inicio_blancos), (-1, fila_fin_items_idx), 14),
        ("BOTTOMPADDING", (0, fila_inicio_blancos), (-1, fila_fin_items_idx), 14),

        # 1. El cuadro exterior unificado de principio a fin sin cortes
        ("BOX", (0, 0), (-1, -1), 0.8, NEGRO),

        # 2. Cabecera agrupada "Valor de Venta"
        ("SPAN", (6, 0), (8, 0)),
        ("LINEBELOW", (0, 0), (-1, 1), 0.8, NEGRO),

        # 3. Líneas divisorias verticales para el cuerpo de ítems y las columnas
        ("LINEAFTER", (0, 1), (-2, fila_fin_items_idx), 0.5, NEGRO),
        ("LINEBELOW", (0, 1), (-1, fila_inicio_blancos - 1), 0.5, NEGRO),

        # 4. Línea firme horizontal que divide el fin de los ítems del inicio de los totales
        ("LINEBELOW", (0, fila_fin_items_idx), (-1, fila_fin_items_idx), 0.8, NEGRO),

        # 5. SPANs horizontales de totales fiscales
        ("SPAN", (0, fila_subtotal_idx), (5, fila_subtotal_idx)),
        ("LINEBELOW", (0, fila_subtotal_idx), (-1, fila_subtotal_idx), 0.5, NEGRO),

        ("SPAN", (0, fila_total_op_idx), (7, fila_total_op_idx)),
        ("LINEBELOW", (0, fila_total_op_idx), (-1, fila_total_op_idx), 0.5, NEGRO),
    ]

    for idx in indices_spans_totales:
        estilo_tabla.append(("SPAN", (0, idx), (7, idx)))
        estilo_tabla.append(("LINEBELOW", (0, idx), (-1, idx), 0.5, NEGRO))

    estilo_tabla.extend([
        ("SPAN", (0, fila_iva_idx), (2, fila_iva_idx)),
        ("LINEAFTER", (2, fila_iva_idx), (2, fila_iva_idx), 0.5, NEGRO),
        ("LINEAFTER", (4, fila_iva_idx), (4, fila_iva_idx), 0.5, NEGRO),
        ("LINEAFTER", (6, fila_iva_idx), (6, fila_iva_idx), 0.5, NEGRO),
        ("LINEAFTER", (7, fila_iva_idx), (7, fila_iva_idx), 0.5, NEGRO),
    ])

    tabla_items.setStyle(TableStyle(estilo_tabla))
    elementos.append(tabla_items)
    elementos.append(Spacer(1, 0.3 * cm))

    # ------------------------------------------------------------------
    # BLOQUE FINAL DE CONTROL Y VALIDACIÓN SIFEN
    # ------------------------------------------------------------------
    buffer_qr = _generar_imagen_qr(orden)
    imagen_qr = Image(buffer_qr, width=2.1 * cm, height=2.1 * cm)

    texto_qr = Paragraph(
        "Consulte la validez de esta Factura Electrónica con el código QR implantado a la izquierda, "
        "o ingresando el identificador único o CDC de la orden dentro del portal SIFEN de la SET.<br/>"
        "<b>ESTE DOCUMENTO ES UNA REPRESENTACIÓN GRÁFICA DE UN DOCUMENTO ELECTRÓNICO (XML)</b>",
        ESTILO_PIE,
    )

    filas_bloque_final = [[imagen_qr, texto_qr]]
    if orden.notas:
        filas_bloque_final.append([
            "",
            Paragraph(f"<b>Información de interés del emisor:</b> {orden.notas}", ESTILO_NOTAS),
        ])
    filas_bloque_final.append([
        "",
        Paragraph(
            "Si su documento presenta algún error u omisión comercial, podrá solicitar la modificación o "
            "anulación correspondiente dentro de los plazos estipulados por la normativa tributaria vigente. "
            "Original: Cliente - Duplicado: Archivo Tributario Contable.",
            ESTILO_PIE,
        ),
    ])

    ANCHO_QR_COL = 2.5 * cm
    tabla_bloque_final = Table(
        filas_bloque_final,
        colWidths=[ANCHO_QR_COL, ANCHO_PAGINA - ANCHO_QR_COL],
    )

    estilo_bloque_final = [
        ("BOX", (0, 0), (-1, -1), 0.8, NEGRO),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("SPAN", (0, 0), (0, len(filas_bloque_final) - 1)),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]
    tabla_bloque_final.setStyle(TableStyle(estilo_bloque_final))
    elementos.append(tabla_bloque_final)

    documento.build(elementos)
    buffer.seek(0)
    return buffer
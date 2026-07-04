"""Report export helpers for ECOMAJES ERP.

Turns a report payload (produced by the Reportes view) into downloadable Excel
and PDF documents. Read-only: it only formats data that was already gathered
from existing sources — it never queries the database or mutates state.

A report payload is a dict::

    {
        "meta": {"ubicacion", "periodo", "date_from", "date_to",
                 "categoria", "generated_at"},
        "kpis": [{"Métrica": str, "Valor": str}, ...],
        "tables": {"<sheet/section name>": [ {col: value, ...}, ... ], ...},
    }
"""

import io

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _meta_rows(meta: dict) -> list[dict]:
    return [
        {"Campo": "Ubicación", "Valor": meta.get("ubicacion", "")},
        {"Campo": "Período", "Valor": meta.get("periodo", "")},
        {"Campo": "Desde", "Valor": str(meta.get("date_from", ""))},
        {"Campo": "Hasta", "Valor": str(meta.get("date_to", ""))},
        {"Campo": "Categoría", "Valor": meta.get("categoria", "")},
        {"Campo": "Generado", "Valor": meta.get("generated_at", "")},
    ]


def _sheet_name(name: str) -> str:
    # Excel sheet names max 31 chars and forbid some characters.
    clean = name
    for ch in "[]:*?/\\":
        clean = clean.replace(ch, " ")
    return clean.strip()[:31] or "Hoja"


def build_excel(report: dict) -> bytes:
    """Render the report as a multi-sheet .xlsx workbook (bytes)."""
    meta = report.get("meta", {})
    buf = io.BytesIO()
    used: set[str] = set()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        # Cover sheet: metadata + KPIs.
        pd.DataFrame(_meta_rows(meta)).to_excel(
            writer, sheet_name="Reporte", index=False, startrow=0
        )
        kpis = report.get("kpis", [])
        kpi_df = pd.DataFrame(kpis) if kpis else pd.DataFrame([{"Info": "Sin datos"}])
        kpi_df.to_excel(
            writer, sheet_name="Reporte", index=False, startrow=len(_meta_rows(meta)) + 2
        )
        used.add("Reporte")

        for name, rows in report.get("tables", {}).items():
            sheet = _sheet_name(name)
            base, i = sheet, 1
            while sheet in used:
                i += 1
                sheet = f"{base[:28]}_{i}"
            used.add(sheet)
            df = pd.DataFrame(rows) if rows else pd.DataFrame([{"Info": "Sin datos"}])
            df.to_excel(writer, sheet_name=sheet, index=False)
    return buf.getvalue()


def _cell(value) -> str:
    if isinstance(value, float):
        return f"{value:,.2f}"
    return "" if value is None else str(value)


def _pdf_table(rows: list[dict]) -> Table:
    headers = list(rows[0].keys())
    data = [headers] + [[_cell(r.get(h)) for h in headers] for r in rows]
    table = Table(data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2b2f3a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c9ccd4")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f3f6")]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def build_pdf(report: dict) -> bytes:
    """Render the report as a landscape A4 PDF document (bytes)."""
    meta = report.get("meta", {})
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=1.2 * cm,
        rightMargin=1.2 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
        title="Reporte ECOMAJES",
    )
    styles = getSampleStyleSheet()
    story: list = []

    story.append(Paragraph("ECOMAJES — Reporte", styles["Title"]))
    story.append(
        Paragraph(
            f"{meta.get('ubicacion', '')} · {meta.get('periodo', '')} · "
            f"{meta.get('date_from', '')} → {meta.get('date_to', '')} · "
            f"Categoría: {meta.get('categoria', '')}",
            styles["Normal"],
        )
    )
    story.append(Paragraph(f"Generado: {meta.get('generated_at', '')}", styles["Normal"]))
    story.append(Spacer(1, 0.5 * cm))

    kpis = report.get("kpis", [])
    if kpis:
        story.append(Paragraph("Resumen", styles["Heading2"]))
        story.append(_pdf_table(kpis))
        story.append(Spacer(1, 0.5 * cm))

    for name, rows in report.get("tables", {}).items():
        story.append(Paragraph(name, styles["Heading2"]))
        if rows:
            story.append(_pdf_table(rows))
        else:
            story.append(Paragraph("Sin datos.", styles["Normal"]))
        story.append(Spacer(1, 0.5 * cm))

    doc.build(story)
    return buf.getvalue()

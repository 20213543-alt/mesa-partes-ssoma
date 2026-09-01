import base64
from datetime import datetime
import io
from io import BytesIO
from itertools import zip_longest
import os
import socket
import traceback
from typing import List
import zoneinfo

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps
import requests
from xhtml2pdf import pisa

# Forzar resolución de DNS a IPv4 para evitar el error [Errno 101] en Render
old_getaddrinfo = socket.getaddrinfo


def new_getaddrinfo(*args, **kwargs):
    responses = old_getaddrinfo(*args, **kwargs)
    return [res for res in responses if res[0] == socket.AF_INET]


socket.getaddrinfo = new_getaddrinfo

app = FastAPI()

# Configuración de carpeta y ruta estática para archivos JS/CSS
os.makedirs("static", exist_ok=True)

# Autogenerar el script frontend para controlar el bloqueo dinámico de incidentes
SCRIPT_JS_PATH = os.path.join("static", "script.js")
JS_CONTENT = """document.addEventListener("DOMContentLoaded", () => {
    const selectTipo = document.querySelector('[name="fin_tipo_evento"]') || document.getElementById('fin_tipo_evento');
    const selectClasificacion = document.querySelector('[name="fin_clasificacion"]') || document.getElementById('fin_clasificacion');

    const camposAccidente = [
        'acc_gravedad',
        'acc_grado_incapacitante',
        'acc_dias_descanso',
        'acc_dias_cargados',
        'acc_num_afectados'
    ];

    function evaluarBloqueoAccidente() {
        const valTipo = selectTipo ? selectTipo.value.toLowerCase() : '';
        const valClasif = selectClasificacion ? selectClasificacion.value.toLowerCase() : '';

        const esIncidente = valTipo.includes('incidente') || valClasif.includes('incidente');

        camposAccidente.forEach(nombre => {
            const elementos = document.querySelectorAll(`[name="${nombre}"]`);
            elementos.forEach(el => {
                el.disabled = esIncidente;
                if (esIncidente) {
                    el.value = '';
                    el.removeAttribute('required');
                }
            });
        });

        const contenedor = document.getElementById('seccion_accidente');
        if (contenedor) {
            contenedor.style.opacity = esIncidente ? '0.4' : '1';
            contenedor.style.pointerEvents = esIncidente ? 'none' : 'auto';
        }
    }

    if (selectTipo) selectTipo.addEventListener('change', evaluarBloqueoAccidente);
    if (selectClasificacion) selectClasificacion.addEventListener('change', evaluarBloqueoAccidente);

    evaluarBloqueoAccidente();
});
"""

with open(SCRIPT_JS_PATH, "w", encoding="utf-8") as js_file:
    js_file.write(JS_CONTENT)

app.mount("/static", StaticFiles(directory="static"), name="static")

GOOGLE_WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbxaliz82ArStXwK5OH2lAn_wK0rp23CIvWy4cglATNt5AhV90VeucsJ7GrB1sFHYANhRw/exec"

CORREOS_PREDETERMINADOS = ["20213543@aloe.ulima.edu.pe"]

PDF_DIR = "pdf_reports"
os.makedirs(PDF_DIR, exist_ok=True)


def optimizar_imagen_base64(bytes_imagen, target_size=(600, 360)):
    try:
        img = Image.open(io.BytesIO(bytes_imagen))
        img = img.convert("RGB")
        img = ImageOps.fit(img, target_size, Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=80)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception as e:
        print(f"Error optimizando la fotografía: {e}")
        return None


def enviar_correo_con_pdf(
    destinatarios: list, asunto: str, cuerpo: str, pdf_path: str = None
) -> bool:
    """Envía el correo por la API HTTP de Resend, incluyendo el PDF en base64."""
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    remitente = os.getenv(
        "RESEND_FROM",
        "Sistema SSOMA <onboarding@resend.dev>",
    ).strip()

    if not api_key:
        print("RESEND_API_KEY no está configurada; se omite el correo.")
        return False

    payload = {
        "from": remitente,
        "to": destinatarios,
        "subject": asunto,
        "html": "<p>" + cuerpo.replace("\n", "<br>") + "</p>",
    }

    if pdf_path and os.path.isfile(pdf_path):
        with open(pdf_path, "rb") as archivo_pdf:
            pdf_b64 = base64.b64encode(archivo_pdf.read()).decode("ascii")
        payload["attachments"] = [{
            "filename": os.path.basename(pdf_path),
            "content": pdf_b64,
        }]

    try:
        respuesta = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        respuesta.raise_for_status()
        datos = respuesta.json()
        print(f"Correo enviado mediante Resend. ID: {datos.get('id', '-')}")
        return True
    except requests.RequestException as error:
        detalle = getattr(error.response, "text", "") if error.response else str(error)
        print(f"Error al enviar correo mediante Resend: {detalle}")
        return False


def g(form_dict, key_or_keys, default="-"):
    """
    Busca de manera flexible claves simples o listas de alias dentro de form_dict.
    Acepta un string o una lista/tupla de nombres de campos posibles.
    """
    if isinstance(key_or_keys, (list, tuple)):
        keys = key_or_keys
    else:
        keys = [key_or_keys]

    for k in keys:
        val = form_dict.get(k)
        if val is not None:
            if isinstance(val, list):
                val = val[0] if len(val) > 0 else None
            if val is not None and str(val).strip() != "" and str(val).strip().lower() != "none":
                return str(val).strip()
    return default


def html_to_pdf_file(html_string: str, pdf_path: str):
    with open(pdf_path, "wb") as pdf_file:
        pisa_status = pisa.CreatePDF(
            BytesIO(html_string.encode("utf-8")), dest=pdf_file
        )
    return not pisa_status.err


def generar_pdf_preliminar(
    f: dict,
    codigo: str,
    fecha_registro: str,
    pdf_path: str,
    fotos_base64: list = None,
):
    if fotos_base64 and len(fotos_base64) > 0:
        celdas = []
        for b64 in fotos_base64:
            celdas.append(
                f'<td style="text-align: center; padding: 4px; width: 50%; vertical-align: middle;">'
                f'<img src="data:image/jpeg;base64,{b64}" style="width: 100%; border: 1px solid #cbd5e0; border-radius: 3px;" />'
                f"</td>"
            )

        filas_html = ""
        for i in range(0, len(celdas), 2):
            filas_html += f"<tr>{''.join(celdas[i:i+2])}</tr>"

        img_html = f'<table style="width: 100%; border-collapse: collapse; margin: 0 auto;">{filas_html}</table>'
    else:
        img_html = '<p style="color: #718096; font-size: 8pt; padding: 15px; text-align: center;">Sin fotografía adjunta</p>'

    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <style>
            @page {{ size: a4 portrait; margin: 10mm; }}
            body {{ font-family: Helvetica, Arial, sans-serif; font-size: 8.5pt; color: #111; }}
            .header-table {{ width: 100%; border-collapse: collapse; margin-bottom: 10px; background-color: #1a365d; }}
            .header-table td {{ padding: 8px; border: none; vertical-align: middle; }}
            .title {{ font-size: 11pt; font-weight: bold; color: #ffffff; }}
            .subtitle {{ font-size: 8pt; color: #ffffff; margin-top: 3px; }}
            .badge-box {{ background-color: #d69e2e; color: #1a365d; padding: 4px 8px; font-weight: bold; font-size: 9pt; text-align: center; border-radius: 3px; }}
            .sec-header {{ background-color: #1a365d; color: #ffffff; font-weight: bold; font-size: 8.5pt; padding: 4px; margin-top: 8px; margin-bottom: 4px; }}
            .grid-table {{ width: 100%; border-collapse: collapse; margin-bottom: 6px; }}
            .grid-table td {{ border: 1px solid #cbd5e0; padding: 4px; font-size: 8pt; vertical-align: middle; }}
            .lbl {{ font-weight: bold; color: #2d3748; background-color: #f7fafc; width: 22%; }}
            .val {{ color: #1a202c; width: 28%; }}
            .text-box {{ border: 1px solid #cbd5e0; background-color: #f7fafc; padding: 6px; font-size: 8pt; line-height: 1.2; margin-bottom: 6px; }}
            .photo-box {{ text-align: center; padding: 6px; border: 1px solid #cbd5e0; background-color: #f7fafc; margin-bottom: 6px; }}
            .footer {{ margin-top: 15px; font-size: 7.5pt; color: #718096; text-align: center; border-top: 1px solid #e2e8f0; padding-top: 4px; }}
        </style>
    </head>
    <body>
        <table class="header-table">
            <tr>
                <td style="width: 70%;">
                    <div class="title">EMPRESA MUNICIPAL DE APOYO A PROYECTOS ESTRATÉGICOS S.A.</div>
                    <div class="subtitle">INFORME PRELIMINAR DE INCIDENTE / ACCIDENTE</div>
                </td>
                <td style="width: 30%; text-align: right;">
                    <span class="badge-box">{codigo}</span>
                </td>
            </tr>
        </table>

        <table class="grid-table">
            <tr>
                <td class="lbl">Razón Social:</td>
                <td class="val" colspan="2">{g(f, ['pre_razon_social', 'razon_social'], 'EMPRESA MUNICIPAL DE APOYO A PROYECTOS ESTRATÉGICOS S.A.')}</td>
                <td class="lbl">RUC:</td>
                <td class="val">{g(f, ['pre_ruc', 'ruc'], '20100063337')}</td>
            </tr>
            <tr>
                <td class="lbl">Tipo de Evento:</td>
                <td class="val" colspan="4">{g(f, ['pre_tipo_evento', 'tipo_evento_pre', 'tipo_evento'])}</td>
            </tr>
        </table>

        <div class="sec-header">ANTECEDENTES</div>
        <table class="grid-table">
            <tr>
                <td class="lbl">Fecha de Evento:</td>
                <td class="val">{g(f, ['pre_fecha_evento', 'fecha_evento_pre', 'fecha_evento'])}</td>
                <td class="lbl">Hora de Ocurrencia:</td>
                <td class="val">{g(f, ['pre_hora_evento', 'hora_ocurrencia_pre', 'hora_evento'])}</td>
            </tr>
            <tr>
                <td class="lbl">Lugar de Ocurrencia:</td>
                <td class="val">{g(f, ['pre_lugar_evento', 'lugar_ocurrencia_pre', 'lugar_evento'])}</td>
                <td class="lbl">Fecha de Reporte:</td>
                <td class="val">{g(f, ['pre_fecha_reporte', 'fecha_reporte_pre', 'fecha_reporte'])}</td>
            </tr>
        </table>
        <div class="text-box">
            <b>Trabajo que se Realizaba:</b><br/>
            {g(f, ['pre_trabajo_realizaba', 'trabajo_realizaba_pre', 'trabajo_realizaba'])}
        </div>

        <div class="sec-header">DESCRIPCIÓN DE LOS LESIONADOS</div>
        <table class="grid-table">
            <tr>
                <td class="lbl">Nombre Completo:</td>
                <td class="val">{g(f, ['pre_nombre_lesionado', 'nombre_lesionado_pre', 'nombre_lesionado'])}</td>
                <td class="lbl">Edad:</td>
                <td class="val">{g(f, ['pre_edad_lesionado', 'edad_lesionado_pre', 'edad'])}</td>
            </tr>
            <tr>
                <td class="lbl">Cargo:</td>
                <td class="val" colspan="3">{g(f, ['pre_cargo_lesionado', 'cargo_lesionado_pre', 'cargo'])}</td>
            </tr>
        </table>
        <div class="text-box">
            <b>Breve Descripción del Suceso:</b><br/>
            {g(f, ['pre_breve_descripcion', 'breve_descripcion_pre', 'descripcion'])}
        </div>

        <div class="sec-header">REGISTRO FOTOGRÁFICO</div>
        <div class="photo-box">
            {img_html}
        </div>

        <div class="sec-header">RESPONSABLE DEL REPORTE</div>
        <table class="grid-table">
            <tr>
                <td class="lbl">Nombre y Apellido:</td>
                <td class="val">{g(f, ['pre_resp_nombre', 'resp_nombre_pre', 'inv_nombre'])}</td>
                <td class="lbl">Cargo:</td>
                <td class="val">{g(f, ['pre_resp_cargo', 'resp_cargo_pre', 'inv_cargo'])}</td>
            </tr>
            <tr>
                <td class="lbl">Fecha:</td>
                <td class="val" colspan="3">{g(f, ['pre_resp_fecha', 'resp_fecha_pre', 'fecha_reporte'])}</td>
            </tr>
            <tr>
                <td class="lbl">Firma:</td>
                <td class="val" colspan="3"><b>[FIRMA REGISTRADA]</b></td>
            </tr>
        </table>

        <div class="footer">
            Documento Digital Generado por el Sistema SSOMA - EMAPE S.A. | Fecha Registro System: {fecha_registro}
        </div>
    </body>
    </html>
    """
    html_to_pdf_file(html_content, pdf_path)


def generar_pdf_100_porciento(
    f: dict, codigo: str, tipo_informe: str, fecha_registro: str, pdf_path: str
):
    filas_trabajadores = ""
    for trab in f.get("lista_trabajadores", []):
        filas_trabajadores += f"""
        <tr>
            <td style="width: 9%;">{trab.get('paterno','-')}</td>
            <td style="width: 9%;">{trab.get('materno','-')}</td>
            <td style="width: 11%;">{trab.get('nombres','-')}</td>
            <td style="width: 11%;">{trab.get('ocupacion','-')}</td>
            <td style="width: 13%;">{trab.get('area_interna','-')}</td>
            <td style="width: 9%;">{trab.get('condicion','-')}</td>
            <td style="width: 5%;">{trab.get('sexo','-')}</td>
            <td style="width: 8%;">{trab.get('dni','-')}</td>
            <td style="width: 5%;">{trab.get('edad','-')}</td>
            <td style="width: 6%;">{trab.get('turno','-')}</td>
            <td style="width: 14%;">{trab.get('personal','-')}</td>
        </tr>
        """
    if not filas_trabajadores:
        filas_trabajadores = (
            "<tr><td colspan='11'>No se registraron trabajadores</td></tr>"
        )

    filas_causas_inmediatas = ""
    for ci in f.get("causas_inmediatas_list", []):
        filas_causas_inmediatas += f"""
        <tr>
            <td style="text-align:center; width: 6%;">{ci.get('fila','-')}</td>
            <td style="width: 24%;">{ci.get('tipo','-')}</td>
            <td style="width: 35%;">{ci.get('causa','-')}</td>
            <td style="width: 35%;">{ci.get('obs','-')}</td>
        </tr>
        """
    if not filas_causas_inmediatas:
        filas_causas_inmediatas = "<tr><td colspan='4'>Sin registros</td></tr>"

    filas_causas_basicas = ""
    for cb in f.get("causas_basicas_list", []):
        filas_causas_basicas += f"""
        <tr>
            <td style="text-align:center; width: 6%;">{cb.get('fila','-')}</td>
            <td style="width: 20%;">{cb.get('tipo','-')}</td>
            <td style="width: 24%;">{cb.get('causa','-')}</td>
            <td style="width: 25%;">{cb.get('subyacente','-')}</td>
            <td style="width: 25%;">{cb.get('obs','-')}</td>
        </tr>
        """
    if not filas_causas_basicas:
        filas_causas_basicas = "<tr><td colspan='5'>Sin registros</td></tr>"

    filas_medidas = ""
    for mc in f.get("medidas_correctivas_list", []):
        filas_medidas += f"""
        <tr>
            <td style="text-align:center; width: 6%;">{mc.get('fila','-')}</td>
            <td style="width: 16%;">{mc.get('tipo','-')}</td>
            <td style="width: 28%;">{mc.get('accion','-')}</td>
            <td style="width: 16%;">{mc.get('responsable','-')}</td>
            <td style="width: 10%;">{mc.get('fecha','-')}</td>
            <td style="width: 10%;">{mc.get('situacion','-')}</td>
            <td style="width: 14%;">{mc.get('obs','-')}</td>
        </tr>
        """
    if not filas_medidas:
        filas_medidas = "<tr><td colspan='7'>Sin registros</td></tr>"

    inv_nombre_val = g(f, ["inv_nombre", "resp_nombre"])
    firma_inv_default = f"<b>[REGISTRADO POR: {inv_nombre_val}]</b>"
    firma_inv_text = g(f, ["firma_inv_text", "inv_firma"], firma_inv_default)

    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <style>
            @page {{ size: a4 portrait; margin: 8mm; }}
            body {{ font-family: Helvetica, Arial, sans-serif; font-size: 7.5pt; color: #111; }}
            .header-table {{ width: 100%; border-collapse: collapse; margin-bottom: 8px; background-color: #1a365d; }}
            .header-table td {{ padding: 6px; border: none; vertical-align: middle; }}
            .title {{ font-size: 11pt; font-weight: bold; color: #ffffff; }}
            .subtitle {{ font-size: 7.5pt; color: #ffffff; margin-top: 2px; }}
            .badge-box {{ background-color: #d69e2e; color: #1a365d; padding: 3px 6px; font-weight: bold; font-size: 8.5pt; text-align: center; border-radius: 3px; }}
            .sec-header {{ background-color: #1a365d; color: #ffffff; font-weight: bold; font-size: 8pt; padding: 4px; margin-top: 6px; margin-bottom: 3px; }}
            .sec-red {{ background-color: #742a2a; color: #ffffff; }}
            .sec-green {{ background-color: #1a365d; color: #ffffff; border-bottom: 2px solid #d69e2e; }}
            .grid-table {{ width: 100%; border-collapse: collapse; margin-bottom: 5px; table-layout: fixed; }}
            .grid-table td, .grid-table th {{ border: 1px solid #cbd5e0; padding: 3px; font-size: 6.5pt; vertical-align: middle; word-wrap: break-word; }}
            .grid-table th {{ background-color: #edf2f7; color: #1a365d; text-align: left; font-weight: bold; }}
            .text-box {{ border: 1px solid #cbd5e0; background-color: #f7fafc; padding: 4px; font-size: 7pt; line-height: 1.1; margin-bottom: 5px; word-wrap: break-word; }}
            .footer {{ margin-top: 8px; font-size: 6.5pt; color: #718096; text-align: center; border-top: 1px solid #e2e8f0; padding-top: 3px; }}
            
            /* ESTILOS ESPECÍFICOS COSTOS */
            .cost-title {{ font-weight: bold; color: #1a365d; background-color: #edf2f7; font-size: 7pt; padding: 4px; }}
            .cost-val {{ font-weight: bold; color: #1a365d; background-color: #edf2f7; text-align: right; font-size: 7pt; padding: 4px; }}
            .cost-sub-item {{ padding-left: 15px; color: #4a5568; font-size: 6.5pt; }}
            .cost-sub-val {{ text-align: right; color: #2d3748; font-size: 6.5pt; padding-right: 4px; }}
            .cost-total-lbl {{ font-weight: bold; color: #ffffff; background-color: #1a365d; font-size: 7.5pt; padding: 5px; }}
            .cost-total-val {{ font-weight: bold; color: #d69e2e; background-color: #1a365d; text-align: right; font-size: 8pt; padding: 5px; }}
        </style>
    </head>
    <body>
        <table class="header-table">
            <tr>
                <td style="width: 70%;">
                    <div class="title">EMAPE S.A. - MESA DE PARTES SSOMA</div>
                    <div class="subtitle">CONSTANCIA Y REGISTRO OFICIAL - {tipo_informe.upper()}</div>
                </td>
                <td style="width: 30%; text-align: right;">
                    <span class="badge-box">{codigo}</span>
                </td>
            </tr>
        </table>

        <div class="sec-header">DATOS DEL EMPLEADOR PRINCIPAL</div>
        <table class="grid-table">
            <tr>
                <td style="width: 22%; font-weight: bold; background-color: #f7fafc;">Razón Social:</td>
                <td style="width: 28%;" colspan="3">{g(f, ['emp_razon_social', 'razon_social'], 'EMPRESA MUNICIPAL DE APOYO A PROYECTOS ESTRATÉGICOS S.A.')}</td>
                <td style="width: 22%; font-weight: bold; background-color: #f7fafc;">RUC:</td>
                <td style="width: 28%;">{g(f, ['emp_ruc', 'ruc'], '20100063337')}</td>
            </tr>
            <tr>
                <td style="font-weight: bold; background-color: #f7fafc;">Sede:</td>
                <td>{g(f, ['emp_sede', 'sede'])}</td>
                <td style="font-weight: bold; background-color: #f7fafc;">Dirección:</td>
                <td colspan="3">{g(f, ['emp_direccion', 'direccion'])}</td>
            </tr>
            <tr>
                <td style="font-weight: bold; background-color: #f7fafc;">N° Trab. Centro Laboral:</td>
                <td>{g(f, ['emp_num_trabajadores', 'emp_num_trab', 'num_trabajadores'])}</td>
                <td style="font-weight: bold; background-color: #f7fafc;">N° Afiliados SCTR:</td>
                <td>{g(f, ['emp_num_sctr', 'num_sctr'])}</td>
                <td style="font-weight: bold; background-color: #f7fafc;">Aseguradora SCTR:</td>
                <td>{g(f, ['emp_aseguradora', 'aseguradora'])}</td>
            </tr>
        </table>

        <div class="sec-header">DATOS DEL EMPLEADOR DE TERCERIZACIÓN, CONTRATISTA U OTROS</div>
        <table class="grid-table">
            <tr>
                <td style="width: 22%; font-weight: bold; background-color: #f7fafc;">Razón Social / Nombre:</td>
                <td style="width: 28%;" colspan="3">{g(f, 'ter_razon_social')}</td>
                <td style="width: 22%; font-weight: bold; background-color: #f7fafc;">RUC:</td>
                <td style="width: 28%;">{g(f, 'ter_ruc')}</td>
            </tr>
            <tr>
                <td style="font-weight: bold; background-color: #f7fafc;">Domicilio:</td>
                <td colspan="3">{g(f, 'ter_domicilio')}</td>
                <td style="font-weight: bold; background-color: #f7fafc;">Actividad Económica:</td>
                <td>{g(f, 'ter_actividad')}</td>
            </tr>
            <tr>
                <td style="font-weight: bold; background-color: #f7fafc;">N° Trab. Centro Laboral:</td>
                <td>{g(f, ['ter_num_trabajadores', 'ter_num_trab'])}</td>
                <td style="font-weight: bold; background-color: #f7fafc;">N° Afiliados SCTR:</td>
                <td>{g(f, 'ter_num_sctr')}</td>
                <td style="font-weight: bold; background-color: #f7fafc;">Aseguradora:</td>
                <td>{g(f, 'ter_aseguradora')}</td>
            </tr>
        </table>

        <div class="sec-header">1) OCURRENCIA DEL EVENTO Y 2) TIPO Y CLASIFICACIÓN</div>
        <table class="grid-table">
            <tr>
                <td style="width: 22%; font-weight: bold; background-color: #f7fafc;">Fecha Evento:</td>
                <td style="width: 28%;">{g(f, ['fin_fecha_evento', 'fecha_evento'])}</td>
                <td style="width: 22%; font-weight: bold; background-color: #f7fafc;">Hora Evento:</td>
                <td style="width: 28%;">{g(f, ['fin_hora_evento', 'hora_evento'])}</td>
                <td style="width: 22%; font-weight: bold; background-color: #f7fafc;">Lugar Exacto:</td>
                <td style="width: 28%;">{g(f, ['fin_lugar_exacto', 'lugar_exacto', 'lugar_evento'])}</td>
            </tr>
            <tr>
                <td style="font-weight: bold; background-color: #f7fafc;">Tipo de Evento:</td>
                <td>{g(f, ['fin_tipo_evento', 'tipo_evento'])}</td>
                <td style="font-weight: bold; background-color: #f7fafc;">Clasificación Evento:</td>
                <td>{g(f, ['fin_clasificacion', 'clasificacion'])}</td>
                <td style="font-weight: bold; background-color: #f7fafc;">Solo Incidente:</td>
                <td>{g(f, ['fin_incidente_peligro', 'fin_solo_incidente', 'solo_incidente'])}</td>
            </tr>
        </table>

        <div class="sec-header">DATOS DEL TRABAJADOR AFECTADO E INVOLUCRADO EN EL EVENTO</div>
        <table class="grid-table">
            <thead>
                <tr>
                    <th style="width: 9%;">A. Paterno</th>
                    <th style="width: 9%;">A. Materno</th>
                    <th style="width: 11%;">Nombres</th>
                    <th style="width: 11%;">Ocupación</th>
                    <th style="width: 13%;">Área Interna</th>
                    <th style="width: 9%;">Condición</th>
                    <th style="width: 5%;">Sexo</th>
                    <th style="width: 8%;">DNI</th>
                    <th style="width: 5%;">Edad</th>
                    <th style="width: 6%;">Turno</th>
                    <th style="width: 14%;">Personal</th>
                </tr>
            </thead>
            <tbody>
                {filas_trabajadores}
            </tbody>
        </table>

        <div class="sec-header sec-red">ACCIDENTE (EVALUACIÓN DE GRAVEDAD)</div>
        <table class="grid-table">
            <tr>
                <td style="width: 22%; font-weight: bold; background-color: #f7fafc;">Gravedad Accidente:</td>
                <td style="width: 28%;">{g(f, ['acc_gravedad', 'fin_gravedad_evento', 'gravedad'])}</td>
                <td style="width: 22%; font-weight: bold; background-color: #f7fafc;">Grado Incapacitante:</td>
                <td style="width: 28%;">{g(f, ['acc_grado_incapacitante', 'grado_incapacitante'])}</td>
                <td style="width: 22%; font-weight: bold; background-color: #f7fafc;">Días Descanso Médico:</td>
                <td style="width: 28%;">{g(f, ['acc_dias_descanso', 'dias_descanso'])}</td>
            </tr>
            <tr>
                <td style="font-weight: bold; background-color: #f7fafc;">Días Cargados:</td>
                <td>{g(f, ['acc_dias_cargados', 'dias_cargados'])}</td>
                <td style="font-weight: bold; background-color: #f7fafc;">N° Trab. Afectados:</td>
                <td colspan="3">{g(f, ['acc_num_afectados', 'num_afectados'])}</td>
            </tr>
        </table>

        <div class="sec-header">SOLO EN CASO DE INCIDENTE DE PRIMEROS AUXILIOS</div>
        <div class="text-box">
            <b>Tipo de Atención en Primeros Auxilios:</b> {g(f, ['inc_primeros_auxilios', 'pa_tipo_atencion', 'primeros_auxilios'])}
        </div>

        <div class="sec-header">DETALLE DE LESIONES Y LUGAR DE ATENCIÓN</div>
        <table class="grid-table">
            <tr>
                <td style="width: 22%; font-weight: bold; background-color: #f7fafc;">Forma Accidente/Incidente:</td>
                <td style="width: 28%;">{g(f, ['les_forma_evento', 'les_forma', 'forma_evento'])}</td>
                <td style="width: 22%; font-weight: bold; background-color: #f7fafc;">Tipo de Lesión:</td>
                <td style="width: 28%;" colspan="3">{g(f, ['les_tipo_lesion', 'les_tipo', 'tipo_lesion'])}</td>
            </tr>
            <tr>
                <td style="font-weight: bold; background-color: #f7fafc;">Agente Causante:</td>
                <td>{g(f, ['les_agente_causante', 'les_agente', 'agente_causante'])}</td>
                <td style="font-weight: bold; background-color: #f7fafc;">Parte Cuerpo Afectada:</td>
                <td colspan="3">{g(f, ['les_parte_cuerpo', 'parte_cuerpo'])}</td>
            </tr>
            <tr>
                <td style="font-weight: bold; background-color: #f7fafc;">Hospital / Clínica / Tópico:</td>
                <td colspan="5">{g(f, ['les_hospital_atencion', 'les_hospital', 'hospital_atencion'])}</td>
            </tr>
        </table>

        <div class="sec-header">DATOS DEL INCIDENTE CON DAÑO A LA PROPIEDAD / MEDIO AMBIENTE</div>
        <table class="grid-table">
            <tr>
                <td style="width: 22%; font-weight: bold; background-color: #f7fafc;">Daño Material:</td>
                <td style="width: 28%;">{g(f, ['dan_material', 'dano_material'])}</td>
                <td style="width: 22%; font-weight: bold; background-color: #f7fafc;">Agente Causante del Daño:</td>
                <td style="width: 28%;">{g(f, ['dan_agente_causante', 'dan_agente'])}</td>
            </tr>
        </table>
        <div class="text-box">
            <b>Descripción del Evento (Daños / M.A.):</b> {g(f, ['dan_descripcion_evento', 'dan_descripcion'])}
        </div>

        <!-- SECCIÓN DE VALORACIÓN DE COSTES COMPLETA -->
        <div class="sec-header sec-green">VALORACIÓN DE LOS COSTES DEL ACCIDENTE</div>
        <table class="grid-table">
            <thead>
                <tr style="background-color: #2b6cb0; color: #ffffff;">
                    <th style="width: 70%; font-weight: bold; font-size: 7pt; color: #ffffff; background-color: #2b6cb0;">Concepto / Categoría de Coste</th>
                    <th style="width: 30%; font-weight: bold; font-size: 7pt; color: #ffffff; background-color: #2b6cb0; text-align: right;">Monto Estimado (S/.)</th>
                </tr>
            </thead>
            <tbody>
                <!-- CATEGORÍA 1 -->
                <tr>
                    <td class="cost-title">1. COSTO DEL PERSONAL TOTAL</td>
                    <td class="cost-val">S/ {g(f, 'coste_total_personal', '0.00')}</td>
                </tr>

                <!-- CATEGORÍA 2 -->
                <tr>
                    <td class="cost-title">2. COSTO DE DAÑOS MATERIALES TOTAL</td>
                    <td class="cost-val">S/ {g(f, 'coste_total_danos_materiales', '0.00')}</td>
                </tr>
                <tr>
                    <td class="cost-sub-item">&bull; Edificios e Instalaciones</td>
                    <td class="cost-sub-val">S/ {g(f, ['costo_edificios', 'costo_edificio', 'cos_edificios'], '0.00')}</td>
                </tr>
                <tr>
                    <td class="cost-sub-item">&bull; Máquinas, Equipos y Herramientas</td>
                    <td class="cost-sub-val">S/ {g(f, ['costo_maquinaria', 'costo_maquinas', 'costo_equipos', 'cos_maquinaria'], '0.00')}</td>
                </tr>
                <tr>
                    <td class="cost-sub-item">&bull; Materias Primas / Productos</td>
                    <td class="cost-sub-val">S/ {g(f, ['costo_mat_primas', 'costo_materias_primas', 'costo_mat_prima', 'cos_mat_primas'], '0.00')}</td>
                </tr>
                <tr>
                    <td class="cost-sub-item">&bull; Tiempo Perdido Parada Máquina</td>
                    <td class="cost-sub-val">S/ {g(f, ['costo_parada', 'costo_parada_maquina', 'costo_tiempo_perdido', 'cos_parada'], '0.00')}</td>
                </tr>

                <!-- CATEGORÍA 3 -->
                <tr>
                    <td class="cost-title">3. SUB-TOTAL OTROS COSTES</td>
                    <td class="cost-val">S/ {g(f, 'coste_subtotal_otros', '0.00')}</td>
                </tr>
                <tr>
                    <td class="cost-sub-item">&bull; Primeros Auxilios / Médicos</td>
                    <td class="cost-sub-val">S/ {g(f, ['costo_primeros_auxilios', 'costo_auxilios', 'costo_medicos', 'cos_primeros_auxilios'], '0.00')}</td>
                </tr>
                <tr>
                    <td class="cost-sub-item">&bull; Sanciones Administrativas / Gastos Legales</td>
                    <td class="cost-sub-val">S/ {g(f, ['costo_sanciones', 'costo_multas', 'cos_sanciones'], '0.00')} / S/ {g(f, ['costo_legales', 'costo_gastos_legales', 'cos_legales'], '0.00')}</td>
                </tr>
                <tr>
                    <td class="cost-sub-item">&bull; Responsabilidad Civil / Medio Ambiente</td>
                    <td class="cost-sub-val">S/ {g(f, ['costo_resp_civil', 'costo_responsabilidad_civil', 'cos_resp_civil'], '0.00')} / S/ {g(f, ['costo_medio_ambiente', 'costo_medioambiente', 'cos_medio_ambiente'], '0.00')}</td>
                </tr>
                <tr>
                    <td class="cost-sub-item">&bull; Baja de Rendimiento</td>
                    <td class="cost-sub-val">S/ {g(f, ['costo_baja_rendimiento', 'costo_rendimiento', 'cos_baja_rendimiento'], '0.00')}</td>
                </tr>

                <!-- CATEGORÍA 4 -->
                <tr>
                    <td class="cost-title">4. GASTOS DIVERSOS (2% ESTIMADO INVESTIGACIONES)</td>
                    <td class="cost-val">S/ {g(f, 'coste_gastos_diversos', '0.00')}</td>
                </tr>

                <!-- TOTAL FINAL -->
                <tr>
                    <td class="cost-total-lbl">COSTO TOTAL DEL ACCIDENTE</td>
                    <td class="cost-total-val">S/ {g(f, 'coste_total_accidente', '0.00')}</td>
                </tr>
            </tbody>
        </table>

        <div class="sec-header">ANÁLISIS DEL ACCIDENTE</div>
        <table class="grid-table">
            <tr><td style="width: 22%; font-weight: bold; background-color: #f7fafc;">¿Qué sucedió?:</td><td colspan="5">{g(f, 'ana_que_sucedio')}</td></tr>
            <tr><td style="font-weight: bold; background-color: #f7fafc;">¿Por qué? / Tipo Contacto:</td><td colspan="5">{g(f, 'ana_tipo_contacto')}</td></tr>
            <tr><td style="font-weight: bold; background-color: #f7fafc;">¿Por qué? / Causa Inmediata:</td><td colspan="5">{g(f, 'ana_causa_inmediata')}</td></tr>
            <tr><td style="font-weight: bold; background-color: #f7fafc;">¿Por qué? / Causa Básica:</td><td colspan="5">{g(f, 'ana_causa_basica')}</td></tr>
            <tr><td style="font-weight: bold; background-color: #f7fafc;">¿Por qué? / Falta Control:</td><td colspan="5">{g(f, 'ana_falta_control')}</td></tr>
        </table>

        <div class="sec-header">CAUSAS INMEDIATAS O DIRECTAS</div>
        <table class="grid-table">
            <thead>
                <tr>
                    <th style="width: 6%;">Fila</th>
                    <th style="width: 24%;">Tipo</th>
                    <th style="width: 35%;">Causas Frecuentes</th>
                    <th style="width: 35%;">Observaciones</th>
                </tr>
            </thead>
            <tbody>
                {filas_causas_inmediatas}
            </tbody>
        </table>

        <div class="sec-header">CAUSAS SUBYACENTES / BÁSICAS</div>
        <table class="grid-table">
            <thead>
                <tr>
                    <th style="width: 6%;">Fila</th>
                    <th style="width: 20%;">Tipo</th>
                    <th style="width: 24%;">Causas Comunes</th>
                    <th style="width: 25%;">Causa Subyacente</th>
                    <th style="width: 25%;">Observaciones</th>
                </tr>
            </thead>
            <tbody>
                {filas_causas_basicas}
            </tbody>
        </table>

        <div class="sec-header">ACCIONES CORRECTIVAS Y/O PREVENTIVAS PARA EVITAR REPETICIÓN</div>
        <table class="grid-table">
            <thead>
                <tr>
                    <th style="width: 6%;">Fila</th>
                    <th style="width: 16%;">Tipo Acción</th>
                    <th style="width: 28%;">¿Qué se debería hacer?</th>
                    <th style="width: 16%;">Responsable</th>
                    <th style="width: 10%;">F. Prog.</th>
                    <th style="width: 10%;">Situación</th>
                    <th style="width: 14%;">Observación</th>
                </tr>
            </thead>
            <tbody>
                {filas_medidas}
            </tbody>
        </table>

        <div class="sec-header">RESPONSABLE DE REGISTRO, INVESTIGACIÓN Y TESTIGOS</div>
        <table class="grid-table">
            <tr>
                <td style="width: 22%; font-weight: bold; background-color: #f7fafc;">Nombre Resp./Investigador:</td>
                <td style="width: 28%;">{g(f, ['inv_nombre', 'resp_nombre'])}</td>
                <td style="width: 22%; font-weight: bold; background-color: #f7fafc;">Cargo:</td>
                <td style="width: 28%;">{g(f, ['inv_cargo', 'resp_cargo'])}</td>
            </tr>
            <tr>
                <td style="font-weight: bold; background-color: #f7fafc;">Firma Investigador:</td>
                <td colspan="3">{firma_inv_text}</td>
            </tr>
            <tr>
                <td style="font-weight: bold; background-color: #f7fafc;">Nombre Completo Testigo:</td>
                <td>{g(f, 'tes_nombre')}</td>
                <td style="font-weight: bold; background-color: #f7fafc;">Cargo / Vínculo:</td>
                <td>{g(f, 'tes_cargo')}</td>
            </tr>
            <tr>
                <td style="font-weight: bold; background-color: #f7fafc;">Firma del Testigo:</td>
                <td colspan="3">{g(f, 'tes_firma', '<b>[FIRMA EN NEGRITAS]</b>')}</td>
            </tr>
        </table>

        <div class="footer">
            Documento Digital Generado por el Sistema de Gestión SSOMA - EMAPE S.A. | Fecha Registro: {fecha_registro}
        </div>
    </body>
    </html>
    """
    html_to_pdf_file(html_content, pdf_path)


@app.get("/", response_class=HTMLResponse)
def home():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Servidor SSOMA activo</h1>"


@app.get("/descargar-pdf/{filename}")
def descargar_pdf(filename: str):
    file_path = os.path.join(PDF_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(
            file_path, media_type="application/pdf", filename=filename
        )
    return JSONResponse(
        status_code=404, content={"error": "Archivo PDF no encontrado"}
    )


@app.post("/enviar-reporte", response_class=HTMLResponse)
async def enviar_reporte(
    request: Request, fotografia_pre: List[UploadFile] = File(None)
):
    try:
        form_data = await request.form()
        form_dict = {}
        for key in form_data.keys():
            val = form_data.getlist(key)
            form_dict[key] = val[0] if len(val) == 1 else val

        # Campos calculados por main.js. Se normalizan a nombres canónicos para
        # que estén disponibles tanto en el PDF como en el webhook.
        campos_costos = {
            "coste_total_personal": [
                "coste_total_personal", "costo_personal_total", "costo_personal",
                "cos_personal", "costo_mano_obra"
            ],
            "coste_total_danos_materiales": [
                "coste_total_danos_materiales", "costo_materiales_total",
                "costo_materiales", "cos_materiales", "subtotal_materiales"
            ],
            "coste_subtotal_otros": [
                "coste_subtotal_otros", "subtotal_otros", "costo_otros_total",
                "costo_otros", "subtotal_otros_costes"
            ],
            "coste_gastos_diversos": [
                "coste_gastos_diversos", "gastos_diversos_2pct", "gastos_diversos",
                "costo_gastos_diversos", "costo_diversos", "gastos_2pct"
            ],
            "coste_total_accidente": [
                "coste_total_accidente", "costo_total_accidente", "costo_total",
                "total_costo", "costo_final"
            ],
        }
        for nombre_canonico, alias in campos_costos.items():
            form_dict[nombre_canonico] = g(form_dict, alias, "0.00")

        # Control de seguridad backend para Incidentes
        tipo_evt = str(form_dict.get("fin_tipo_evento", "")).lower()
        clasif_evt = str(form_dict.get("fin_clasificacion", "")).lower()

        if "incidente" in tipo_evt or "incidente" in clasif_evt:
            form_dict["acc_gravedad"] = "-"
            form_dict["acc_grado_incapacitante"] = "-"
            form_dict["acc_dias_descanso"] = "-"
            form_dict["acc_dias_cargados"] = "-"
            form_dict["acc_num_afectados"] = "-"

        tz_peru = zoneinfo.ZoneInfo("America/Lima")
        ahora_peru = datetime.now(tz_peru)
        fecha_registro_str = ahora_peru.strftime("%d/%m/%Y %H:%M:%S")

        tipo_informe_raw = str(form_data.get("tipo_informe", "")).strip()
        es_preliminar = "PRELIMINAR" in tipo_informe_raw.upper()
        tipo_informe = (
            "Informe Preliminar"
            if es_preliminar
            else "Informe Final de Accidente"
        )

        fotos_base64 = []

        if fotografia_pre:
            for foto in fotografia_pre:
                if foto and hasattr(foto, "filename") and foto.filename:
                    try:
                        contenido = await foto.read()
                        if contenido and len(contenido) > 0:
                            encoded = optimizar_imagen_base64(contenido)
                            if encoded:
                                fotos_base64.append(encoded)
                    except Exception as err_img:
                        print(f"Error procesando la fotografía: {err_img}")

        if not fotos_base64:
            archivos_alt = form_data.getlist(
                "foto_evento_pre"
            ) or form_data.getlist("foto_evento")
            for foto in archivos_alt:
                if hasattr(foto, "filename") and foto.filename:
                    try:
                        contenido = await foto.read()
                        if contenido and len(contenido) > 0:
                            encoded = optimizar_imagen_base64(contenido)
                            if encoded:
                                fotos_base64.append(encoded)
                    except Exception as err_img:
                        print(
                            f"Error procesando la imagen alternativa: {err_img}"
                        )

        # Extracción de trabajadores
        lista_trabajadores = []
        paterno_list = form_data.getlist("trab_paterno[]") or form_data.getlist(
            "trab_paterno"
        )
        materno_list = form_data.getlist("trab_materno[]") or form_data.getlist(
            "trab_materno"
        )
        nombres_list = form_data.getlist("trab_nombres[]") or form_data.getlist(
            "trab_nombres"
        )
        ocupacion_list = form_data.getlist(
            "trab_ocupacion[]"
        ) or form_data.getlist("trab_ocupacion")
        area_list = (
            form_data.getlist("trab_area_interna[]")
            or form_data.getlist("trab_area_interna")
            or form_data.getlist("trab_area[]")
            or form_data.getlist("trab_area")
        )
        condicion_list = form_data.getlist(
            "trab_condicion[]"
        ) or form_data.getlist("trab_condicion")
        sexo_list = form_data.getlist("trab_sexo[]") or form_data.getlist(
            "trab_sexo"
        )
        dni_list = form_data.getlist("trab_dni[]") or form_data.getlist(
            "trab_dni"
        )
        edad_list = form_data.getlist("trab_edad[]") or form_data.getlist(
            "trab_edad"
        )
        turno_list = form_data.getlist("trab_turno[]") or form_data.getlist(
            "trab_turno"
        )
        personal_list = form_data.getlist(
            "trab_personal[]"
        ) or form_data.getlist("trab_personal")

        for p, m, n, oc, ar, co, sx, d, ed, tu, pe in zip_longest(
            paterno_list,
            materno_list,
            nombres_list,
            ocupacion_list,
            area_list,
            condicion_list,
            sexo_list,
            dni_list,
            edad_list,
            turno_list,
            personal_list,
            fillvalue="",
        ):
            p, m, n, oc, ar, co, sx, d, ed, tu, pe = (
                str(p or ""),
                str(m or ""),
                str(n or ""),
                str(oc or ""),
                str(ar or ""),
                str(co or ""),
                str(sx or ""),
                str(d or ""),
                str(ed or ""),
                str(tu or ""),
                str(pe or ""),
            )
            if any([p, m, n, d]):
                lista_trabajadores.append({
                    "paterno": p,
                    "materno": m,
                    "nombres": n,
                    "ocupacion": oc,
                    "area_interna": ar,
                    "condicion": co,
                    "sexo": sx,
                    "dni": d,
                    "edad": ed,
                    "turno": tu,
                    "personal": pe,
                })

        form_dict["lista_trabajadores"] = lista_trabajadores

        # 1. Causas Inmediatas
        causas_inmediatas_list = []
        for i in range(1, 6):
            t = str(form_data.get(f"cinm_tipo_{i}", "")).strip()
            c = str(form_data.get(f"cinm_causa_{i}", "")).strip()
            o = str(form_data.get(f"cinm_obs_{i}", "")).strip()
            if t or c or o:
                causas_inmediatas_list.append(
                    {"fila": str(i), "tipo": t, "causa": c, "obs": o}
                )

        if not causas_inmediatas_list:
            for f_num, t, c, o in zip_longest(
                form_data.getlist("ci_fila[]") or form_data.getlist("ci_fila"),
                form_data.getlist("ci_tipo[]") or form_data.getlist("ci_tipo"),
                form_data.getlist("ci_causa[]")
                or form_data.getlist("ci_causa"),
                form_data.getlist("ci_obs[]") or form_data.getlist("ci_obs"),
                fillvalue="",
            ):
                f_num, t, c, o = (
                    str(f_num or ""),
                    str(t or ""),
                    str(c or ""),
                    str(o or ""),
                )
                if t or c or o:
                    causas_inmediatas_list.append(
                        {"fila": f_num, "tipo": t, "causa": c, "obs": o}
                    )

        form_dict["causas_inmediatas_list"] = causas_inmediatas_list

        # 2. Causas Básicas
        causas_basicas_list = []
        for i in range(1, 6):
            t = str(form_data.get(f"csub_tipo_{i}", "")).strip()
            c = str(form_data.get(f"csub_causa_{i}", "")).strip()
            s = str(form_data.get(f"csub_subyacente_{i}", "")).strip()
            o = str(form_data.get(f"csub_obs_{i}", "")).strip()
            if t or c or s or o:
                causas_basicas_list.append({
                    "fila": str(i),
                    "tipo": t,
                    "causa": c,
                    "subyacente": s,
                    "obs": o,
                })

        if not causas_basicas_list:
            for f_num, t, c, s, o in zip_longest(
                form_data.getlist("cb_fila[]") or form_data.getlist("cb_fila"),
                form_data.getlist("cb_tipo[]") or form_data.getlist("cb_tipo"),
                form_data.getlist("cb_causa[]")
                or form_data.getlist("cb_causa"),
                form_data.getlist("cb_subyacente[]")
                or form_data.getlist("cb_subyacente"),
                form_data.getlist("cb_obs[]") or form_data.getlist("cb_obs"),
                fillvalue="",
            ):
                f_num, t, c, s, o = (
                    str(f_num or ""),
                    str(t or ""),
                    str(c or ""),
                    str(s or ""),
                    str(o or ""),
                )
                if t or c or s or o:
                    causas_basicas_list.append({
                        "fila": f_num,
                        "tipo": t,
                        "causa": c,
                        "subyacente": s,
                        "obs": o,
                    })

        form_dict["causas_basicas_list"] = causas_basicas_list

        # 3. Medidas Correctivas
        medidas_correctivas_list = []
        for i in range(1, 10):
            t = str(form_data.get(f"acc_tipo_{i}", "")).strip()
            a = str(form_data.get(f"acc_control_{i}", "")).strip()
            r = str(form_data.get(f"acc_resp_{i}", "")).strip()
            fe = str(form_data.get(f"acc_fecha_{i}", "")).strip()
            si = str(form_data.get(f"acc_sit_{i}", "")).strip()
            o = str(form_data.get(f"acc_obs_{i}", "")).strip()
            if t or a or r or fe or si or o:
                medidas_correctivas_list.append({
                    "fila": str(i),
                    "tipo": t,
                    "accion": a,
                    "responsable": r,
                    "fecha": fe,
                    "situacion": si,
                    "obs": o,
                })

        if not medidas_correctivas_list:
            for f_num, t, a, r, fe, si, o in zip_longest(
                form_data.getlist("mc_fila[]") or form_data.getlist("mc_fila"),
                form_data.getlist("mc_tipo[]") or form_data.getlist("mc_tipo"),
                form_data.getlist("mc_accion[]")
                or form_data.getlist("mc_accion"),
                form_data.getlist("mc_responsable[]")
                or form_data.getlist("mc_responsable"),
                form_data.getlist("mc_fecha[]")
                or form_data.getlist("mc_fecha"),
                form_data.getlist("mc_situacion[]")
                or form_data.getlist("mc_situacion"),
                form_data.getlist("mc_obs[]") or form_data.getlist("mc_obs"),
                fillvalue="",
            ):
                f_num, t, a, r, fe, si, o = (
                    str(f_num or ""),
                    str(t or ""),
                    str(a or ""),
                    str(r or ""),
                    str(fe or ""),
                    str(si or ""),
                    str(o or ""),
                )
                if t or a or r or fe:
                    medidas_correctivas_list.append({
                        "fila": f_num,
                        "tipo": t,
                        "accion": a,
                        "responsable": r,
                        "fecha": fe,
                        "situacion": si,
                        "obs": o,
                    })

        form_dict["medidas_correctivas_list"] = medidas_correctivas_list

        # Generación de Código de Comprobante
        if es_preliminar:
            codigo_comprobante = f"PRE-{ahora_peru.strftime('%Y%m%d%H%M%S')}"
        else:
            codigo_comprobante = f"FIN-{ahora_peru.strftime('%Y%m%d%H%M%S')}"

            cadena_area_interna = ", ".join([
                t["area_interna"]
                for t in lista_trabajadores
                if t.get("area_interna")
            ])
            datos_sheet = {
                "fin_fecha_evento": g(form_dict, ["fin_fecha_evento", "fecha_evento"], ""),
                "fin_hora_evento": g(form_dict, ["fin_hora_evento", "hora_evento"], ""),
                "fin_lugar_exacto": g(form_dict, ["fin_lugar_exacto", "lugar_exacto"], ""),
                "fin_tipo_evento": g(form_dict, ["fin_tipo_evento", "tipo_evento"], ""),
                "trab_nombres": ", ".join([
                    t["nombres"] for t in lista_trabajadores if t.get("nombres")
                ]),
                "trab_paterno": ", ".join([
                    t["paterno"] for t in lista_trabajadores if t.get("paterno")
                ]),
                "trab_materno": ", ".join([
                    t["materno"] for t in lista_trabajadores if t.get("materno")
                ]),
                "trab_dni": ", ".join([
                    t["dni"] for t in lista_trabajadores if t.get("dni")
                ]),
                "ana_que_sucedio": g(form_dict, ["ana_que_sucedio", "que_sucedio"], ""),
                "inv_nombre": g(form_dict, ["inv_nombre", "resp_nombre"], ""),
                "trab_area_interna[]": cadena_area_interna,
                "trab_area_interna": cadena_area_interna,
                "trab_area": cadena_area_interna,
                # Envió robusto de Costos a Google Sheets con búsqueda flexible
                "costo_personal_total": g(form_dict, "coste_total_personal", "0.00"),
                "costo_materiales_total": g(form_dict, "coste_total_danos_materiales", "0.00"),
                "costo_edificios": g(form_dict, ["costo_edificios", "costo_edificio"], "0.00"),
                "costo_maquinaria": g(form_dict, ["costo_maquinaria", "costo_maquinas", "costo_equipos"], "0.00"),
                "costo_mat_primas": g(form_dict, ["costo_mat_primas", "costo_materias_primas"], "0.00"),
                "costo_parada": g(form_dict, ["costo_parada", "costo_parada_maquina"], "0.00"),
                "subtotal_otros": g(form_dict, "coste_subtotal_otros", "0.00"),
                "costo_primeros_auxilios": g(form_dict, ["costo_primeros_auxilios", "costo_auxilios"], "0.00"),
                "costo_sanciones": g(form_dict, ["costo_sanciones", "costo_multas"], "0.00"),
                "costo_legales": g(form_dict, ["costo_legales", "costo_gastos_legales"], "0.00"),
                "costo_resp_civil": g(form_dict, ["costo_resp_civil", "costo_responsabilidad_civil"], "0.00"),
                "costo_medio_ambiente": g(form_dict, ["costo_medio_ambiente", "costo_medioambiente"], "0.00"),
                "costo_baja_rendimiento": g(form_dict, ["costo_baja_rendimiento", "costo_rendimiento"], "0.00"),
                "gastos_diversos_2pct": g(form_dict, "coste_gastos_diversos", "0.00"),
                "costo_total_accidente": g(form_dict, "coste_total_accidente", "0.00"),
            }

            try:
                res = requests.post(
                    GOOGLE_WEBHOOK_URL, json=datos_sheet, timeout=5
                )
                if res.status_code == 200:
                    res_json = res.json()
                    if (
                        isinstance(res_json, dict)
                        and "codigo_comprobante" in res_json
                    ):
                        codigo_comprobante = res_json["codigo_comprobante"]
            except Exception as err_sheet:
                print(f"Error Google Sheets Webhook: {err_sheet}")

        pdf_filename = f"Reporte_{codigo_comprobante}.pdf"
        pdf_filepath = os.path.join(PDF_DIR, pdf_filename)

        if es_preliminar:
            generar_pdf_preliminar(
                form_dict,
                codigo_comprobante,
                fecha_registro_str,
                pdf_filepath,
                fotos_base64,
            )
            nombre_afectado = g(
                form_dict,
                ["pre_nombre_lesionado", "nombre_lesionado_pre", "nombre_lesionado"],
                "No especificado",
            )
        else:
            generar_pdf_100_porciento(
                form_dict,
                codigo_comprobante,
                tipo_informe,
                fecha_registro_str,
                pdf_filepath,
            )
            nombres_trabajadores = [
                f"{t.get('paterno', '')} {t.get('nombres', '')}".strip()
                for t in lista_trabajadores
                if t.get("nombres") or t.get("paterno")
            ]
            if nombres_trabajadores:
                nombre_afectado = ", ".join(nombres_trabajadores)
            else:
                nombre_afectado = g(
                    form_dict,
                    ["fin_nombre_lesionado", "nombre_lesionado"],
                    "No especificado",
                )

        asunto = f"NUEVO REGISTRO SSOMA [{codigo_comprobante}]: {tipo_informe} - {nombre_afectado}"
        cuerpo = f"Se ha generado un {tipo_informe}.\n\nCódigo: {codigo_comprobante}\nFecha/Hora: {fecha_registro_str}\nAfectado: {nombre_afectado}\n\nAdjunto encontrará el archivo PDF correspondiente."

        enviar_correo_con_pdf(
            CORREOS_PREDETERMINADOS, asunto, cuerpo, pdf_filepath
        )

        html_confirmacion = f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Reporte Guardado</title>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7f6; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }}
                .card {{ background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); max-width: 500px; width: 90%; text-align: center; }}
                .icon {{ font-size: 50px; color: #28a745; margin-bottom: 10px; }}
                h2 {{ color: #333; margin-bottom: 15px; }}
                .comprobante-box {{ background-color: #e9ecef; border-left: 5px solid #007bff; padding: 15px; text-align: left; margin: 20px 0; border-radius: 4px; }}
                .comprobante-box p {{ margin: 5px 0; font-size: 14px; color: #495057; }}
                .code {{ font-weight: bold; font-size: 16px; color: #007bff; }}
                .btn-group {{ display: flex; gap: 10px; justify-content: center; margin-top: 20px; }}
                .btn {{ display: inline-block; padding: 11px 18px; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 14px; }}
                .btn-primary {{ background-color: #007bff; color: white; }}
                .btn-success {{ background-color: #28a745; color: white; }}
            </style>
        </head>
        <body>
            <div class="card">
                <div class="icon">✓</div>
                <h2>¡{tipo_informe} Generado!</h2>
                <p>El PDF correspondiente ha sido creado exitosamente y enviado por correo.</p>
                <div class="comprobante-box">
                    <p><strong>Código:</strong> <span class="code">{codigo_comprobante}</span></p>
                    <p><strong>Tipo:</strong> {tipo_informe}</p>
                    <p><strong>Fecha y Hora:</strong> {fecha_registro_str}</p>
                    <p><strong>Afectado:</strong> {nombre_afectado}</p>
                </div>
                <div class="btn-group">
                    <a href="/descargar-pdf/{pdf_filename}" class="btn btn-success" target="_blank">📥 Descargar PDF</a>
                    <a href="/" class="btn btn-primary">Nuevo Registro</a>
                </div>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_confirmacion, status_code=200)

    except Exception as e:
        error_detallado = traceback.format_exc()
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "trace": error_detallado},
        )

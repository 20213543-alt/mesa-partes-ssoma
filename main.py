import os
import smtplib
import requests
import traceback
import base64
import io
from datetime import datetime
import zoneinfo
from io import BytesIO
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from xhtml2pdf import pisa
from PIL import Image

app = FastAPI()

GOOGLE_WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbxaliz82ArStXwK5OH2lAn_wK0rp23CIvWy4cglATNt5AhV90VeucsJ7GrB1sFHYANhRw/exec"

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "")

CORREOS_PREDETERMINADOS = ["chanelone14@gmail.com", "20213543@aloe.ulima.edu.pe"]

PDF_DIR = "pdf_reports"
os.makedirs(PDF_DIR, exist_ok=True)

def optimizar_imagen_base64(bytes_imagen):
    """Redimensiona y comprime la imagen a JPEG para evitar fallos de memoria en xhtml2pdf."""
    try:
        img = Image.open(io.BytesIO(bytes_imagen))
        img = img.convert("RGB")
        img.thumbnail((700, 700))  # Tamaño ideal para hoja A4
        
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=75)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception as e:
        print(f"Error optimizando la fotografía: {e}")
        return None

def enviar_correo_con_pdf(destinatarios: list, asunto: str, cuerpo: str, pdf_path: str = None):
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        return

    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = ", ".join(destinatarios)
        msg['Subject'] = asunto
        msg.attach(MIMEText(cuerpo, 'plain'))

        if pdf_path and os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                adjunto = MIMEApplication(f.read(), _subtype="pdf")
                adjunto.add_header('Content-Disposition', 'attachment', filename=os.path.basename(pdf_path))
                msg.attach(adjunto)

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, destinatarios, msg.as_string())
        server.quit()
    except Exception as e:
        print(f"Error al enviar correo: {e}")

def g(form_dict, key, default="-"):
    val = form_dict.get(key)
    if val is None or str(val).strip() == "":
        return default
    return str(val).strip()

def html_to_pdf_file(html_string: str, pdf_path: str):
    with open(pdf_path, "wb") as pdf_file:
        pisa_status = pisa.CreatePDF(BytesIO(html_string.encode("utf-8")), dest=pdf_file)
    return not pisa_status.err

def generar_pdf_preliminar(f: dict, codigo: str, fecha_registro: str, pdf_path: str, foto_base64: str = None):
    if foto_base64:
        img_html = f'<img src="data:image/jpeg;base64,{foto_base64}" width="380" height="230" />'
    else:
        img_html = '<p style="color: #718096; font-size: 8pt; padding: 15px;">Sin fotografía adjunta</p>'

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
            .photo-box {{ text-align: center; padding: 8px; border: 1px solid #cbd5e0; background-color: #f7fafc; margin-bottom: 6px; }}
            .footer {{ margin-top: 15px; font-size: 7.5pt; color: #718096; text-align: center; border-top: 1px solid #e2e8f0; padding-top: 4px; }}
        </style>
    </head>
    <body>
        <!-- ENCABEZADO CORREGIDO CON TABLA PURA -->
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
                <td class="val" colspan="2">{g(f, 'pre_razon_social', 'EMPRESA MUNICIPAL DE APOYO A PROYECTOS ESTRATÉGICOS S.A.')}</td>
                <td class="lbl">RUC:</td>
                <td class="val">{g(f, 'pre_ruc', '20100063337')}</td>
            </tr>
            <tr>
                <td class="lbl">Tipo de Evento:</td>
                <td class="val" colspan="4">{g(f, 'pre_tipo_evento', g(f, 'tipo_evento_pre'))}</td>
            </tr>
        </table>

        <div class="sec-header">ANTECEDENTES</div>
        <table class="grid-table">
            <tr>
                <td class="lbl">Fecha de Evento:</td>
                <td class="val">{g(f, 'pre_fecha_evento', g(f, 'fecha_evento_pre'))}</td>
                <td class="lbl">Hora de Ocurrencia:</td>
                <td class="val">{g(f, 'pre_hora_evento', g(f, 'hora_ocurrencia_pre'))}</td>
            </tr>
            <tr>
                <td class="lbl">Lugar de Ocurrencia:</td>
                <td class="val">{g(f, 'pre_lugar_evento', g(f, 'lugar_ocurrencia_pre'))}</td>
                <td class="lbl">Fecha de Reporte:</td>
                <td class="val">{g(f, 'pre_fecha_reporte', g(f, 'fecha_reporte_pre'))}</td>
            </tr>
        </table>
        <div class="text-box">
            <b>Trabajo que se Realizaba:</b><br/>
            {g(f, 'pre_trabajo_realizaba', g(f, 'trabajo_realizaba_pre'))}
        </div>

        <div class="sec-header">DESCRIPCIÓN DE LOS LESIONADOS</div>
        <table class="grid-table">
            <tr>
                <td class="lbl">Nombre Completo:</td>
                <td class="val">{g(f, 'pre_nombre_lesionado', g(f, 'nombre_lesionado_pre'))}</td>
                <td class="lbl">Edad:</td>
                <td class="val">{g(f, 'pre_edad_lesionado', g(f, 'edad_lesionado_pre'))}</td>
            </tr>
            <tr>
                <td class="lbl">Cargo:</td>
                <td class="val" colspan="3">{g(f, 'pre_cargo_lesionado', g(f, 'cargo_lesionado_pre'))}</td>
            </tr>
        </table>
        <div class="text-box">
            <b>Breve Descripción del Suceso:</b><br/>
            {g(f, 'pre_breve_descripcion', g(f, 'breve_descripcion_pre'))}
        </div>

        <div class="sec-header">REGISTRO FOTOGRÁFICO</div>
        <div class="photo-box">
            {img_html}
        </div>

        <div class="sec-header">RESPONSABLE DEL REPORTE</div>
        <table class="grid-table">
            <tr>
                <td class="lbl">Nombre y Apellido:</td>
                <td class="val">{g(f, 'pre_resp_nombre', g(f, 'resp_nombre_pre'))}</td>
                <td class="lbl">Cargo:</td>
                <td class="val">{g(f, 'pre_resp_cargo', g(f, 'resp_cargo_pre'))}</td>
            </tr>
            <tr>
                <td class="lbl">Fecha:</td>
                <td class="val" colspan="3">{g(f, 'pre_resp_fecha', g(f, 'resp_fecha_pre'))}</td>
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

def generar_pdf_100_porciento(f: dict, codigo: str, tipo_informe: str, fecha_registro: str, pdf_path: str):
    filas_trabajadores = ""
    for trab in f.get("lista_trabajadores", []):
        filas_trabajadores += f"""
        <tr>
            <td>{trab.get('paterno','-')}</td>
            <td>{trab.get('materno','-')}</td>
            <td>{trab.get('nombres','-')}</td>
            <td>{trab.get('ocupacion','-')}</td>
            <td>{trab.get('condicion','-')}</td>
            <td>{trab.get('sexo','-')}</td>
            <td>{trab.get('dni','-')}</td>
            <td>{trab.get('edad','-')}</td>
            <td>{trab.get('turno','-')}</td>
            <td>{trab.get('personal','-')}</td>
        </tr>
        """
    if not filas_trabajadores:
        filas_trabajadores = "<tr><td colspan='10'>No se registraron trabajadores</td></tr>"

    filas_causas_inmediatas = ""
    for ci in f.get("causas_inmediatas_list", []):
        filas_causas_inmediatas += f"""
        <tr>
            <td style='text-align:center;'>{ci.get('fila','-')}</td>
            <td>{ci.get('tipo','-')}</td>
            <td>{ci.get('causa','-')}</td>
            <td>{ci.get('obs','-')}</td>
        </tr>
        """
    if not filas_causas_inmediatas:
        filas_causas_inmediatas = "<tr><td colspan='4'>Sin registros</td></tr>"

    filas_causas_basicas = ""
    for cb in f.get("causas_basicas_list", []):
        filas_causas_basicas += f"""
        <tr>
            <td style='text-align:center;'>{cb.get('fila','-')}</td>
            <td>{cb.get('tipo','-')}</td>
            <td>{cb.get('causa','-')}</td>
            <td>{cb.get('subyacente','-')}</td>
            <td>{cb.get('obs','-')}</td>
        </tr>
        """
    if not filas_causas_basicas:
        filas_causas_basicas = "<tr><td colspan='5'>Sin registros</td></tr>"

    filas_medidas = ""
    for mc in f.get("medidas_correctivas_list", []):
        filas_medidas += f"""
        <tr>
            <td style='text-align:center;'>{mc.get('fila','-')}</td>
            <td>{mc.get('tipo','-')}</td>
            <td>{mc.get('accion','-')}</td>
            <td>{mc.get('responsable','-')}</td>
            <td>{mc.get('fecha','-')}</td>
            <td>{mc.get('situacion','-')}</td>
            <td>{mc.get('obs','-')}</td>
        </tr>
        """
    if not filas_medidas:
        filas_medidas = "<tr><td colspan='7'>Sin registros</td></tr>"

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
            .sec-header {{ background-color: #1a365d; color: #ffffff; font-weight: bold; font-size: 8pt; padding: 3px; margin-top: 6px; margin-bottom: 3px; }}
            .sec-red {{ background-color: #742a2a; color: #ffffff; }}
            .grid-table {{ width: 100%; border-collapse: collapse; margin-bottom: 5px; }}
            .grid-table td, .grid-table th {{ border: 1px solid #cbd5e0; padding: 3px; font-size: 7pt; vertical-align: middle; }}
            .grid-table th {{ background-color: #edf2f7; color: #1a365d; text-align: left; font-weight: bold; }}
            .lbl {{ font-weight: bold; color: #2d3748; background-color: #f7fafc; width: 22%; }}
            .val {{ color: #1a202c; width: 28%; }}
            .text-box {{ border: 1px solid #cbd5e0; background-color: #f7fafc; padding: 4px; font-size: 7pt; line-height: 1.1; margin-bottom: 5px; }}
            .footer {{ margin-top: 8px; font-size: 6.5pt; color: #718096; text-align: center; border-top: 1px solid #e2e8f0; padding-top: 3px; }}
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
                <td class="lbl">Razón Social:</td>
                <td class="val" colspan="3">{g(f, 'emp_razon_social', 'EMPRESA MUNICIPAL DE APOYO A PROYECTOS ESTRATÉGICOS S.A.')}</td>
                <td class="lbl">RUC:</td>
                <td class="val">{g(f, 'emp_ruc', '20100063337')}</td>
            </tr>
            <tr>
                <td class="lbl">Sede:</td>
                <td class="val">{g(f, 'emp_sede')}</td>
                <td class="lbl">Dirección:</td>
                <td class="val" colspan="3">{g(f, 'emp_direccion')}</td>
            </tr>
            <tr>
                <td class="lbl">N° Trab. Centro Laboral:</td>
                <td class="val">{g(f, 'emp_num_trab')}</td>
                <td class="lbl">N° Afiliados SCTR:</td>
                <td class="val">{g(f, 'emp_num_sctr')}</td>
                <td class="lbl">Aseguradora SCTR:</td>
                <td class="val">{g(f, 'emp_aseguradora')}</td>
            </tr>
        </table>

        <div class="sec-header">DATOS DEL EMPLEADOR DE TERCERIZACIÓN, CONTRATISTA U OTROS</div>
        <table class="grid-table">
            <tr>
                <td class="lbl">Razón Social / Nombre:</td>
                <td class="val" colspan="3">{g(f, 'ter_razon_social')}</td>
                <td class="lbl">RUC:</td>
                <td class="val">{g(f, 'ter_ruc')}</td>
            </tr>
            <tr>
                <td class="lbl">Domicilio:</td>
                <td class="val" colspan="3">{g(f, 'ter_domicilio')}</td>
                <td class="lbl">Actividad Económica:</td>
                <td class="val">{g(f, 'ter_actividad')}</td>
            </tr>
            <tr>
                <td class="lbl">N° Trab. Centro Laboral:</td>
                <td class="val">{g(f, 'ter_num_trab')}</td>
                <td class="lbl">N° Afiliados SCTR:</td>
                <td class="val">{g(f, 'ter_num_sctr')}</td>
                <td class="lbl">Aseguradora:</td>
                <td class="val">{g(f, 'ter_aseguradora')}</td>
            </tr>
        </table>

        <div class="sec-header">1) OCURRENCIA DEL EVENTO Y 2) TIPO Y CLASIFICACIÓN</div>
        <table class="grid-table">
            <tr>
                <td class="lbl">Fecha Evento:</td>
                <td class="val">{g(f, 'fin_fecha_evento')}</td>
                <td class="lbl">Hora Evento:</td>
                <td class="val">{g(f, 'fin_hora_evento')}</td>
                <td class="lbl">Lugar Exacto:</td>
                <td class="val">{g(f, 'fin_lugar_exacto')}</td>
            </tr>
            <tr>
                <td class="lbl">Tipo de Evento:</td>
                <td class="val">{g(f, 'fin_tipo_evento')}</td>
                <td class="lbl">Clasificación Evento:</td>
                <td class="val">{g(f, 'fin_clasificacion')}</td>
                <td class="lbl">Solo Incidente:</td>
                <td class="val">{g(f, 'fin_solo_incidente')}</td>
            </tr>
        </table>

        <div class="sec-header">DATOS DEL TRABAJADOR AFECTADO E INVOLUCRADO EN EL EVENTO</div>
        <table class="grid-table">
            <thead>
                <tr>
                    <th>A. Paterno</th>
                    <th>A. Materno</th>
                    <th>Nombres</th>
                    <th>Ocupación</th>
                    <th>Condición</th>
                    <th>Sexo</th>
                    <th>DNI</th>
                    <th>Edad</th>
                    <th>Turno</th>
                    <th>Personal</th>
                </tr>
            </thead>
            <tbody>
                {filas_trabajadores}
            </tbody>
        </table>

        <div class="sec-header sec-red">ACCIDENTE (EVALUACIÓN DE GRAVEDAD)</div>
        <table class="grid-table">
            <tr>
                <td class="lbl">Gravedad Accidente:</td>
                <td class="val">{g(f, 'fin_gravedad_evento')}</td>
                <td class="lbl">Grado Incapacitante:</td>
                <td class="val">{g(f, 'acc_grado_incapacitante')}</td>
                <td class="lbl">Días Descanso Médico:</td>
                <td class="val">{g(f, 'acc_dias_descanso')}</td>
            </tr>
            <tr>
                <td class="lbl">Días Cargados:</td>
                <td class="val">{g(f, 'acc_dias_cargados')}</td>
                <td class="lbl">N° Trab. Afectados:</td>
                <td class="val" colspan="3">{g(f, 'acc_num_afectados')}</td>
            </tr>
        </table>

        <div class="sec-header">SOLO EN CASO DE INCIDENTE DE PRIMEROS AUXILIOS</div>
        <div class="text-box">
            <b>Tipo de Atención en Primeros Auxilios:</b> {g(f, 'pa_tipo_atencion')}
        </div>

        <div class="sec-header">DETALLE DE LESIONES Y LUGAR DE ATENCIÓN</div>
        <table class="grid-table">
            <tr>
                <td class="lbl">Forma Accidente/Incidente:</td>
                <td class="val">{g(f, 'les_forma')}</td>
                <td class="lbl">Tipo de Lesión:</td>
                <td class="val" colspan="3">{g(f, 'les_tipo')}</td>
            </tr>
            <tr>
                <td class="lbl">Agente Causante:</td>
                <td class="val">{g(f, 'les_agente')}</td>
                <td class="lbl">Parte Cuerpo Afectada:</td>
                <td class="val" colspan="3">{g(f, 'les_parte_cuerpo')}</td>
            </tr>
            <tr>
                <td class="lbl">Hospital / Clínica / Tópico:</td>
                <td class="val" colspan="5">{g(f, 'les_hospital')}</td>
            </tr>
        </table>

        <div class="sec-header">DATOS DEL INCIDENTE CON DAÑO A LA PROPIEDAD / MEDIO AMBIENTE</div>
        <table class="grid-table">
            <tr>
                <td class="lbl">Daño Material:</td>
                <td class="val">{g(f, 'dan_material')}</td>
                <td class="lbl">Agente Causante del Daño:</td>
                <td class="val">{g(f, 'dan_agente')}</td>
            </tr>
        </table>
        <div class="text-box">
            <b>Descripción del Evento (Daños / M.A.):</b> {g(f, 'dan_descripcion')}
        </div>

        <div class="sec-header">ANÁLISIS DEL ACCIDENTE</div>
        <table class="grid-table">
            <tr><td class="lbl">¿Qué sucedió?:</td><td class="val" colspan="5">{g(f, 'ana_que_sucedio')}</td></tr>
            <tr><td class="lbl">¿Por qué? / Tipo Contacto:</td><td class="val" colspan="5">{g(f, 'ana_tipo_contacto')}</td></tr>
            <tr><td class="lbl">¿Por qué? / Causa Inmediata:</td><td class="val" colspan="5">{g(f, 'ana_causa_inmediata')}</td></tr>
            <tr><td class="lbl">¿Por qué? / Causa Básica:</td><td class="val" colspan="5">{g(f, 'ana_causa_basica')}</td></tr>
            <tr><td class="lbl">¿Por qué? / Falta Control:</td><td class="val" colspan="5">{g(f, 'ana_falta_control')}</td></tr>
        </table>

        <div class="sec-header">CAUSAS INMEDIATAS O DIRECTAS</div>
        <table class="grid-table">
            <thead>
                <tr>
                    <th style="width: 8%;">Fila</th>
                    <th style="width: 25%;">Tipo</th>
                    <th style="width: 35%;">Causas Frecuentes</th>
                    <th>Observaciones</th>
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
                    <th style="width: 8%;">Fila</th>
                    <th style="width: 22%;">Tipo</th>
                    <th style="width: 25%;">Causas Comunes</th>
                    <th style="width: 25%;">Causa Subyacente</th>
                    <th>Observaciones</th>
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
                    <th style="width: 14%;">Tipo Acción</th>
                    <th style="width: 28%;">¿Qué se debería hacer?</th>
                    <th style="width: 18%;">Responsable</th>
                    <th style="width: 12%;">F. Prog.</th>
                    <th style="width: 10%;">Situación</th>
                    <th>Observación</th>
                </tr>
            </thead>
            <tbody>
                {filas_medidas}
            </tbody>
        </table>

        <div class="sec-header">RESPONSABLE DE REGISTRO, INVESTIGACIÓN Y TESTIGOS</div>
        <table class="grid-table">
            <tr>
                <td class="lbl">Nombre Resp./Investigador:</td>
                <td class="val">{g(f, 'inv_nombre')}</td>
                <td class="lbl">Cargo:</td>
                <td class="val">{g(f, 'inv_cargo')}</td>
            </tr>
            <tr>
                <td class="lbl">Firma Investigador:</td>
                <td class="val" colspan="3">{g(f, 'firma_inv_text', f"<b>[REGISTRADO POR: {g(f, 'inv_nombre')}]</b>")}</td>
            </tr>
            <tr>
                <td class="lbl">Nombre Completo Testigo:</td>
                <td class="val">{g(f, 'tes_nombre')}</td>
                <td class="lbl">Cargo / Vínculo:</td>
                <td class="val">{g(f, 'tes_cargo')}</td>
            </tr>
            <tr>
                <td class="lbl">Firma del Testigo:</td>
                <td class="val" colspan="3">{g(f, 'tes_firma', '<b>[FIRMA EN NEGRITAS]</b>')}</td>
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
        return FileResponse(file_path, media_type='application/pdf', filename=filename)
    return JSONResponse(status_code=404, content={"error": "Archivo PDF no encontrado"})

@app.post("/enviar-reporte", response_class=HTMLResponse)
async def enviar_reporte(request: Request):
    try:
        form_data = await request.form()
        form_dict = {}
        for key in form_data.keys():
            val = form_data.getlist(key)
            form_dict[key] = val[0] if len(val) == 1 else val

        tz_peru = zoneinfo.ZoneInfo("America/Lima")
        ahora_peru = datetime.now(tz_peru)
        fecha_registro_str = ahora_peru.strftime("%d/%m/%Y %H:%M:%S")

        tipo_informe_raw = str(form_data.get("tipo_informe", "")).strip()
        es_preliminar = "PRELIMINAR" in tipo_informe_raw.upper()
        tipo_informe = "Informe Preliminar" if es_preliminar else "Informe Final de Accidente"

        # Procesar Fotografía con Optimización de Imagen (Pillow)
        foto_base64 = None
        archivo_foto = form_data.get("fotografia_pre") or form_data.get("foto_evento_pre") or form_data.get("foto_evento")

        if archivo_foto and hasattr(archivo_foto, "filename") and archivo_foto.filename:
            try:
                contents = await archivo_foto.read()
                if contents and len(contents) > 0:
                    foto_base64 = optimizar_imagen_base64(contents)
            except Exception as err_img:
                print(f"Error procesando la imagen: {err_img}")

        # Parsear Trabajadores
        lista_trabajadores = []
        paterno_list = form_data.getlist("trab_paterno[]") or [form_data.get("trab_paterno", "")]
        materno_list = form_data.getlist("trab_materno[]") or [form_data.get("trab_materno", "")]
        nombres_list = form_data.getlist("trab_nombres[]") or [form_data.get("trab_nombres", "")]
        ocupacion_list = form_data.getlist("trab_ocupacion[]") or [form_data.get("trab_ocupacion", "")]
        condicion_list = form_data.getlist("trab_condicion[]") or [form_data.get("trab_condicion", "")]
        sexo_list = form_data.getlist("trab_sexo[]") or [form_data.get("trab_sexo", "")]
        dni_list = form_data.getlist("trab_dni[]") or [form_data.get("trab_dni", "")]
        edad_list = form_data.getlist("trab_edad[]") or [form_data.get("trab_edad", "")]
        turno_list = form_data.getlist("trab_turno[]") or [form_data.get("trab_turno", "")]
        personal_list = form_data.getlist("trab_personal[]") or [form_data.get("trab_personal", "")]

        for p, m, n, oc, co, sx, d, ed, tu, pe in zip(
            paterno_list, materno_list, nombres_list, ocupacion_list, condicion_list, sexo_list, dni_list, edad_list, turno_list, personal_list
        ):
            if any([p, m, n, d]):
                lista_trabajadores.append({
                    "paterno": p, "materno": m, "nombres": n, "ocupacion": oc, "condicion": co,
                    "sexo": sx, "dni": d, "edad": ed, "turno": tu, "personal": pe
                })

        form_dict["lista_trabajadores"] = lista_trabajadores

        # Tablas secundarias
        causas_inmediatas_list = []
        for f_num, t, c, o in zip(form_data.getlist("ci_fila[]"), form_data.getlist("ci_tipo[]"), form_data.getlist("ci_causa[]"), form_data.getlist("ci_obs[]")):
            if t or c or o:
                causas_inmediatas_list.append({"fila": f_num, "tipo": t, "causa": c, "obs": o})
        form_dict["causas_inmediatas_list"] = causas_inmediatas_list

        causas_basicas_list = []
        for f_num, t, c, s, o in zip(form_data.getlist("cb_fila[]"), form_data.getlist("cb_tipo[]"), form_data.getlist("cb_causa[]"), form_data.getlist("cb_subyacente[]"), form_data.getlist("cb_obs[]")):
            if t or c or s or o:
                causas_basicas_list.append({"fila": f_num, "tipo": t, "causa": c, "subyacente": s, "obs": o})
        form_dict["causas_basicas_list"] = causas_basicas_list

        medidas_correctivas_list = []
        for f_num, t, a, r, fe, si, o in zip(form_data.getlist("mc_fila[]"), form_data.getlist("mc_tipo[]"), form_data.getlist("mc_accion[]"), form_data.getlist("mc_responsable[]"), form_data.getlist("mc_fecha[]"), form_data.getlist("mc_situacion[]"), form_data.getlist("mc_obs[]")):
            if t or a or r or fe:
                medidas_correctivas_list.append({"fila": f_num, "tipo": t, "accion": a, "responsable": r, "fecha": fe, "situacion": si, "obs": o})
        form_dict["medidas_correctivas_list"] = medidas_correctivas_list

        codigo_comprobante = f"PRE-{ahora_peru.strftime('%Y%m%d%H%M%S')}"

        if not es_preliminar:
            datos_sheet = {
                "fin_fecha_evento": form_data.get("fin_fecha_evento", ""),
                "fin_hora_evento": form_data.get("fin_hora_evento", ""),
                "fin_lugar_exacto": form_data.get("fin_lugar_exacto", ""),
                "fin_tipo_evento": form_data.get("fin_tipo_evento", ""),
                "trab_nombres": ", ".join([t['nombres'] for t in lista_trabajadores if t['nombres']]),
                "trab_paterno": ", ".join([t['paterno'] for t in lista_trabajadores if t['paterno']]),
                "trab_materno": ", ".join([t['materno'] for t in lista_trabajadores if t['materno']]),
                "trab_dni": ", ".join([t['dni'] for t in lista_trabajadores if t['dni']]),
                "ana_que_sucedio": form_data.get("ana_que_sucedio", ""),
                "inv_nombre": form_data.get("inv_nombre", "")
            }

            try:
                res = requests.post(GOOGLE_WEBHOOK_URL, json=datos_sheet, timeout=10)
                res_json = res.json()
                if "codigo_comprobante" in res_json:
                    codigo_comprobante = res_json["codigo_comprobante"]
            except Exception as err_sheet:
                print(f"Error Google Sheets: {err_sheet}")

        pdf_filename = f"Reporte_{codigo_comprobante}.pdf"
        pdf_filepath = os.path.join(PDF_DIR, pdf_filename)

        if es_preliminar:
            generar_pdf_preliminar(form_dict, codigo_comprobante, fecha_registro_str, pdf_filepath, foto_base64)
            nombre_afectado = form_data.get("pre_nombre_lesionado") or form_data.get("nombre_lesionado_pre") or "No especificado"
        else:
            generar_pdf_100_porciento(form_dict, codigo_comprobante, tipo_informe, fecha_registro_str, pdf_filepath)
            nombre_afectado = ", ".join([f"{t.get('paterno','')} {t.get('nombres','')}".strip() for t in lista_trabajadores if t.get('nombres')]) or "No especificado"

        correo_usuario = str(form_data.get("correo_destino", "")).strip()
        lista_destinos = list(CORREOS_PREDETERMINADOS)
        if correo_usuario and correo_usuario not in lista_destinos:
            lista_destinos.append(correo_usuario)

        asunto = f"NUEVO REGISTRO SSOMA [{codigo_comprobante}]: {tipo_informe} - {nombre_afectado}"
        cuerpo = f"Se ha generado un {tipo_informe}.\n\nCódigo: {codigo_comprobante}\nFecha/Hora: {fecha_registro_str}\nAfectado: {nombre_afectado}\n\nAdjunto encontrará el archivo PDF correspondiente."
        
        enviar_correo_con_pdf(lista_destinos, asunto, cuerpo, pdf_filepath)

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
                <p>El PDF correspondiente ha sido creado exitosamente.</p>
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
        return JSONResponse(status_code=500, content={"error": str(e), "trace": error_detallado})

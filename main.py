import os
import smtplib
import requests
import traceback
from datetime import datetime
import zoneinfo
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from weasyprint import HTML

app = FastAPI()

# Webhook de Google Apps Script
GOOGLE_WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbxaliz82ArStXwK5OH2lAn_wK0rp23CIvWy4cglATNt5AhV90VeucsJ7GrB1sFHYANhRw/exec"

# Configuración del servidor de correo SMTP
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "")

CORREOS_PREDETERMINADOS = ["chanelone14@gmail.com", "20213543@aloe.ulima.edu.pe"]

# Carpeta para almacenar temporalmente los PDFs generados
PDF_DIR = "pdf_reports"
os.makedirs(PDF_DIR, exist_ok=True)

def enviar_correo_con_pdf(destinatarios: list, asunto: str, cuerpo: str, pdf_path: str = None):
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        return

    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = ", ".join(destinatarios)
        msg['Subject'] = asunto
        msg.attach(MIMEText(cuerpo, 'plain'))

        # Adjuntar archivo PDF
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

def generar_pdf_reporte(datos: dict, codigo: str, tipo_informe: str, fecha_registro: str, pdf_path: str):
    # Crear filas dinámicas para la lista de trabajadores en el PDF
    filas_trabajadores = ""
    for trab in datos.get("lista_trabajadores", []):
        filas_trabajadores += f"""
        <tr>
            <td>{trab['paterno']} {trab['materno']} {trab['nombres']}</td>
            <td>{trab['dni']}</td>
        </tr>
        """
    if not filas_trabajadores:
        filas_trabajadores = "<tr><td colspan='2'>No especificado</td></tr>"

    # Plantilla visual en HTML/CSS que se transformará en el documento PDF
    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <style>
            @page {{ size: A4; margin: 15mm 12mm; background-color: #ffffff; }}
            body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 10pt; color: #222; margin: 0; padding: 0; }}
            .header {{ background-color: #003366; color: white; padding: 15px; border-radius: 6px; margin-bottom: 20px; }}
            .header table {{ width: 100%; border-collapse: collapse; }}
            .title {{ font-size: 15pt; font-weight: bold; text-transform: uppercase; }}
            .subtitle {{ font-size: 9.5pt; opacity: 0.9; margin-top: 4px; }}
            .badge {{ background-color: #f0a500; color: #003366; padding: 6px 12px; font-weight: bold; font-size: 11pt; border-radius: 4px; }}
            .section-title {{ font-size: 11pt; font-weight: bold; color: #003366; border-bottom: 2px solid #003366; padding-bottom: 3px; margin-top: 15px; margin-bottom: 8px; text-transform: uppercase; }}
            .grid-table {{ width: 100%; border-collapse: collapse; margin-bottom: 10px; }}
            .grid-table td, .grid-table th {{ border: 1px solid #cccccc; padding: 6px 8px; font-size: 9pt; vertical-align: top; }}
            .grid-table th {{ background-color: #f2f4f8; color: #003366; text-align: left; font-weight: bold; }}
            .label {{ font-weight: bold; color: #444; background-color: #f8f9fa; width: 25%; }}
            .value {{ color: #111; width: 25%; }}
            .text-box {{ border: 1px solid #cccccc; background-color: #fcfcfc; padding: 8px; font-size: 9pt; line-height: 1.4; border-radius: 4px; margin-bottom: 10px; }}
            .footer {{ margin-top: 25px; font-size: 8pt; color: #666; text-align: center; border-top: 1px solid #ddd; padding-top: 8px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <table>
                <tr>
                    <td>
                        <div class="title">EMAPE S.A. - MESA DE PARTES SSOMA</div>
                        <div class="subtitle">CONSTANCIA DE REGISTRO - INFORME {tipo_informe}</div>
                    </td>
                    <td style="text-align: right;">
                        <div class="badge">{codigo}</div>
                    </td>
                </tr>
            </table>
        </div>

        <div class="section-title">1. DATOS GENERALES DEL EVENTO</div>
        <table class="grid-table">
            <tr>
                <td class="label">Fecha Evento:</td>
                <td class="value">{datos.get('fin_fecha_evento', 'N/A')}</td>
                <td class="label">Hora Evento:</td>
                <td class="value">{datos.get('fin_hora_evento', 'N/A')}</td>
            </tr>
            <tr>
                <td class="label">Lugar Exacto:</td>
                <td class="value">{datos.get('fin_lugar_exacto', 'N/A')}</td>
                <td class="label">Tipo de Evento:</td>
                <td class="value">{datos.get('fin_tipo_evento', 'N/A')}</td>
            </tr>
        </table>

        <div class="section-title">2. PERSONAS AFECTADAS / TRABAJADORES</div>
        <table class="grid-table">
            <thead>
                <tr>
                    <th>Apellidos y Nombres</th>
                    <th>DNI / Documento</th>
                </tr>
            </thead>
            <tbody>
                {filas_trabajadores}
            </tbody>
        </table>

        <div class="section-title">3. DESCRIPCIÓN Y ANÁLISIS DEL SUCESO</div>
        <div class="text-box">
            {datos.get('ana_que_sucedio', 'Sin descripción detallada.')}
        </div>

        <div class="section-title">4. INFORMACIÓN DE REGISTRO</div>
        <table class="grid-table">
            <tr>
                <td class="label">Responsable / Investigador:</td>
                <td class="value">{datos.get('inv_nombre', 'N/A')}</td>
                <td class="label">Fecha y Hora de Registro:</td>
                <td class="value">{fecha_registro}</td>
            </tr>
        </table>

        <div class="footer">
            Documento digital generado por el Sistema SSOMA - EMAPE S.A.
        </div>
    </body>
    </html>
    """
    HTML(string=html_content).write_pdf(pdf_path)

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

        tz_peru = zoneinfo.ZoneInfo("America/Lima")
        ahora_peru = datetime.now(tz_peru)
        fecha_registro_str = ahora_peru.strftime("%d/%m/%Y %H:%M:%S")

        tipo_informe = form_data.get("tipo_informe", "PRELIMINAR")

        lista_trabajadores = []
        if tipo_informe == "PRELIMINAR":
            fecha_evento = form_data.get("fecha_evento_pre", "")
            hora_evento = form_data.get("hora_ocurrencia_pre", "")
            lugar_exacto = form_data.get("lugar_ocurrencia_pre", "")
            tipo_evento = form_data.get("tipo_evento_pre", "PRELIMINAR")
            trab_nombres_str = form_data.get("nombre_lesionado_pre", "")
            trab_paterno_str = ""
            trab_materno_str = ""
            trab_dni_str = "N/A"
            ana_que_sucedio = form_data.get("breve_descripcion_pre", "")
            inv_nombre_str = form_data.get("resp_nombre_pre", "")
            
            lista_trabajadores.append({"nombres": trab_nombres_str, "paterno": "", "materno": "", "dni": "N/A"})
        else:
            fecha_evento = form_data.get("fin_fecha_evento", "")
            hora_evento = form_data.get("fin_hora_evento", "")
            lugar_exacto = form_data.get("fin_lugar_exacto", "")
            tipo_evento = form_data.get("fin_tipo_evento", "FINAL")
            
            nombres_list = form_data.getlist("trab_nombres[]") or [form_data.get("trab_nombres", "")]
            paterno_list = form_data.getlist("trab_paterno[]") or [form_data.get("trab_paterno", "")]
            materno_list = form_data.getlist("trab_materno[]") or [form_data.get("trab_materno", "")]
            dni_list = form_data.getlist("trab_dni[]") or [form_data.get("trab_dni", "")]

            for n, p, m, d in zip(nombres_list, paterno_list, materno_list, dni_list):
                if n or p or d:
                    lista_trabajadores.append({"nombres": n, "paterno": p, "materno": m, "dni": d})

            trab_nombres_str = ", ".join(filter(None, nombres_list))
            trab_paterno_str = ", ".join(filter(None, paterno_list))
            trab_materno_str = ", ".join(filter(None, materno_list))
            trab_dni_str = ", ".join(filter(None, dni_list))

            ana_que_sucedio = form_data.get("ana_que_sucedio", "")
            inv_nombre_str = form_data.get("inv_nombre", "")

        datos_envio = {
            "fin_fecha_evento": fecha_evento,
            "fin_hora_evento": hora_evento,
            "fin_lugar_exacto": lugar_exacto,
            "fin_tipo_evento": tipo_evento,
            "trab_nombres": trab_nombres_str,
            "trab_paterno": trab_paterno_str,
            "trab_materno": trab_materno_str,
            "trab_dni": trab_dni_str,
            "ana_que_sucedio": ana_que_sucedio,
            "inv_nombre": inv_nombre_str,
            "lista_trabajadores": lista_trabajadores
        }

        # 1. ENVIAR REGISTRO A GOOGLE SHEETS
        codigo_comprobante = f"EMP-{ahora_peru.strftime('%Y%m%d')}-000"
        try:
            res = requests.post(GOOGLE_WEBHOOK_URL, json=datos_envio, timeout=8)
            res_json = res.json()
            if "codigo_comprobante" in res_json:
                codigo_comprobante = res_json["codigo_comprobante"]
        except Exception as err_sheet:
            print(f"Error al conectar con Google Sheets: {err_sheet}")

        # 2. CREAR EL ARCHIVO PDF
        pdf_filename = f"Reporte_{codigo_comprobante}.pdf"
        pdf_filepath = os.path.join(PDF_DIR, pdf_filename)
        generar_pdf_reporte(datos_envio, codigo_comprobante, tipo_informe, fecha_registro_str, pdf_filepath)

        # 3. MANDAR CORREO CON EL PDF ANEXADO
        correo_usuario = form_data.get("correo_destino", "").strip()
        lista_destinos = list(CORREOS_PREDETERMINADOS)
        if correo_usuario and correo_usuario not in lista_destinos:
            lista_destinos.append(correo_usuario)

        nombre_completo = f"{trab_paterno_str} {trab_materno_str} {trab_nombres_str}".strip() or "No especificado"
        asunto = f"NUEVO REGISTRO SSOMA [{codigo_comprobante}]: Informe {tipo_informe} - {nombre_completo}"
        cuerpo = f"Se ha registrado un Informe {tipo_informe}.\n\nCódigo: {codigo_comprobante}\nFecha/Hora: {fecha_registro_str}\nAfectado: {nombre_completo}\n\nAdjunto encontrará el informe en formato PDF."
        
        enviar_correo_con_pdf(lista_destinos, asunto, cuerpo, pdf_filepath)

        # 4. PANTALLA FINAL CON OPCIÓN DE DESCARGA
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
                <h2>¡Reporte Guardado Exitosamente!</h2>
                <p>Las respuestas han sido almacenadas y el PDF fue generado correctamente.</p>
                <div class="comprobante-box">
                    <p><strong>Código de Comprobante:</strong> <span class="code">{codigo_comprobante}</span></p>
                    <p><strong>Fecha y Hora:</strong> {fecha_registro_str}</p>
                    <p><strong>Afectado / Trabajador:</strong> {nombre_completo}</p>
                    <p><strong>DNI:</strong> {trab_dni_str}</p>
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

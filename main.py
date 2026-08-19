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

GOOGLE_WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbxaliz82ArStXwK5OH2lAn_wK0rp23CIvWy4cglATNt5AhV90VeucsJ7GrB1sFHYANhRw/exec"

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "")

CORREOS_PREDETERMINADOS = ["chanelone14@gmail.com", "20213543@aloe.ulima.edu.pe"]

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
        print(f"Error al enviar correo con PDF: {e}")

def generar_pdf_reporte_completo(f: dict, codigo: str, tipo_informe: str, fecha_registro: str, pdf_path: str):
    # Generar tabla de trabajadores
    filas_trabajadores = ""
    for trab in f.get("lista_trabajadores", []):
        filas_trabajadores += f"""
        <tr>
            <td>{trab['paterno']} {trab['materno']} {trab['nombres']}</td>
            <td>{trab['dni']}</td>
            <td>{trab.get('puesto', '-')}</td>
            <td>{trab.get('area', '-')}</td>
        </tr>
        """
    if not filas_trabajadores:
        filas_trabajadores = "<tr><td colspan='4'>No se registraron trabajadores</td></tr>"

    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <style>
            @page {{ size: A4; margin: 12mm 10mm; background-color: #ffffff; }}
            body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 8.5pt; color: #222; margin: 0; padding: 0; }}
            .header {{ background-color: #003366; color: white; padding: 12px; border-radius: 5px; margin-bottom: 12px; }}
            .header table {{ width: 100%; border-collapse: collapse; }}
            .title {{ font-size: 13pt; font-weight: bold; text-transform: uppercase; }}
            .subtitle {{ font-size: 8.5pt; opacity: 0.9; margin-top: 3px; }}
            .badge {{ background-color: #f0a500; color: #003366; padding: 5px 10px; font-weight: bold; font-size: 10pt; border-radius: 3px; }}
            
            .section-title {{ font-size: 9.5pt; font-weight: bold; color: #003366; border-bottom: 1.5px solid #003366; padding-bottom: 2px; margin-top: 10px; margin-bottom: 6px; text-transform: uppercase; }}
            
            .grid-table {{ width: 100%; border-collapse: collapse; margin-bottom: 8px; table-layout: fixed; }}
            .grid-table td, .grid-table th {{ border: 1px solid #cccccc; padding: 4px 6px; font-size: 8pt; vertical-align: top; word-wrap: break-word; }}
            .grid-table th {{ background-color: #f2f4f8; color: #003366; text-align: left; font-weight: bold; }}
            
            .label {{ font-weight: bold; color: #444; background-color: #f8f9fa; width: 25%; }}
            .value {{ color: #111; width: 25%; }}
            
            .text-box {{ border: 1px solid #cccccc; background-color: #fcfcfc; padding: 6px; font-size: 8pt; line-height: 1.3; min-height: 35px; border-radius: 3px; margin-bottom: 8px; }}
            .footer {{ margin-top: 15px; font-size: 7.5pt; color: #666; text-align: center; border-top: 1px solid #ddd; padding-top: 5px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <table>
                <tr>
                    <td>
                        <div class="title">EMAPE S.A. - MESA DE PARTES SSOMA</div>
                        <div class="subtitle">REGISTRO COMPLETO DE RESPUESTAS - INFORME {tipo_informe}</div>
                    </td>
                    <td style="text-align: right;">
                        <div class="badge">{codigo}</div>
                    </td>
                </tr>
            </table>
        </div>

        <div class="section-title">1. DATOS GENERALES DEL INFORME Y EVENTO</div>
        <table class="grid-table">
            <tr>
                <td class="label">Tipo de Informe:</td>
                <td class="value">{tipo_informe}</td>
                <td class="label">Fecha y Hora Registro:</td>
                <td class="value">{fecha_registro}</td>
            </tr>
            <tr>
                <td class="label">Fecha del Evento:</td>
                <td class="value">{f.get('fin_fecha_evento') or f.get('fecha_evento_pre') or '-'}</td>
                <td class="label">Hora del Evento:</td>
                <td class="value">{f.get('fin_hora_evento') or f.get('hora_ocurrencia_pre') or '-'}</td>
            </tr>
            <tr>
                <td class="label">Lugar Exacto:</td>
                <td class="value">{f.get('fin_lugar_exacto') or f.get('lugar_ocurrencia_pre') or '-'}</td>
                <td class="label">Tipo de Evento:</td>
                <td class="value">{f.get('fin_tipo_evento') or f.get('tipo_evento_pre') or '-'}</td>
            </tr>
            <tr>
                <td class="label">Gravedad del Evento:</td>
                <td class="value">{f.get('fin_gravedad_evento') or f.get('gravedad_evento_pre') or '-'}</td>
                <td class="label">Correo Notificación:</td>
                <td class="value">{f.get('correo_destino') or '-'}</td>
            </tr>
        </table>

        <div class="section-title">2. DATOS DE LOS TRABAJADORES AFECTADOS</div>
        <table class="grid-table">
            <thead>
                <tr>
                    <th>Apellidos y Nombres</th>
                    <th>DNI / Documento</th>
                    <th>Puesto / Cargo</th>
                    <th>Área / Gerencia</th>
                </tr>
            </thead>
            <tbody>
                {filas_trabajadores}
            </tbody>
        </table>

        <div class="section-title">3. ANÁLISIS DEL SUCESO Y DESCRIPCIÓN DETALLADA</div>
        <div class="text-box">
            <strong>¿Qué sucedió y cómo sucedió?:</strong><br>
            {f.get('ana_que_sucedio') or f.get('breve_descripcion_pre') or '-'}
        </div>

        <div class="section-title">4. CAUSAS DE LA INVESTIGACIÓN (INMEDIATAS Y BÁSICAS)</div>
        <table class="grid-table">
            <tr>
                <td class="label">Actos Subestándar:</td>
                <td class="value" colspan="3">{f.get('ana_actos_subestandar') or '-'}</td>
            </tr>
            <tr>
                <td class="label">Condiciones Subestándar:</td>
                <td class="value" colspan="3">{f.get('ana_condiciones_subestandar') or '-'}</td>
            </tr>
            <tr>
                <td class="label">Factores Personales:</td>
                <td class="value" colspan="3">{f.get('ana_factores_personales') or '-'}</td>
            </tr>
            <tr>
                <td class="label">Factores del Trabajo:</td>
                <td class="value" colspan="3">{f.get('ana_factores_trabajo') or '-'}</td>
            </tr>
        </table>

        <div class="section-title">5. ACCIONES CORRECTIVAS Y MEDIDAS PREVENTIVAS</div>
        <div class="text-box">
            {f.get('medidas_correctivas') or '-'}
        </div>

        <div class="section-title">6. INTEGRANTES DE LA INVESTIGACIÓN Y FIRMAS</div>
        <table class="grid-table">
            <tr>
                <td class="label">Nombre Investigador:</td>
                <td class="value">{f.get('inv_nombre') or f.get('resp_nombre_pre') or '-'}</td>
                <td class="label">Cargo Investigador:</td>
                <td class="value">{f.get('inv_cargo') or '-'}</td>
            </tr>
            <tr>
                <td class="label">Firma Digital / Nombre:</td>
                <td class="value">{f.get('firma_inv_text') or f.get('firma_pre_text') or '-'}</td>
                <td class="label">Testigos / Afectados:</td>
                <td class="value">{f.get('testigo_nombre') or '-'}</td>
            </tr>
        </table>

        <div class="footer">
            Documento integral de respuestas - Sistema de Gestión SSOMA - EMAPE S.A.
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
        form_dict = dict(form_data)

        tz_peru = zoneinfo.ZoneInfo("America/Lima")
        ahora_peru = datetime.now(tz_peru)
        fecha_registro_str = ahora_peru.strftime("%d/%m/%Y %H:%M:%S")

        tipo_informe = form_data.get("tipo_informe", "PRELIMINAR")

        # Capturar lista completa de trabajadores
        lista_trabajadores = []
        if tipo_informe == "PRELIMINAR":
            trab_nombres_str = form_data.get("nombre_lesionado_pre", "")
            lista_trabajadores.append({
                "nombres": trab_nombres_str, "paterno": "", "materno": "", "dni": "-", "puesto": "-", "area": "-"
            })
            trab_paterno_str, trab_materno_str, trab_dni_str = "", "", "N/A"
        else:
            nombres_list = form_data.getlist("trab_nombres[]") or [form_data.get("trab_nombres", "")]
            paterno_list = form_data.getlist("trab_paterno[]") or [form_data.get("trab_paterno", "")]
            materno_list = form_data.getlist("trab_materno[]") or [form_data.get("trab_materno", "")]
            dni_list = form_data.getlist("trab_dni[]") or [form_data.get("trab_dni", "")]
            puesto_list = form_data.getlist("trab_puesto[]") or [form_data.get("trab_puesto", "")]
            area_list = form_data.getlist("trab_area[]") or [form_data.get("trab_area", "")]

            for n, p, m, d, pu, ar in zip(nombres_list, paterno_list, materno_list, dni_list, puesto_list, area_list):
                if n or p or d:
                    lista_trabajadores.append({
                        "nombres": n, "paterno": p, "materno": m, "dni": d, "puesto": pu, "area": ar
                    })

            trab_nombres_str = ", ".join(filter(None, nombres_list))
            trab_paterno_str = ", ".join(filter(None, paterno_list))
            trab_materno_str = ", ".join(filter(None, materno_list))
            trab_dni_str = ", ".join(filter(None, dni_list))

        form_dict["lista_trabajadores"] = lista_trabajadores

        # 1. ENVÍO A GOOGLE SHEETS
        datos_sheet = {
            "fin_fecha_evento": form_data.get("fin_fecha_evento") or form_data.get("fecha_evento_pre", ""),
            "fin_hora_evento": form_data.get("fin_hora_evento") or form_data.get("hora_ocurrencia_pre", ""),
            "fin_lugar_exacto": form_data.get("fin_lugar_exacto") or form_data.get("lugar_ocurrencia_pre", ""),
            "fin_tipo_evento": form_data.get("fin_tipo_evento") or form_data.get("tipo_evento_pre", ""),
            "trab_nombres": trab_nombres_str,
            "trab_paterno": trab_paterno_str,
            "trab_materno": trab_materno_str,
            "trab_dni": trab_dni_str,
            "ana_que_sucedio": form_data.get("ana_que_sucedio") or form_data.get("breve_descripcion_pre", ""),
            "inv_nombre": form_data.get("inv_nombre") or form_data.get("resp_nombre_pre", "")
        }

        codigo_comprobante = f"EMP-{ahora_peru.strftime('%Y%m%d')}-000"
        try:
            res = requests.post(GOOGLE_WEBHOOK_URL, json=datos_sheet, timeout=8)
            res_json = res.json()
            if "codigo_comprobante" in res_json:
                codigo_comprobante = res_json["codigo_comprobante"]
        except Exception as err_sheet:
            print(f"Error Google Sheets: {err_sheet}")

        # 2. GENERAR PDF COMPLETO DE TODAS LAS PREGUNTAS
        pdf_filename = f"Reporte_{codigo_comprobante}.pdf"
        pdf_filepath = os.path.join(PDF_DIR, pdf_filename)
        generar_pdf_reporte_completo(form_dict, codigo_comprobante, tipo_informe, fecha_registro_str, pdf_filepath)

        # 3. CORREO ELECTRÓNICO CON ADJUNTO PDF
        correo_usuario = form_data.get("correo_destino", "").strip()
        lista_destinos = list(CORREOS_PREDETERMINADOS)
        if correo_usuario and correo_usuario not in lista_destinos:
            lista_destinos.append(correo_usuario)

        nombre_completo = f"{trab_paterno_str} {trab_materno_str} {trab_nombres_str}".strip() or "No especificado"
        asunto = f"NUEVO REGISTRO SSOMA [{codigo_comprobante}]: Informe {tipo_informe} - {nombre_completo}"
        cuerpo = f"Se ha registrado un Informe {tipo_informe}.\n\nCódigo: {codigo_comprobante}\nFecha/Hora: {fecha_registro_str}\nAfectado: {nombre_completo}\n\nAdjunto encontrará el informe completo en formato PDF."
        
        enviar_correo_con_pdf(lista_destinos, asunto, cuerpo, pdf_filepath)

        # 4. PANTALLA DE CONFIRMACIÓN
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
                <p>Todas las respuestas del formulario han sido compiladas en el PDF oficial.</p>
                <div class="comprobante-box">
                    <p><strong>Código de Comprobante:</strong> <span class="code">{codigo_comprobante}</span></p>
                    <p><strong>Fecha y Hora:</strong> {fecha_registro_str}</p>
                    <p><strong>Afectado / Trabajador:</strong> {nombre_completo}</p>
                    <p><strong>DNI:</strong> {trab_dni_str}</p>
                </div>
                <div class="btn-group">
                    <a href="/descargar-pdf/{pdf_filename}" class="btn btn-success" target="_blank">📥 Descargar PDF Completo</a>
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

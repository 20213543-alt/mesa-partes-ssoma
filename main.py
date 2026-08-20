import os
import io
import base64
import smtplib
from datetime import datetime
from zoneinfo import ZoneInfo
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

import requests
from PIL import Image
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from xhtml2pdf import pisa

app = FastAPI(title="Sistema de Registro e Investigación de Accidentes/Incidentes")

# Carpeta local para almacenar PDFs generados de forma temporal
PDF_DIR = "pdf_reports"
os.makedirs(PDF_DIR, exist_ok=True)

# Montar archivos estáticos y plantillas
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Configuración de Servidor SMTP (Credenciales desde variables de entorno)
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# URL Webhook de Google Apps Script para el informe final
GAS_WEBHOOK_URL = os.getenv("GAS_WEBHOOK_URL", "")

# DESTINATARIO FIJO CONFIGURADO
DESTINATARIO_AUTOMATICO = ["s.espinozav_ext@emape.gob.pe"]


def optimizar_imagen_base64(base64_str: str, max_size=(700, 700), quality=70) -> str:
    """Optimiza y comprime imágenes para reducir carga en memoria al crear el PDF."""
    if not base64_str:
        return ""
    try:
        if "," in base64_str:
            base64_str = base64_str.split(",")[1]
        img_bytes = base64.b64decode(base64_str)
        img = Image.open(io.BytesIO(img_bytes))
        
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
            
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality)
        return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception as e:
        print(f"Error optimizando imagen: {e}")
        return ""


def enviar_correo_con_pdf(pdf_path: str, codigo_reporte: str, tipo_informe: str):
    """Envia el PDF adjunto al correo oficial sin intervención del usuario."""
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print("ADVERTENCIA: No se configuraron las credenciales SENDER_EMAIL o SENDER_PASSWORD en Render.")
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = ", ".join(DESTINATARIO_AUTOMATICO)
        msg['Subject'] = f"[{tipo_informe.upper()}] Reporte de Incidente/Accidente - {codigo_reporte}"

        cuerpo = (
            f"Estimados,\n\n"
            f"Se ha generado un nuevo {tipo_informe} en el sistema SSOMA.\n"
            f"Código de registro: {codigo_reporte}\n\n"
            f"Se adjunta el reporte oficial en formato PDF.\n\n"
            f"Atentamente,\n"
            f"Sistema de Gestión SSOMA"
        )
        msg.attach(MIMEText(cuerpo, 'plain'))

        with open(pdf_path, "rb") as f:
            adjunto = MIMEApplication(f.read(), _subtype="pdf")
            adjunto.add_header("Content-Disposition", "attachment", filename=os.path.basename(pdf_path))
            msg.attach(adjunto)

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"Correo enviado exitosamente a {DESTINATARIO_AUTOMATICO}")
        return True
    except Exception as e:
        print(f"Error enviando el correo electrónico: {e}")
        return False


@app.get("/", response_class=HTMLResponse)
async def leer_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/enviar-reporte")
async def procesar_reporte(request: Request):
    try:
        form_data = await request.form()
        tipo_informe = form_data.get("tipo_informe", "Informe Final")
        
        # 1. Obtener la Hora Oficial de Perú (America/Lima)
        ahora_peru = datetime.now(ZoneInfo("America/Lima"))
        fecha_peru_str = ahora_peru.strftime("%Y-%m-%d")
        
        codigo_comprobante = ""
        
        # 2. Lógica para generar código según tipo de informe
        if tipo_informe == "Informe Preliminar":
            codigo_comprobante = "PRE-" + ahora_peru.strftime("%Y%m%d%H%M%S")
        else:
            # Petición a Google Apps Script para registrar y obtener correlativo
            payload_gas = {
                "fin_fecha_evento": form_data.get("fin_fecha_evento", ""),
                "fin_hora_evento": form_data.get("fin_hora_evento", ""),
                "fin_lugar_exacto": form_data.get("fin_lugar_exacto", ""),
                "fin_tipo_evento": form_data.get("fin_tipo_evento", ""),
                "trab_nombres": form_data.get("trab_nombres", ""),
                "trab_paterno": form_data.get("trab_paterno", ""),
                "trab_materno": form_data.get("trab_materno", ""),
                "trab_dni": form_data.get("trab_dni", ""),
                "ana_que_sucedio": form_data.get("ana_que_sucedio", ""),
                "inv_nombre": form_data.get("inv_nombre", "")
            }
            
            if GAS_WEBHOOK_URL:
                try:
                    res = requests.post(GAS_WEBHOOK_URL, json=payload_gas, timeout=10)
                    if res.status_code == 200:
                        data_res = res.json()
                        codigo_comprobante = data_res.get("codigo_comprobante", "")
                except Exception as err_gas:
                    print(f"Error comunicando con Google Sheets: {err_gas}")
            
            if not codigo_comprobante:
                codigo_comprobante = "EMP-" + fecha_peru_str + "-000"

        # 3. Procesar Listas Dinámicas
        ci_tipos = form_data.getlist("ci_tipo[]")
        ci_causas = form_data.getlist("ci_causa[]")
        ci_obss = form_data.getlist("ci_obs[]")
        causas_inmediatas = list(zip(ci_tipos, ci_causas, ci_obss))

        cb_tipos = form_data.getlist("cb_tipo[]")
        cb_causas = form_data.getlist("cb_causa[]")
        cb_subyacentes = form_data.getlist("cb_subyacente[]")
        cb_obss = form_data.getlist("cb_obs[]")
        causas_basicas = list(zip(cb_tipos, cb_causas, cb_subyacentes, cb_obss))

        mc_tipos = form_data.getlist("mc_tipo[]")
        mc_acciones = form_data.getlist("mc_accion[]")
        mc_responsables = form_data.getlist("mc_responsable[]")
        mc_fechas = form_data.getlist("mc_fecha[]")
        mc_situaciones = form_data.getlist("mc_situacion[]")
        mc_obss = form_data.getlist("mc_obs[]")
        medidas_correctivas = list(zip(mc_tipos, mc_acciones, mc_responsables, mc_fechas, mc_situaciones, mc_obss))

        # 4. Procesar y Optimizar Fotografías Evidencia
        fotos_raw = form_data.getlist("fotos_evidencia_base64[]")
        fotos_optimizadas = [optimizar_imagen_base64(f) for f in fotos_raw if f]

        # Contexto completo para renderizar el HTML del PDF
        contexto_pdf = {
            "codigo_comprobante": codigo_comprobante,
            "tipo_informe": tipo_informe,
            "fecha_reporte": fecha_peru_str,
            "form": form_data,
            "causas_inmediatas": causas_inmediatas,
            "causas_basicas": causas_basicas,
            "medidas_correctivas": medidas_correctivas,
            "fotos": fotos_optimizadas
        }

        # 5. Generar PDF con xhtml2pdf
        html_content = templates.get_template("pdf_template.html").render(contexto_pdf)
        pdf_filename = f"Reporte_{codigo_comprobante}.pdf"
        pdf_path = os.path.join(PDF_DIR, pdf_filename)

        with open(pdf_path, "wb") as pdf_file:
            pisa.CreatePDF(io.StringIO(html_content), dest=pdf_file)

        # 6. Enviar Correo Automático a s.espinozav_ext@emape.gob.pe
        enviar_correo_con_pdf(pdf_path, codigo_comprobante, tipo_informe)

        # 7. Respuesta JSON para visualización/descarga directa
        return JSONResponse({
            "status": "success",
            "message": "Reporte registrado y enviado con éxito.",
            "codigo": codigo_comprobante,
            "pdf_url": f"/descargar-pdf/{pdf_filename}"
        })

    except Exception as e:
        print(f"Error procesando reporte: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/descargar-pdf/{filename}")
async def descargar_pdf(filename: str):
    file_path = os.path.join(PDF_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type='application/pdf', filename=filename)
    return JSONResponse({"error": "Archivo no encontrado"}, status_code=404)

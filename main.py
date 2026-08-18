import os
import smtplib
import requests
import traceback
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
import openpyxl

app = FastAPI()

GOOGLE_WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbxaliz82ArStXwK5OH2lAn_wK0rp23CIvWy4cglATNt5AhV90VeucsJ7GrB1sFHYANhRw/exec"
PLANTILLA_PATH = "INFORME DE ACCIDENTES (1).xlsx"

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "")

CORREOS_NOTIFICACION = ["chanelone14@gmail.com", "20213543@aloe.ulima.edu.pe"]

def enviar_correo_notificacion(asunto: str, cuerpo: str):
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        return

    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = ", ".join(CORREOS_NOTIFICACION)
        msg['Subject'] = asunto
        msg.attach(MIMEText(cuerpo, 'plain'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=5)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, CORREOS_NOTIFICACION, msg.as_string())
        server.quit()
    except Exception as e:
        print(f"Error al enviar correo: {e}")

@app.get("/", response_class=HTMLResponse)
def home():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Servidor SSOMA activo</h1>"

@app.post("/enviar-reporte")
async def enviar_reporte(request: Request):
    try:
        form_data = await request.form()

        # Extraer variables con soporte para arreglos o valores individuales
        fin_fecha_evento = form_data.get("fin_fecha_evento", "")
        fin_hora_evento = form_data.get("fin_hora_evento", "")
        fin_lugar_exacto = form_data.get("fin_lugar_exacto", "")
        fin_tipo_evento = form_data.get("fin_tipo_evento", "")
        
        trab_nombres = form_data.get("trab_nombres") or form_data.get("trab_nombres[]") or ""
        trab_paterno = form_data.get("trab_paterno") or form_data.get("trab_paterno[]") or ""
        trab_materno = form_data.get("trab_materno") or form_data.get("trab_materno[]") or ""
        trab_dni = form_data.get("trab_dni") or form_data.get("trab_dni[]") or ""
        
        ana_que_sucedio = form_data.get("ana_que_sucedio", "")
        inv_nombre = form_data.get("inv_nombre") or form_data.get("inv_nombre[]") or ""

        # Objeto mapeado exacto para Google Sheets
        datos_envio = {
            "fin_fecha_evento": fin_fecha_evento,
            "fin_hora_evento": fin_hora_evento,
            "fin_lugar_exacto": fin_lugar_exacto,
            "fin_tipo_evento": fin_tipo_evento,
            "trab_nombres": trab_nombres,
            "trab_paterno": trab_paterno,
            "trab_materno": trab_materno,
            "trab_dni": trab_dni,
            "ana_que_sucedio": ana_que_sucedio,
            "inv_nombre": inv_nombre
        }

        # 1. ENVIAR A GOOGLE SHEETS
        try:
            requests.post(GOOGLE_WEBHOOK_URL, json=datos_envio, timeout=8)
        except Exception as err_sheet:
            print(f"Error al enviar a Google Sheets: {err_sheet}")

        # Llenar Excel para descarga
        if os.path.exists(PLANTILLA_PATH):
            wb = openpyxl.load_workbook(PLANTILLA_PATH)
            ws = wb.active
        else:
            wb = openpyxl.Workbook()
            ws = wb.active

        ws['C30'] = fin_fecha_evento
        ws['C31'] = fin_hora_evento
        ws['R30'] = fin_lugar_exacto

        nombre_completo = f"{trab_paterno} {trab_materno} {trab_nombres}".strip() or "Anónimo"
        asunto = f"NUEVO REGISTRO SSOMA: Informe Final - {nombre_completo}"
        cuerpo = f"Se ha registrado un Informe Final de Accidente.\nTrabajador: {nombre_completo}\nDNI: {trab_dni}\nFecha: {fin_fecha_evento}"
        nombre_archivo = "Informe_Final.xlsx"

        wb.save(nombre_archivo)
        
        # 2. ENVIAR CORREO DE NOTIFICACIÓN
        enviar_correo_notificacion(asunto, cuerpo)

        return FileResponse(
            path=nombre_archivo,
            filename=nombre_archivo,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except Exception as e:
        error_detallado = traceback.format_exc()
        return JSONResponse(status_code=500, content={"error": str(e), "trace": error_detallado})

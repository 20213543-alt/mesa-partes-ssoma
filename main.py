import os
import smtplib
import traceback
from typing import List, Optional
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
import openpyxl

app = FastAPI()

PLANTILLA_PATH = "INFORME DE ACCIDENTES (1).xlsx"
HISTORICO_PATH = "RESPUESTAS_SSOMA.xlsx"

# Configuración de correo
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "")

CORREOS_NOTIFICACION = ["chanelone14@gmail.com", "20213543@aloe.ulima.edu.pe"]

def guardar_en_historico(datos: list):
    """Crea el archivo si no existe y añade la fila"""
    try:
        if not os.path.exists(HISTORICO_PATH):
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Consolidado"
            ws.append(["Tipo Informe", "Fecha Evento", "Hora", "Afectado/Lesionado", "DNI", "Lugar", "Tipo Evento"])
        else:
            wb = openpyxl.load_workbook(HISTORICO_PATH)
            ws = wb.active

        ws.append(datos)
        wb.save(HISTORICO_PATH)
    except Exception as e:
        print(f"Error al guardar en el Excel histórico: {e}")

def enviar_correo_notificacion(asunto: str, cuerpo: str):
    """Envía correo con timeout seguro"""
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
    return "<h1>El archivo index.html no existe en el servidor.</h1>"

@app.post("/enviar-reporte")
def enviar_reporte(
    tipo_informe: str = Form("PRELIMINAR"),
    tipo_evento_pre: Optional[str] = Form(None),
    fecha_evento_pre: Optional[str] = Form(None),
    hora_ocurrencia_pre: Optional[str] = Form(None),
    lugar_ocurrencia_pre: Optional[str] = Form(None),
    fecha_reporte_pre: Optional[str] = Form(None),
    trabajo_realizaba_pre: Optional[str] = Form(None),
    nombre_lesionado_pre: Optional[str] = Form(None),
    edad_lesionado_pre: Optional[str] = Form(None),
    cargo_lesionado_pre: Optional[str] = Form(None),
    breve_descripcion_pre: Optional[str] = Form(None),
    resp_nombre_pre: Optional[str] = Form(None),

    fin_fecha_evento: Optional[str] = Form(None),
    fin_hora_evento: Optional[str] = Form(None),
    fin_lugar_exacto: Optional[str] = Form(None),
    fin_tipo_evento: Optional[str] = Form(None),
    trab_paterno: List[str] = Form([]),
    trab_nombres: List[str] = Form([]),
    trab_dni: List[str] = Form([])
):
    try:
        # Cargar plantilla o crear libro limpio si falla
        if os.path.exists(PLANTILLA_PATH):
            wb = openpyxl.load_workbook(PLANTILLA_PATH)
            ws = wb.active  # Selecciona la primera hoja activa automáticamente
        else:
            wb = openpyxl.Workbook()
            ws = wb.active

        if tipo_informe == "PRELIMINAR":
            ws['C4'] = tipo_evento_pre or ""
            ws['C6'] = fecha_evento_pre or ""
            ws['J6'] = hora_ocurrencia_pre or ""
            ws['C7'] = lugar_ocurrencia_pre or ""
            ws['J7'] = fecha_reporte_pre or ""
            ws['C8'] = trabajo_realizaba_pre or ""
            ws['C10'] = nombre_lesionado_pre or ""
            ws['E10'] = edad_lesionado_pre or ""
            ws['F10'] = cargo_lesionado_pre or ""
            ws['C12'] = breve_descripcion_pre or ""
            ws['C20'] = resp_nombre_pre or ""
            
            guardar_en_historico([
                "PRELIMINAR", fecha_evento_pre, hora_ocurrencia_pre, 
                nombre_lesionado_pre, "-", lugar_ocurrencia_pre, tipo_evento_pre
            ])
            
            asunto = f"NUEVO REGISTRO SSOMA: Informe Preliminar - {nombre_lesionado_pre or 'Anonimo'}"
            cuerpo = f"Se ha registrado un Informe Preliminar.\nTrabajador: {nombre_lesionado_pre}\nFecha: {fecha_evento_pre}"
            nombre_archivo = f"Informe_Preliminar.xlsx"

        else:
            ws['C30'] = fin_fecha_evento or ""
            ws['C31'] = fin_hora_evento or ""
            ws['R30'] = fin_lugar_exacto or ""

            nombre_completo = f"{trab_paterno[0] if trab_paterno else ''} {trab_nombres[0] if trab_nombres else ''}"
            dni = trab_dni[0] if trab_dni else ""

            guardar_en_historico([
                "FINAL", fin_fecha_evento, fin_hora_evento, 
                nombre_completo, dni, fin_lugar_exacto, fin_tipo_evento
            ])

            asunto = f"NUEVO REGISTRO SSOMA: Informe Final - {nombre_completo}"
            cuerpo = f"Se ha registrado un Informe Final de Accidente.\nTrabajador: {nombre_completo}\nFecha: {fin_fecha_evento}"
            nombre_archivo = f"Informe_Final.xlsx"

        wb.save(nombre_archivo)
        
        # Enviar correo de notificación
        enviar_correo_notificacion(asunto, cuerpo)

        return FileResponse(
            path=nombre_archivo,
            filename=nombre_archivo,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except Exception as e:
        error_detallado = traceback.format_exc()
        print(error_detallado)
        return JSONResponse(status_code=500, content={"error": str(e), "trace": error_detallado})

@app.get("/descargar-historico")
def descargar_historico():
    if os.path.exists(HISTORICO_PATH):
        return FileResponse(HISTORICO_PATH, filename="RESPUESTAS_SSOMA.xlsx")
    return {"mensaje": "Aún no hay respuestas registradas en el histórico."}

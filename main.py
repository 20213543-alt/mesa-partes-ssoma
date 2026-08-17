import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, FileResponse
import openpyxl

app = FastAPI()

PLANTILLA_PATH = "INFORME DE ACCIDENTES (1).xlsx"

@app.get("/", response_class=HTMLResponse)
def home():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/enviar-reporte")
def enviar_reporte(
    tipo_evento: str = Form(...),
    fecha_evento: str = Form(...),
    hora_evento: str = Form(...),
    nombre_lesionado: str = Form(...),
    edad: str = Form(...),
    cargo: str = Form(...),
    acto_subestandar: str = Form(""),
    condicion_subestandar: str = Form(""),
    descripcion: str = Form(""),
    correo_destino: str = Form(...)
):
    wb = openpyxl.load_workbook(PLANTILLA_PATH)
    ws_pre = wb['INFORME_PRELIMINAR']

    ws_pre['C4'] = tipo_evento
    ws_pre['C6'] = fecha_evento
    ws_pre['J8'] = hora_evento
    ws_pre['C10'] = nombre_lesionado
    ws_pre['E10'] = edad
    ws_pre['F10'] = cargo
    ws_pre['C15'] = descripcion

    if 'T_FACTORES' in wb.sheetnames:
        ws_fact = wb['T_FACTORES']
        ws_fact['B4'] = acto_subestandar
        ws_fact['B5'] = condicion_subestandar

    nombre_archivo = f"Informe_SSOMA_{nombre_lesionado.replace(' ', '_')}.xlsx"
    wb.save(nombre_archivo)

    remitente = os.environ.get("CORREO_REMITENTE")
    password = os.environ.get("PASSWORD_REMITENTE")

    if remitente and password:
        try:
            msg = MIMEMultipart()
            msg['From'] = remitente
            msg['To'] = correo_destino
            msg['Subject'] = f"REPORTE SSOMA EMAPE: {tipo_evento} - {nombre_lesionado}"

            with open(nombre_archivo, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f"attachment; filename={nombre_archivo}")
                msg.attach(part)

            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(remitente, password)
            server.send_message(msg)
            server.quit()
        except Exception as e:
            print(f"Error al enviar correo: {e}")

    return FileResponse(
        path=nombre_archivo,
        filename=nombre_archivo,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

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
    no_informe: str = Form(""),
    fecha_informe: str = Form(""),
    tipo_evento: str = Form(""),
    nombre_trabajador: str = Form(...),
    dni: str = Form(""),
    edad: str = Form(""),
    area: str = Form(""),
    puesto: str = Form(""),
    fecha_evento: str = Form(""),
    hora_evento: str = Form(""),
    lugar_exacto: str = Form(""),
    descripcion_suceso: str = Form(""),
    correo_destino: str = Form(...)
):
    wb = openpyxl.load_workbook(PLANTILLA_PATH)
    ws = wb.active

    # Inyección de datos a las celdas del formato oficial
    ws['D6'] = no_informe
    ws['R6'] = fecha_informe
    ws['D7'] = tipo_evento
    ws['D23'] = nombre_trabajador
    ws['C24'] = dni
    ws['N24'] = edad
    ws['C25'] = area
    ws['C26'] = puesto
    ws['C30'] = fecha_evento
    ws['C31'] = hora_evento
    ws['N30'] = lugar_exacto
    ws['A39'] = descripcion_suceso

    nombre_archivo = f"Registro_{nombre_trabajador.replace(' ', '_')}.xlsx"
    wb.save(nombre_archivo)

    return FileResponse(
        path=nombre_archivo,
        filename=nombre_archivo,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

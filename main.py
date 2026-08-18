import os
import smtplib
import traceback
import zoneinfo
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()

# Definir rutas absolutas para evitar fallos de ubicación en servidores Linux
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

# Crear directorios si no existen en Render
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

# Montar archivos estáticos y plantillas
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Configuración de correo SMTP
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "tu_correo@gmail.com"  # Configurar con tu correo emisor
SMTP_PASSWORD = "tu_contrasena_de_aplicacion"  # Configurar contraseña de aplicación

CORREOS_DESTINO = ["chanelone14@gmail.com", "sebastianstalin19@gmail.com"]


def enviar_correo_con_adjunto(asunto: str, cuerpo: str, adjunto_bytes: bytes = None, nombre_adjunto: str = "reporte.pdf"):
    msg = MIMEMultipart()
    msg["From"] = SMTP_USER
    msg["To"] = ", ".join(CORREOS_DESTINO)
    msg["Subject"] = asunto
    msg.attach(MIMEText(cuerpo, "plain"))

    if adjunto_bytes:
        part = MIMEApplication(adjunto_bytes, Name=nombre_adjunto)
        part["Content-Disposition"] = f'attachment; filename="{nombre_adjunto}"'
        msg.attach(part)

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, CORREOS_DESTINO, msg.as_string())


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Verifica si index.html existe antes de renderizar para prevenir errores 500."""
    index_path = os.path.join(TEMPLATES_DIR, "index.html")
    if not os.path.exists(index_path):
        return HTMLResponse(
            content="""
            <div style='font-family: sans-serif; text-align: center; padding: 40px;'>
                <h2 style='color: #dc2626;'>Falta el archivo index.html</h2>
                <p>Crea la carpeta <b>templates</b> y coloca el archivo <b>index.html</b> adentro.</p>
            </div>
            """,
            status_code=500
        )
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/enviar-reporte-preliminar", response_class=HTMLResponse)
async def enviar_reporte_preliminar(request: Request, pdf_file: UploadFile = File(None)):
    try:
        form_data = await request.form()
        try:
            tz_peru = zoneinfo.ZoneInfo("America/Lima")
            ahora_peru = datetime.now(tz_peru)
        except Exception:
            ahora_peru = datetime.now()

        fecha_registro_str = ahora_peru.strftime("%d/%m/%Y %H:%M:%S")
        nombre_lesionado = form_data.get("nombre_lesionado_pre") or "No especificado"
        fecha_evento = form_data.get("fecha_evento_pre") or "No especificada"
        tipo_evento = form_data.get("tipo_evento_pre") or "No especificado"
        codigo_comprobante = f"PRE-{ahora_peru.strftime('%Y%m%d')}-{ahora_peru.strftime('%H%M%S')}"

        pdf_bytes = await pdf_file.read() if pdf_file else None

        asunto = f"INFORME PRELIMINAR SSOMA [{codigo_comprobante}]: {nombre_lesionado}"
        cuerpo = f"""Se ha generado un nuevo Informe Preliminar de Accidente/Incidente.

Código de Comprobante: {codigo_comprobante}
Fecha y Hora de Registro: {fecha_registro_str}
Lesionado/Afectado: {nombre_lesionado}
Fecha del Evento: {fecha_evento}
Tipo de Evento: {tipo_evento}
"""
        enviar_correo_con_adjunto(
            asunto=asunto,
            cuerpo=cuerpo,
            adjunto_bytes=pdf_bytes,
            nombre_adjunto=f"Informe_Preliminar_{codigo_comprobante}.pdf"
        )

        return HTMLResponse(content=f"""
            <div style='font-family: sans-serif; text-align: center; padding: 40px;'>
                <h2 style='color: #16a34a;'>¡Informe Preliminar Enviado!</h2>
                <p>Código: <b>{codigo_comprobante}</b></p>
                <a href='/' style='display: inline-block; background: #1d4ed8; color: white; padding: 10px 20px; border-radius: 5px; text-decoration: none;'>Volver</a>
            </div>
        """, status_code=200)

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e), "trace": traceback.format_exc()})


@app.post("/enviar-reporte", response_class=HTMLResponse)
async def enviar_reporte_final(request: Request):
    try:
        form_data = await request.form()
        try:
            tz_peru = zoneinfo.ZoneInfo("America/Lima")
            ahora_peru = datetime.now(tz_peru)
        except Exception:
            ahora_peru = datetime.now()

        fecha_registro_str = ahora_peru.strftime("%d/%m/%Y %H:%M:%S")
        codigo_comprobante = f"FIN-{ahora_peru.strftime('%Y%m%d')}-{ahora_peru.strftime('%H%M%S')}"

        asunto = f"INFORME FINAL SSOMA [{codigo_comprobante}]"
        cuerpo = f"""Se ha registrado un nuevo Informe Final de Accidente/Incidente.

Código de Comprobante: {codigo_comprobante}
Fecha y Hora de Registro: {fecha_registro_str}
Lugar Exacto: {form_data.get('fin_lugar_exacto', 'N/A')}
Tipo de Evento: {form_data.get('fin_tipo_evento', 'N/A')}
Investigador: {form_data.get('inv_nombre', 'N/A')}
"""
        enviar_correo_con_adjunto(asunto=asunto, cuerpo=cuerpo)
        return HTMLResponse(content=f"<h2>¡Informe Final {codigo_comprobante} registrado con éxito!</h2><a href='/'>Volver</a>")

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e), "trace": traceback.format_exc()})

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

# Configurar archivos estáticos y plantillas si existen en tu proyecto
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ==========================================
# CONFIGURACIÓN DE CORREO SMTP
# ==========================================
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "tu_correo@gmail.com"  # Reemplaza con tu correo emisor
SMTP_PASSWORD = "tu_contrasena_de_aplicacion"  # Reemplaza con tu contraseña de aplicación

# Lista fija de correos destino
CORREOS_DESTINO = ["chanelone14@gmail.com", "sebastianstalin19@gmail.com"]


def enviar_correo_con_adjunto(asunto: str, cuerpo: str, adjunto_bytes: bytes = None, nombre_adjunto: str = "reporte.pdf"):
    """Función auxiliar para enviar correos a la lista de destinos fijos."""
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
    """Renderiza la página principal del formulario."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/enviar-reporte-preliminar", response_class=HTMLResponse)
async def enviar_reporte_preliminar(
    request: Request,
    pdf_file: UploadFile = File(None)
):
    """Procesa la captura en PDF del Informe Preliminar y la envía por correo."""
    try:
        form_data = await request.form()

        # Obtener fecha/hora segura para Perú
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

        pdf_bytes = None
        if pdf_file:
            pdf_bytes = await pdf_file.read()

        asunto = f"INFORME PRELIMINAR SSOMA [{codigo_comprobante}]: {nombre_lesionado}"
        cuerpo = f"""Se ha generado un nuevo Informe Preliminar de Accidente/Incidente.

Código de Comprobante: {codigo_comprobante}
Fecha y Hora de Registro: {fecha_registro_str}
Lesionado/Afectado: {nombre_lesionado}
Fecha del Evento: {fecha_evento}
Tipo de Evento: {tipo_evento}

Se adjunta a este correo la captura visual completa del informe en formato PDF.
"""
        enviar_correo_con_adjunto(
            asunto=asunto,
            cuerpo=cuerpo,
            adjunto_bytes=pdf_bytes,
            nombre_adjunto=f"Informe_Preliminar_{codigo_comprobante}.pdf"
        )

        html_confirmacion = f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Informe Preliminar Enviado</title>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #0f172a; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; color: #333; }}
                .card {{ background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.3); max-width: 500px; width: 90%; text-align: center; }}
                .icon {{ font-size: 50px; color: #16a34a; margin-bottom: 10px; }}
                h2 {{ color: #0f172a; margin-bottom: 20px; }}
                .comprobante-box {{ background-color: #f1f5f9; border-left: 5px solid #16a34a; padding: 15px; text-align: left; margin: 20px 0; border-radius: 4px; }}
                .comprobante-box p {{ margin: 5px 0; font-size: 14px; color: #334155; }}
                .code {{ font-weight: bold; font-size: 16px; color: #16a34a; }}
                .btn {{ display: inline-block; background-color: #1d4ed8; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin-top: 15px; font-weight: bold; }}
                .btn:hover {{ background-color: #1e40af; }}
            </style>
        </head>
        <body>
            <div class="card">
                <div class="icon">✓</div>
                <h2>¡Informe Preliminar Enviado!</h2>
                <p>Se realizó la captura en PDF del informe y se envió correctamente por correo.</p>
                
                <div class="comprobante-box">
                    <p><strong>Código de Comprobante:</strong> <span class="code">{codigo_comprobante}</span></p>
                    <p><strong>Fecha y Hora:</strong> {fecha_registro_str}</p>
                    <p><strong>Lesionado:</strong> {nombre_lesionado}</p>
                    <p><strong>Destinatarios:</strong> chanelone14@gmail.com, sebastianstalin19@gmail.com</p>
                </div>

                <a href="/" class="btn">Volver al Formulario</a>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_confirmacion, status_code=200)

    except Exception as e:
        error_detallado = traceback.format_exc()
        return JSONResponse(status_code=500, content={"error": str(e), "trace": error_detallado})


@app.post("/enviar-reporte", response_class=HTMLResponse)
async def enviar_reporte_final(request: Request):
    """Procesa el Informe Final de Accidente."""
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
        error_detallado = traceback.format_exc()
        return JSONResponse(status_code=500, content={"error": str(e), "trace": error_detallado})

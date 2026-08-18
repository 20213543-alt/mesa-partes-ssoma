import os
import smtplib
import requests
import traceback
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI()

GOOGLE_WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbxaliz82ArStXwK5OH2lAn_wK0rp23CIvWy4cglATNt5AhV90VeucsJ7GrB1sFHYANhRw/exec"

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

@app.post("/enviar-reporte", response_class=HTMLResponse)
async def enviar_reporte(request: Request):
    try:
        form_data = await request.form()

        ahora = datetime.now()
        fecha_registro_str = ahora.strftime("%d/%m/%Y %H:%M:%S")

        # Extraer variables
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

        # 1. ENVIAR A GOOGLE SHEETS Y OBTENER EL CÓDIGO CORRELATIVO
        codigo_comprobante = f"EMP-{ahora.strftime('%Y%m%d')}-000" # Valor respaldo
        try:
            res = requests.post(GOOGLE_WEBHOOK_URL, json=datos_envio, timeout=8)
            res_json = res.json()
            if "codigo_comprobante" in res_json:
                codigo_comprobante = res_json["codigo_comprobante"]
        except Exception as err_sheet:
            print(f"Error al enviar a Google Sheets: {err_sheet}")

        nombre_completo = f"{trab_paterno} {trab_materno} {trab_nombres}".strip() or "Anónimo"
        
        # 2. ENVIAR CORREO DE NOTIFICACIÓN
        asunto = f"NUEVO REGISTRO SSOMA [{codigo_comprobante}]: Informe Final - {nombre_completo}"
        cuerpo = f"Se ha registrado un Informe Final de Accidente.\n\nCódigo de Comprobante: {codigo_comprobante}\nFecha de Registro: {fecha_registro_str}\nTrabajador: {nombre_completo}\nDNI: {trab_dni}\nFecha Evento: {fin_fecha_evento}"
        enviar_correo_notificacion(asunto, cuerpo)

        # 3. MOSTRAR PANTALLA DE CONFIRMACIÓN EN LA WEB
        html_confirmacion = f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Reporte Registrado Exitosamente</title>
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background-color: #f4f7f6;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    margin: 0;
                }}
                .card {{
                    background: white;
                    padding: 30px;
                    border-radius: 12px;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                    max-width: 500px;
                    width: 90%;
                    text-align: center;
                }}
                .icon {{
                    font-size: 50px;
                    color: #28a745;
                    margin-bottom: 10px;
                }}
                h2 {{ color: #333; margin-bottom: 20px; }}
                .comprobante-box {{
                    background-color: #e9ecef;
                    border-left: 5px solid #007bff;
                    padding: 15px;
                    text-align: left;
                    margin: 20px 0;
                    border-radius: 4px;
                }}
                .comprobante-box p {{ margin: 5px 0; font-size: 14px; color: #495057; }}
                .code {{ font-weight: bold; font-size: 16px; color: #007bff; }}
                .btn {{
                    display: inline-block;
                    background-color: #007bff;
                    color: white;
                    padding: 10px 20px;
                    text-decoration: none;
                    border-radius: 5px;
                    margin-top: 15px;
                    font-weight: bold;
                }}
                .btn:hover {{ background-color: #0056b3; }}
            </style>
        </head>
        <body>
            <div class="card">
                <div class="icon">✓</div>
                <h2>¡Reporte Enviado con Éxito!</h2>
                <p>El informe ha sido registrado correctamente en la base de datos de SSOMA.</p>
                
                <div class="comprobante-box">
                    <p><strong>Código de Comprobante:</strong> <span class="code">{codigo_comprobante}</span></p>
                    <p><strong>Fecha y Hora de Registro:</strong> {fecha_registro_str}</p>
                    <p><strong>Afectado / Trabajador:</strong> {nombre_completo}</p>
                    <p><strong>DNI:</strong> {trab_dni}</p>
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

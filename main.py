import os
import io
import base64
import smtplib
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import List, Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from xhtml2pdf import pisa

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

app = FastAPI(
    title="Mesa de Partes SSOMA - EMAPE S.A.",
    description="Sistema de Registro y Generación de Informes SSOMA",
    version="2.0.0"
)

# Permitir CORS para peticiones desde cualquier origen
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directori local temporal para guardar los PDFs generados
PDF_DIR = "pdf_reports"
os.makedirs(PDF_DIR, exist_ok=True)

# --- CONFIGURACIÓN DE CORREO SALIENTE ---
SENDER_EMAIL = os.getenv("SENDER_EMAIL")       # Tu correo Gmail emisor (Configurar en Render)
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD") # Contraseña de Aplicación de Google
RECEIVER_EMAIL = "s.espinozav_ext@emape.gob.pe" # Destinatario automático fijo


def optimizar_imagen_base64(file_bytes: bytes, max_width: int = 800) -> str:
    """Comprime y redimensiona imágenes para evitar sobrecargar xhtml2pdf."""
    try:
        image = Image.open(io.BytesIO(file_bytes))
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
        
        # Redimensionar manteniendo aspecto
        if image.width > max_width:
            ratio = max_width / float(image.width)
            new_height = int((float(image.height) * float(ratio)))
            image = image.resize((max_width, new_height), Image.Resampling.LANCZOS)
        
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=70)
        encoded_string = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return f"data:image/jpeg;base64,{encoded_string}"
    except Exception as e:
        print(f"Error optimizando imagen: {e}")
        return ""


def enviar_correo_notificacion(pdf_path: str, tipo_reporte: str, correlativo: str, inspector: str):
    """Envía el PDF generado a s.espinozav_ext@emape.gob.pe automáticamente."""
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print("⚠️ ADVERTENCIA: SENDER_EMAIL o SENDER_PASSWORD no están configurados en las variables de entorno.")
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECEIVER_EMAIL
        msg['Subject'] = f"MESA DE PARTES SSOMA - {tipo_reporte} N° {correlativo}"

        cuerpo = (
            f"Estimado(a),\n\n"
            f"Se ha registrado un nuevo reporte en la Mesa de Partes SSOMA - EMAPE S.A.\n\n"
            f"• Tipo de Reporte: {tipo_reporte}\n"
            f"• N° Correlativo: {correlativo}\n"
            f"• Inspector / Registrador: {inspector}\n"
            f"• Fecha de Registro: {datetime.now(ZoneInfo('America/Lima')).strftime('%d/%m/%Y %H:%M')}\n\n"
            f"Se adjunta el informe oficial en formato PDF.\n\n"
            f"--------------------------------------------------\n"
            f"Sistema Automático Mesa de Partes SSOMA - EMAPE S.A."
        )
        msg.attach(MIMEText(cuerpo, 'plain', 'utf-8'))

        # Adjuntar PDF
        if os.path.exists(pdf_path):
            with open(pdf_path, "rb") as adjunto:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(adjunto.read())
                encoders.encode_base64(part)
                
                filename = os.path.basename(pdf_path)
                part.add_header("Content-Disposition", f"attachment; filename={filename}")
                msg.attach(part)

        # Servidor SMTP de Gmail (Puerto 465 SSL)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)

        print(f"✅ Correo enviado exitosamente a {RECEIVER_EMAIL}")
        return True

    except Exception as e:
        print(f"❌ Error enviando el correo: {e}")
        return False


def generar_html_pdf(data: dict) -> str:
    """Genera la estructura HTML formateada para xhtml2pdf."""
    
    # Filas de Causas Inmediatas
    filas_cinm = ""
    for item in data.get("causas_inmediatas", []):
        filas_cinm += f"""
        <tr>
            <td style="width: 10%; text-align: center;">{item['fila']}</td>
            <td style="width: 30%;">{item['tipo']}</td>
            <td style="width: 30%;">{item['causa']}</td>
            <td style="width: 30%;">{item['obs']}</td>
        </tr>
        """
    if not filas_cinm:
        filas_cinm = "<tr><td colspan='4' style='text-align:center;'>Sin registros</td></tr>"

    # Filas de Causas Básicas
    filas_csub = ""
    for item in data.get("causas_basicas", []):
        filas_csub += f"""
        <tr>
            <td style="width: 10%; text-align: center;">{item['fila']}</td>
            <td style="width: 25%;">{item['tipo']}</td>
            <td style="width: 25%;">{item['causa']}</td>
            <td style="width: 20%;">{item['subyacente']}</td>
            <td style="width: 20%;">{item['obs']}</td>
        </tr>
        """
    if not filas_csub:
        filas_csub = "<tr><td colspan='5' style='text-align:center;'>Sin registros</td></tr>"

    # Filas de Medidas Correctivas
    filas_acc = ""
    for item in data.get("medidas_correctivas", []):
        filas_acc += f"""
        <tr>
            <td style="width: 8%; text-align: center;">{item['fila']}</td>
            <td style="width: 18%;">{item['tipo']}</td>
            <td style="width: 26%;">{item['accion']}</td>
            <td style="width: 18%;">{item['responsable']}</td>
            <td style="width: 12%; text-align: center;">{item['fecha']}</td>
            <td style="width: 18%;">{item['situacion']}</td>
        </tr>
        """
    if not filas_acc:
        filas_acc = "<tr><td colspan='6' style='text-align:center;'>Sin registros</td></tr>"

    # Fotos adjuntas
    html_fotos = ""
    for idx, foto in enumerate(data.get("fotos", []), 1):
        if foto:
            html_fotos += f"""
            <div style="margin-bottom: 15px; text-align: center;">
                <p><strong>Evidencia Fotográfica N° {idx}</strong></p>
                <img src="{foto}" style="max-width: 450px; max-height: 300px; border: 1px solid #ccc; padding: 4px;" />
            </div>
            """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @page {{
                size: A4;
                margin: 15mm;
            }}
            body {{
                font-family: Helvetica, Arial, sans-serif;
                font-size: 10pt;
                color: #333333;
            }}
            .header-table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 15px;
            }}
            .header-table td {{
                border: 1px solid #1E3A8A;
                padding: 6px;
                vertical-align: middle;
            }}
            .title {{
                font-size: 13pt;
                font-weight: bold;
                color: #1E3A8A;
                text-align: center;
            }}
            .section-header {{
                background-color: #1E3A8A;
                color: #FFFFFF;
                font-weight: bold;
                padding: 5px 8px;
                font-size: 10pt;
                margin-top: 15px;
                margin-bottom: 8px;
            }}
            table.data-table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 10px;
            }}
            table.data-table th {{
                background-color: #E2E8F0;
                border: 1px solid #94A3B8;
                padding: 5px;
                font-size: 9pt;
            }}
            table.data-table td {{
                border: 1px solid #CBD5E1;
                padding: 5px;
                font-size: 8.5pt;
            }}
            .box {{
                border: 1px solid #CBD5E1;
                padding: 8px;
                font-size: 9pt;
                min-height: 40px;
                background-color: #F8FAFC;
            }}
        </style>
    </head>
    <body>

        <table class="header-table">
            <tr>
                <td style="width: 25%; text-align: center;">
                    <strong style="color: #1E3A8A; font-size: 14pt;">EMAPE S.A.</strong>
                </td>
                <td style="width: 50%;" class="title">
                    MESA DE PARTES SSOMA<br/>INFORME OFICIAL
                </td>
                <td style="width: 25%; font-size: 8pt;">
                    <strong>Correlativo:</strong> {data.get('correlativo')}<br/>
                    <strong>Fecha:</strong> {data.get('fecha_registro')}<br/>
                    <strong>Tipo:</strong> {data.get('tipo_reporte')}
                </td>
            </tr>
        </table>

        <div class="section-header">1. DATOS GENERALES</div>
        <table class="data-table">
            <tr>
                <th style="width: 20%;">Sede / Ubicación</th>
                <td style="width: 30%;">{data.get('sede')}</td>
                <th style="width: 20%;">Inspector / Registrador</th>
                <td style="width: 30%;">{data.get('inspector')}</td>
            </tr>
            <tr>
                <th>Lugar Específico</th>
                <td>{data.get('lugar_especifico')}</td>
                <th>Empresa / Área</th>
                <td>{data.get('empresa')}</td>
            </tr>
            <tr>
                <th>Fecha Incidente / Inspección</th>
                <td>{data.get('fecha_evento')}</td>
                <th>Hora</th>
                <td>{data.get('hora_evento')}</td>
            </tr>
        </table>

        <div class="section-header">2. DESCRIPCIÓN DEL EVENTO / HALLAZGO</div>
        <div class="box">
            {data.get('descripcion_evento', 'Sin descripción.')}
        </div>

        <div class="section-header">3. ANÁLISIS DE CAUSAS INMEDIATAS</div>
        <table class="data-table">
            <thead>
                <tr>
                    <th>N°</th>
                    <th>Tipo</th>
                    <th>Causa Inmediata</th>
                    <th>Observación</th>
                </tr>
            </thead>
            <tbody>
                {filas_cinm}
            </tbody>
        </table>

        <div class="section-header">4. ANÁLISIS DE CAUSAS BÁSICAS / SUBYACENTES</div>
        <table class="data-table">
            <thead>
                <tr>
                    <th>N°</th>
                    <th>Tipo</th>
                    <th>Causa Básica</th>
                    <th>Factor Subyacente</th>
                    <th>Observación</th>
                </tr>
            </thead>
            <tbody>
                {filas_csub}
            </tbody>
        </table>

        <div class="section-header">5. MEDIDAS CORRECTIVAS Y PREVENTIVAS</div>
        <table class="data-table">
            <thead>
                <tr>
                    <th>N°</th>
                    <th>Tipo Control</th>
                    <th>Acción Correctiva</th>
                    <th>Responsable</th>
                    <th>F. Límite</th>
                    <th>Estado</th>
                </tr>
            </thead>
            <tbody>
                {filas_acc}
            </tbody>
        </table>

        {f'<div class="section-header">6. EVIDENCIA FOTOGRÁFICA</div>{html_fotos}' if html_fotos else ''}

    </body>
    </html>
    """


@app.get("/")
def home():
    return {"status": "online", "message": "API Mesa de Partes SSOMA EMAPE S.A. operativa."}


@app.post("/enviar-reporte")
async def recibir_reporte(request: Request):
    """Procesa los datos del formulario, genera el PDF y lo envía automáticamente."""
    try:
        form_data = await request.form()
        
        # 1. Parseo de datos básicos del encabezado
        hora_lima = datetime.now(ZoneInfo("America/Lima")).strftime("%d/%m/%Y %H:%M")
        
        tipo_reporte = form_data.get("tipo_reporte", "INFORME SSOMA")
        correlativo = form_data.get("correlativo", "001")
        inspector = form_data.get("inspector", "Personal SSOMA")

        data_dict = {
            "correlativo": correlativo,
            "tipo_reporte": tipo_reporte,
            "fecha_registro": hora_lima,
            "sede": form_data.get("sede", "-"),
            "inspector": inspector,
            "lugar_especifico": form_data.get("lugar_especifico", "-"),
            "empresa": form_data.get("empresa", "EMAPE S.A."),
            "fecha_evento": form_data.get("fecha_evento", "-"),
            "hora_evento": form_data.get("hora_evento", "-"),
            "descripcion_evento": form_data.get("descripcion_evento", ""),
        }

        # 2. Parseo de Causas Inmediatas (5 inputs estáticos del HTML)
        causas_inmediatas = []
        for i in range(1, 6):
            tipo = form_data.get(f"cinm_tipo_{i}", "").strip()
            causa = form_data.get(f"cinm_causa_{i}", "").strip()
            obs = form_data.get(f"cinm_obs_{i}", "").strip()
            if tipo or causa or obs:
                causas_inmediatas.append({"fila": i, "tipo": tipo, "causa": causa, "obs": obs})
        data_dict["causas_inmediatas"] = causas_inmediatas

        # 3. Parseo de Causas Básicas (5 inputs estáticos)
        causas_basicas = []
        for i in range(1, 6):
            tipo = form_data.get(f"csub_tipo_{i}", "").strip()
            causa = form_data.get(f"csub_causa_{i}", "").strip()
            subyacente = form_data.get(f"csub_subyacente_{i}", "").strip()
            obs = form_data.get(f"csub_obs_{i}", "").strip()
            if tipo or causa or subyacente or obs:
                causas_basicas.append({
                    "fila": i, "tipo": tipo, "causa": causa, "subyacente": subyacente, "obs": obs
                })
        data_dict["causas_basicas"] = causas_basicas

        # 4. Parseo de Medidas Correctivas (4 inputs estáticos)
        medidas_correctivas = []
        for i in range(1, 5):
            tipo = form_data.get(f"acc_tipo_{i}", "").strip()
            accion = form_data.get(f"acc_control_{i}", "").strip()
            resp = form_data.get(f"acc_resp_{i}", "").strip()
            fecha = form_data.get(f"acc_fecha_{i}", "").strip()
            sit = form_data.get(f"acc_sit_{i}", "").strip()
            if tipo or accion or resp:
                medidas_correctivas.append({
                    "fila": i, "tipo": tipo, "accion": accion,
                    "responsable": resp, "fecha": fecha, "situacion": sit
                })
        data_dict["medidas_correctivas"] = medidas_correctivas

        # 5. Procesamiento de Fotos Adjuntas
        fotos_base64 = []
        for key in form_data.keys():
            if key.startswith("foto_") or key == "fotos":
                file_obj = form_data[key]
                if hasattr(file_obj, "read"):
                    bytes_content = await file_obj.read()
                    if bytes_content:
                        b64_img = optimizar_imagen_base64(bytes_content)
                        if b64_img:
                            fotos_base64.append(b64_img)
        data_dict["fotos"] = fotos_base64

        # 6. Generar el PDF
        html_content = generar_html_pdf(data_dict)
        pdf_filename = f"Reporte_SSOMA_{correlativo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf_path = os.path.join(PDF_DIR, pdf_filename)

        with open(pdf_path, "wb") as f:
            pisa_status = pisa.CreatePDF(io.StringIO(html_content), dest=f)

        if pisa_status.err:
            raise HTTPException(status_code=500, detail="Error al estructurar el PDF con xhtml2pdf.")

        # 7. Envío del Correo Automático
        correo_enviado = enviar_correo_notificacion(
            pdf_path=pdf_path,
            tipo_reporte=tipo_reporte,
            correlativo=correlativo,
            inspector=inspector
        )

        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": "Reporte registrado y enviado a s.espinozav_ext@emape.gob.pe con éxito.",
                "pdf_filename": pdf_filename,
                "email_sent": correo_enviado
            }
        )

    except Exception as e:
        print(f"Error procesando el reporte: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Ocurrió un error en el servidor: {str(e)}"}
        )


@app.get("/descargar-pdf/{filename}")
def descargar_pdf(filename: str):
    """Endpoint opcional para descargar los PDFs generados desde el servidor."""
    path = os.path.join(PDF_DIR, filename)
    if os.path.exists(path):
        return FileResponse(path, media_type="application/pdf", filename=filename)
    raise HTTPException(status_code=404, detail="Archivo PDF no encontrado.")

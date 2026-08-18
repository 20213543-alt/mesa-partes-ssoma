# Correos destino fijos
CORREOS_NOTIFICACION = ["chanelone14@gmail.com", "sebastianstalin19@gmail.com"]

@app.post("/enviar-reporte-preliminar", response_class=HTMLResponse)
async def enviar_reporte_preliminar(
    request: Request,
    pdf_file: UploadFile = File(None)
):
    """Maneja el Informe Preliminar (Captura de pantalla PDF enviada a los 2 correos fijos)"""
    try:
        form_data = await request.form()

        tz_peru = zoneinfo.ZoneInfo("America/Lima")
        ahora_peru = datetime.now(tz_peru)
        fecha_registro_str = ahora_peru.strftime("%d/%m/%Y %H:%M:%S")

        nombre_lesionado = form_data.get("nombre_lesionado_pre") or form_data.get("nombre_lesionado") or "Anónimo"
        fecha_evento = form_data.get("fecha_evento_pre") or form_data.get("fecha_evento") or ""
        tipo_evento = form_data.get("tipo_evento_pre") or form_data.get("tipo_evento") or ""

        codigo_comprobante = f"PRE-{ahora_peru.strftime('%Y%m%d')}-{ahora_peru.strftime('%H%M%S')}"

        pdf_bytes = None
        if pdf_file:
            pdf_bytes = await pdf_file.read()

        asunto = f"INFORME PRELIMINAR SSOMA [{codigo_comprobante}]: {nombre_lesionado}"
        cuerpo = f"""Se ha generado un nuevo Informe Preliminar de Accidente/Incidente.

Código de Comprobante: {codigo_comprobante}
Fecha y Hora de Registro (Perú): {fecha_registro_str}
Lesionado/Afectado: {nombre_lesionado}
Fecha del Evento: {fecha_evento}
Tipo de Evento: {tipo_evento}

Se adjunta a este correo la captura visual completa del informe en formato PDF.
"""
        enviar_correo_con_adjunto(
            asunto=asunto,
            cuerpo=cuerpo,
            adjunto_bytes=pdf_bytes,
            nombre_adjunto=f"Informe_Preliminar_Captura_{codigo_comprobante}.pdf"
        )

        html_confirmacion = f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Informe Preliminar Enviado</title>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7f6; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }}
                .card {{ background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); max-width: 500px; width: 90%; text-align: center; }}
                .icon {{ font-size: 50px; color: #28a745; margin-bottom: 10px; }}
                h2 {{ color: #333; margin-bottom: 20px; }}
                .comprobante-box {{ background-color: #e9ecef; border-left: 5px solid #28a745; padding: 15px; text-align: left; margin: 20px 0; border-radius: 4px; }}
                .comprobante-box p {{ margin: 5px 0; font-size: 14px; color: #495057; }}
                .code {{ font-weight: bold; font-size: 16px; color: #28a745; }}
                .btn {{ display: inline-block; background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin-top: 15px; font-weight: bold; }}
                .btn:hover {{ background-color: #0056b3; }}
            </style>
        </head>
        <body>
            <div class="card">
                <div class="icon">✓</div>
                <h2>¡Informe Preliminar Enviado!</h2>
                <p>Se realizó la captura en PDF del informe y fue enviada por correo a los destinatarios registrados.</p>
                
                <div class="comprobante-box">
                    <p><strong>Código de Comprobante:</strong> <span class="code">{codigo_comprobante}</span></p>
                    <p><strong>Fecha y Hora (Perú):</strong> {fecha_registro_str}</p>
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

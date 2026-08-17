import os
import smtplib
from typing import List, Optional
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from fastapi import FastAPI, Form, UploadFile, File
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
    tipo_informe: str = Form("PRELIMINAR"),
    correo_destino: str = Form(...),
    
    # --- CAMPOS PRELIMINAR ---
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
    resp_cargo_pre: Optional[str] = Form(None),
    resp_fecha_pre: Optional[str] = Form(None),
    fotografia_pre: Optional[UploadFile] = File(None),

    # --- CAMPOS INFORME FINAL ---
    emp_sede: Optional[str] = Form(None),
    emp_direccion: Optional[str] = Form(None),
    emp_num_trabajadores: Optional[str] = Form(None),
    emp_num_sctr: Optional[str] = Form(None),
    emp_aseguradora: Optional[str] = Form(None),

    ter_razon_social: Optional[str] = Form(None),
    ter_ruc: Optional[str] = Form(None),
    ter_domicilio: Optional[str] = Form(None),
    ter_actividad: Optional[str] = Form(None),
    ter_num_trabajadores: Optional[str] = Form(None),
    ter_num_sctr: Optional[str] = Form(None),
    ter_aseguradora: Optional[str] = Form(None),

    fin_fecha_evento: Optional[str] = Form(None),
    fin_hora_evento: Optional[str] = Form(None),
    fin_lugar_exacto: Optional[str] = Form(None),
    fin_tipo_evento: Optional[str] = Form(None),
    fin_clasificacion: Optional[str] = Form(None),
    fin_incidente_peligro: Optional[str] = Form(None),

    trab_paterno: List[str] = Form([]),
    trab_materno: List[str] = Form([]),
    trab_nombres: List[str] = Form([]),
    trab_ocupacion: List[str] = Form([]),
    trab_condicion: List[str] = Form([]),
    trab_sexo: List[str] = Form([]),
    trab_dni: List[str] = Form([]),
    trab_edad: List[str] = Form([]),
    trab_turno: List[str] = Form([]),
    trab_personal: List[str] = Form([]),

    acc_gravedad: Optional[str] = Form(None),
    acc_grado_incapacitante: Optional[str] = Form(None),
    acc_dias_descanso: Optional[str] = Form(None),
    acc_dias_cargados: Optional[str] = Form(None),
    acc_num_afectados: Optional[str] = Form(None),

    inc_primeros_auxilios: Optional[str] = Form(None),

    les_forma_evento: Optional[str] = Form(None),
    les_tipo_lesion: Optional[str] = Form(None),
    les_agente_causante: Optional[str] = Form(None),
    les_parte_cuerpo: Optional[str] = Form(None),
    les_hospital_atencion: Optional[str] = Form(None),

    dan_material: Optional[str] = Form(None),
    dan_agente_causante: Optional[str] = Form(None),
    dan_descripcion_evento: Optional[str] = Form(None),

    ana_que_sucedio: Optional[str] = Form(None),
    ana_tipo_contacto: Optional[str] = Form(None),
    ana_causa_inmediata: Optional[str] = Form(None),
    ana_causa_basica: Optional[str] = Form(None),
    ana_falta_control: Optional[str] = Form(None),

    # Causas Inmediatas
    cinm_tipo_1: Optional[str] = Form(None), cinm_causa_1: Optional[str] = Form(None), cinm_obs_1: Optional[str] = Form(None),
    cinm_tipo_2: Optional[str] = Form(None), cinm_causa_2: Optional[str] = Form(None), cinm_obs_2: Optional[str] = Form(None),
    cinm_tipo_3: Optional[str] = Form(None), cinm_causa_3: Optional[str] = Form(None), cinm_obs_3: Optional[str] = Form(None),
    cinm_tipo_4: Optional[str] = Form(None), cinm_causa_4: Optional[str] = Form(None), cinm_obs_4: Optional[str] = Form(None),
    cinm_tipo_5: Optional[str] = Form(None), cinm_causa_5: Optional[str] = Form(None), cinm_obs_5: Optional[str] = Form(None),

    # Causas Subyacentes
    csub_tipo_1: Optional[str] = Form(None), csub_causa_1: Optional[str] = Form(None), csub_subyacente_1: Optional[str] = Form(None), csub_obs_1: Optional[str] = Form(None),
    csub_tipo_2: Optional[str] = Form(None), csub_causa_2: Optional[str] = Form(None), csub_subyacente_2: Optional[str] = Form(None), csub_obs_2: Optional[str] = Form(None),
    csub_tipo_3: Optional[str] = Form(None), csub_causa_3: Optional[str] = Form(None), csub_subyacente_3: Optional[str] = Form(None), csub_obs_3: Optional[str] = Form(None),
    csub_tipo_4: Optional[str] = Form(None), csub_causa_4: Optional[str] = Form(None), csub_subyacente_4: Optional[str] = Form(None), csub_obs_4: Optional[str] = Form(None),
    csub_tipo_5: Optional[str] = Form(None), csub_causa_5: Optional[str] = Form(None), csub_subyacente_5: Optional[str] = Form(None), csub_obs_5: Optional[str] = Form(None),

    # Acciones Correctivas
    acc_tipo_1: Optional[str] = Form(None), acc_control_1: Optional[str] = Form(None), acc_resp_1: Optional[str] = Form(None), acc_fecha_1: Optional[str] = Form(None), acc_sit_1: Optional[str] = Form(None), acc_obs_1: Optional[str] = Form(None),
    acc_tipo_2: Optional[str] = Form(None), acc_control_2: Optional[str] = Form(None), acc_resp_2: Optional[str] = Form(None), acc_fecha_2: Optional[str] = Form(None), acc_sit_2: Optional[str] = Form(None), acc_obs_2: Optional[str] = Form(None),
    acc_tipo_3: Optional[str] = Form(None), acc_control_3: Optional[str] = Form(None), acc_resp_3: Optional[str] = Form(None), acc_fecha_3: Optional[str] = Form(None), acc_sit_3: Optional[str] = Form(None), acc_obs_3: Optional[str] = Form(None),
    acc_tipo_4: Optional[str] = Form(None), acc_control_4: Optional[str] = Form(None), acc_resp_4: Optional[str] = Form(None), acc_fecha_4: Optional[str] = Form(None), acc_sit_4: Optional[str] = Form(None), acc_obs_4: Optional[str] = Form(None),

    # Firmas
    inv_nombre: Optional[str] = Form(None),
    inv_cargo: Optional[str] = Form(None),
    tes_nombre: Optional[str] = Form(None),
    tes_cargo: Optional[str] = Form(None)
):
    wb = openpyxl.load_workbook(PLANTILLA_PATH)

    if tipo_informe == "PRELIMINAR":
        ws = wb['INFORME_PRELIMINAR'] if 'INFORME_PRELIMINAR' in wb.sheetnames else wb.active
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
        ws['E20'] = resp_cargo_pre or ""
        ws['G20'] = resp_fecha_pre or ""
        ws['I20'] = (resp_nombre_pre or "").upper()
        nombre_archivo = f"Informe_Preliminar_{(nombre_lesionado_pre or 'SSOMA').replace(' ', '_')}.xlsx"

    else:
        ws = wb.active
        # 1. Empleador
        ws['D10'] = emp_direccion or ""
        ws['R11'] = emp_num_trabajadores or ""
        ws['D13'] = emp_num_sctr or ""
        ws['R13'] = emp_aseguradora or ""

        # Contratista
        ws['D16'] = ter_razon_social or ""
        ws['R16'] = ter_ruc or ""
        ws['D17'] = ter_domicilio or ""
        ws['D18'] = ter_actividad or ""
        ws['R18'] = ter_num_trabajadores or ""
        ws['D21'] = ter_num_sctr or ""
        ws['R21'] = ter_aseguradora or ""

        # Ocurrencia
        ws['C30'] = fin_fecha_evento or ""
        ws['C31'] = fin_hora_evento or ""
        ws['R30'] = fin_lugar_exacto or ""

        # Trabajadores (Fila inicial)
        if len(trab_nombres) > 0:
            nombre_full = f"{trab_paterno[0]} {trab_materno[0]} {trab_nombres[0]}"
            ws['D23'] = nombre_full
            ws['C24'] = trab_dni[0] if len(trab_dni) > 0 else ""
            ws['N24'] = trab_edad[0] if len(trab_edad) > 0 else ""
            ws['N25'] = trab_sexo[0] if len(trab_sexo) > 0 else ""
            ws['C26'] = trab_ocupacion[0] if len(trab_ocupacion) > 0 else ""

        # Accidente / Lesión
        ws['C33'] = acc_gravedad or ""
        ws['C47'] = les_tipo_lesion or ""
        ws['C48'] = les_parte_cuerpo or ""
        ws['C50'] = les_agente_causante or ""
        ws['C51'] = acc_dias_descanso or ""
        ws['R36'] = les_hospital_atencion or ""

        # Causas Inmediatas
        ws['B56'] = cinm_tipo_1 or ""
        ws['D56'] = f"{cinm_causa_1 or ''} - {cinm_obs_1 or ''}"

        # Causas Básicas
        ws['B65'] = csub_tipo_1 or ""
        ws['D65'] = f"{csub_causa_1 or ''} | {csub_subyacente_1 or ''} - {csub_obs_1 or ''}"

        # Acciones Correctivas
        ws['C79'] = f"[{acc_tipo_1 or ''}] {acc_control_1 or ''}"
        ws['M79'] = acc_resp_1 or ""
        ws['R79'] = acc_fecha_1 or ""
        ws['S79'] = acc_sit_1 or ""

        # Firmas
        ws['C96'] = inv_nombre or ""
        ws['R96'] = inv_cargo or ""
        ws['S96'] = (inv_nombre or "").upper()
        ws['C89'] = tes_nombre or ""
        ws['R89'] = tes_cargo or ""

        nombre_archivo = f"Informe_Final_Accidente_{(trab_paterno[0] if len(trab_paterno)>0 else 'SSOMA')}.xlsx"

    wb.save(nombre_archivo)

    return FileResponse(
        path=nombre_archivo,
        filename=nombre_archivo,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

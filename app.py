import os
from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine, text
import requests
from pydantic import BaseModel
import time

class PreguntaIn(BaseModel):
    pregunta: str

app = FastAPI()

url = os.environ["DATABASE_URL"].replace("postgres://", "postgresql://", 1)
engine = create_engine(url)

# Timeout configurable por variable de entorno, con valor por defecto más realista
GEMINI_TIMEOUT = float(os.environ.get("GEMINI_TIMEOUT", "25"))

@app.get("/")
def inicio():
    return {"mensaje": "Verificacion del microservicio: Conexion exitosa"}

@app.get("/empleados")
def listar_empleados():
    with engine.connect() as conn:
        filas = conn.execute(
            text("SELECT id, nombre, especialidad FROM empleados_empleado")
        ).mappings().all()
    return [dict(f) for f in filas]

@app.post("/consultar-ia")
def consultar_ia(pregunta_in: PreguntaIn):
    api_key = os.environ["GEMINI_API_KEY"]
    gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key={api_key}"

    with engine.connect() as conn:
        filas = conn.execute(text("""
            SELECT t.titulo, t.estado, e.nombre AS empleado
            FROM tareas_tarea t
            LEFT JOIN empleados_empleado e ON t.empleado_id = e.id
        """)).mappings().all()

    if filas:
        lineas = [f"- {f['titulo']} ({f['estado']}) — {f['empleado'] or 'sin asignar'}" for f in filas]
        tareas_texto = "\n".join(lineas)
    else:
        tareas_texto = "No hay tareas registradas actualmente."

    contexto = (
        "Eres un asistente que responde preguntas sobre gestión de "
        "empleados y tareas asignadas dentro de una empresa. "
        "Responde de forma breve y directa, en un máximo de 20 palabras. "
        "Esta es la lista actual de tareas:\n"
        f"{tareas_texto}\n\n"
        f"Pregunta: {pregunta_in.pregunta}"
    )

    payload = {
        "contents": [{"parts": [{"text": contexto}]}],
        "generationConfig": {
            "maxOutputTokens": 80,
            "thinkingConfig": {"thinkingBudget": 0}
        }
    }

    intentos_maximos = 3
    ultimo_error = None

    for intento in range(intentos_maximos):
        try:
            respuesta = requests.post(gemini_url, json=payload, timeout=GEMINI_TIMEOUT)
            respuesta.raise_for_status()
            datos = respuesta.json()
            partes = datos["candidates"][0].get("content", {}).get("parts")
            if not partes:
                raise HTTPException(status_code=502, detail="La IA no generó texto en la respuesta.")
            texto = partes[0]["text"]
            return {"respuesta": texto}

        except requests.HTTPError as e:
            codigo = e.response.status_code
            if codigo == 503 and intento < intentos_maximos - 1:
                time.sleep(2 ** intento)  # backoff: 1s, 2s, 4s
                continue
            raise HTTPException(status_code=codigo, detail=e.response.text)

        
        except (requests.Timeout, requests.ConnectionError) as e:
            ultimo_error = e
            if intento < intentos_maximos - 1:
                time.sleep(2 ** intento)
                continue
            raise HTTPException(
                status_code=504,
                detail=f"Gemini no respondió a tiempo tras {intentos_maximos} intentos: {ultimo_error}"
            )

        except requests.RequestException as e:
            raise HTTPException(status_code=502, detail=str(e))
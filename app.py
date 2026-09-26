import os
import time
from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine, text
import requests
from pydantic import BaseModel

class PreguntaIn(BaseModel):
    pregunta: str

app = FastAPI()

url = os.environ["DATABASE_URL"].replace("postgres://", "postgresql://", 1)
engine = create_engine(url)

GEMINI_TIMEOUT = float(os.environ.get("GEMINI_TIMEOUT", "25"))

BASE_URL = "https://backend-empleados-9oud.onrender.com"

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

@app.get("/tareas")
def listar_tareas():
    with engine.connect() as conn:
        filas = conn.execute(text("""
            SELECT t.id, t.titulo, t.estado, e.nombre AS empleado
            FROM tareas_tarea t
            LEFT JOIN empleados_empleado e ON t.empleado_id = e.id
        """)).mappings().all()
    return [dict(f) for f in filas]

@app.post("/consultar-ia")
def consultar_ia(pregunta_in: PreguntaIn):
    api_key = os.environ["GEMINI_API_KEY"]
    gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key={api_key}"

    try:
        empleados_data = requests.get(f"{BASE_URL}/empleados", timeout=10).json()
    except requests.RequestException:
        empleados_data = []

    try:
        tareas_data = requests.get(f"{BASE_URL}/tareas", timeout=10).json()
    except requests.RequestException:
        tareas_data = []

    empleados_texto = "\n".join(
        f"- {e['nombre']} ({e['especialidad']})" for e in empleados_data
    ) or "No hay empleados registrados."

    tareas_texto = "\n".join(
        f"- {t['titulo']} ({t['estado']}) — {t['empleado'] or 'sin asignar'}" for t in tareas_data
    ) or "No hay tareas registradas actualmente."

    contexto = (
        "Eres un asistente que responde preguntas sobre gestión de "
        "empleados y tareas asignadas dentro de una empresa. "
        "Responde de forma breve y directa, en un máximo de 20 palabras. "
        f"Empleados:\n{empleados_texto}\n\n"
        f"Tareas:\n{tareas_texto}\n\n"
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
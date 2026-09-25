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

    contexto = (
        "Eres un asistente que responde preguntas sobre gestión de "
        "empleados y tareas asignadas dentro de una empresa. "
        "Responde de forma breve y directa, en un máximo de 20 palabras. "
        f"Pregunta: {pregunta_in.pregunta}"
    )

    payload = {
        "contents": [{"parts": [{"text": contexto}]}],
        "generationConfig": {
            "maxOutputTokens": 60
        }
    }

    intentos_maximos = 3
    for intento in range(intentos_maximos):
        try:
            respuesta = requests.post(gemini_url, json=payload, timeout=10)
            respuesta.raise_for_status()
            datos = respuesta.json()
            texto = datos["candidates"][0]["content"]["parts"][0]["text"]
            return {"respuesta": texto}
        except requests.HTTPError as e:
            codigo = e.response.status_code
            if codigo == 503 and intento < intentos_maximos - 1:
                time.sleep(2)
                continue
            raise HTTPException(status_code=codigo, detail=e.response.text)
        except requests.RequestException as e:
            raise HTTPException(status_code=502, detail=str(e))

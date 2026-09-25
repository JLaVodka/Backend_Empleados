import os
from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine, text
import requests 
from pydantic import BaseModel

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
        f"Pregunta: {pregunta_in.pregunta}"
    )
    payload = {"contents": [{"parts": [{"text": contexto}]}]}

    try:
        respuesta = requests.post(gemini_url, json=payload, timeout=10)
        respuesta.raise_for_status()
        datos = respuesta.json()
        texto = datos["candidates"][0]["content"]["parts"][0]["text"]
    except requests.RequestException as e:
        detalle = str(e)
        if e.response is not None:
            detalle = f"{e.response.status_code}: {e.response.text}"
        raise HTTPException(status_code=502, detail=detalle)

    return {"respuesta": texto}

import os
from fastapi import FastAPI
from sqlalchemy import create_engine, text

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

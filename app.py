from fastapi import FastAPI

app=FastAPI()

@app.get("/")
def inicio():
    return {"mensaje": "Verificacion del microservicio: Conexion exitosa"}
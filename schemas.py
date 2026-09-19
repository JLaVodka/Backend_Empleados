from pydantic import BaseModel

class EmpleadoOut(BaseModel):
    id: int
    nombre: str
    especialidad: str

    class Config:
        from_attributes = True
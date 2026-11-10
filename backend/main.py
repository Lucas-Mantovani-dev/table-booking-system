from fastapi import FastAPI, HTTPException
from backend import services

app = FastAPI()

@app.get("/tables")
def get_tables():
    tables_list = services.get_tables()

    
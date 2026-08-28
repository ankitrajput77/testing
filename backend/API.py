import pandas as pd
import numpy as np
from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def home():
    return {"message": "it is working."}


from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database.config import configure_database
from app.routers import operations, component_quantities, leadtime, raw_material_router

app = FastAPI()

# CORS Configuration
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

configure_database()


app.include_router(operations.router, tags=["operations/production"])
app.include_router(component_quantities.router, tags=["component_quantities"])
app.include_router(leadtime.router, tags=["leadtime"])
app.include_router(raw_material_router.router,tags=["rawmaterial/machinestatus"])

# TO RUN
# uvicorn app.main:app --host 172.18.7.85 --port 7070 --reload
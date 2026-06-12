from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import cases, geometry, meshing, results, runs, sweeps, system, templates, validation
from app.config import settings
from app.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="OpenFOAM GUI", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system.router, prefix="/api/system", tags=["system"])
app.include_router(cases.router, prefix="/api/cases", tags=["cases"])
app.include_router(templates.router, prefix="/api/templates", tags=["templates"])
app.include_router(geometry.router, prefix="/api/geometry", tags=["geometry"])
app.include_router(meshing.router, prefix="/api/meshing", tags=["meshing"])
app.include_router(validation.router, prefix="/api/validation", tags=["validation"])
app.include_router(runs.router, prefix="/api/runs", tags=["runs"])
app.include_router(results.router, prefix="/api/results", tags=["results"])
app.include_router(sweeps.router, prefix="/api/sweeps", tags=["sweeps"])

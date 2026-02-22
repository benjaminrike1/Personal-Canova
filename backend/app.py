import logging

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from backend.core.database import init_db
from backend.services.reminders import ReminderService
from backend.api import (
    checkins,
    chat,
    activities,
    races,
    injuries,
    training_plan,
    analytics,
    athlete,
    notebook,
    personal_records,
    export,
    weather,
    phases,
)

logging.basicConfig(level=logging.INFO)

BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(title="Coach", version="0.1.0")

# Static files and templates
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

reminder_service = ReminderService()


@app.on_event("startup")
async def startup():
    init_db()
    # Start email reminder scheduler
    try:
        reminder_service.schedule_all()
    except Exception as e:
        logging.warning(f"Failed to start reminder scheduler: {e}")


@app.on_event("shutdown")
async def shutdown():
    reminder_service.stop()


# --- Page routes ---

@app.get("/")
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/checkin/{checkin_type}")
async def checkin_page(request: Request, checkin_type: str):
    return templates.TemplateResponse("checkin.html", {
        "request": request,
        "checkin_type": checkin_type,
    })


@app.get("/chat")
async def chat_page(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})


@app.get("/plan")
async def plan_page(request: Request):
    return templates.TemplateResponse("plan.html", {"request": request})


@app.get("/races")
async def races_page(request: Request):
    return templates.TemplateResponse("races.html", {"request": request})


@app.get("/injuries")
async def injuries_page(request: Request):
    return templates.TemplateResponse("injuries.html", {"request": request})


@app.get("/analytics")
async def analytics_page(request: Request):
    return templates.TemplateResponse("analytics.html", {"request": request})


@app.get("/onboarding")
async def onboarding_page(request: Request):
    return templates.TemplateResponse("onboarding.html", {"request": request})


@app.get("/notebook")
async def notebook_page(request: Request):
    return templates.TemplateResponse("notebook.html", {"request": request})


@app.get("/settings")
async def settings_page(request: Request):
    return templates.TemplateResponse("settings.html", {"request": request})


# --- API routers ---

app.include_router(checkins.router, prefix="/api/checkins", tags=["checkins"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(activities.router, prefix="/api/activities", tags=["activities"])
app.include_router(races.router, prefix="/api/races", tags=["races"])
app.include_router(injuries.router, prefix="/api/injuries", tags=["injuries"])
app.include_router(training_plan.router, prefix="/api/plan", tags=["training_plan"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(athlete.router, prefix="/api/athlete", tags=["athlete"])
app.include_router(notebook.router, prefix="/api/notebook", tags=["notebook"])
app.include_router(personal_records.router, prefix="/api/records", tags=["personal_records"])
app.include_router(export.router, prefix="/api/export", tags=["export"])
app.include_router(weather.router, prefix="/api/weather", tags=["weather"])
app.include_router(phases.router, prefix="/api/phases", tags=["phases"])

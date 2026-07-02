from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes_search import router as search_router
from app.api.routes_dupe import router as dupe_router
from app.api.dependencies import close_db

app = FastAPI(
    title="AuraMatch AI",
    description="AI-Powered Fragrance Recommendation Engine",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search_router)
app.include_router(dupe_router)

@app.on_event("shutdown")
async def shutdown():
    await close_db()

@app.get("/")
async def root():
    return {"app": "AuraMatch AI", "status": "running"}

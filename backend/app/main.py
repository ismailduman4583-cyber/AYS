from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from .routers import auth, araclar, operasyon, workspace, modules, admin, v5
app=FastAPI(title='Ambulans Yönetim Sistemi AYS API',version='13.0.0')
app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_credentials=False,allow_methods=['*'],allow_headers=['*'])
app.include_router(auth.router); app.include_router(araclar.router); app.include_router(operasyon.router)
app.include_router(workspace.router); app.include_router(modules.router); app.include_router(admin.router); app.include_router(v5.router)
@app.get('/health')
def health(): return {'status':'ok','version':'13.0.0'}

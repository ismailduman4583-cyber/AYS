import uuid, jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import text
from .db import get_db
from .config import settings
from .models import Kullanici

bearer=HTTPBearer()
def current_user(c:HTTPAuthorizationCredentials=Depends(bearer),db:Session=Depends(get_db)):
    try:
        payload=jwt.decode(c.credentials,settings.jwt_secret,algorithms=['HS256']); uid=uuid.UUID(payload['sub'])
    except Exception: raise HTTPException(401,'Geçersiz veya süresi dolmuş oturum')
    u=db.get(Kullanici,uid)
    if not u or not u.aktif_mi: raise HTTPException(401,'Kullanıcı pasif veya bulunamadı')
    return u

def has_permission(db:Session,u:Kullanici,modul:str,islem:str)->bool:
    yid=db.execute(text("SELECT yetki_id FROM aftys.yetkiler WHERE modul=:m AND islem=:i"),{'m':modul,'i':islem}).scalar_one_or_none()
    if not yid: return False
    override=db.execute(text("SELECT izin FROM aftys.kullanici_yetkileri WHERE kullanici_id=:u AND yetki_id=:y"),{'u':str(u.kullanici_id),'y':yid}).scalar_one_or_none()
    if override is not None: return bool(override)
    allowed=db.execute(text("""SELECT bool_or(ry.izin) FROM aftys.kullanici_rolleri kr JOIN aftys.rol_yetkileri ry ON ry.rol_id=kr.rol_id
      WHERE kr.kullanici_id=:u AND ry.yetki_id=:y"""),{'u':str(u.kullanici_id),'y':yid}).scalar_one_or_none()
    return bool(allowed)

def require_permission(db:Session,u:Kullanici,modul:str,islem:str):
    if not has_permission(db,u,modul,islem): raise HTTPException(403,f'Yetkiniz yok: {modul} / {islem}')

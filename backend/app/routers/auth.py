from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, text
from ..db import get_db
from ..models import Kullanici
from ..schemas import LoginIn
from ..security import verify_password, create_token

router=APIRouter(prefix='/api/auth',tags=['Auth'])
@router.post('/login')
def login(body:LoginIn,db:Session=Depends(get_db)):
    u=db.execute(text("SELECT kullanici_id FROM aftys.kullanicilar WHERE tc_kimlik_no=:x OR (tc_kimlik_no IS NULL AND kullanici_adi=:x) LIMIT 1"),{'x':body.kullanici_adi}).scalar(); u=db.get(Kullanici,u) if u else None
    if not u or not u.aktif_mi or not verify_password(body.parola,u.parola_hash):
        raise HTTPException(401,'TC Kimlik No veya parola hatalı')
    force=db.execute(text("SELECT COALESCE(parola_degistir_zorunlu,false) FROM aftys.kullanicilar WHERE kullanici_id=:u"),{'u':str(u.kullanici_id)}).scalar()
    return {'access_token':create_token(str(u.kullanici_id)),'token_type':'bearer','ad_soyad':u.ad_soyad,'parola_degistir_zorunlu':bool(force)}

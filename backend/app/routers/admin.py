from typing import Any
import os
from uuid import UUID, uuid4
import json
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy import text
from sqlalchemy.orm import Session
from ..db import get_db
from ..deps import current_user
from ..security import hash_password

router=APIRouter(prefix='/api/admin',tags=['Kullanıcı/Rol/Yetki'])

def require_admin(db:Session,u):
    roles=[r[0] for r in db.execute(text("SELECT r.ad FROM aftys.kullanici_rolleri kr JOIN aftys.roller r ON r.rol_id=kr.rol_id WHERE kr.kullanici_id=:u"),{'u':str(u.kullanici_id)}).all()]
    if not any(x in ('Sistem Yöneticisi','Yönetici') for x in roles): raise HTTPException(403,'Bu işlem için Yönetici veya Sistem Yöneticisi rolü gerekir')

def rows(r): return [dict(x._mapping) for x in r]

@router.get('/access')
def access(db:Session=Depends(get_db),u=Depends(current_user)):
    require_admin(db,u)
    users=rows(db.execute(text("""SELECT k.kullanici_id::text kullanici_id,k.kullanici_adi,k.tc_kimlik_no,k.ad_soyad,k.eposta,k.telefon,k.aktif_mi,
      COALESCE(array_agg(DISTINCT r.ad) FILTER (WHERE r.ad IS NOT NULL),'{}') roller,
      COALESCE(array_agg(DISTINCT r.rol_id) FILTER (WHERE r.rol_id IS NOT NULL),'{}') rol_ids
      FROM aftys.kullanicilar k LEFT JOIN aftys.kullanici_rolleri kr ON kr.kullanici_id=k.kullanici_id LEFT JOIN aftys.roller r ON r.rol_id=kr.rol_id
      GROUP BY k.kullanici_id ORDER BY k.ad_soyad""")))
    roles=rows(db.execute(text("SELECT rol_id,ad,aktif_mi FROM aftys.roller WHERE aktif_mi=true ORDER BY rol_id")))
    perms=rows(db.execute(text("SELECT yetki_id,modul,islem,COALESCE(aciklama,'') aciklama FROM aftys.yetkiler ORDER BY modul,islem")))
    overrides=rows(db.execute(text("SELECT kullanici_id::text kullanici_id,yetki_id,izin FROM aftys.kullanici_yetkileri")))
    return {'users':users,'roles':roles,'permissions':perms,'overrides':overrides}

@router.post('/users',status_code=201)
def create_user(b:dict[str,Any]=Body(...),db:Session=Depends(get_db),u=Depends(current_user)):
    require_admin(db,u)
    for f in ('tc_kimlik_no','ad_soyad','parola'):
        if not str(b.get(f) or '').strip(): raise HTTPException(422,f'{f} zorunlu')
    if len(str(b['parola']))<8: raise HTTPException(422,'Şifre en az 8 karakter olmalı')
    username=str(b['tc_kimlik_no']).strip();
    if len(username)!=11 or not username.isdigit(): raise HTTPException(422,'TC Kimlik No 11 haneli olmalı')
    full_name=str(b['ad_soyad']).strip()
    role_ids=[int(x) for x in (b.get('rol_ids') or [])]
    overrides=b.get('overrides') or []
    try:
      # Canlı veritabanında UUID default'u bulunmasa bile kayıt çalışsın.
      uid=uuid4()
      db.execute(text("""INSERT INTO aftys.kullanicilar
        (kullanici_id,kullanici_adi,tc_kimlik_no,parola_hash,ad_soyad,eposta,telefon,aktif_mi)
        VALUES(:id,:ka,:ka,:p,:ad,:e,:t,true)"""),{
          'id':str(uid),'ka':username,'p':hash_password(str(b['parola'])),'ad':full_name,
          'e':(str(b.get('eposta')).strip() if b.get('eposta') else None),
          't':(str(b.get('telefon')).strip() if b.get('telefon') else None)})
      if role_ids:
        valid={int(x[0]) for x in db.execute(text("SELECT rol_id FROM aftys.roller WHERE aktif_mi=true")).all()}
        invalid=[x for x in role_ids if x not in valid]
        if invalid: raise HTTPException(422,f'Geçersiz rol: {invalid[0]}')
        for rid in role_ids:
          db.execute(text("INSERT INTO aftys.kullanici_rolleri(kullanici_id,rol_id) VALUES(:u,:r) ON CONFLICT DO NOTHING"),{'u':str(uid),'r':rid})
      for item in overrides:
        yid=int(item.get('yetki_id'))
        exists=db.execute(text("SELECT 1 FROM aftys.yetkiler WHERE yetki_id=:y"),{'y':yid}).scalar_one_or_none()
        if not exists: raise HTTPException(422,f'Geçersiz yetki: {yid}')
        db.execute(text("INSERT INTO aftys.kullanici_yetkileri(kullanici_id,yetki_id,izin) VALUES(:u,:y,:i) ON CONFLICT(kullanici_id,yetki_id) DO UPDATE SET izin=EXCLUDED.izin"),{'u':str(uid),'y':yid,'i':bool(item.get('izin'))})
      db.execute(text("""INSERT INTO aftys.audit_log
        (kullanici_id,entity_type,entity_id,islem,yeni_json)
        VALUES(:cu,'KULLANICI',:id,'CREATE',CAST(:j AS jsonb))"""),{
          'cu':str(u.kullanici_id),'id':str(uid),
          'j':json.dumps({'kullanici_adi':username,'ad_soyad':full_name},ensure_ascii=False)})
      db.commit()
      return {'kullanici_id':str(uid),'kullanici_adi':username,'ad_soyad':full_name}
    except HTTPException:
      db.rollback(); raise
    except Exception as e:
      db.rollback()
      msg=str(e).lower()
      if 'unique' in msg or 'duplicate' in msg or 'kullanicilar_kullanici_adi' in msg:
        raise HTTPException(409,'TC Kimlik No zaten kullanılıyor')
      # Ham veritabanı ayrıntısını kullanıcıya dökmeyip, takip edilebilir bir hata ver.
      raise HTTPException(500,'Kullanıcı kaydı tamamlanamadı. Veritabanı uyumluluğu kontrol edilmelidir.')

@router.put('/users/{uid}/access')
def set_access(uid:UUID,b:dict[str,Any]=Body(...),db:Session=Depends(get_db),u=Depends(current_user)):
    require_admin(db,u)
    if str(uid)==str(u.kullanici_id) and b.get('aktif_mi') is False: raise HTTPException(409,'Kendi hesabınızı pasife alamazsınız')
    if 'aktif_mi' in b: db.execute(text("UPDATE aftys.kullanicilar SET aktif_mi=:a WHERE kullanici_id=:u"),{'a':bool(b['aktif_mi']),'u':str(uid)})
    if 'rol_ids' in b:
      db.execute(text("DELETE FROM aftys.kullanici_rolleri WHERE kullanici_id=:u"),{'u':str(uid)})
      for rid in b.get('rol_ids') or []: db.execute(text("INSERT INTO aftys.kullanici_rolleri(kullanici_id,rol_id) VALUES(:u,:r)"),{'u':str(uid),'r':rid})
    if 'overrides' in b:
      db.execute(text("DELETE FROM aftys.kullanici_yetkileri WHERE kullanici_id=:u"),{'u':str(uid)})
      for item in b.get('overrides') or []:
        db.execute(text("INSERT INTO aftys.kullanici_yetkileri(kullanici_id,yetki_id,izin) VALUES(:u,:y,:i)"),{'u':str(uid),'y':item['yetki_id'],'i':bool(item['izin'])})
    db.execute(text("INSERT INTO aftys.audit_log(kullanici_id,entity_type,entity_id,islem,yeni_json) VALUES(:cu,'KULLANICI',:id,'ACCESS_UPDATE',CAST(:j AS jsonb))"),{'cu':str(u.kullanici_id),'id':str(uid),'j':'{}'})
    db.commit(); return {'ok':True}

@router.put('/users/{uid}/password')
def reset_password(uid:UUID,b:dict[str,Any]=Body(default={}),db:Session=Depends(get_db),u=Depends(current_user)):
    require_admin(db,u)
    if not db.execute(text("SELECT 1 FROM aftys.kullanicilar WHERE kullanici_id=:id"),{'id':str(uid)}).first(): raise HTTPException(404,'Kullanıcı bulunamadı')
    pw=os.environ.get('AFTYS_RESET_PASSWORD','Degistir123!')
    if len(pw)<8: raise HTTPException(500,'Standart geçici parola yapılandırması geçersiz')
    db.execute(text("UPDATE aftys.kullanicilar SET parola_hash=:p,parola_degistir_zorunlu=true,updated_at=now() WHERE kullanici_id=:u"),{'p':hash_password(pw),'u':str(uid)})
    db.execute(text("INSERT INTO aftys.audit_log(kullanici_id,entity_type,entity_id,islem,gerekce) VALUES(:cu,'KULLANICI',:id,'PASSWORD_RESET','Yönetici tarafından standart geçici parola ile sıfırlandı')"),{'cu':str(u.kullanici_id),'id':str(uid)})
    db.commit(); return {'ok':True,'gecici_parola_standart':True,'ilk_giriste_degistir':True}

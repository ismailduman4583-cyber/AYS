import os, time, uuid
from sqlalchemy import create_engine, text
from pwdlib import PasswordHash
url=os.environ['DATABASE_URL']; user=os.environ.get('AFTYS_ADMIN_USER','admin'); pw=os.environ.get('AFTYS_ADMIN_PASSWORD')
if not pw: raise SystemExit('AFTYS_ADMIN_PASSWORD is required')
engine=create_engine(url,pool_pre_ping=True); ph=PasswordHash.recommended()
for i in range(30):
    try:
        with engine.begin() as c:
            row=c.execute(text("select kullanici_id from aftys.kullanicilar where kullanici_adi=:u"),{'u':user}).first()
            if not row:
                uid=uuid.uuid4()
                c.execute(text("insert into aftys.kullanicilar(kullanici_id,kullanici_adi,parola_hash,ad_soyad) values(:id,:u,:p,:n)"),{'id':str(uid),'u':user,'p':ph.hash(pw),'n':'AFTYS Sistem Yöneticisi'})
            else: uid=row[0]
            rid=c.execute(text("select rol_id from aftys.roller where ad='Sistem Yöneticisi'" )).scalar_one_or_none()
            if rid:
                c.execute(text("insert into aftys.kullanici_rolleri(kullanici_id,rol_id) values(:u,:r) on conflict do nothing"),{'u':str(uid),'r':rid})
        break
    except Exception:
        if i==29: raise
        time.sleep(2)
print('AFTYS admin bootstrap OK')

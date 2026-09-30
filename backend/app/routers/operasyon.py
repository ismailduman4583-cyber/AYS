from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from ..db import get_db
from ..deps import current_user, require_permission
from ..models import Arac, Ariza, IsEmri, ServisIslemi, TeslimTesellum, GayrifaalDonem, AracDurumu, AracZamanCizelgesi, AuditLog
from ..schemas import IsEmriCreate, TeknikOnarim, ServiseGonder, ServistenTeslimAl, TesteAl, GoreveDondur

router=APIRouter(prefix='/api/operasyon',tags=['Teknik Operasyon'])

def now(): return datetime.now(timezone.utc)

def next_work_no(db:Session):
    year=datetime.now(timezone.utc).year
    n=db.execute(text("""INSERT INTO aftys.numara_sayaclari(seri,yil,son_no) VALUES('IE',:y,1)
      ON CONFLICT(seri,yil) DO UPDATE SET son_no=aftys.numara_sayaclari.son_no+1 RETURNING son_no"""),{'y':year}).scalar_one()
    return f"IE-{year}-{int(n):04d}"

def durum_id(db:Session,kod:str):
    d=db.scalar(select(AracDurumu).where(AracDurumu.kod==kod))
    if not d: raise HTTPException(500,f'Araç durum tanımı eksik: {kod}')
    return d.arac_durum_id

def timeline(db,arac_id,tip,kaynak_tipi,kaynak_id,ozet,u):
    db.add(AracZamanCizelgesi(arac_id=arac_id,olay_tipi=tip,kaynak_tipi=kaynak_tipi,kaynak_id=str(kaynak_id),ozet=ozet,kullanici_id=u.kullanici_id))

def audit(db,u,entity_type,entity_id,islem,eski=None,yeni=None,gerekce=None):
    db.add(AuditLog(kullanici_id=u.kullanici_id,entity_type=entity_type,entity_id=str(entity_id),islem=islem,eski_json=eski,yeni_json=yeni,gerekce=gerekce))

@router.post('/is-emirleri',status_code=201)
def is_emri_ac(b:IsEmriCreate,db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Arıza & İş Emri','EKLE')
    a=db.get(Arac,b.arac_id)
    if not a: raise HTTPException(404,'Araç bulunamadı')
    if b.ariza_id and not db.get(Ariza,b.ariza_id): raise HTTPException(404,'Arıza bulunamadı')
    try:
        x=IsEmri(is_emri_no=next_work_no(db),arac_id=b.arac_id,kaynak_tipi='ARIZA' if b.ariza_id else None,kaynak_id=b.ariza_id,islem_turu=b.islem_turu,talep=b.talep,oncelik=b.oncelik,sorumlu_kullanici_id=b.sorumlu_kullanici_id or u.kullanici_id)
        db.add(x); db.flush()
        if b.ariza_id:
            ar=db.get(Ariza,b.ariza_id); ar.durum='IS_EMRI_ACILDI'
        timeline(db,a.arac_id,'IS_EMRI_ACILDI','IS_EMRI',x.is_emri_id,f'{x.is_emri_no} açıldı',u)
        audit(db,u,'IS_EMRI',x.is_emri_id,'CREATE',yeni={'is_emri_no':x.is_emri_no,'durum':x.durum})
        db.commit(); return {'is_emri_id':x.is_emri_id,'is_emri_no':x.is_emri_no,'durum':x.durum}
    except: db.rollback(); raise

@router.post('/is-emirleri/{is_emri_id}/teknik-onarim')
def teknik_onarim(is_emri_id:int,b:TeknikOnarim,db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Arıza & İş Emri','EKLE')
    x=db.get(IsEmri,is_emri_id)
    if not x: raise HTTPException(404,'İş emri bulunamadı')
    if x.durum in ('TAMAMLANDI','IPTAL'): raise HTTPException(409,'Kapalı iş emri değiştirilemez')
    x.durum='ISLEMDE'; x.yapilan_islem=b.yapilan_islem
    timeline(db,x.arac_id,'TEKNIK_ONARIM','IS_EMRI',x.is_emri_id,'Teknik Birimde onarım işlemi kaydedildi',u)
    audit(db,u,'IS_EMRI',x.is_emri_id,'TEKNIK_ONARIM',yeni={'durum':'ISLEMDE','yapilan_islem':b.yapilan_islem})
    db.commit(); return {'is_emri_id':x.is_emri_id,'durum':x.durum}

@router.post('/is-emirleri/{is_emri_id}/servise-gonder',status_code=201)
def servise_gonder(is_emri_id:int,b:ServiseGonder,db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Arıza & İş Emri','EKLE')
    x=db.get(IsEmri,is_emri_id)
    if not x: raise HTTPException(404,'İş emri bulunamadı')
    a=db.get(Arac,x.arac_id)
    if x.durum in ('TAMAMLANDI','IPTAL'): raise HTTPException(409,'Kapalı iş emri servise gönderilemez')
    acik=db.scalar(select(ServisIslemi).where(ServisIslemi.arac_id==a.arac_id,ServisIslemi.cikis_tarihi.is_(None)))
    if acik: raise HTTPException(409,'Araç için açık servis işlemi mevcut')
    try:
        s=ServisIslemi(arac_id=a.arac_id,servis_id=b.servis_id,kaynak_tipi='IS_EMRI',kaynak_id=x.is_emri_id,giris_tarihi=now(),servis_kabul_no=b.servis_kabul_no,durum='SERVISTE')
        db.add(s); db.flush()
        t=TeslimTesellum(arac_id=a.arac_id,teslim_turu='DIS_SERVISE_TESLIM',tarih_saat=now(),servis_id=b.servis_id,teslim_eden=b.teslim_eden,servis_yetkilisi=b.servis_yetkilisi,neden=b.neden,aciklama=b.aciklama,created_by=u.kullanici_id)
        db.add(t)
        g=GayrifaalDonem(arac_id=a.arac_id,baslangic_ts=now(),kaynak_tipi='SERVIS_ISLEMI',kaynak_id=s.servis_islem_id,aciklama=b.neden)
        db.add(g)
        a.arac_durum_id=durum_id(db,'ARIZALI_SERVISTE'); x.durum='ISLEMDE'
        timeline(db,a.arac_id,'SERVISE_GONDERILDI','SERVIS_ISLEMI',s.servis_islem_id,'Araç dış servise gönderildi',u)
        audit(db,u,'SERVIS_ISLEMI',s.servis_islem_id,'CREATE',yeni={'is_emri_id':x.is_emri_id,'servis_id':b.servis_id})
        db.commit(); return {'servis_islem_id':s.servis_islem_id,'durum':'SERVISTE'}
    except: db.rollback(); raise

@router.post('/servis-islemleri/{servis_islem_id}/teslim-al')
def servisten_teslim_al(servis_islem_id:int,b:ServistenTeslimAl,db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Arıza & İş Emri','EKLE')
    s=db.get(ServisIslemi,servis_islem_id)
    if not s: raise HTTPException(404,'Servis işlemi bulunamadı')
    if s.cikis_tarihi: raise HTTPException(409,'Araç zaten servisten teslim alınmış')
    a=db.get(Arac,s.arac_id)
    try:
        s.cikis_tarihi=now(); s.yapilan_islem=b.yapilan_islem; s.degisen_parcalar=b.degisen_parcalar
        s.parca_tutari=b.parca_tutari; s.iscilik_tutari=b.iscilik_tutari; s.diger_tutar=b.diger_tutar; s.durum='TESLIM_ALINDI'
        t=TeslimTesellum(arac_id=a.arac_id,teslim_turu='DIS_SERVISTEN_TESLIM_ALMA',tarih_saat=now(),servis_id=s.servis_id,teslim_alan=b.teslim_alan,servis_yetkilisi=b.servis_yetkilisi,aciklama=b.aciklama,created_by=u.kullanici_id)
        db.add(t)
        a.arac_durum_id=durum_id(db,'ARIZA_GIDERILDI_TEST')
        if s.kaynak_tipi=='IS_EMRI' and s.kaynak_id:
            x=db.get(IsEmri,s.kaynak_id)
            if x: x.durum='TESTTE'; x.yapilan_islem=b.yapilan_islem
        timeline(db,a.arac_id,'SERVISTEN_TESLIM_ALINDI','SERVIS_ISLEMI',s.servis_islem_id,'Araç servisten teslim alındı ve teste alındı',u)
        audit(db,u,'SERVIS_ISLEMI',s.servis_islem_id,'TESLIM_AL',yeni={'durum':'TESLIM_ALINDI'})
        db.commit(); return {'servis_islem_id':s.servis_islem_id,'arac_durumu':'ARIZA_GIDERILDI_TEST'}
    except: db.rollback(); raise

@router.post('/is-emirleri/{is_emri_id}/teste-al')
def teste_al(is_emri_id:int,b:TesteAl,db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Arıza & İş Emri','EKLE')
    x=db.get(IsEmri,is_emri_id)
    if not x: raise HTTPException(404,'İş emri bulunamadı')
    if x.durum in ('TAMAMLANDI','IPTAL'): raise HTTPException(409,'Kapalı iş emri teste alınamaz')
    a=db.get(Arac,x.arac_id); x.durum='TESTTE'; x.yapilan_islem=b.yapilan_islem or x.yapilan_islem
    a.arac_durum_id=durum_id(db,'ARIZA_GIDERILDI_TEST')
    timeline(db,a.arac_id,'TESTE_ALINDI','IS_EMRI',x.is_emri_id,'Araç test sürecine alındı',u)
    audit(db,u,'IS_EMRI',x.is_emri_id,'TESTE_AL',yeni={'durum':'TESTTE'})
    db.commit(); return {'is_emri_id':x.is_emri_id,'durum':'TESTTE'}

@router.post('/is-emirleri/{is_emri_id}/goreve-dondur')
def goreve_dondur(is_emri_id:int,b:GoreveDondur,db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Arıza & İş Emri','EKLE')
    x=db.get(IsEmri,is_emri_id)
    if not x: raise HTTPException(404,'İş emri bulunamadı')
    if x.durum!='TESTTE': raise HTTPException(409,'Göreve dönüş için iş emri TESTTE durumunda olmalı')
    a=db.get(Arac,x.arac_id)
    if not b.test_basarili:
        x.durum='ISLEMDE'; x.sonuc=b.sonuc
        timeline(db,a.arac_id,'TEST_BASARISIZ','IS_EMRI',x.is_emri_id,'Test başarısız; araç onarım sürecine döndü',u)
        audit(db,u,'IS_EMRI',x.is_emri_id,'TEST_BASARISIZ',gerekce=b.sonuc)
        db.commit(); return {'is_emri_id':x.is_emri_id,'durum':'ISLEMDE','goreve_dondu':False}
    try:
        x.durum='TAMAMLANDI'; x.kapanis_tarihi=now(); x.sonuc=b.sonuc
        a.arac_durum_id=durum_id(db,'AKTIF_YEDEK' if b.hedef_durum=='YEDEK' else 'AKTIF_GOREVDE')
        g=db.scalar(select(GayrifaalDonem).where(GayrifaalDonem.arac_id==a.arac_id,GayrifaalDonem.bitis_ts.is_(None)).order_by(GayrifaalDonem.baslangic_ts.desc()))
        if g: g.bitis_ts=now()
        if x.kaynak_tipi=='ARIZA' and x.kaynak_id:
            ar=db.get(Ariza,x.kaynak_id)
            if ar: ar.durum='TAMAMLANDI'
        timeline(db,a.arac_id,'GOREVE_DONDU','IS_EMRI',x.is_emri_id,'Araç test sonrası göreve döndü',u)
        audit(db,u,'IS_EMRI',x.is_emri_id,'TAMAMLA',yeni={'durum':'TAMAMLANDI','hedef_durum':b.hedef_durum})
        db.commit(); return {'is_emri_id':x.is_emri_id,'durum':'TAMAMLANDI','goreve_dondu':True,'hedef_durum':b.hedef_durum}
    except: db.rollback(); raise

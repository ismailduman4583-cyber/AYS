from datetime import datetime, timezone, timedelta
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from sqlalchemy import select, func, text
from ..db import get_db
from ..deps import current_user, require_permission
from ..models import Arac, KimlikGecmisi, KmGecmisi, Ariza, AracDurumu, AracZamanCizelgesi
from ..schemas import AracCreate, KmCreate, KimlikChange, ArizaCreate

router=APIRouter(prefix='/api/araclar',tags=['Araçlar'])

def aktif_kimlik(db,arac_id,tip):
    return db.scalar(select(KimlikGecmisi).where(KimlikGecmisi.arac_id==arac_id,KimlikGecmisi.alan_tipi==tip,KimlikGecmisi.bitis_tarihi.is_(None)))

@router.get('')
def liste(q:str|None=None,db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Araçlar','GORUNTULE')
    stmt=select(Arac).where(Arac.aktif_mi==True)
    if q:
        ids=select(KimlikGecmisi.arac_id).where(func.upper(KimlikGecmisi.deger).contains(q.upper()))
        stmt=stmt.where(Arac.arac_id.in_(ids))
    rows=db.scalars(stmt.order_by(Arac.marka,Arac.model)).all()
    out=[]
    for a in rows:
        p=aktif_kimlik(db,a.arac_id,'PLAKA')
        d=db.get(AracDurumu,a.arac_durum_id) if a.arac_durum_id else None
        gecici=db.execute(text("SELECT 1 FROM aftys.arac_devirleri WHERE arac_id=:a AND devir_turu='GECICI' AND COALESCE(durum,'AKTIF') NOT IN ('KAPANDI','IPTAL','TAMAMLANDI') ORDER BY fiili_devir_tarihi DESC LIMIT 1"),{'a':str(a.arac_id)}).first()
        st=db.execute(text("SELECT concat_ws(' — ',NULLIF(trim(concat_ws(' ',kod,telsiz_adi)),''),ad) FROM aftys.istasyon_birimler WHERE birim_id=:i"),{'i':a.gunluk_birim_id}).scalar_one_or_none() if a.gunluk_birim_id else None
        lk=db.execute(text('SELECT adblue_var FROM aftys.km_gecmisi WHERE arac_id=:a ORDER BY tarih_saat DESC LIMIT 1'),{'a':str(a.arac_id)}).scalar_one_or_none()
        out.append({'arac_id':str(a.arac_id),'plaka':p.deger if p else None,'arac_sinifi':a.arac_sinifi,'ambulans_tipi':db.execute(text('SELECT ambulans_tipi FROM aftys.araclar WHERE arac_id=:id'),{'id':str(a.arac_id)}).scalar_one_or_none(),'marka':a.marka,'model':a.model,'model_yili':a.model_yili,'gosterge_km':a.gosterge_km,'durum':'GECICI_DEVIRDE' if gecici else (d.kod if d else None),'istasyon_birim_id':a.gunluk_birim_id,'istasyon':st,'adblue_var':bool(lk)})
    return out

@router.post('',status_code=201)
def olustur(b:AracCreate,db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Araçlar','EKLE')
    existing=db.scalar(select(KimlikGecmisi).where(KimlikGecmisi.alan_tipi=='PLAKA',func.upper(KimlikGecmisi.deger)==b.plaka.upper(),KimlikGecmisi.bitis_tarihi.is_(None)))
    if existing: raise HTTPException(409,'Bu plaka aktif olarak kayıtlı')
    try:
        durum=b.arac_durum_id
        if durum is None:
            d=db.scalar(select(AracDurumu).where(AracDurumu.kod=='AKTIF_YEDEK'))
            durum=d.arac_durum_id if d else None
        a=Arac(arac_sinifi=b.arac_sinifi,arac_tur_id=b.arac_tur_id,marka=b.marka,model=b.model,model_yili=b.model_yili,yakit_turu=b.yakit_turu,renk=b.renk,arac_durum_id=durum,gunluk_birim_id=b.gunluk_birim_id,gosterge_km=b.baslangic_km,kumulatif_km=b.baslangic_km,aciklama=b.aciklama)
        db.add(a); db.flush()
        db.execute(text("UPDATE aftys.araclar SET ambulans_tipi=:tip WHERE arac_id=:id"),{'tip':b.ambulans_tipi if b.arac_sinifi=='AMBULANS' else None,'id':str(a.arac_id)})
        for tip,val in [('PLAKA',b.plaka),('SASI_NO',b.sasi_no),('MOTOR_NO',b.motor_no)]:
            if val: db.add(KimlikGecmisi(arac_id=a.arac_id,alan_tipi=tip,deger=val,degisiklik_tipi='ILK_KAYIT'))
        db.add(KmGecmisi(arac_id=a.arac_id,gosterge_km=b.baslangic_km,kumulatif_km=b.baslangic_km,tibbi_donanim_markasi=b.tibbi_donanim_markasi,adblue_var=b.adblue_var,kaynak_tipi='ARAC_ILK_KAYIT'))
        db.add(AracZamanCizelgesi(arac_id=a.arac_id,olay_tipi='ARAC_KAYDI',kaynak_tipi='ARAC',kaynak_id=str(a.arac_id),ozet=f'{b.plaka} araç kaydı oluşturuldu',kullanici_id=u.kullanici_id))
        db.commit(); return {'arac_id':str(a.arac_id),'plaka':b.plaka}
    except: db.rollback(); raise


def arac_yonetici(db:Session,u):
    ok=db.execute(text("SELECT 1 FROM aftys.kullanici_rolleri kr JOIN aftys.roller r ON r.rol_id=kr.rol_id WHERE kr.kullanici_id=:uid AND r.ad IN ('Sistem Yöneticisi','Yönetici') LIMIT 1"),{'uid':str(u.kullanici_id)}).first()
    if not ok: raise HTTPException(403,'Bu işlem için yönetici rolü gerekir')

AMBULANS_TURLERI={'PANELVAN','DÖRT SEDYELİ','KAR PALETLİ','OBEZ/YOĞUN BAKIM','YENİDOĞAN','MOTOSİKLET'}

@router.put('/{arac_id}/yonetici')
def arac_admin_guncelle(arac_id:UUID,b:dict=Body(...),db:Session=Depends(get_db),u=Depends(current_user)):
    arac_yonetici(db,u)
    a=db.get(Arac,arac_id)
    if not a or not a.aktif_mi: raise HTTPException(404,'Aktif araç bulunamadı')
    plaka=str(b.get('plaka') or '').strip().upper()
    marka=str(b.get('marka') or '').strip()
    if not plaka or not marka: raise HTTPException(422,'Plaka ve marka zorunlu')
    tip=b.get('ambulans_tipi') or None
    if a.arac_sinifi=='AMBULANS' and tip not in AMBULANS_TURLERI:
        raise HTTPException(422,'Geçerli ambulans türünü seçin')
    yil=b.get('model_yili')
    if yil not in (None,'') and not 1950<=int(yil)<=2200:
        raise HTTPException(422,'Model yılı geçersiz')
    eski=aktif_kimlik(db,arac_id,'PLAKA')
    if not eski or eski.deger.upper()!=plaka:
        cakisma=db.scalar(select(KimlikGecmisi).where(KimlikGecmisi.alan_tipi=='PLAKA',func.upper(KimlikGecmisi.deger)==plaka,KimlikGecmisi.bitis_tarihi.is_(None)))
        if cakisma: raise HTTPException(409,'Bu plaka başka araçta kayıtlı')
        if eski: eski.bitis_tarihi=datetime.now(timezone.utc)
        db.add(KimlikGecmisi(arac_id=arac_id,alan_tipi='PLAKA',deger=plaka,degisiklik_tipi='KAYIT_DUZELTME'))
    a.marka=marka
    a.model=str(b.get('model') or '').strip() or None
    a.model_yili=int(yil) if yil not in (None,'') else None
    db.execute(text("UPDATE aftys.araclar SET ambulans_tipi=:tip WHERE arac_id=:id"),{'tip':tip if a.arac_sinifi=='AMBULANS' else None,'id':str(arac_id)})
    db.add(AracZamanCizelgesi(arac_id=arac_id,olay_tipi='ARAC_BILGI_DUZELTME',kaynak_tipi='ARAC',kaynak_id=str(arac_id),ozet='Araç bilgileri yönetici tarafından düzenlendi',kullanici_id=u.kullanici_id))
    db.commit()
    return {'ok':True}

@router.delete('/{arac_id}/yonetici')
def arac_admin_sil(arac_id:UUID,db:Session=Depends(get_db),u=Depends(current_user)):
    arac_yonetici(db,u)
    a=db.get(Arac,arac_id)
    if not a or not a.aktif_mi: raise HTTPException(404,'Aktif araç bulunamadı')
    a.aktif_mi=False
    db.add(AracZamanCizelgesi(arac_id=arac_id,olay_tipi='ARAC_PASIFE_ALINDI',kaynak_tipi='ARAC',kaynak_id=str(arac_id),ozet='Araç yönetici tarafından pasife alındı',kullanici_id=u.kullanici_id))
    db.commit()
    return {'ok':True}

@router.get('/{arac_id}')
def detay(arac_id:UUID,db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Araçlar','GORUNTULE')
    a=db.get(Arac,arac_id)
    if not a: raise HTTPException(404,'Araç bulunamadı')
    kimlik={x.alan_tipi:x.deger for x in db.scalars(select(KimlikGecmisi).where(KimlikGecmisi.arac_id==arac_id,KimlikGecmisi.bitis_tarihi.is_(None))).all()}
    last_km=db.scalar(select(KmGecmisi).where(KmGecmisi.arac_id==arac_id).order_by(KmGecmisi.tarih_saat.desc()))
    d=db.get(AracDurumu,a.arac_durum_id) if a.arac_durum_id else None
    return {'arac_id':str(a.arac_id),'arac_sinifi':a.arac_sinifi,'marka':a.marka,'model':a.model,'model_yili':a.model_yili,'gosterge_km':a.gosterge_km,'kumulatif_km':a.kumulatif_km,'yakit_turu':a.yakit_turu,'renk':a.renk,'durum':d.kod if d else None,'adblue_var':last_km.adblue_var if last_km else False,'tibbi_donanim_markasi':last_km.tibbi_donanim_markasi if last_km else None,'kimlik':kimlik}

@router.post('/{arac_id}/km')
def km_ekle(arac_id:UUID,b:KmCreate,db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Araçlar','DUZENLE')
    a=db.get(Arac,arac_id)
    if not a: raise HTTPException(404,'Araç bulunamadı')
    if b.gosterge_km<a.gosterge_km: raise HTTPException(409,'Yeni KM mevcut gösterge KM değerinden düşük. Sayaç değişimi sürecini kullanın.')
    delta=b.gosterge_km-a.gosterge_km; a.gosterge_km=b.gosterge_km; a.kumulatif_km+=delta
    k=KmGecmisi(arac_id=arac_id,gosterge_km=a.gosterge_km,kumulatif_km=a.kumulatif_km,kaynak_tipi='MANUEL_KM',aciklama=b.aciklama)
    db.add(k); db.add(AracZamanCizelgesi(arac_id=arac_id,olay_tipi='KM_GIRISI',kaynak_tipi='KM',kaynak_id='MANUEL',ozet=f'Gösterge KM {a.gosterge_km} olarak güncellendi',kullanici_id=u.kullanici_id)); db.commit(); return {'gosterge_km':a.gosterge_km,'kumulatif_km':a.kumulatif_km}

@router.post('/{arac_id}/kimlik-degisikligi')
def kimlik_degistir(arac_id:UUID,b:KimlikChange,db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Araçlar','DUZENLE')
    if not db.get(Arac,arac_id): raise HTTPException(404,'Araç bulunamadı')
    old=aktif_kimlik(db,arac_id,b.alan_tipi)
    now=datetime.now(timezone.utc)
    if old: old.bitis_tarihi=now
    db.add(KimlikGecmisi(arac_id=arac_id,alan_tipi=b.alan_tipi,deger=b.yeni_deger,baslangic_tarihi=now,degisiklik_tipi=b.degisiklik_tipi,neden=b.neden))
    db.commit(); return {'alan':b.alan_tipi,'eski':old.deger if old else None,'yeni':b.yeni_deger}


@router.get('/{arac_id}/tahsis')
def tahsis_bilgisi(arac_id:UUID,db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Araçlar','GORUNTULE')
    row=db.execute(text("""SELECT t.tahsis_id,t.birim_id,b.ad birim_adi,b.kod telsiz_kodu,b.telsiz_adi,t.baslangic_tarihi,t.baslangic_km,t.neden,t.aciklama
      FROM aftys.arac_tahsisleri t JOIN aftys.istasyon_birimler b ON b.birim_id=t.birim_id
      WHERE t.arac_id=:a AND t.bitis_tarihi IS NULL ORDER BY t.baslangic_tarihi DESC LIMIT 1"""),{'a':str(arac_id)}).mappings().first()
    return dict(row) if row else None

@router.post('/{arac_id}/istasyona-zimmetle')
def istasyona_zimmetle(arac_id:UUID,b:dict,db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Araçlar','DUZENLE')
    a=db.get(Arac,arac_id)
    if not a: raise HTTPException(404,'Araç bulunamadı')
    birim_id=b.get('birim_id')
    if not birim_id: raise HTTPException(422,'İstasyon / Birim zorunlu')
    if not db.execute(text('SELECT 1 FROM aftys.istasyon_birimler WHERE birim_id=:i AND aktif_mi=true'),{'i':birim_id}).scalar(): raise HTTPException(404,'İstasyon / Birim bulunamadı')
    try:
        now=b.get('baslangic_tarihi') or datetime.now(timezone.utc).isoformat()
        db.execute(text("UPDATE aftys.arac_tahsisleri SET bitis_tarihi=:t,bitis_km=:km WHERE arac_id=:a AND bitis_tarihi IS NULL"),{'t':now,'km':a.gosterge_km,'a':str(arac_id)})
        db.execute(text("INSERT INTO aftys.arac_tahsisleri(arac_id,birim_id,baslangic_tarihi,baslangic_km,neden,aciklama) VALUES(:a,:b,:t,:km,:n,:ac)"),{'a':str(arac_id),'b':birim_id,'t':now,'km':a.gosterge_km,'n':b.get('neden') or 'İstasyona zimmet','ac':b.get('aciklama')})
        durum=db.execute(text("SELECT arac_durum_id FROM aftys.arac_durumlari WHERE kod='AKTIF_GOREVDE' LIMIT 1")).scalar_one_or_none()
        a.gunluk_birim_id=birim_id
        if durum: a.arac_durum_id=durum
        db.add(AracZamanCizelgesi(arac_id=arac_id,olay_tipi='ISTASYONA_ZIMMET',kaynak_tipi='TAHSIS',kaynak_id=str(birim_id),ozet='Araç istasyona/birime zimmetlendi',kullanici_id=u.kullanici_id))
        db.commit(); return {'ok':True}
    except: db.rollback(); raise

@router.post('/{arac_id}/zimmeti-kaldir')
def zimmeti_kaldir(arac_id:UUID,b:dict|None=None,db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Araçlar','DUZENLE')
    a=db.get(Arac,arac_id)
    if not a: raise HTTPException(404,'Araç bulunamadı')
    try:
        db.execute(text("UPDATE aftys.arac_tahsisleri SET bitis_tarihi=now(),bitis_km=:km WHERE arac_id=:a AND bitis_tarihi IS NULL"),{'km':a.gosterge_km,'a':str(arac_id)})
        durum=db.execute(text("SELECT arac_durum_id FROM aftys.arac_durumlari WHERE kod='AKTIF_YEDEK' LIMIT 1")).scalar_one_or_none()
        a.gunluk_birim_id=None
        if durum: a.arac_durum_id=durum
        db.add(AracZamanCizelgesi(arac_id=arac_id,olay_tipi='ZIMMET_KALDIRILDI',kaynak_tipi='TAHSIS',kaynak_id='YEDEK',ozet='İstasyon/birim zimmeti kapatıldı; araç yedeğe alındı',kullanici_id=u.kullanici_id))
        db.commit(); return {'ok':True}
    except: db.rollback(); raise

@router.post('/{arac_id}/arizalar',status_code=201)
def ariza_ac(arac_id:UUID,b:ArizaCreate,db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Arıza & İş Emri','EKLE')
    a=db.get(Arac,arac_id)
    if not a: raise HTTPException(404,'Araç bulunamadı')
    km_id=None
    if b.gosterge_km is not None:
        if b.gosterge_km<a.gosterge_km: raise HTTPException(409,'Arıza KM mevcut KM değerinden düşük')
        delta=b.gosterge_km-a.gosterge_km; a.gosterge_km=b.gosterge_km; a.kumulatif_km+=delta
        k=KmGecmisi(arac_id=arac_id,gosterge_km=a.gosterge_km,kumulatif_km=a.kumulatif_km,kaynak_tipi='ARIZA')
        db.add(k); db.flush(); km_id=k.km_id
    cutoff=datetime.now(timezone.utc)-timedelta(days=730)
    repeat=db.scalar(select(func.count()).select_from(Ariza).where(Ariza.arac_id==arac_id,Ariza.kategori==b.kategori,Ariza.sistem_parca==b.sistem_parca,Ariza.tarih_saat>=cutoff))>0
    x=Ariza(arac_id=arac_id,km_id=km_id,kategori=b.kategori,sistem_parca=b.sistem_parca,aciklama=b.aciklama,tekrar_ariza_mi=repeat)
    db.add(x); db.flush(); db.add(AracZamanCizelgesi(arac_id=arac_id,olay_tipi='ARIZA_ACILDI',kaynak_tipi='ARIZA',kaynak_id=str(x.ariza_id),ozet=b.aciklama,kullanici_id=u.kullanici_id)); db.commit(); db.refresh(x)
    return {'ariza_id':x.ariza_id,'tekrar_ariza_mi':repeat}

from datetime import datetime, timezone
from uuid import UUID
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Body, UploadFile, File
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi.responses import FileResponse
import os, uuid, pathlib
from ..db import get_db
from ..deps import current_user, require_permission

router=APIRouter(prefix='/api/workspace',tags=['AFTYS Workspace'])

def rows(result):
    return [dict(r._mapping) for r in result]

def next_work_no(db:Session):
    year=datetime.now(timezone.utc).year
    n=db.execute(text("""INSERT INTO aftys.numara_sayaclari(seri,yil,son_no) VALUES('IE',:y,1)
      ON CONFLICT(seri,yil) DO UPDATE SET son_no=aftys.numara_sayaclari.son_no+1 RETURNING son_no"""),{'y':year}).scalar_one()
    return f"IE-{year}-{int(n):04d}"

@router.get('/arac/{arac_id}/detay')
def arac_detay(arac_id:UUID,db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Araçlar','GORUNTULE')
    vehicle=db.execute(text("""
      SELECT a.arac_id,a.arac_sinifi,a.marka,a.model,a.model_yili,a.yakit_turu,a.renk,a.gosterge_km,a.kumulatif_km,a.aciklama,
             d.kod AS durum,
             (SELECT deger FROM aftys.arac_kimlik_gecmisi WHERE arac_id=a.arac_id AND alan_tipi='PLAKA' AND bitis_tarihi IS NULL LIMIT 1) plaka,
             (SELECT deger FROM aftys.arac_kimlik_gecmisi WHERE arac_id=a.arac_id AND alan_tipi='SASI_NO' AND bitis_tarihi IS NULL LIMIT 1) sasi_no,
             (SELECT deger FROM aftys.arac_kimlik_gecmisi WHERE arac_id=a.arac_id AND alan_tipi='MOTOR_NO' AND bitis_tarihi IS NULL LIMIT 1) motor_no,
             (SELECT tibbi_donanim_markasi FROM aftys.km_gecmisi WHERE arac_id=a.arac_id ORDER BY tarih_saat DESC LIMIT 1) tibbi_donanim_markasi,
             COALESCE((SELECT adblue_var FROM aftys.km_gecmisi WHERE arac_id=a.arac_id ORDER BY tarih_saat DESC LIMIT 1),false) adblue_var
      FROM aftys.araclar a LEFT JOIN aftys.arac_durumlari d ON d.arac_durum_id=a.arac_durum_id WHERE a.arac_id=:id
    """),{'id':str(arac_id)}).mappings().first()
    if not vehicle: raise HTTPException(404,'Araç bulunamadı')
    ruhsat=db.execute(text("SELECT * FROM aftys.arac_ruhsat WHERE arac_id=:id AND bitis_tarihi IS NULL ORDER BY created_at DESC LIMIT 1"),{'id':str(arac_id)}).mappings().first()
    belgeler=rows(db.execute(text("SELECT belge_id,belge_turu,belge_adi,belge_no,duzenleyen,baslangic_tarihi,bitis_tarihi,sureli_mi,yenileme_durumu,versiyon_no,odenen_tutar,aciklama,created_at FROM aftys.arac_belgeleri WHERE arac_id=:id ORDER BY created_at DESC"),{'id':str(arac_id)}))
    ekler=rows(db.execute(text("""SELECT ek_id::text ek_id,entity_id,dosya_adi,mime_type,yukleme_tarihi FROM aftys.dosyalar_ekler WHERE entity_type='ARAC_BELGESI' AND entity_id IN (SELECT belge_id::text FROM aftys.arac_belgeleri WHERE arac_id=:id) ORDER BY yukleme_tarihi DESC"""),{'id':str(arac_id)}))
    for b in belgeler: b['dosyalar']=[e for e in ekler if e['entity_id']==str(b['belge_id'])]
    arizalar=rows(db.execute(text("""SELECT ariza_id,tarih_saat,kategori,sistem_parca,aciklama,durum,tekrar_ariza_mi,
      (SELECT gosterge_km FROM aftys.km_gecmisi k WHERE k.km_id=a.km_id) gosterge_km FROM aftys.arizalar a WHERE arac_id=:id ORDER BY tarih_saat DESC"""),{'id':str(arac_id)}))
    bakimlar=rows(db.execute(text("SELECT bakim_id,tarih_saat,bakim_turu,yapilan_islemler,degisen_parcalar,yapan_tipi,parca_tutari,iscilik_tutari,diger_tutar,toplam_tutar,aciklama FROM aftys.bakimlar WHERE arac_id=:id ORDER BY tarih_saat DESC"),{'id':str(arac_id)}))
    is_emirleri=rows(db.execute(text("SELECT is_emri_id,is_emri_no,islem_turu,talep,oncelik,durum,acilis_tarihi,kapanis_tarihi,yapilan_islem,sonuc FROM aftys.is_emirleri WHERE arac_id=:id ORDER BY acilis_tarihi DESC"),{'id':str(arac_id)}))
    timeline=rows(db.execute(text("SELECT timeline_id,olay_tipi,olay_tarihi,kaynak_tipi,kaynak_id,ozet FROM aftys.arac_zaman_cizelgesi WHERE arac_id=:id ORDER BY olay_tarihi DESC LIMIT 200"),{'id':str(arac_id)}))
    return {'arac':dict(vehicle),'ruhsat':dict(ruhsat) if ruhsat else None,'belgeler':belgeler,'arizalar':arizalar,'bakimlar':bakimlar,'is_emirleri':is_emirleri,'timeline':timeline}

@router.post('/arac/{arac_id}/ruhsat')
def ruhsat_kaydet(arac_id:UUID,b:dict[str,Any]=Body(...),db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Araçlar','DUZENLE')
    if not db.execute(text("SELECT 1 FROM aftys.araclar WHERE arac_id=:id"),{'id':str(arac_id)}).first(): raise HTTPException(404,'Araç bulunamadı')
    now=datetime.now(timezone.utc)
    db.execute(text("UPDATE aftys.arac_ruhsat SET bitis_tarihi=:n WHERE arac_id=:id AND bitis_tarihi IS NULL"),{'n':now,'id':str(arac_id)})
    db.execute(text("""INSERT INTO aftys.arac_ruhsat(arac_id,ilk_tescil_tarihi,tescil_tarihi,ruhsat_seri_no,ticari_ad,tip,varyant,versiyon,arac_cinsi,kullanim_amaci,motor_gucu_kw,motor_hacmi_cc,yakit_turu,renk,koltuk_sayisi,azami_yuklu_agirlik_kg,bos_agirlik_kg,sahip_kurum,aciklama,created_by)
      VALUES(:id,:ilk,:tescil,:seri,:ticari,:tip,:varyant,:versiyon,:cins,:amac,:guc,:hacim,:yakit,:renk,:koltuk,:azami,:bos,:sahip,:aciklama,:u)"""),{
      'id':str(arac_id),'ilk':b.get('ilk_tescil_tarihi') or None,'tescil':b.get('tescil_tarihi') or None,'seri':b.get('ruhsat_seri_no') or None,
      'ticari':b.get('ticari_ad') or None,'tip':b.get('tip') or None,'varyant':b.get('varyant') or None,'versiyon':b.get('versiyon') or None,
      'cins':b.get('arac_cinsi') or None,'amac':b.get('kullanim_amaci') or None,'guc':b.get('motor_gucu_kw') or None,'hacim':b.get('motor_hacmi_cc') or None,
      'yakit':b.get('yakit_turu') or None,'renk':b.get('renk') or None,'koltuk':b.get('koltuk_sayisi') or None,'azami':b.get('azami_yuklu_agirlik_kg') or None,
      'bos':b.get('bos_agirlik_kg') or None,'sahip':b.get('sahip_kurum') or None,'aciklama':b.get('aciklama') or None,'u':str(u.kullanici_id)})
    db.execute(text("INSERT INTO aftys.arac_zaman_cizelgesi(arac_id,olay_tipi,kaynak_tipi,kaynak_id,ozet,kullanici_id) VALUES(:id,'RUHSAT_GUNCELLENDI','ARAC_RUHSAT',:id,'Ruhsat bilgileri güncellendi',:u)"),{'id':str(arac_id),'u':str(u.kullanici_id)})
    db.commit(); return {'ok':True}

@router.post('/arac/{arac_id}/belgeler')
def belge_ekle(arac_id:UUID,b:dict[str,Any]=Body(...),db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Araçlar','DUZENLE')
    if not b.get('belge_turu'): raise HTTPException(422,'Belge türü zorunlu')
    r=db.execute(text("""INSERT INTO aftys.arac_belgeleri(arac_id,belge_turu,belge_adi,belge_no,duzenleyen,baslangic_tarihi,bitis_tarihi,sureli_mi,yenileme_durumu,odenen_tutar,aciklama,created_by)
      VALUES(:id,:tur,:adi,:no,:duz,:bas,:bit,:sureli,:yen,:tutar,:acik,:u) RETURNING belge_id"""),{
      'id':str(arac_id),'tur':b.get('belge_turu'),'adi':b.get('belge_adi') or None,'no':b.get('belge_no') or None,'duz':b.get('duzenleyen') or None,
      'bas':b.get('baslangic_tarihi') or None,'bit':b.get('bitis_tarihi') or None,'sureli':bool(b.get('sureli_mi')),'yen':b.get('yenileme_durumu') or 'ISLEM_YAPILMADI',
      'tutar':b.get('odenen_tutar') or None,'acik':b.get('aciklama') or None,'u':str(u.kullanici_id)}).scalar_one()
    db.execute(text("INSERT INTO aftys.arac_zaman_cizelgesi(arac_id,olay_tipi,kaynak_tipi,kaynak_id,ozet,kullanici_id) VALUES(:id,'BELGE_EKLENDI','ARAC_BELGESI',:kid,:ozet,:u)"),{'id':str(arac_id),'kid':str(r),'ozet':f"{b.get('belge_turu')} belgesi eklendi",'u':str(u.kullanici_id)})
    db.commit(); return {'belge_id':r}

@router.post('/arac/{arac_id}/bakim')
def bakim_ekle(arac_id:UUID,b:dict[str,Any]=Body(...),db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Bakım & Servis','EKLE')
    if not b.get('bakim_turu'): raise HTTPException(422,'Bakım türü zorunlu')
    r=db.execute(text("""INSERT INTO aftys.bakimlar(arac_id,bakim_turu,yapilan_islemler,degisen_parcalar,yapan_tipi,servis_id,parca_tutari,iscilik_tutari,diger_tutar,aciklama,created_by)
      VALUES(:id,:tur,:islem,:parca,:yapan,:servis,:pt,:it,:dt,:acik,:u) RETURNING bakim_id"""),{
      'id':str(arac_id),'tur':b.get('bakim_turu'),'islem':b.get('yapilan_islemler') or None,'parca':b.get('degisen_parcalar') or None,
      'yapan':b.get('yapan_tipi') or 'TEKNIK_BIRIM','servis':b.get('servis_id') or None,'pt':b.get('parca_tutari') or 0,'it':b.get('iscilik_tutari') or 0,
      'dt':b.get('diger_tutar') or 0,'acik':b.get('aciklama') or None,'u':str(u.kullanici_id)}).scalar_one()
    db.execute(text("INSERT INTO aftys.arac_zaman_cizelgesi(arac_id,olay_tipi,kaynak_tipi,kaynak_id,ozet,kullanici_id) VALUES(:id,'BAKIM_KAYDI','BAKIM',:kid,:ozet,:u)"),{'id':str(arac_id),'kid':str(r),'ozet':f"{b.get('bakim_turu')} bakım kaydı eklendi",'u':str(u.kullanici_id)})
    db.commit(); return {'bakim_id':r}

@router.get('/servisler')
def servisler(db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Servisler','GORUNTULE')
    return rows(db.execute(text("SELECT servis_id,ad,servis_turu FROM aftys.servisler WHERE aktif_mi=true ORDER BY ad")))

@router.post('/arac/{arac_id}/servise-gonder')
def hizli_servise_gonder(arac_id:UUID,b:dict[str,Any]=Body(...),db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Bakım & Servis','EKLE')
    servis_id=b.get('servis_id')
    if not servis_id: raise HTTPException(422,'Servis seçimi zorunlu')
    if not db.execute(text("SELECT 1 FROM aftys.servisler WHERE servis_id=:s AND aktif_mi=true"),{'s':servis_id}).first(): raise HTTPException(404,'Servis bulunamadı')
    if db.execute(text("SELECT 1 FROM aftys.servis_islemleri WHERE arac_id=:a AND cikis_tarihi IS NULL"),{'a':str(arac_id)}).first(): raise HTTPException(409,'Araç için açık servis işlemi mevcut')
    ie=db.execute(text("SELECT is_emri_id FROM aftys.is_emirleri WHERE arac_id=:a AND durum NOT IN ('TAMAMLANDI','IPTAL') ORDER BY acilis_tarihi DESC LIMIT 1"),{'a':str(arac_id)}).scalar()
    if not ie:
        ie=db.execute(text("INSERT INTO aftys.is_emirleri(is_emri_no,arac_id,islem_turu,talep,oncelik,sorumlu_kullanici_id,created_by) VALUES(:no,:a,'DIGER',:t,'NORMAL',:u,:u) RETURNING is_emri_id"),{'no':next_work_no(db),'a':str(arac_id),'t':b.get('neden') or 'Dış servise gönderim','u':str(u.kullanici_id)}).scalar_one()
    sid=db.execute(text("""INSERT INTO aftys.servis_islemleri(arac_id,servis_id,kaynak_tipi,kaynak_id,giris_tarihi,servis_kabul_no,durum)
      VALUES(:a,:s,'IS_EMRI',:ie,now(),:no,'SERVISTE') RETURNING servis_islem_id"""),{'a':str(arac_id),'s':servis_id,'ie':ie,'no':b.get('servis_kabul_no') or None}).scalar_one()
    db.execute(text("INSERT INTO aftys.teslim_tesellum(arac_id,teslim_turu,tarih_saat,servis_id,teslim_eden,servis_yetkilisi,neden,aciklama,created_by) VALUES(:a,'DIS_SERVISE_TESLIM',now(),:s,:te,:sy,:n,:ac,:u)"),{'a':str(arac_id),'s':servis_id,'te':b.get('teslim_eden') or u.ad_soyad,'sy':b.get('servis_yetkilisi') or None,'n':b.get('neden') or 'Servis işlemi','ac':b.get('aciklama') or None,'u':str(u.kullanici_id)})
    db.execute(text("INSERT INTO aftys.gayrifaal_donemler(arac_id,baslangic_ts,kaynak_tipi,kaynak_id,aciklama) VALUES(:a,now(),'SERVIS_ISLEMI',:sid,:n)"),{'a':str(arac_id),'sid':sid,'n':b.get('neden') or 'Servis'})
    db.execute(text("UPDATE aftys.is_emirleri SET durum='ISLEMDE' WHERE is_emri_id=:ie"),{'ie':ie})
    db.execute(text("UPDATE aftys.araclar SET arac_durum_id=(SELECT arac_durum_id FROM aftys.arac_durumlari WHERE kod='ARIZALI_SERVISTE') WHERE arac_id=:a"),{'a':str(arac_id)})
    db.execute(text("INSERT INTO aftys.arac_zaman_cizelgesi(arac_id,olay_tipi,kaynak_tipi,kaynak_id,ozet,kullanici_id) VALUES(:a,'SERVISE_GONDERILDI','SERVIS_ISLEMI',:sid,'Araç dış servise gönderildi',:u)"),{'a':str(arac_id),'sid':str(sid),'u':str(u.kullanici_id)})
    db.commit(); return {'servis_islem_id':sid,'is_emri_id':ie,'durum':'SERVISTE'}

@router.get('/ariza-is-emri')
def ariza_is_emri(db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Arıza & İş Emri','GORUNTULE')
    arizalar=rows(db.execute(text("""SELECT ar.ariza_id,ar.arac_id,ar.tarih_saat,ar.kategori,ar.sistem_parca,ar.aciklama,ar.durum,ar.tekrar_ariza_mi,
      (SELECT deger FROM aftys.arac_kimlik_gecmisi WHERE arac_id=ar.arac_id AND alan_tipi='PLAKA' AND bitis_tarihi IS NULL LIMIT 1) plaka
      FROM aftys.arizalar ar ORDER BY ar.tarih_saat DESC LIMIT 200""")))
    is_emirleri=rows(db.execute(text("""SELECT ie.is_emri_id,ie.is_emri_no,ie.arac_id,ie.islem_turu,ie.talep,ie.oncelik,ie.durum,ie.acilis_tarihi,ie.yapilan_islem,ie.sonuc,
      (SELECT deger FROM aftys.arac_kimlik_gecmisi WHERE arac_id=ie.arac_id AND alan_tipi='PLAKA' AND bitis_tarihi IS NULL LIMIT 1) plaka
      FROM aftys.is_emirleri ie ORDER BY ie.acilis_tarihi DESC LIMIT 200""")))
    return {'arizalar':arizalar,'is_emirleri':is_emirleri}

@router.get('/uyarilar')
def uyarilar(db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Uyarılar','GORUNTULE')
    manual=rows(db.execute(text("SELECT uyari_id,uyari_turu,entity_type,entity_id,baslangic_tarihi,son_tarih,durum,mesaj FROM aftys.uyarilar WHERE durum<>'KAPANDI' ORDER BY COALESCE(son_tarih,baslangic_tarihi)")))
    expiring=rows(db.execute(text("""SELECT -belge_id AS uyari_id,'BELGE_SURESI' AS uyari_turu,'ARAC_BELGESI' AS entity_type,belge_id::text entity_id,created_at baslangic_tarihi,bitis_tarihi::timestamptz son_tarih,'ACIK' AS durum,
      COALESCE((SELECT deger FROM aftys.arac_kimlik_gecmisi WHERE arac_id=b.arac_id AND alan_tipi='PLAKA' AND bitis_tarihi IS NULL LIMIT 1),'Plakasız') || ' - ' || belge_turu || ' belgesinin süresi ' || bitis_tarihi::text || ' tarihinde doluyor.' AS mesaj
      FROM aftys.arac_belgeleri b WHERE sureli_mi=true AND bitis_tarihi IS NOT NULL AND bitis_tarihi <= current_date + interval '30 day' AND bitis_tarihi >= current_date ORDER BY bitis_tarihi""")))
    return manual+expiring

@router.post('/uyarilar/{uyari_id}/durum')
def uyari_durum(uyari_id:int,b:dict[str,Any]=Body(...),db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Uyarılar','DUZENLE')
    if uyari_id<0: return {'ok':True,'derived':True}
    durum=b.get('durum','GORULDU')
    if durum not in ('ACIK','GORULDU','KAPANDI'): raise HTTPException(422,'Geçersiz durum')
    db.execute(text("UPDATE aftys.uyarilar SET durum=:d WHERE uyari_id=:id"),{'d':durum,'id':uyari_id}); db.commit(); return {'ok':True}


@router.get('/belgeler/{belge_id}/dosyalar')
def belge_dosyalari(belge_id:int,db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Araçlar','GORUNTULE')
    return rows(db.execute(text("SELECT ek_id::text ek_id,dosya_adi,mime_type,aciklama,yukleme_tarihi FROM aftys.dosyalar_ekler WHERE entity_type='ARAC_BELGESI' AND entity_id=:id ORDER BY yukleme_tarihi DESC"),{'id':str(belge_id)}))

@router.post('/belgeler/{belge_id}/dosya',status_code=201)
async def belge_dosya_yukle(belge_id:int,dosya:UploadFile=File(...),db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Araçlar','DUZENLE')
    if not db.execute(text("SELECT 1 FROM aftys.arac_belgeleri WHERE belge_id=:id"),{'id':belge_id}).first(): raise HTTPException(404,'Belge bulunamadı')
    root=pathlib.Path(os.environ.get('AFTYS_UPLOAD_DIR','/data/uploads')); root.mkdir(parents=True,exist_ok=True)
    suffix=pathlib.Path(dosya.filename or '').suffix[:12]
    key=f"{uuid.uuid4()}{suffix}"; target=root/key
    total=0
    with target.open('wb') as f:
        while True:
            chunk=await dosya.read(1024*1024)
            if not chunk: break
            total+=len(chunk)
            if total>25*1024*1024:
                f.close(); target.unlink(missing_ok=True); raise HTTPException(413,'Dosya 25 MB sınırını aşıyor')
            f.write(chunk)
    ek=db.execute(text("INSERT INTO aftys.dosyalar_ekler(entity_type,entity_id,dosya_adi,mime_type,storage_key,yukleyen_id) VALUES('ARAC_BELGESI',:id,:ad,:mime,:key,:u) RETURNING ek_id"),{'id':str(belge_id),'ad':dosya.filename or key,'mime':dosya.content_type or 'application/octet-stream','key':key,'u':str(u.kullanici_id)}).scalar_one()
    db.commit(); return {'ek_id':str(ek),'dosya_adi':dosya.filename}

@router.get('/dosyalar/{ek_id}')
def dosya_indir(ek_id:UUID,db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Araçlar','GORUNTULE')
    row=db.execute(text("SELECT dosya_adi,mime_type,storage_key FROM aftys.dosyalar_ekler WHERE ek_id=:id"),{'id':str(ek_id)}).mappings().first()
    if not row: raise HTTPException(404,'Dosya kaydı bulunamadı')
    path=pathlib.Path(os.environ.get('AFTYS_UPLOAD_DIR','/data/uploads'))/row['storage_key']
    if not path.exists(): raise HTTPException(404,'Dosya depoda bulunamadı')
    return FileResponse(str(path),media_type=row['mime_type'] or 'application/octet-stream',filename=row['dosya_adi'])

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Body, UploadFile, File, Form
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi.responses import FileResponse
import os, uuid, pathlib
from ..db import get_db
from ..deps import current_user, require_permission

router=APIRouter(prefix='/api/modules',tags=['AFTYS Modüller'])
MODUL_MAP={'bakim-servis':'Bakım & Servis','trafik-kazalari':'Trafik Kazaları','trafik-cezalari':'Trafik Cezaları','tibbi-donanim':'Tıbbi Donanım','teknik-birim-deposu':'Teknik Birim Deposu','ambulans-degisimi':'Ambulans Değişimi','teslim-tesellum':'Teslim–Tesellüm','devir-terkin-donusum':'Devir/Terkin/Dönüşüm','istasyonlar-birimler':'İstasyonlar & Birimler','servisler':'Servisler','ayarlar':'Ayarlar','rapor-merkezi':'Rapor Merkezi'}

def result_rows(r): return [dict(x._mapping) for x in r]

def plate_expr(alias='x'):
    return f"(SELECT deger FROM aftys.arac_kimlik_gecmisi WHERE arac_id={alias}.arac_id AND alan_tipi='PLAKA' AND bitis_tarihi IS NULL LIMIT 1)"

@router.get('/{slug}')
def liste(slug:str,db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,MODUL_MAP.get(slug,'Ayarlar'),'GORUNTULE')
    q=None
    if slug=='bakim-servis': q=f"""SELECT bakim_id::text id,'Bakım' tur,{plate_expr('b')} plaka,bakim_turu baslik,COALESCE(yapilan_islemler,'') detay,tarih_saat tarih,COALESCE(yapan_tipi,'') durum FROM aftys.bakimlar b ORDER BY tarih_saat DESC LIMIT 200"""
    elif slug=='trafik-kazalari': q=f"""SELECT kaza_id::text id,kaza_dosya_no baslik,{plate_expr('k')} plaka,COALESCE(yer,'') detay,tarih_saat tarih,dosya_durumu durum FROM aftys.trafik_kazalari k ORDER BY tarih_saat DESC LIMIT 200"""
    elif slug=='trafik-cezalari': q=f"""SELECT ceza_id::text id,COALESCE(tutanak_no,'Ceza #'||ceza_id) baslik,{plate_expr('c')} plaka,COALESCE(ihlal_turu,'') || CASE WHEN ceza_tutari IS NULL THEN '' ELSE ' • '||ceza_tutari::text||' TL' END detay,ceza_tarihi tarih,durum FROM aftys.trafik_cezalari c ORDER BY ceza_tarihi DESC LIMIT 200"""
    elif slug=='tibbi-donanim': q="""SELECT cihaz_id::text id,cihaz_adi baslik,COALESCE(marka,'')||CASE WHEN model IS NULL THEN '' ELSE ' '||model END detay,COALESCE(seri_no,kunye_no,'') plaka,NULL::timestamptz tarih,durum FROM aftys.tibbi_donanim WHERE aktif_mi=true ORDER BY cihaz_adi"""
    elif slug=='teknik-birim-deposu': q="""SELECT m.malzeme_id::text id,m.malzeme_adi baslik,COALESCE(m.raf_konum,'') plaka,COALESCE(SUM(l.mevcut_miktar),0)::text||' '||m.birim detay,NULL::timestamptz tarih,CASE WHEN m.kritik_seviye IS NOT NULL AND COALESCE(SUM(l.mevcut_miktar),0)<=m.kritik_seviye THEN 'KRITIK' ELSE 'AKTIF' END durum FROM aftys.depo_malzemeleri m LEFT JOIN aftys.depo_lotlari l ON l.malzeme_id=m.malzeme_id WHERE m.aktif_mi=true GROUP BY m.malzeme_id ORDER BY m.malzeme_adi"""
    elif slug=='ambulans-degisimi': q="""SELECT degisim_id::text id,'Ambulans Değişimi #'||degisim_id baslik,(SELECT deger FROM aftys.arac_kimlik_gecmisi WHERE arac_id=d.cikan_arac_id AND alan_tipi='PLAKA' AND bitis_tarihi IS NULL LIMIT 1)||' → '||(SELECT deger FROM aftys.arac_kimlik_gecmisi WHERE arac_id=d.gelen_arac_id AND alan_tipi='PLAKA' AND bitis_tarihi IS NULL LIMIT 1) plaka,COALESCE(neden,'') detay,tarih_saat tarih,'TAMAMLANDI' durum FROM aftys.ambulans_degisimleri d ORDER BY tarih_saat DESC LIMIT 200"""
    elif slug=='teslim-tesellum': q=f"""SELECT teslim_id::text id,teslim_turu baslik,{plate_expr('t')} plaka,COALESCE(neden,aciklama,'') detay,tarih_saat tarih,'KAYITLI' durum FROM aftys.teslim_tesellum t ORDER BY tarih_saat DESC LIMIT 200"""
    elif slug=='devir-terkin-donusum': q="""SELECT * FROM (
      SELECT devir_id::text id,'Devir - '||devir_turu baslik,(SELECT deger FROM aftys.arac_kimlik_gecmisi WHERE arac_id=d.arac_id AND alan_tipi='PLAKA' AND bitis_tarihi IS NULL LIMIT 1) plaka,alan_kurum detay,fiili_devir_tarihi::timestamptz tarih,durum FROM aftys.arac_devirleri d
      UNION ALL SELECT terkin_id::text,'Terkin',(SELECT deger FROM aftys.arac_kimlik_gecmisi WHERE arac_id=t.arac_id AND alan_tipi='PLAKA' AND bitis_tarihi IS NULL LIMIT 1),neden,terkin_tarihi::timestamptz,'TAMAMLANDI' FROM aftys.arac_terkinleri t
      UNION ALL SELECT donusum_id::text,'Dönüşüm',(SELECT deger FROM aftys.arac_kimlik_gecmisi WHERE arac_id=x.arac_id AND alan_tipi='PLAKA' AND bitis_tarihi IS NULL LIMIT 1),eski_arac_sinifi||' → '||yeni_arac_sinifi,donusum_tarihi::timestamptz,'TAMAMLANDI' FROM aftys.arac_donusumleri x
      ) z ORDER BY tarih DESC LIMIT 200"""
    elif slug=='istasyonlar-birimler': q="""SELECT birim_id::text id,ad baslik,COALESCE(ilce,'') plaka,COALESCE(adres,'') detay,created_at tarih,CASE WHEN aktif_mi THEN 'AKTIF' ELSE 'PASIF' END durum FROM aftys.istasyon_birimler ORDER BY ad"""
    elif slug=='servisler': q="""SELECT servis_id::text id,ad baslik,servis_turu plaka,COALESCE(hizmet_verilen_markalar,'')||CASE WHEN telefon IS NULL THEN '' ELSE ' • '||telefon END detay,NULL::timestamptz tarih,CASE WHEN aktif_mi THEN 'AKTIF' ELSE 'PASIF' END durum,servis_turu,ad,hizmet_verilen_markalar,yetkili_kisi,telefon,eposta,adres,aciklama,aktif_mi FROM aftys.servisler ORDER BY ad"""
    elif slug=='ayarlar': q="""SELECT tanim_id::text id,grup||' / '||ad baslik,kod plaka,'Sıra: '||sira::text detay,NULL::timestamptz tarih,CASE WHEN aktif_mi THEN 'AKTIF' ELSE 'PASIF' END durum FROM aftys.tanimlar ORDER BY grup,sira,ad"""
    elif slug=='rapor-merkezi':
        counts={}
        for key,sql in {
          'toplam_arac':'SELECT count(*) FROM aftys.araclar WHERE aktif_mi=true','ambulans':'SELECT count(*) FROM aftys.araclar WHERE aktif_mi=true AND arac_sinifi=\'AMBULANS\'',
          'hizmet_araci':'SELECT count(*) FROM aftys.araclar WHERE aktif_mi=true AND arac_sinifi=\'HIZMET_ARACI\'','acik_ariza':"SELECT count(*) FROM aftys.arizalar WHERE durum<>'TAMAMLANDI'",
          'serviste':"SELECT count(*) FROM aftys.servis_islemleri WHERE cikis_tarihi IS NULL",
          'ambulans_degisimi':"SELECT count(*) FROM aftys.ambulans_degisimleri",'devir_terkin_donusum':"SELECT (SELECT count(*) FROM aftys.arac_devirleri)+(SELECT count(*) FROM aftys.arac_terkinleri)+(SELECT count(*) FROM aftys.arac_donusumleri)",
          'kaza':'SELECT count(*) FROM aftys.trafik_kazalari','ceza':'SELECT count(*) FROM aftys.trafik_cezalari','tibbi_donanim':'SELECT count(*) FROM aftys.tibbi_donanim WHERE aktif_mi=true','depo_kalem':'SELECT count(*) FROM aftys.depo_malzemeleri WHERE aktif_mi=true'
        }.items(): counts[key]=db.execute(text(sql)).scalar_one()
        return {'counts':counts,'records':[]}
    else: raise HTTPException(404,'Modül bulunamadı')
    return {'records':result_rows(db.execute(text(q)))}

@router.post('/{slug}',status_code=201)
def ekle(slug:str,b:dict[str,Any]=Body(...),db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,MODUL_MAP.get(slug,'Ayarlar'),'EKLE')
    uid=str(u.kullanici_id)
    try:
      if slug=='bakim-servis':
        if not b.get('arac_id') or not b.get('bakim_turu'): raise HTTPException(422,'Araç ve bakım türü zorunlu')
        rid=db.execute(text("INSERT INTO aftys.bakimlar(arac_id,bakim_turu,yapilan_islemler,yapan_tipi,aciklama,created_by) VALUES(:a,:t,:y,:yt,:ac,:u) RETURNING bakim_id"),{'a':b['arac_id'],'t':b['bakim_turu'],'y':b.get('yapilan_islemler') or None,'yt':b.get('yapan_tipi') or 'TEKNIK_BIRIM','ac':b.get('aciklama') or None,'u':uid}).scalar_one()
      elif slug=='trafik-kazalari':
        if not b.get('arac_id'): raise HTTPException(422,'Araç zorunlu')
        rid=db.execute(text("INSERT INTO aftys.trafik_kazalari(arac_id,tarih_saat,yer,surucu_adi,olus_sekli,kaza_turu,yaralanma_var_mi,maddi_hasar_var_mi,created_by) VALUES(:a,now(),:yer,:s,:o,:k,:y,:m,:u) RETURNING kaza_id"),{'a':b['arac_id'],'yer':b.get('yer') or None,'s':b.get('surucu_adi') or None,'o':b.get('olus_sekli') or None,'k':b.get('kaza_turu') or None,'y':bool(b.get('yaralanma_var_mi')),'m':bool(b.get('maddi_hasar_var_mi',True)),'u':uid}).scalar_one()
      elif slug=='trafik-cezalari':
        if not b.get('arac_id') or b.get('ceza_tutari') in (None,''): raise HTTPException(422,'Araç ve ceza tutarı zorunlu')
        rid=db.execute(text("INSERT INTO aftys.trafik_cezalari(arac_id,ceza_tarihi,tutanak_no,ihlal_turu,yer,surucu_adi,ceza_tutari,durum,aciklama) VALUES(:a,now(),:no,:ih,:yer,:s,:t,:d,:ac) RETURNING ceza_id"),{'a':b['arac_id'],'no':b.get('tutanak_no') or None,'ih':b.get('ihlal_turu') or None,'yer':b.get('yer') or None,'s':b.get('surucu_adi') or None,'t':b['ceza_tutari'],'d':b.get('durum') or 'ODENMEDI','ac':b.get('aciklama') or None}).scalar_one()
      elif slug=='tibbi-donanim':
        if not b.get('cihaz_adi'): raise HTTPException(422,'Cihaz adı zorunlu')
        rid=db.execute(text("INSERT INTO aftys.tibbi_donanim(cihaz_adi,marka,model,seri_no,kunye_no,durum,aciklama) VALUES(:c,:m,:mo,:s,:k,:d,:ac) RETURNING cihaz_id"),{'c':b['cihaz_adi'],'m':b.get('marka') or None,'mo':b.get('model') or None,'s':b.get('seri_no') or None,'k':b.get('kunye_no') or None,'d':b.get('durum') or 'AKTIF','ac':b.get('aciklama') or None}).scalar_one()
      elif slug=='teknik-birim-deposu':
        if not b.get('malzeme_adi') or not b.get('birim'): raise HTTPException(422,'Malzeme adı ve birim zorunlu')
        rid=db.execute(text("INSERT INTO aftys.depo_malzemeleri(ana_kategori,alt_kategori,malzeme_adi,birim,raf_konum,kritik_seviye,aciklama) VALUES(:ak,:alt,:m,:b,:raf,:k,:ac) RETURNING malzeme_id"),{'ak':b.get('ana_kategori') or 'DIGER_MALZEME','alt':b.get('alt_kategori') or None,'m':b['malzeme_adi'],'b':b['birim'],'raf':b.get('raf_konum') or None,'k':b.get('kritik_seviye') or None,'ac':b.get('aciklama') or None}).scalar_one()
        if float(b.get('mevcut_miktar') or 0)>0: db.execute(text("INSERT INTO aftys.depo_lotlari(malzeme_id,lot_no,skt,mevcut_miktar) VALUES(:m,:l,:s,:q)"),{'m':rid,'l':b.get('lot_no') or None,'s':b.get('skt') or None,'q':b.get('mevcut_miktar')})
      elif slug=='ambulans-degisimi':
        required=['istasyon_birim_id','cikan_arac_id','gelen_arac_id']
        if any(not b.get(x) for x in required): raise HTTPException(422,'İstasyon, çıkan ve gelen araç zorunlu')
        if str(b['cikan_arac_id'])==str(b['gelen_arac_id']): raise HTTPException(422,'Çıkan ve gelen ambulans aynı olamaz')
        for aid in (b['cikan_arac_id'],b['gelen_arac_id']):
            if not db.execute(text("SELECT 1 FROM aftys.araclar WHERE arac_id=:a AND aktif_mi=true"),{'a':aid}).first(): raise HTTPException(422,'Seçilen araçlardan biri aktif değil')
        rid=db.execute(text("INSERT INTO aftys.ambulans_degisimleri(istasyon_birim_id,cikan_arac_id,cikan_km,gelen_arac_id,gelen_km,neden,teslim_eden,teslim_alan,aciklama) VALUES(:i,:c,:ck,:g,:gk,:n,:te,:ta,:ac) RETURNING degisim_id"),{'i':b['istasyon_birim_id'],'c':b['cikan_arac_id'],'ck':int(b['cikan_km']) if str(b.get('cikan_km') or '').strip() else None,'g':b['gelen_arac_id'],'gk':int(b['gelen_km']) if str(b.get('gelen_km') or '').strip() else None,'n':b.get('neden') or None,'te':b.get('teslim_eden') or None,'ta':b.get('teslim_alan') or None,'ac':b.get('aciklama') or None}).scalar_one()
        # Gelen araç istasyona atanır, çıkan araç aktif zimmetten çıkarılır.
        db.execute(text("UPDATE aftys.araclar SET gunluk_birim_id=NULL WHERE arac_id=:a"),{'a':b['cikan_arac_id']})
        db.execute(text("UPDATE aftys.araclar SET gunluk_birim_id=:i WHERE arac_id=:a"),{'i':b['istasyon_birim_id'],'a':b['gelen_arac_id']})
        db.execute(text("UPDATE aftys.arac_tahsisleri SET bitis_tarihi=now(),updated_at=now() WHERE arac_id=:a AND bitis_tarihi IS NULL"),{'a':b['cikan_arac_id']})
        db.execute(text("UPDATE aftys.arac_tahsisleri SET bitis_tarihi=now(),updated_at=now() WHERE arac_id=:a AND bitis_tarihi IS NULL"),{'a':b['gelen_arac_id']})
        db.execute(text("INSERT INTO aftys.arac_tahsisleri(arac_id,birim_id,baslangic_tarihi,neden,created_by) VALUES(:a,:i,now(),'Ambulans değişimi',:u)"),{'a':b['gelen_arac_id'],'i':b['istasyon_birim_id'],'u':uid})
      elif slug=='teslim-tesellum':
        if not b.get('arac_id') or not b.get('teslim_turu'): raise HTTPException(422,'Araç ve teslim türü zorunlu')
        rid=db.execute(text("INSERT INTO aftys.teslim_tesellum(arac_id,teslim_turu,tarih_saat,servis_id,teslim_eden,teslim_alan,neden,aciklama,created_by) VALUES(:a,:t,now(),:s,:te,:ta,:n,:ac,:u) RETURNING teslim_id"),{'a':b['arac_id'],'t':b['teslim_turu'],'s':b.get('servis_id') or None,'te':b.get('teslim_eden') or None,'ta':b.get('teslim_alan') or None,'n':b.get('neden') or None,'ac':b.get('aciklama') or None,'u':uid}).scalar_one()
      elif slug=='devir-terkin-donusum':
        if not b.get('arac_id') or not b.get('islem_turu'): raise HTTPException(422,'Araç ve işlem türü zorunlu')
        tur=b['islem_turu']
        if tur=='DEVIR':
            if not b.get('alan_kurum'): raise HTTPException(422,'Alan kurum zorunlu')
            rid=db.execute(text("INSERT INTO aftys.arac_devirleri(arac_id,devir_turu,alan_kurum,fiili_devir_tarihi,km,teslim_eden,teslim_alan,aciklama) VALUES(:a,:dt,:kurum,now(),:km,:te,:ta,:ac) RETURNING devir_id"),{'a':b['arac_id'],'dt':b.get('devir_turu') or 'GECICI','kurum':b['alan_kurum'],'km':b.get('km') or None,'te':b.get('teslim_eden') or None,'ta':b.get('teslim_alan') or None,'ac':b.get('aciklama') or None}).scalar_one()
        elif tur=='TERKIN':
            rid=db.execute(text("INSERT INTO aftys.arac_terkinleri(arac_id,neden,terkin_tarihi,son_km,aciklama) VALUES(:a,:n,current_date,:km,:ac) RETURNING terkin_id"),{'a':b['arac_id'],'n':b.get('neden') or 'Terkin','km':b.get('km') or None,'ac':b.get('aciklama') or None}).scalar_one()
        elif tur=='DONUSUM':
            old=db.execute(text("SELECT arac_sinifi FROM aftys.araclar WHERE arac_id=:a"),{'a':b['arac_id']}).scalar_one_or_none()
            if not old: raise HTTPException(404,'Araç bulunamadı')
            new=b.get('yeni_arac_sinifi') or ('HIZMET_ARACI' if old=='AMBULANS' else 'AMBULANS')
            rid=db.execute(text("INSERT INTO aftys.arac_donusumleri(arac_id,eski_arac_sinifi,yeni_arac_sinifi,donusum_tarihi,km,aciklama) VALUES(:a,:e,:y,current_date,:km,:ac) RETURNING donusum_id"),{'a':b['arac_id'],'e':old,'y':new,'km':b.get('km') or None,'ac':b.get('aciklama') or None}).scalar_one()
            db.execute(text("UPDATE aftys.araclar SET arac_sinifi=:y WHERE arac_id=:a"),{'y':new,'a':b['arac_id']})
        else: raise HTTPException(422,'İşlem türü DEVIR, TERKIN veya DONUSUM olmalı')
      elif slug=='istasyonlar-birimler':
        if not b.get('ad'): raise HTTPException(422,'Birim adı zorunlu')
        rid=db.execute(text("INSERT INTO aftys.istasyon_birimler(tip,ad,kod,ilce,adres,sorumlu_kisi,telefon) VALUES(:t,:a,:k,:i,:ad,:s,:tel) RETURNING birim_id"),{'t':b.get('tip') or 'ISTASYON','a':b['ad'],'k':b.get('kod') or None,'i':b.get('ilce') or None,'ad':b.get('adres') or None,'s':b.get('sorumlu_kisi') or None,'tel':b.get('telefon') or None}).scalar_one()
      elif slug=='servisler':
        if not b.get('ad'): raise HTTPException(422,'Servis adı zorunlu')
        rid=db.execute(text("INSERT INTO aftys.servisler(servis_turu,ad,hizmet_verilen_markalar,yetkili_kisi,telefon,eposta,adres,aciklama) VALUES(:t,:a,:h,:y,:tel,:e,:ad,:ac) RETURNING servis_id"),{'t':b.get('servis_turu') or 'ARAC','a':b['ad'],'h':b.get('hizmet_verilen_markalar') or None,'y':b.get('yetkili_kisi') or None,'tel':b.get('telefon') or None,'e':b.get('eposta') or None,'ad':b.get('adres') or None,'ac':b.get('aciklama') or None}).scalar_one()
      elif slug=='ayarlar':
        if not b.get('grup') or not b.get('ad'): raise HTTPException(422,'Tanım grubu ve tanım adı zorunlu')
        base=''.join(ch for ch in str(b['grup']).upper() if ch.isalnum())[:8] or 'TANIM'
        seq=db.execute(text("SELECT COALESCE(max(sira),0)+1 FROM aftys.tanimlar WHERE grup=:g"),{'g':b['grup']}).scalar_one()
        kod=f'{base}-{int(seq):03d}'
        rid=db.execute(text("INSERT INTO aftys.tanimlar(grup,kod,ad,sira) VALUES(:g,:k,:a,:s) ON CONFLICT(grup,kod) DO UPDATE SET ad=excluded.ad,sira=excluded.sira,aktif_mi=true RETURNING tanim_id"),{'g':b['grup'],'k':kod,'a':b['ad'],'s':b.get('sira') or seq}).scalar_one()
      else: raise HTTPException(405,'Bu modülde yeni kayıt desteklenmiyor')
      db.commit(); return {'id':str(rid),'ok':True}
    except HTTPException: db.rollback(); raise
    except Exception as e: db.rollback(); raise HTTPException(500,f'Kayıt işlemi başarısız: {e.__class__.__name__}')

@router.put('/servisler/{servis_id}')
def servis_guncelle(servis_id:int,b:dict[str,Any]=Body(...),db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Servisler','DUZENLE')
    if not str(b.get('ad') or '').strip(): raise HTTPException(422,'Servis adı zorunlu')
    r=db.execute(text("UPDATE aftys.servisler SET servis_turu=:t,ad=:a,hizmet_verilen_markalar=:h,yetkili_kisi=:y,telefon=:tel,eposta=:e,adres=:ad,aciklama=:ac,aktif_mi=:aktif WHERE servis_id=:id RETURNING servis_id"),{'t':b.get('servis_turu') or 'ARAC','a':str(b['ad']).strip(),'h':b.get('hizmet_verilen_markalar') or None,'y':b.get('yetkili_kisi') or None,'tel':b.get('telefon') or None,'e':b.get('eposta') or None,'ad':b.get('adres') or None,'ac':b.get('aciklama') or None,'aktif':bool(b.get('aktif_mi',True)),'id':servis_id}).scalar_one_or_none()
    if not r: raise HTTPException(404,'Servis bulunamadı')
    db.commit(); return {'ok':True}

@router.get('/lookup/vehicles/all')
def arac_lookup(db:Session=Depends(get_db),u=Depends(current_user)):
    return result_rows(db.execute(text("""SELECT a.arac_id::text value,COALESCE((SELECT deger FROM aftys.arac_kimlik_gecmisi WHERE arac_id=a.arac_id AND alan_tipi='PLAKA' AND bitis_tarihi IS NULL LIMIT 1),'PLAKASIZ')||' • '||a.marka||' '||COALESCE(a.model,'') label,a.arac_sinifi FROM aftys.araclar a WHERE a.aktif_mi=true ORDER BY label""")))

@router.get('/lookup/stations')
def station_lookup(db:Session=Depends(get_db),u=Depends(current_user)):
    return result_rows(db.execute(text("SELECT birim_id::text value, trim(concat(COALESCE(kod,''),CASE WHEN kod IS NOT NULL AND telsiz_adi IS NOT NULL THEN ' ' ELSE '' END,COALESCE(telsiz_adi,''),' — ',ad)) label, ad, kod telsiz_kodu, telsiz_adi FROM aftys.istasyon_birimler WHERE aktif_mi=true ORDER BY COALESCE(kod,''),ad")))

@router.get('/lookup/services')
def service_lookup(db:Session=Depends(get_db),u=Depends(current_user)):
    return result_rows(db.execute(text("SELECT servis_id::text value,ad||COALESCE(' • '||NULLIF(btrim(hizmet_verilen_markalar),''),'') label FROM aftys.servisler WHERE aktif_mi=true ORDER BY ad")))


# =========================================================
# V4.2 - Kaza dosyası, trafik cezası belgeleri ve kronoloji
# =========================================================

def _files_for(db:Session, entity_type:str, entity_id:str):
    return result_rows(db.execute(text("""SELECT ek_id::text ek_id,entity_type,entity_id,dosya_adi,mime_type,COALESCE(aciklama,'BELGE') kategori,yukleme_tarihi
      FROM aftys.dosyalar_ekler WHERE entity_type=:t AND entity_id=:i ORDER BY yukleme_tarihi DESC"""),{'t':entity_type,'i':str(entity_id)}))

def _timeline_sort_key(x):
    return str(x.get('tarih') or '')

@router.get('/trafik-kazalari/{kaza_id}/detail')
def kaza_detail(kaza_id:int,db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Trafik Kazaları','GORUNTULE')
    kaza=db.execute(text(f"""SELECT k.*,{plate_expr('k')} plaka FROM aftys.trafik_kazalari k WHERE kaza_id=:id"""),{'id':kaza_id}).mappings().first()
    if not kaza: raise HTTPException(404,'Kaza dosyası bulunamadı')
    servisler=result_rows(db.execute(text("""SELECT ks.*,s.ad servis_adi FROM aftys.kaza_servisleri ks JOIN aftys.servisler s ON s.servis_id=ks.servis_id WHERE ks.kaza_id=:id ORDER BY COALESCE(ks.giris_tarihi,ks.cikis_tarihi) DESC NULLS LAST"""),{'id':kaza_id}))
    faturalar=result_rows(db.execute(text("""SELECT f.*,s.ad servis_adi FROM aftys.kaza_faturalari f LEFT JOIN aftys.servisler s ON s.servis_id=f.servis_id WHERE f.kaza_id=:id ORDER BY f.fatura_tarihi DESC NULLS LAST,f.kaza_fatura_id DESC"""),{'id':kaza_id}))
    sigorta=result_rows(db.execute(text("SELECT * FROM aftys.sigorta_kasko_surecleri WHERE kaza_id=:id ORDER BY sigorta_id DESC"),{'id':kaza_id}))
    tahsilatlar=result_rows(db.execute(text("SELECT * FROM aftys.kaza_tahsilatlari WHERE kaza_id=:id ORDER BY COALESCE(tahsilat_tarihi,created_at::date) DESC,tahsilat_id DESC"),{'id':kaza_id}))
    hukuk=result_rows(db.execute(text("SELECT * FROM aftys.hukuki_icra WHERE kaza_id=:id ORDER BY COALESCE(son_islem_tarihi,teblig_tarihi,durusma_tarihi) DESC NULLS LAST,hukuk_id DESC"),{'id':kaza_id}))
    hids=[int(x['hukuk_id']) for x in hukuk]
    talepler=[]
    if hids:
        placeholders=','.join(str(x) for x in hids)
        talepler=result_rows(db.execute(text(f"SELECT * FROM aftys.hukuki_talepler WHERE hukuk_id IN ({placeholders}) ORDER BY talep_id DESC")))
    files=_files_for(db,'TRAFIK_KAZASI',str(kaza_id))
    timeline=[{'tarih':kaza['tarih_saat'],'tur':'KAZA','baslik':'Kaza kaydı oluşturuldu','detay':kaza.get('yer') or ''}]
    for x in servisler:
        if x.get('giris_tarihi'): timeline.append({'tarih':x['giris_tarihi'],'tur':'SERVIS','baslik':'Onarım servisine giriş','detay':x.get('servis_adi') or ''})
        if x.get('cikis_tarihi'): timeline.append({'tarih':x['cikis_tarihi'],'tur':'SERVIS','baslik':'Onarım servisinden çıkış','detay':x.get('sonuc') or x.get('servis_adi') or ''})
    for x in faturalar: timeline.append({'tarih':x.get('fatura_tarihi'),'tur':'FATURA','baslik':'Servis faturası','detay':f"{x.get('fatura_no') or ''} • {x.get('toplam_tutar') or 0} TL"})
    for x in tahsilatlar: timeline.append({'tarih':x.get('tahsilat_tarihi') or x.get('created_at'),'tur':'TAHSILAT','baslik':x.get('tahsilat_turu') or 'Tahsilat','detay':f"Talep {x.get('talep_tutari') or 0} TL • Tahsil {x.get('tahsil_edilen_tutar') or 0} TL"})
    for x in hukuk: timeline.append({'tarih':x.get('son_islem_tarihi') or x.get('teblig_tarihi') or x.get('durusma_tarihi'),'tur':'HUKUK','baslik':x.get('dosya_no') or 'Hukuki süreç','detay':x.get('durum') or x.get('merci') or ''})
    for x in files: timeline.append({'tarih':x.get('yukleme_tarihi'),'tur':'BELGE','baslik':x.get('kategori') or 'Belge','detay':x.get('dosya_adi') or ''})
    timeline=sorted(timeline,key=_timeline_sort_key,reverse=True)
    return {'kaza':dict(kaza),'servisler':servisler,'faturalar':faturalar,'sigorta':sigorta,'tahsilatlar':tahsilatlar,'hukuk':hukuk,'talepler':talepler,'dosyalar':files,'timeline':timeline}

@router.put('/trafik-kazalari/{kaza_id}')
def kaza_update(kaza_id:int,b:dict[str,Any]=Body(...),db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Trafik Kazaları','DUZENLE')
    allowed=['yer','surucu_adi','surucu_personel_no','olus_sekli','kaza_turu','karsi_taraf_bilgisi','kolluk_bilgisi','arac_fiili_durumu','dosya_durumu']
    sets=[]; vals={'id':kaza_id}
    for k in allowed:
        if k in b: sets.append(f"{k}=:{k}"); vals[k]=b[k] or None
    if 'yaralanma_var_mi' in b: sets.append('yaralanma_var_mi=:yar'); vals['yar']=bool(b['yaralanma_var_mi'])
    if 'maddi_hasar_var_mi' in b: sets.append('maddi_hasar_var_mi=:mh'); vals['mh']=bool(b['maddi_hasar_var_mi'])
    if sets: db.execute(text('UPDATE aftys.trafik_kazalari SET '+','.join(sets)+' WHERE kaza_id=:id'),vals)
    db.commit(); return {'ok':True}

@router.post('/trafik-kazalari/{kaza_id}/servis',status_code=201)
def kaza_servis_ekle(kaza_id:int,b:dict[str,Any]=Body(...),db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Trafik Kazaları','EKLE')
    if not b.get('servis_id'): raise HTTPException(422,'Servis seçimi zorunlu')
    rid=db.execute(text("""INSERT INTO aftys.kaza_servisleri(kaza_id,servis_id,giris_tarihi,cikis_tarihi,giris_km,cikis_km,kabul_no,yapilan_islem,sonuc)
      VALUES(:k,:s,COALESCE(CAST(:g AS timestamptz),now()),CAST(:c AS timestamptz),:gkm,:ckm,:no,:y,:son) RETURNING kaza_servis_id"""),{'k':kaza_id,'s':b['servis_id'],'g':b.get('giris_tarihi'),'c':b.get('cikis_tarihi'),'gkm':b.get('giris_km') or None,'ckm':b.get('cikis_km') or None,'no':b.get('kabul_no') or None,'y':b.get('yapilan_islem') or None,'son':b.get('sonuc') or None}).scalar_one()
    db.commit(); return {'id':rid}

@router.put('/trafik-kazalari/{kaza_id}/servis/{servis_kayit_id}')
def kaza_servis_guncelle(kaza_id:int,servis_kayit_id:int,b:dict[str,Any]=Body(...),db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Trafik Kazaları','DUZENLE')
    db.execute(text("""UPDATE aftys.kaza_servisleri SET servis_id=COALESCE(:s,servis_id),giris_tarihi=COALESCE(CAST(:g AS timestamptz),giris_tarihi),cikis_tarihi=CAST(:c AS timestamptz),giris_km=:gkm,cikis_km=:ckm,kabul_no=:no,yapilan_islem=:y,sonuc=:son WHERE kaza_id=:k AND kaza_servis_id=:id"""),{'k':kaza_id,'id':servis_kayit_id,'s':b.get('servis_id'),'g':b.get('giris_tarihi'),'c':b.get('cikis_tarihi'),'gkm':b.get('giris_km') or None,'ckm':b.get('cikis_km') or None,'no':b.get('kabul_no') or None,'y':b.get('yapilan_islem') or None,'son':b.get('sonuc') or None}); db.commit(); return {'ok':True}

@router.post('/trafik-kazalari/{kaza_id}/fatura',status_code=201)
def kaza_fatura_ekle(kaza_id:int,b:dict[str,Any]=Body(...),db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Trafik Kazaları','EKLE')
    if b.get('toplam_tutar') in (None,''): raise HTTPException(422,'Fatura tutarı zorunlu')
    rid=db.execute(text("""INSERT INTO aftys.kaza_faturalari(kaza_id,servis_id,fatura_no,fatura_tarihi,toplam_tutar) VALUES(:k,:s,:n,:t,:x) RETURNING kaza_fatura_id"""),{'k':kaza_id,'s':b.get('servis_id') or None,'n':b.get('fatura_no') or None,'t':b.get('fatura_tarihi') or None,'x':b['toplam_tutar']}).scalar_one(); db.commit(); return {'id':rid}

@router.put('/trafik-kazalari/{kaza_id}/fatura/{fatura_id}')
def kaza_fatura_guncelle(kaza_id:int,fatura_id:int,b:dict[str,Any]=Body(...),db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Trafik Kazaları','DUZENLE')
    db.execute(text("UPDATE aftys.kaza_faturalari SET servis_id=:s,fatura_no=:n,fatura_tarihi=:t,toplam_tutar=:x WHERE kaza_id=:k AND kaza_fatura_id=:id"),{'k':kaza_id,'id':fatura_id,'s':b.get('servis_id') or None,'n':b.get('fatura_no') or None,'t':b.get('fatura_tarihi') or None,'x':b.get('toplam_tutar') or 0}); db.commit(); return {'ok':True}

@router.post('/trafik-kazalari/{kaza_id}/tahsilat',status_code=201)
def kaza_tahsilat_ekle(kaza_id:int,b:dict[str,Any]=Body(...),db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Trafik Kazaları','EKLE')
    rid=db.execute(text("""INSERT INTO aftys.kaza_tahsilatlari(kaza_id,tahsilat_turu,talep_tutari,tahsil_edilen_tutar,tahsilat_tarihi,odeyen_taraf,durum,aciklama,created_by)
      VALUES(:k,:tur,:tal,:tah,:tar,:od,:d,:ac,:u) RETURNING tahsilat_id"""),{'k':kaza_id,'tur':b.get('tahsilat_turu') or 'DEGER_KAYBI','tal':b.get('talep_tutari') or 0,'tah':b.get('tahsil_edilen_tutar') or 0,'tar':b.get('tahsilat_tarihi') or None,'od':b.get('odeyen_taraf') or None,'d':b.get('durum') or 'ACIK','ac':b.get('aciklama') or None,'u':str(u.kullanici_id)}).scalar_one(); db.commit(); return {'id':rid}

@router.put('/trafik-kazalari/{kaza_id}/tahsilat/{tahsilat_id}')
def kaza_tahsilat_guncelle(kaza_id:int,tahsilat_id:int,b:dict[str,Any]=Body(...),db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Trafik Kazaları','DUZENLE')
    db.execute(text("""UPDATE aftys.kaza_tahsilatlari SET tahsilat_turu=:tur,talep_tutari=:tal,tahsil_edilen_tutar=:tah,tahsilat_tarihi=:tar,odeyen_taraf=:od,durum=:d,aciklama=:ac WHERE kaza_id=:k AND tahsilat_id=:id"""),{'k':kaza_id,'id':tahsilat_id,'tur':b.get('tahsilat_turu') or 'DEGER_KAYBI','tal':b.get('talep_tutari') or 0,'tah':b.get('tahsil_edilen_tutar') or 0,'tar':b.get('tahsilat_tarihi') or None,'od':b.get('odeyen_taraf') or None,'d':b.get('durum') or 'ACIK','ac':b.get('aciklama') or None}); db.commit(); return {'ok':True}

@router.post('/trafik-kazalari/{kaza_id}/hukuk',status_code=201)
def kaza_hukuk_ekle(kaza_id:int,b:dict[str,Any]=Body(...),db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Trafik Kazaları','EKLE')
    rid=db.execute(text("""INSERT INTO aftys.hukuki_icra(kaza_id,muhatap,dosya_no,merci,teblig_tarihi,odeme_emri_tarihi,son_islem_tarihi,durum,aciklama,dosya_turu,karsi_taraf,avukat_vekil,karar_sonucu,durusma_tarihi)
      VALUES(:k,:m,:no,:me,:teb,:oe,:si,:d,:ac,:tur,:kt,:av,:ks,:dt) RETURNING hukuk_id"""),{'k':kaza_id,'m':b.get('muhatap') or 'KURUM','no':b.get('dosya_no') or None,'me':b.get('merci') or None,'teb':b.get('teblig_tarihi') or None,'oe':b.get('odeme_emri_tarihi') or None,'si':b.get('son_islem_tarihi') or None,'d':b.get('durum') or 'ACIK','ac':b.get('aciklama') or None,'tur':b.get('dosya_turu') or None,'kt':b.get('karsi_taraf') or None,'av':b.get('avukat_vekil') or None,'ks':b.get('karar_sonucu') or None,'dt':b.get('durusma_tarihi') or None}).scalar_one(); db.commit(); return {'id':rid}

@router.put('/trafik-kazalari/{kaza_id}/hukuk/{hukuk_id}')
def kaza_hukuk_guncelle(kaza_id:int,hukuk_id:int,b:dict[str,Any]=Body(...),db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Trafik Kazaları','DUZENLE')
    db.execute(text("""UPDATE aftys.hukuki_icra SET muhatap=:m,dosya_no=:no,merci=:me,teblig_tarihi=:teb,odeme_emri_tarihi=:oe,son_islem_tarihi=:si,durum=:d,aciklama=:ac,dosya_turu=:tur,karsi_taraf=:kt,avukat_vekil=:av,karar_sonucu=:ks,durusma_tarihi=:dt WHERE kaza_id=:k AND hukuk_id=:id"""),{'k':kaza_id,'id':hukuk_id,'m':b.get('muhatap') or 'KURUM','no':b.get('dosya_no') or None,'me':b.get('merci') or None,'teb':b.get('teblig_tarihi') or None,'oe':b.get('odeme_emri_tarihi') or None,'si':b.get('son_islem_tarihi') or None,'d':b.get('durum') or 'ACIK','ac':b.get('aciklama') or None,'tur':b.get('dosya_turu') or None,'kt':b.get('karsi_taraf') or None,'av':b.get('avukat_vekil') or None,'ks':b.get('karar_sonucu') or None,'dt':b.get('durusma_tarihi') or None}); db.commit(); return {'ok':True}

@router.post('/trafik-kazalari/{kaza_id}/hukuk/{hukuk_id}/talep',status_code=201)
def kaza_hukuk_talep(kaza_id:int,hukuk_id:int,b:dict[str,Any]=Body(...),db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Trafik Kazaları','EKLE')
    rid=db.execute(text("""INSERT INTO aftys.hukuki_talepler(hukuk_id,talep_turu,talep_tutari,odenen_tutar,odeyen_taraf,durum,aciklama) VALUES(:h,:tur,:tal,:od,:ot,:d,:ac) RETURNING talep_id"""),{'h':hukuk_id,'tur':b.get('talep_turu') or 'DIGER','tal':b.get('talep_tutari') or 0,'od':b.get('odenen_tutar') or 0,'ot':b.get('odeyen_taraf') or None,'d':b.get('durum') or 'ACIK','ac':b.get('aciklama') or None}).scalar_one(); db.commit(); return {'id':rid}

@router.put('/trafik-kazalari/{kaza_id}/hukuk/{hukuk_id}/talep/{talep_id}')
def kaza_hukuk_talep_guncelle(kaza_id:int,hukuk_id:int,talep_id:int,b:dict[str,Any]=Body(...),db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Trafik Kazaları','DUZENLE')
    db.execute(text("""UPDATE aftys.hukuki_talepler SET talep_turu=:tur,talep_tutari=:tal,odenen_tutar=:od,odeyen_taraf=:ot,durum=:d,aciklama=:ac WHERE hukuk_id=:h AND talep_id=:id"""),{'h':hukuk_id,'id':talep_id,'tur':b.get('talep_turu') or 'DIGER','tal':b.get('talep_tutari') or 0,'od':b.get('odenen_tutar') or 0,'ot':b.get('odeyen_taraf') or None,'d':b.get('durum') or 'ACIK','ac':b.get('aciklama') or None}); db.commit(); return {'ok':True}

@router.post('/trafik-kazalari/{kaza_id}/dosya',status_code=201)
async def kaza_dosya_yukle(kaza_id:int,kategori:str=Form('BELGE'),dosya:UploadFile=File(...),db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Trafik Kazaları','DUZENLE')
    if not db.execute(text("SELECT 1 FROM aftys.trafik_kazalari WHERE kaza_id=:id"),{'id':kaza_id}).first(): raise HTTPException(404,'Kaza bulunamadı')
    root=pathlib.Path(os.environ.get('AFTYS_UPLOAD_DIR','/data/uploads')); root.mkdir(parents=True,exist_ok=True)
    suffix=pathlib.Path(dosya.filename or '').suffix[:12]; key=f"{uuid.uuid4()}{suffix}"; target=root/key; total=0
    with target.open('wb') as f:
        while True:
            chunk=await dosya.read(1024*1024)
            if not chunk: break
            total+=len(chunk)
            if total>25*1024*1024: f.close(); target.unlink(missing_ok=True); raise HTTPException(413,'Dosya 25 MB sınırını aşıyor')
            f.write(chunk)
    ek=db.execute(text("INSERT INTO aftys.dosyalar_ekler(entity_type,entity_id,dosya_adi,mime_type,storage_key,aciklama,yukleyen_id) VALUES('TRAFIK_KAZASI',:id,:ad,:mime,:key,:kat,:u) RETURNING ek_id"),{'id':str(kaza_id),'ad':dosya.filename or key,'mime':dosya.content_type or 'application/octet-stream','key':key,'kat':kategori,'u':str(u.kullanici_id)}).scalar_one(); db.commit(); return {'ek_id':str(ek)}

@router.get('/trafik-cezalari/{ceza_id}/detail')
def ceza_detail(ceza_id:int,db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Trafik Cezaları','GORUNTULE')
    row=db.execute(text(f"SELECT c.*,{plate_expr('c')} plaka FROM aftys.trafik_cezalari c WHERE ceza_id=:id"),{'id':ceza_id}).mappings().first()
    if not row: raise HTTPException(404,'Ceza kaydı bulunamadı')
    return {'ceza':dict(row),'dosyalar':_files_for(db,'TRAFIK_CEZASI',str(ceza_id))}

@router.put('/trafik-cezalari/{ceza_id}')
def ceza_update(ceza_id:int,b:dict[str,Any]=Body(...),db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Trafik Cezaları','DUZENLE')
    db.execute(text("""UPDATE aftys.trafik_cezalari SET tutanak_no=:no,ihlal_turu=:ih,yer=:yer,surucu_adi=:s,ceza_tutari=:t,durum=:d,teblig_tarihi=:teb,son_odeme_tarihi=:son,odeme_tarihi=:ot,odenen_tutar=:od,odeyen_taraf=:op,itiraz_tarihi=:it,itiraz_dosya_no=:idn,itiraz_mercii=:im,itiraz_sonucu=:isn,aciklama=:ac WHERE ceza_id=:id"""),{'id':ceza_id,'no':b.get('tutanak_no') or None,'ih':b.get('ihlal_turu') or None,'yer':b.get('yer') or None,'s':b.get('surucu_adi') or None,'t':b.get('ceza_tutari') or 0,'d':b.get('durum') or 'ODENMEDI','teb':b.get('teblig_tarihi') or None,'son':b.get('son_odeme_tarihi') or None,'ot':b.get('odeme_tarihi') or None,'od':b.get('odenen_tutar') or None,'op':b.get('odeyen_taraf') or None,'it':b.get('itiraz_tarihi') or None,'idn':b.get('itiraz_dosya_no') or None,'im':b.get('itiraz_mercii') or None,'isn':b.get('itiraz_sonucu') or None,'ac':b.get('aciklama') or None}); db.commit(); return {'ok':True}

@router.post('/trafik-cezalari/{ceza_id}/dosya',status_code=201)
async def ceza_dosya_yukle(ceza_id:int,kategori:str=Form('CEZA_TUTANAGI'),dosya:UploadFile=File(...),db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Trafik Cezaları','DUZENLE')
    if not db.execute(text("SELECT 1 FROM aftys.trafik_cezalari WHERE ceza_id=:id"),{'id':ceza_id}).first(): raise HTTPException(404,'Ceza bulunamadı')
    root=pathlib.Path(os.environ.get('AFTYS_UPLOAD_DIR','/data/uploads')); root.mkdir(parents=True,exist_ok=True)
    suffix=pathlib.Path(dosya.filename or '').suffix[:12]; key=f"{uuid.uuid4()}{suffix}"; target=root/key; total=0
    with target.open('wb') as f:
        while True:
            chunk=await dosya.read(1024*1024)
            if not chunk: break
            total+=len(chunk)
            if total>25*1024*1024: f.close(); target.unlink(missing_ok=True); raise HTTPException(413,'Dosya 25 MB sınırını aşıyor')
            f.write(chunk)
    ek=db.execute(text("INSERT INTO aftys.dosyalar_ekler(entity_type,entity_id,dosya_adi,mime_type,storage_key,aciklama,yukleyen_id) VALUES('TRAFIK_CEZASI',:id,:ad,:mime,:key,:kat,:u) RETURNING ek_id"),{'id':str(ceza_id),'ad':dosya.filename or key,'mime':dosya.content_type or 'application/octet-stream','key':key,'kat':kategori,'u':str(u.kullanici_id)}).scalar_one(); db.commit(); return {'ek_id':str(ek)}

@router.get('/dosyalar/{ek_id}')
def module_dosya_indir(ek_id:uuid.UUID,db:Session=Depends(get_db),u=Depends(current_user)):
    row=db.execute(text("SELECT dosya_adi,mime_type,storage_key FROM aftys.dosyalar_ekler WHERE ek_id=:id"),{'id':ek_id}).mappings().first()
    if not row: raise HTTPException(404,'Dosya kaydı bulunamadı')
    path=pathlib.Path(os.environ.get('AFTYS_UPLOAD_DIR','/data/uploads'))/row['storage_key']
    if not path.exists(): raise HTTPException(404,'Dosya depoda bulunamadı')
    return FileResponse(str(path),media_type=row['mime_type'] or 'application/octet-stream',filename=row['dosya_adi'])

@router.get('/rapor-merkezi/{tur}/detay')
def rapor_detay(tur:str,db:Session=Depends(get_db),u=Depends(current_user)):
    require_permission(db,u,'Rapor Merkezi','GORUNTULE')
    plate=lambda a: f"(SELECT deger FROM aftys.arac_kimlik_gecmisi WHERE arac_id={a}.arac_id AND alan_tipi='PLAKA' AND bitis_tarihi IS NULL LIMIT 1)"
    queries={
      'toplam_arac':f"""SELECT {plate('a')} plaka,a.marka||' '||COALESCE(a.model,'') \"marka/model\",a.model_yili,COALESCE(i.ad,'') \"istasyon/birim\",COALESCE(d.ad,'') durum,a.gosterge_km km,CASE WHEN COALESCE((SELECT adblue_var FROM aftys.km_gecmisi km WHERE km.arac_id=a.arac_id ORDER BY tarih_saat DESC LIMIT 1),false) THEN 'Var' ELSE 'Yok' END \"AdBlue\",(SELECT max(b.tarih_saat) FROM aftys.bakimlar b WHERE b.arac_id=a.arac_id) \"son bakım / son servis\" FROM aftys.araclar a LEFT JOIN aftys.istasyon_birimler i ON i.birim_id=a.gunluk_birim_id LEFT JOIN aftys.arac_durumlari d ON d.arac_durum_id=a.arac_durum_id WHERE a.aktif_mi=true ORDER BY plaka""",
      'ambulans':f"""SELECT {plate('a')} plaka,a.marka||' '||COALESCE(a.model,'') \"marka/model\",a.model_yili,COALESCE(i.ad,'') \"istasyon/birim\",COALESCE(d.ad,'') durum,a.gosterge_km km,CASE WHEN COALESCE((SELECT adblue_var FROM aftys.km_gecmisi km WHERE km.arac_id=a.arac_id ORDER BY tarih_saat DESC LIMIT 1),false) THEN 'Var' ELSE 'Yok' END \"AdBlue\" FROM aftys.araclar a LEFT JOIN aftys.istasyon_birimler i ON i.birim_id=a.gunluk_birim_id LEFT JOIN aftys.arac_durumlari d ON d.arac_durum_id=a.arac_durum_id WHERE a.aktif_mi=true AND a.arac_sinifi='AMBULANS' ORDER BY plaka""",
      'hizmet_araci':f"""SELECT {plate('a')} plaka,a.marka||' '||COALESCE(a.model,'') \"marka/model\",a.model_yili,COALESCE(i.ad,'') \"istasyon/birim\",COALESCE(d.ad,'') durum,a.gosterge_km km FROM aftys.araclar a LEFT JOIN aftys.istasyon_birimler i ON i.birim_id=a.gunluk_birim_id LEFT JOIN aftys.arac_durumlari d ON d.arac_durum_id=a.arac_durum_id WHERE a.aktif_mi=true AND a.arac_sinifi='HIZMET_ARACI' ORDER BY plaka""",
      'acik_ariza':f"""SELECT {plate('a')} arac,COALESCE(i.ad,'') istasyon,x.tarih_saat \"arıza tarihi\",x.kategori,x.sistem_parca \"sistem/parça\",x.durum,FLOOR(EXTRACT(EPOCH FROM (now()-x.tarih_saat))/86400)::int \"gayrifaal süre\" FROM aftys.arizalar x JOIN aftys.araclar a ON a.arac_id=x.arac_id LEFT JOIN aftys.istasyon_birimler i ON i.birim_id=COALESCE(x.birim_id,a.gunluk_birim_id) WHERE x.durum<>'TAMAMLANDI' ORDER BY x.tarih_saat DESC""",
      'acik_is_emri':f"""SELECT w.is_emri_no \"iş emri no\",{plate('a')} arac,w.acilis_tarihi tarih,w.talep \"arıza/talep\",COALESCE(k.ad_soyad,'') \"teknik personel\",COALESCE(s.ad,'') servis,w.durum FROM aftys.is_emirleri w JOIN aftys.araclar a ON a.arac_id=w.arac_id LEFT JOIN aftys.kullanicilar k ON k.kullanici_id=w.sorumlu_kullanici_id LEFT JOIN aftys.servis_islemleri si ON si.arac_id=w.arac_id AND si.cikis_tarihi IS NULL LEFT JOIN aftys.servisler s ON s.servis_id=si.servis_id WHERE w.durum NOT IN ('TAMAMLANDI','IPTAL') ORDER BY w.acilis_tarihi DESC""",
      'serviste':f"""SELECT {plate('a')} arac,s.ad servis,si.giris_tarihi \"giriş tarihi\",FLOOR(EXTRACT(EPOCH FROM (now()-si.giris_tarihi))/86400)::int \"gün sayısı\",COALESCE(si.yapilan_islem,'') işlem,si.toplam_tutar maliyet FROM aftys.servis_islemleri si JOIN aftys.araclar a ON a.arac_id=si.arac_id JOIN aftys.servisler s ON s.servis_id=si.servis_id WHERE si.cikis_tarihi IS NULL ORDER BY si.giris_tarihi""",
      'kaza':f"""SELECT k.kaza_dosya_no \"kaza dosya no\",{plate('a')} arac,k.tarih_saat tarih,k.surucu_adi sürücü,k.dosya_durumu durum,COALESCE((SELECT string_agg(ks.yapilan_islem,'; ') FROM aftys.kaza_servisleri ks WHERE ks.kaza_id=k.kaza_id),'') onarım,COALESCE((SELECT string_agg(COALESCE(sk.trafik_sigorta_sirketi,'')||' '||COALESCE(sk.kasko_sirketi,''),'; ') FROM aftys.sigorta_kasko_surecleri sk WHERE sk.kaza_id=k.kaza_id),'') \"sigorta/kasko\",COALESCE((SELECT sum(ht.talep_tutari) FROM aftys.hukuki_icra hi JOIN aftys.hukuki_talepler ht ON ht.hukuk_id=hi.hukuk_id WHERE hi.kaza_id=k.kaza_id AND ht.talep_turu ILIKE '%DEĞER%'),0) \"değer kaybı\",COALESCE((SELECT string_agg(hi.durum,'; ') FROM aftys.hukuki_icra hi WHERE hi.kaza_id=k.kaza_id),'') \"hukuki süreç\" FROM aftys.trafik_kazalari k JOIN aftys.araclar a ON a.arac_id=k.arac_id ORDER BY k.tarih_saat DESC""",
      'ceza':f"""SELECT {plate('a')} arac,c.surucu_adi sürücü,c.tutanak_no \"tutanak no\",c.ceza_tutari \"ceza tutarı\",c.durum,c.odeme_tarihi \"ödeme tarihi\" FROM aftys.trafik_cezalari c JOIN aftys.araclar a ON a.arac_id=c.arac_id ORDER BY c.ceza_tarihi DESC""",
      'tibbi_donanim':f"""SELECT t.cihaz_adi cihaz,COALESCE(t.marka,'')||' '||COALESCE(t.model,'') \"marka/model\",t.seri_no \"seri no\",t.kunye_no \"künye no\",COALESCE({plate('a')},'') \"bağlı araç\",t.durum FROM aftys.tibbi_donanim t LEFT JOIN aftys.donanim_atamalari da ON da.cihaz_id=t.cihaz_id AND da.bitis_tarihi IS NULL LEFT JOIN aftys.araclar a ON a.arac_id=da.arac_id WHERE t.aktif_mi=true ORDER BY t.cihaz_adi""",
      'depo_kalem':"""SELECT m.malzeme_adi malzeme,COALESCE(sum(l.mevcut_miktar),0) stok,m.birim,string_agg(COALESCE(l.lot_no,l.seri_no,''),', ') \"lot/seri\",min(l.skt) \"SKT\",m.raf_konum raf FROM aftys.depo_malzemeleri m LEFT JOIN aftys.depo_lotlari l ON l.malzeme_id=m.malzeme_id WHERE m.aktif_mi=true GROUP BY m.malzeme_id ORDER BY m.malzeme_adi"""
    }
    if tur not in queries: raise HTTPException(404,'Rapor türü bulunamadı')
    return {'records':result_rows(db.execute(text(queries[tur])))}

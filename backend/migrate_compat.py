import os
from sqlalchemy import create_engine, text
url=os.environ['DATABASE_URL']
engine=create_engine(url,pool_pre_ping=True)
modules=['Analiz','Araçlar','Arıza & İş Emri','Uyarılar','Bakım & Servis','Trafik Kazaları','Trafik Cezaları','Tıbbi Donanım','Teknik Birim Deposu','Ambulans Değişimi','Teslim–Tesellüm','Devir/Terkin/Dönüşüm','İstasyonlar & Birimler','Servisler','Rapor Merkezi','Kullanıcılar','Ayarlar']
actions=['GORUNTULE','EKLE','DUZENLE','PASIFE_AL','ONAYLA','RAPORLA']
with engine.begin() as c:
    # Kullanıcı yönetimi için eski canlı şemalarla uyumluluk.
    c.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
    c.execute(text("ALTER TABLE aftys.kullanicilar ADD COLUMN IF NOT EXISTS eposta varchar(160)"))
    c.execute(text("ALTER TABLE aftys.kullanicilar ADD COLUMN IF NOT EXISTS telefon varchar(30)"))
    c.execute(text("ALTER TABLE aftys.kullanicilar ADD COLUMN IF NOT EXISTS parola_degistir_zorunlu boolean NOT NULL DEFAULT false"))
    c.execute(text("ALTER TABLE aftys.istasyon_birimler ADD COLUMN IF NOT EXISTS telsiz_adi varchar(160)"))
    c.execute(text("""CREATE TABLE IF NOT EXISTS aftys.arac_tahsisleri (
      tahsis_id bigserial PRIMARY KEY, arac_id uuid NOT NULL REFERENCES aftys.araclar(arac_id),
      birim_id bigint NOT NULL REFERENCES aftys.istasyon_birimler(birim_id), baslangic_tarihi timestamptz NOT NULL DEFAULT now(),
      bitis_tarihi timestamptz, baslangic_km bigint, bitis_km bigint, neden text, onay_protokol_no varchar(120), aciklama text)"""))
    c.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_arac_aktif_tahsis ON aftys.arac_tahsisleri(arac_id) WHERE bitis_tarihi IS NULL"))
    c.execute(text("ALTER TABLE aftys.kullanicilar ADD COLUMN IF NOT EXISTS aktif_mi boolean"))
    c.execute(text("UPDATE aftys.kullanicilar SET aktif_mi=true WHERE aktif_mi IS NULL"))
    c.execute(text("ALTER TABLE aftys.kullanicilar ALTER COLUMN aktif_mi SET DEFAULT true"))
    c.execute(text("ALTER TABLE aftys.kullanicilar ALTER COLUMN aktif_mi SET NOT NULL"))
    c.execute(text("ALTER TABLE aftys.kullanicilar ALTER COLUMN kullanici_id SET DEFAULT gen_random_uuid()"))
    c.execute(text("ALTER TABLE aftys.km_gecmisi ADD COLUMN IF NOT EXISTS tibbi_donanim_markasi varchar(160)"))
    c.execute(text("ALTER TABLE aftys.km_gecmisi ADD COLUMN IF NOT EXISTS adblue_var boolean"))
    c.execute(text("UPDATE aftys.km_gecmisi SET adblue_var=false WHERE adblue_var IS NULL"))
    c.execute(text("ALTER TABLE aftys.km_gecmisi ALTER COLUMN adblue_var SET DEFAULT false"))
    c.execute(text("ALTER TABLE aftys.km_gecmisi ALTER COLUMN adblue_var SET NOT NULL"))
    c.execute(text("ALTER TABLE aftys.hukuki_icra ADD COLUMN IF NOT EXISTS dosya_turu varchar(80)"))
    c.execute(text("ALTER TABLE aftys.hukuki_icra ADD COLUMN IF NOT EXISTS karsi_taraf text"))
    c.execute(text("ALTER TABLE aftys.hukuki_icra ADD COLUMN IF NOT EXISTS avukat_vekil text"))
    c.execute(text("ALTER TABLE aftys.hukuki_icra ADD COLUMN IF NOT EXISTS karar_sonucu text"))
    c.execute(text("ALTER TABLE aftys.hukuki_icra ADD COLUMN IF NOT EXISTS durusma_tarihi date"))
    c.execute(text("""CREATE TABLE IF NOT EXISTS aftys.kaza_tahsilatlari (
      tahsilat_id bigserial PRIMARY KEY,
      kaza_id bigint NOT NULL REFERENCES aftys.trafik_kazalari(kaza_id),
      tahsilat_turu varchar(80) NOT NULL DEFAULT 'DEGER_KAYBI',
      talep_tutari numeric(14,2) NOT NULL DEFAULT 0,
      tahsil_edilen_tutar numeric(14,2) NOT NULL DEFAULT 0,
      tahsilat_tarihi date,
      odeyen_taraf varchar(200),
      durum varchar(40) NOT NULL DEFAULT 'ACIK',
      aciklama text,
      created_by uuid REFERENCES aftys.kullanicilar(kullanici_id),
      created_at timestamptz NOT NULL DEFAULT now()
    )"""))
    c.execute(text("CREATE INDEX IF NOT EXISTS ix_kaza_tahsilat_kaza ON aftys.kaza_tahsilatlari(kaza_id, created_at DESC)"))
    for m in modules:
        for a in actions:
            c.execute(text("INSERT INTO aftys.yetkiler(modul,islem,aciklama) VALUES(:m,:a,:x) ON CONFLICT(modul,islem) DO NOTHING"),{'m':m,'a':a,'x':f'{m} / {a}'})
    # Sistem Yöneticisi ve Yönetici tüm yetkilere sahiptir.
    c.execute(text("""INSERT INTO aftys.rol_yetkileri(rol_id,yetki_id,izin)
      SELECT r.rol_id,y.yetki_id,true FROM aftys.roller r CROSS JOIN aftys.yetkiler y
      WHERE r.ad IN ('Sistem Yöneticisi','Yönetici') ON CONFLICT(rol_id,yetki_id) DO UPDATE SET izin=true"""))
    # Teknik Personel operasyon modüllerini kullanabilir, kullanıcı/ayar yönetemez.
    c.execute(text("""INSERT INTO aftys.rol_yetkileri(rol_id,yetki_id,izin)
      SELECT r.rol_id,y.yetki_id,true FROM aftys.roller r CROSS JOIN aftys.yetkiler y
      WHERE r.ad='Teknik Personel' AND y.modul NOT IN ('Kullanıcılar','Ayarlar')
      ON CONFLICT(rol_id,yetki_id) DO UPDATE SET izin=true"""))
    c.execute(text("""INSERT INTO aftys.kullanici_rolleri(kullanici_id,rol_id)
      SELECT k.kullanici_id,r.rol_id FROM aftys.kullanicilar k CROSS JOIN aftys.roller r
      WHERE r.ad='Teknik Personel' AND NOT EXISTS (SELECT 1 FROM aftys.kullanici_rolleri kr WHERE kr.kullanici_id=k.kullanici_id)
      ON CONFLICT DO NOTHING"""))
print('AFTYS compatibility + permission migration OK')
# V5: profil, talepler, yıllık numaralar ve toplu aktarım
with engine.begin() as c:
    c.execute(text("""CREATE TABLE IF NOT EXISTS aftys.numara_sayaclari(
      seri varchar(20) NOT NULL,yil integer NOT NULL,son_no integer NOT NULL DEFAULT 0,PRIMARY KEY(seri,yil))"""))
    c.execute(text("""CREATE TABLE IF NOT EXISTS aftys.teknik_talepler(
      talep_id bigserial PRIMARY KEY,talep_no varchar(30) NOT NULL UNIQUE,
      istasyon_birim_id bigint NOT NULL REFERENCES aftys.istasyon_birimler(birim_id),
      bildiren_kisi varchar(160),iletisim_yontemi varchar(40) NOT NULL DEFAULT 'TELEFON',
      talep_turu varchar(50) NOT NULL,arac_id uuid REFERENCES aftys.araclar(arac_id),aciklama text NOT NULL,
      ariza_kategori varchar(50),ariza_sistem_parca varchar(160),arac_gorev_yapabiliyor boolean,aciliyet varchar(20) NOT NULL DEFAULT 'NORMAL',
      durum varchar(40) NOT NULL DEFAULT 'YENI',sonuc text,is_emri_id bigint REFERENCES aftys.is_emirleri(is_emri_id),
      bildiren_kullanici_id uuid REFERENCES aftys.kullanicilar(kullanici_id),created_by uuid REFERENCES aftys.kullanicilar(kullanici_id),
      created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now())"""))
    c.execute(text("CREATE INDEX IF NOT EXISTS ix_teknik_talep_durum ON aftys.teknik_talepler(durum,created_at DESC)"))
    c.execute(text("""CREATE TABLE IF NOT EXISTS aftys.kullanici_tercihleri(
      kullanici_id uuid PRIMARY KEY REFERENCES aftys.kullanicilar(kullanici_id),bildirimler jsonb NOT NULL DEFAULT '{}'::jsonb,
      tema varchar(30) NOT NULL DEFAULT 'SISTEM',updated_at timestamptz NOT NULL DEFAULT now())"""))
    c.execute(text("""CREATE TABLE IF NOT EXISTS aftys.geri_bildirimler(
      geri_bildirim_id bigserial PRIMARY KEY,kullanici_id uuid REFERENCES aftys.kullanicilar(kullanici_id),tur varchar(30) NOT NULL,
      konu varchar(200) NOT NULL,mesaj text NOT NULL,durum varchar(30) NOT NULL DEFAULT 'YENI',created_at timestamptz NOT NULL DEFAULT now())"""))
    c.execute(text("""CREATE TABLE IF NOT EXISTS aftys.toplu_aktarimlar(
      aktarim_id bigserial PRIMARY KEY,kullanici_id uuid REFERENCES aftys.kullanicilar(kullanici_id),varlik_turu varchar(50) NOT NULL,
      dosya_adi varchar(255),kayit_sayisi integer NOT NULL DEFAULT 0,durum varchar(30) NOT NULL,created_at timestamptz NOT NULL DEFAULT now())"""))
    for m in ['Teknik Destek Talepleri','Toplu Veri Aktarımı','Yardım']:
        for a in actions:
            c.execute(text("INSERT INTO aftys.yetkiler(modul,islem,aciklama) VALUES(:m,:a,:x) ON CONFLICT(modul,islem) DO NOTHING"),{'m':m,'a':a,'x':f'{m} / {a}'})
    c.execute(text("""INSERT INTO aftys.rol_yetkileri(rol_id,yetki_id,izin)
      SELECT r.rol_id,y.yetki_id,true FROM aftys.roller r CROSS JOIN aftys.yetkiler y
      WHERE r.ad IN ('Sistem Yöneticisi','Yönetici') AND y.modul IN ('Teknik Destek Talepleri','Toplu Veri Aktarımı','Yardım')
      ON CONFLICT(rol_id,yetki_id) DO UPDATE SET izin=true"""))
    c.execute(text("""INSERT INTO aftys.rol_yetkileri(rol_id,yetki_id,izin)
      SELECT r.rol_id,y.yetki_id,true FROM aftys.roller r CROSS JOIN aftys.yetkiler y
      WHERE r.ad='Teknik Personel' AND y.modul IN ('Teknik Destek Talepleri','Yardım')
      ON CONFLICT(rol_id,yetki_id) DO UPDATE SET izin=true"""))
    # Mevcut iş emri numaralarını korur; bundan sonraki numaralar uygulama tarafından yıllık sayaçla üretilir.
print('AFTYS V5 migration OK')
# V9: TC giriş, talep yaşam döngüsü, onay/bildirim ve geçmiş analiz altyapısı
with engine.begin() as c:
    c.execute(text("ALTER TABLE aftys.kullanicilar ADD COLUMN IF NOT EXISTS tc_kimlik_no varchar(11)"))
    c.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_kullanicilar_tc ON aftys.kullanicilar(tc_kimlik_no) WHERE tc_kimlik_no IS NOT NULL"))
    for sql in [
      "ALTER TABLE aftys.teknik_talepler ADD COLUMN IF NOT EXISTS goreve_engel boolean NOT NULL DEFAULT false",
      "ALTER TABLE aftys.teknik_talepler ADD COLUMN IF NOT EXISTS pasif_mi boolean NOT NULL DEFAULT false",
      "ALTER TABLE aftys.teknik_talepler ADD COLUMN IF NOT EXISTS kapanis_tarihi timestamptz",
      "ALTER TABLE aftys.teknik_talepler ADD COLUMN IF NOT EXISTS durum_notu text",
      "ALTER TABLE aftys.teknik_talepler ADD COLUMN IF NOT EXISTS kaynak varchar(40) NOT NULL DEFAULT 'UYGULAMA'"
    ]: c.execute(text(sql))
    c.execute(text("""CREATE TABLE IF NOT EXISTS aftys.teknik_talep_zaman_cizelgesi(
      olay_id bigserial PRIMARY KEY,talep_id bigint NOT NULL REFERENCES aftys.teknik_talepler(talep_id),
      durum varchar(50) NOT NULL,aciklama text,kullanici_id uuid REFERENCES aftys.kullanicilar(kullanici_id),
      created_at timestamptz NOT NULL DEFAULT now())"""))
    c.execute(text("""CREATE TABLE IF NOT EXISTS aftys.onay_talepleri(
      onay_id bigserial PRIMARY KEY,entity_type varchar(60) NOT NULL,entity_id varchar(80) NOT NULL,
      islem_turu varchar(30) NOT NULL,eski_json jsonb,yeni_json jsonb,gerekce text NOT NULL,
      talep_eden uuid REFERENCES aftys.kullanicilar(kullanici_id),durum varchar(20) NOT NULL DEFAULT 'BEKLIYOR',
      karar_veren uuid REFERENCES aftys.kullanicilar(kullanici_id),karar_notu text,created_at timestamptz NOT NULL DEFAULT now(),karar_tarihi timestamptz)"""))
    c.execute(text("""CREATE TABLE IF NOT EXISTS aftys.bildirimler(
      bildirim_id bigserial PRIMARY KEY,kullanici_id uuid NOT NULL REFERENCES aftys.kullanicilar(kullanici_id),
      baslik varchar(180) NOT NULL,mesaj text NOT NULL,link varchar(240),okundu boolean NOT NULL DEFAULT false,
      created_at timestamptz NOT NULL DEFAULT now())"""))
    c.execute(text("CREATE INDEX IF NOT EXISTS ix_bildirim_user ON aftys.bildirimler(kullanici_id,okundu,created_at DESC)"))
print('AFTYS V9 migration OK')
# V10: zimmet, onayli silme ve surum altyapisi
with engine.begin() as c:
    c.execute(text("ALTER TABLE aftys.arac_tahsisleri ADD COLUMN IF NOT EXISTS created_by uuid REFERENCES aftys.kullanicilar(kullanici_id)"))
    c.execute(text("ALTER TABLE aftys.arac_tahsisleri ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now()"))
    c.execute(text("CREATE INDEX IF NOT EXISTS ix_tahsis_birim_aktif ON aftys.arac_tahsisleri(birim_id,bitis_tarihi)"))
    # TC yalnızca 11 rakam olduğunda kimlik numarası olarak kabul edilir; bozuk legacy değerler NULL yapılır.
    c.execute(text("UPDATE aftys.kullanicilar SET tc_kimlik_no=NULL WHERE tc_kimlik_no IS NOT NULL AND tc_kimlik_no !~ '^[0-9]{11}$'"))
    c.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_kullanicilar_tc ON aftys.kullanicilar(tc_kimlik_no) WHERE tc_kimlik_no IS NOT NULL"))
print('AFTYS V10 migration OK')

# AYS V13: sade ariza/tamir akisi ve gayrifaal sure takibi
with engine.begin() as c:
    for sql in [
      "ALTER TABLE aftys.teknik_talepler ADD COLUMN IF NOT EXISTS ariza_cozum_yeri varchar(30)",
      "ALTER TABLE aftys.teknik_talepler ADD COLUMN IF NOT EXISTS gayrifaal_baslangic timestamptz",
      "ALTER TABLE aftys.teknik_talepler ADD COLUMN IF NOT EXISTS gayrifaal_bitis timestamptz"
    ]: c.execute(text(sql))
    c.execute(text("CREATE INDEX IF NOT EXISTS ix_teknik_talep_cozum_durum ON aftys.teknik_talepler(ariza_cozum_yeri,durum,created_at DESC)"))
print('AYS V13 migration OK')
# AYS V14: çağrı kaydında seçilen servis
with engine.begin() as c:
    c.execute(text("ALTER TABLE aftys.teknik_talepler ADD COLUMN IF NOT EXISTS servis_id bigint REFERENCES aftys.servisler(servis_id)"))
print('AYS V14 migration OK')


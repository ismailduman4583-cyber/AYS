-- Ambulans Filo Teknik Yonetim Sistemi
-- PostgreSQL V1 - Fiziksel Veritabani Semasi
-- Baseline: 2026-09-16
-- PostgreSQL 15+ onerilir.

BEGIN;

CREATE SCHEMA IF NOT EXISTS aftys;
SET search_path TO aftys, public;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- =========================================================
-- 1) ORTAK YARDIMCI FONKSIYONLAR
-- =========================================================
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END $$;

-- =========================================================
-- 2) KULLANICI / ROL / YETKI
-- =========================================================
CREATE TABLE kullanicilar (
  kullanici_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  kullanici_adi varchar(80) NOT NULL UNIQUE,
  parola_hash text NOT NULL,
  ad_soyad varchar(160) NOT NULL,
  eposta varchar(160),
  telefon varchar(30),
  aktif_mi boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE roller (
  rol_id bigserial PRIMARY KEY,
  ad varchar(80) NOT NULL UNIQUE,
  aktif_mi boolean NOT NULL DEFAULT true
);

CREATE TABLE yetkiler (
  yetki_id bigserial PRIMARY KEY,
  modul varchar(80) NOT NULL,
  islem varchar(40) NOT NULL,
  aciklama text,
  UNIQUE(modul,islem)
);

CREATE TABLE kullanici_rolleri (
  kullanici_id uuid NOT NULL REFERENCES kullanicilar(kullanici_id),
  rol_id bigint NOT NULL REFERENCES roller(rol_id),
  PRIMARY KEY(kullanici_id, rol_id)
);

CREATE TABLE rol_yetkileri (
  rol_id bigint NOT NULL REFERENCES roller(rol_id),
  yetki_id bigint NOT NULL REFERENCES yetkiler(yetki_id),
  izin boolean NOT NULL DEFAULT true,
  PRIMARY KEY(rol_id, yetki_id)
);

CREATE TABLE kullanici_yetkileri (
  kullanici_id uuid NOT NULL REFERENCES kullanicilar(kullanici_id),
  yetki_id bigint NOT NULL REFERENCES yetkiler(yetki_id),
  izin boolean NOT NULL,
  PRIMARY KEY(kullanici_id, yetki_id)
);

-- =========================================================
-- 3) MASTER DATA
-- =========================================================
CREATE TABLE tanimlar (
  tanim_id bigserial PRIMARY KEY,
  grup varchar(80) NOT NULL,
  kod varchar(80) NOT NULL,
  ad varchar(160) NOT NULL,
  sira integer NOT NULL DEFAULT 0,
  aktif_mi boolean NOT NULL DEFAULT true,
  UNIQUE(grup,kod)
);

CREATE TABLE istasyon_birimler (
  birim_id bigserial PRIMARY KEY,
  tip varchar(40) NOT NULL,
  ad varchar(180) NOT NULL,
  kod varchar(50),
  ilce varchar(100),
  adres text,
  latitude numeric(9,6),
  longitude numeric(9,6),
  sorumlu_kisi varchar(160),
  telefon varchar(30),
  aktif_mi boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE servisler (
  servis_id bigserial PRIMARY KEY,
  servis_turu varchar(40) NOT NULL CHECK (servis_turu IN ('ARAC','TIBBI_DONANIM')),
  ad varchar(200) NOT NULL,
  hizmet_verilen_markalar text,
  yetkili_kisi varchar(160),
  unvan varchar(120),
  telefon varchar(30),
  eposta varchar(160),
  adres text,
  latitude numeric(9,6),
  longitude numeric(9,6),
  vergi_no varchar(30),
  vergi_dairesi varchar(120),
  aciklama text,
  aktif_mi boolean NOT NULL DEFAULT true
);

CREATE TABLE arac_turleri (
  arac_tur_id bigserial PRIMARY KEY,
  arac_sinifi varchar(30) NOT NULL CHECK (arac_sinifi IN ('AMBULANS','HIZMET_ARACI')),
  ad varchar(120) NOT NULL,
  aktif_mi boolean NOT NULL DEFAULT true,
  UNIQUE(arac_sinifi, ad)
);

CREATE TABLE arac_durumlari (
  arac_durum_id bigserial PRIMARY KEY,
  kod varchar(60) NOT NULL UNIQUE,
  ad varchar(140) NOT NULL,
  aktif_mi boolean NOT NULL DEFAULT true
);

-- =========================================================
-- 4) ARAC CEKIRDEGI
-- =========================================================
CREATE TABLE araclar (
  arac_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  arac_sinifi varchar(30) NOT NULL CHECK (arac_sinifi IN ('AMBULANS','HIZMET_ARACI')),
  arac_tur_id bigint REFERENCES arac_turleri(arac_tur_id),
  marka varchar(100) NOT NULL,
  model varchar(120),
  model_yili smallint CHECK (model_yili BETWEEN 1950 AND 2200),
  ambulans_tipi varchar(120),
  kasa_tipi varchar(120),
  yakit_turu varchar(50),
  sanziman varchar(50),
  renk varchar(60),
  arac_durum_id bigint REFERENCES arac_durumlari(arac_durum_id),
  gunluk_birim_id bigint REFERENCES istasyon_birimler(birim_id),
  gosterge_km bigint NOT NULL DEFAULT 0 CHECK (gosterge_km >= 0),
  kumulatif_km bigint NOT NULL DEFAULT 0 CHECK (kumulatif_km >= 0),
  qr_token uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
  aciklama text,
  aktif_mi boolean NOT NULL DEFAULT true,
  arsiv_mi boolean NOT NULL DEFAULT false,
  created_by uuid REFERENCES kullanicilar(kullanici_id),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_by uuid REFERENCES kullanicilar(kullanici_id),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ix_araclar_sinif_durum ON araclar(arac_sinifi, arac_durum_id);
CREATE INDEX ix_araclar_birim ON araclar(gunluk_birim_id);

CREATE TABLE arac_kimlik_gecmisi (
  kimlik_gecmis_id bigserial PRIMARY KEY,
  arac_id uuid NOT NULL REFERENCES araclar(arac_id),
  alan_tipi varchar(40) NOT NULL CHECK (alan_tipi IN ('PLAKA','SASI_NO','MOTOR_NO','RUHSAT_SERI_NO')),
  deger varchar(180) NOT NULL,
  baslangic_tarihi timestamptz NOT NULL DEFAULT now(),
  bitis_tarihi timestamptz,
  degisiklik_tipi varchar(30) NOT NULL DEFAULT 'ILK_KAYIT'
    CHECK (degisiklik_tipi IN ('ILK_KAYIT','KAYIT_DUZELTME','RESMI_DEGISIKLIK')),
  neden text,
  created_by uuid REFERENCES kullanicilar(kullanici_id),
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (bitis_tarihi IS NULL OR bitis_tarihi > baslangic_tarihi)
);

CREATE UNIQUE INDEX ux_arac_kimlik_aktif
ON arac_kimlik_gecmisi(arac_id, alan_tipi)
WHERE bitis_tarihi IS NULL;

CREATE INDEX ix_arac_kimlik_deger ON arac_kimlik_gecmisi(alan_tipi, upper(deger));
CREATE INDEX ix_arac_kimlik_tarih ON arac_kimlik_gecmisi(arac_id, alan_tipi, baslangic_tarihi, bitis_tarihi);

CREATE TABLE arac_ruhsat (
  ruhsat_id bigserial PRIMARY KEY,
  arac_id uuid NOT NULL REFERENCES araclar(arac_id),
  ilk_tescil_tarihi date,
  tescil_tarihi date,
  ruhsat_seri_no varchar(100),
  ticari_ad varchar(160),
  tip varchar(100),
  varyant varchar(100),
  versiyon varchar(100),
  arac_cinsi varchar(120),
  kullanim_amaci varchar(160),
  motor_gucu_kw numeric(10,2),
  motor_hacmi_cc integer,
  yakit_turu varchar(50),
  renk varchar(60),
  koltuk_sayisi smallint,
  azami_yuklu_agirlik_kg numeric(12,2),
  katar_agirligi_kg numeric(12,2),
  bos_agirlik_kg numeric(12,2),
  dingil_sayisi smallint,
  sahip_kurum text,
  baslangic_tarihi timestamptz NOT NULL DEFAULT now(),
  bitis_tarihi timestamptz,
  aciklama text,
  created_by uuid REFERENCES kullanicilar(kullanici_id),
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (bitis_tarihi IS NULL OR bitis_tarihi > baslangic_tarihi)
);

CREATE UNIQUE INDEX ux_arac_ruhsat_aktif ON arac_ruhsat(arac_id) WHERE bitis_tarihi IS NULL;

CREATE TABLE km_gecmisi (
  km_id bigserial PRIMARY KEY,
  arac_id uuid NOT NULL REFERENCES araclar(arac_id),
  tarih_saat timestamptz NOT NULL DEFAULT now(),
  gosterge_km bigint NOT NULL CHECK (gosterge_km >= 0),
  kumulatif_km bigint NOT NULL CHECK (kumulatif_km >= 0),
  tibbi_donanim_markasi varchar(160),
  adblue_var boolean NOT NULL DEFAULT false,
  kaynak_tipi varchar(60) NOT NULL,
  kaynak_id text,
  sayac_degisim_mi boolean NOT NULL DEFAULT false,
  eski_gosterge_km bigint,
  aciklama text,
  created_by uuid REFERENCES kullanicilar(kullanici_id),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_km_arac_tarih ON km_gecmisi(arac_id,tarih_saat DESC);

-- =========================================================
-- 5) BELGE / DOSYA / UYARI
-- =========================================================
CREATE TABLE arac_belgeleri (
  belge_id bigserial PRIMARY KEY,
  arac_id uuid NOT NULL REFERENCES araclar(arac_id),
  belge_turu varchar(100) NOT NULL,
  belge_adi varchar(200),
  belge_no varchar(120),
  duzenleyen varchar(200),
  baslangic_tarihi date,
  bitis_tarihi date,
  sureli_mi boolean NOT NULL DEFAULT false,
  yenileme_durumu varchar(30) NOT NULL DEFAULT 'ISLEM_YAPILMADI'
    CHECK (yenileme_durumu IN ('ISLEM_YAPILMADI','YENILEME_SURECINDE','YENILENDI')),
  versiyon_no integer NOT NULL DEFAULT 1,
  onceki_belge_id bigint REFERENCES arac_belgeleri(belge_id),
  odenen_tutar numeric(14,2) CHECK (odenen_tutar IS NULL OR odenen_tutar >= 0),
  aciklama text,
  created_by uuid REFERENCES kullanicilar(kullanici_id),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_belge_bitis ON arac_belgeleri(bitis_tarihi) WHERE sureli_mi=true;

CREATE TABLE dosyalar_ekler (
  ek_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_type varchar(60) NOT NULL,
  entity_id text NOT NULL,
  dosya_adi varchar(255) NOT NULL,
  mime_type varchar(120),
  storage_key text NOT NULL,
  aciklama text,
  yukleyen_id uuid REFERENCES kullanicilar(kullanici_id),
  yukleme_tarihi timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_ek_entity ON dosyalar_ekler(entity_type,entity_id);

CREATE TABLE uyarilar (
  uyari_id bigserial PRIMARY KEY,
  uyari_turu varchar(80) NOT NULL,
  entity_type varchar(60) NOT NULL,
  entity_id text NOT NULL,
  baslangic_tarihi timestamptz NOT NULL DEFAULT now(),
  son_tarih timestamptz,
  durum varchar(30) NOT NULL DEFAULT 'ACIK' CHECK (durum IN ('ACIK','GORULDU','KAPANDI')),
  mesaj text NOT NULL,
  hedef_kullanici_id uuid REFERENCES kullanicilar(kullanici_id),
  hedef_birim_id bigint REFERENCES istasyon_birimler(birim_id),
  created_at timestamptz NOT NULL DEFAULT now()
);

-- =========================================================
-- 6) ARIZA / BAKIM / IS EMRI / SERVIS
-- =========================================================
CREATE TABLE arizalar (
  ariza_id bigserial PRIMARY KEY,
  arac_id uuid NOT NULL REFERENCES araclar(arac_id),
  tarih_saat timestamptz NOT NULL DEFAULT now(),
  km_id bigint REFERENCES km_gecmisi(km_id),
  kategori varchar(30) NOT NULL CHECK (kategori IN ('ARAC_DONANIM','TIBBI_DONANIM','DIGER')),
  sistem_parca varchar(160),
  aciklama text NOT NULL,
  bildiren varchar(160),
  birim_id bigint REFERENCES istasyon_birimler(birim_id),
  durum varchar(40) NOT NULL DEFAULT 'ACIK',
  tekrar_ariza_mi boolean NOT NULL DEFAULT false,
  created_by uuid REFERENCES kullanicilar(kullanici_id),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_ariza_tekrar ON arizalar(arac_id,kategori,sistem_parca,tarih_saat DESC);

CREATE TABLE bakimlar (
  bakim_id bigserial PRIMARY KEY,
  arac_id uuid NOT NULL REFERENCES araclar(arac_id),
  tarih_saat timestamptz NOT NULL DEFAULT now(),
  km_id bigint REFERENCES km_gecmisi(km_id),
  bakim_turu varchar(120) NOT NULL,
  yapilan_islemler text,
  degisen_parcalar text,
  yapan_tipi varchar(30) CHECK (yapan_tipi IN ('TEKNIK_BIRIM','DIS_SERVIS')),
  servis_id bigint REFERENCES servisler(servis_id),
  parca_tutari numeric(14,2) NOT NULL DEFAULT 0,
  iscilik_tutari numeric(14,2) NOT NULL DEFAULT 0,
  diger_tutar numeric(14,2) NOT NULL DEFAULT 0,
  toplam_tutar numeric(14,2) GENERATED ALWAYS AS (parca_tutari+iscilik_tutari+diger_tutar) STORED,
  aciklama text,
  created_by uuid REFERENCES kullanicilar(kullanici_id),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE SEQUENCE is_emri_no_seq START 1;

CREATE TABLE is_emirleri (
  is_emri_id bigserial PRIMARY KEY,
  is_emri_no varchar(30) NOT NULL UNIQUE DEFAULT ('IE-' || to_char(current_date,'YYYY') || '-' || lpad(nextval('is_emri_no_seq')::text,6,'0')),
  arac_id uuid NOT NULL REFERENCES araclar(arac_id),
  kaynak_tipi varchar(30),
  kaynak_id bigint,
  islem_turu varchar(30) NOT NULL CHECK (islem_turu IN ('ARIZA','BAKIM','KONTROL','DIGER')),
  talep text NOT NULL,
  oncelik varchar(20) NOT NULL DEFAULT 'NORMAL',
  durum varchar(30) NOT NULL DEFAULT 'ACIK'
    CHECK (durum IN ('ACIK','ISLEMDE','MALZEME_BEKLIYOR','TESTTE','TAMAMLANDI','IPTAL')),
  sorumlu_kullanici_id uuid REFERENCES kullanicilar(kullanici_id),
  acilis_tarihi timestamptz NOT NULL DEFAULT now(),
  kapanis_tarihi timestamptz,
  yapilan_islem text,
  sonuc text,
  iptal_gerekcesi text,
  created_by uuid REFERENCES kullanicilar(kullanici_id),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE is_emri_personelleri (
  id bigserial PRIMARY KEY,
  is_emri_id bigint NOT NULL REFERENCES is_emirleri(is_emri_id),
  kullanici_id uuid NOT NULL REFERENCES kullanicilar(kullanici_id),
  rol varchar(50),
  atama_tarihi timestamptz NOT NULL DEFAULT now(),
  ayrilma_tarihi timestamptz
);

CREATE TABLE servis_islemleri (
  servis_islem_id bigserial PRIMARY KEY,
  arac_id uuid NOT NULL REFERENCES araclar(arac_id),
  servis_id bigint NOT NULL REFERENCES servisler(servis_id),
  kaynak_tipi varchar(40),
  kaynak_id bigint,
  giris_tarihi timestamptz NOT NULL,
  cikis_tarihi timestamptz,
  giris_km_id bigint REFERENCES km_gecmisi(km_id),
  cikis_km_id bigint REFERENCES km_gecmisi(km_id),
  servis_kabul_no varchar(100),
  yapilan_islem text,
  degisen_parcalar text,
  parca_tutari numeric(14,2) NOT NULL DEFAULT 0,
  iscilik_tutari numeric(14,2) NOT NULL DEFAULT 0,
  diger_tutar numeric(14,2) NOT NULL DEFAULT 0,
  toplam_tutar numeric(14,2) GENERATED ALWAYS AS (parca_tutari+iscilik_tutari+diger_tutar) STORED,
  durum varchar(30) NOT NULL DEFAULT 'SERVISTE',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE gayrifaal_donemler (
  gayrifaal_id bigserial PRIMARY KEY,
  arac_id uuid NOT NULL REFERENCES araclar(arac_id),
  baslangic_ts timestamptz NOT NULL,
  bitis_ts timestamptz,
  kaynak_tipi varchar(40),
  kaynak_id bigint,
  aciklama text,
  CHECK (bitis_ts IS NULL OR bitis_ts >= baslangic_ts)
);

-- =========================================================
-- 7) TESLIM / HASAR
-- =========================================================
CREATE TABLE teslim_tesellum (
  teslim_id bigserial PRIMARY KEY,
  arac_id uuid NOT NULL REFERENCES araclar(arac_id),
  teslim_turu varchar(50) NOT NULL,
  tarih_saat timestamptz NOT NULL DEFAULT now(),
  km_id bigint REFERENCES km_gecmisi(km_id),
  yakit_seviyesi varchar(30),
  adblue_seviyesi varchar(30),
  neden text,
  kaynak_birim_id bigint REFERENCES istasyon_birimler(birim_id),
  hedef_birim_id bigint REFERENCES istasyon_birimler(birim_id),
  servis_id bigint REFERENCES servisler(servis_id),
  teslim_eden varchar(160),
  teslim_alan varchar(160),
  servis_yetkilisi varchar(160),
  tahmini_donus_tarihi date,
  durum varchar(30) NOT NULL DEFAULT 'ACIK',
  aciklama text,
  created_by uuid REFERENCES kullanicilar(kullanici_id),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE teslim_ekipman (
  teslim_ekipman_id bigserial PRIMARY KEY,
  teslim_id bigint NOT NULL REFERENCES teslim_tesellum(teslim_id),
  ekipman_adi varchar(160) NOT NULL,
  durum varchar(30) NOT NULL CHECK (durum IN ('VAR','YOK','HASARLI','TESLIM_EDILMEDI')),
  aciklama text
);

CREATE TABLE hasarlar (
  hasar_id bigserial PRIMARY KEY,
  arac_id uuid NOT NULL REFERENCES araclar(arac_id),
  kaynak_tipi varchar(40),
  kaynak_id bigint,
  bolge varchar(40) NOT NULL,
  hasar_turu varchar(120),
  aciklama text,
  tespit_tarihi timestamptz NOT NULL DEFAULT now(),
  durum varchar(30) NOT NULL DEFAULT 'AKTIF' CHECK (durum IN ('AKTIF','GIDERILDI')),
  giderilme_tarihi timestamptz,
  servis_id bigint REFERENCES servisler(servis_id),
  created_at timestamptz NOT NULL DEFAULT now()
);

-- =========================================================
-- 8) KAZA / SIGORTA / HUKUK / CEZA
-- =========================================================
CREATE SEQUENCE kaza_dosya_no_seq START 1;

CREATE TABLE trafik_kazalari (
  kaza_id bigserial PRIMARY KEY,
  kaza_dosya_no varchar(30) NOT NULL UNIQUE DEFAULT ('KZ-' || to_char(current_date,'YYYY') || '-' || lpad(nextval('kaza_dosya_no_seq')::text,6,'0')),
  arac_id uuid NOT NULL REFERENCES araclar(arac_id),
  tarih_saat timestamptz NOT NULL,
  yer text,
  km_id bigint REFERENCES km_gecmisi(km_id),
  surucu_adi varchar(160),
  surucu_personel_no varchar(80),
  birim_id bigint REFERENCES istasyon_birimler(birim_id),
  olus_sekli text,
  kaza_turu varchar(30),
  karsi_taraf_bilgisi text,
  yaralanma_var_mi boolean NOT NULL DEFAULT false,
  maddi_hasar_var_mi boolean NOT NULL DEFAULT true,
  kolluk_bilgisi text,
  arac_fiili_durumu varchar(50),
  dosya_durumu varchar(50) NOT NULL DEFAULT 'TUTANAK_BEKLENIYOR',
  created_by uuid REFERENCES kullanicilar(kullanici_id),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE kaza_servisleri (
  kaza_servis_id bigserial PRIMARY KEY,
  kaza_id bigint NOT NULL REFERENCES trafik_kazalari(kaza_id),
  servis_id bigint NOT NULL REFERENCES servisler(servis_id),
  giris_tarihi timestamptz,
  cikis_tarihi timestamptz,
  giris_km bigint,
  cikis_km bigint,
  kabul_no varchar(100),
  yapilan_islem text,
  sonuc text
);

CREATE TABLE kaza_faturalari (
  kaza_fatura_id bigserial PRIMARY KEY,
  kaza_id bigint NOT NULL REFERENCES trafik_kazalari(kaza_id),
  servis_id bigint REFERENCES servisler(servis_id),
  fatura_no varchar(100),
  fatura_tarihi date,
  toplam_tutar numeric(14,2) NOT NULL CHECK (toplam_tutar >= 0)
);

CREATE TABLE sigorta_kasko_surecleri (
  sigorta_id bigserial PRIMARY KEY,
  kaza_id bigint NOT NULL REFERENCES trafik_kazalari(kaza_id),
  kurum_kusur_orani numeric(5,2) CHECK (kurum_kusur_orani BETWEEN 0 AND 100),
  karsi_taraf_kusur_orani numeric(5,2) CHECK (karsi_taraf_kusur_orani BETWEEN 0 AND 100),
  karar_tarihi date,
  karar_kaynagi text,
  trafik_sigorta_sirketi varchar(200),
  kasko_sirketi varchar(200),
  hasar_dosya_no varchar(100),
  kasko_dosya_no varchar(100),
  eksper_bilgisi text,
  toplam_onarim_tutari numeric(14,2) NOT NULL DEFAULT 0,
  sigorta_karsilanan numeric(14,2) NOT NULL DEFAULT 0,
  kasko_karsilanan numeric(14,2) NOT NULL DEFAULT 0,
  karsi_taraftan_tahsil numeric(14,2) NOT NULL DEFAULT 0,
  net_kurum_maliyeti numeric(14,2)
    GENERATED ALWAYS AS (GREATEST(toplam_onarim_tutari-sigorta_karsilanan-kasko_karsilanan-karsi_taraftan_tahsil,0)) STORED
);

CREATE TABLE hukuki_icra (
  hukuk_id bigserial PRIMARY KEY,
  kaza_id bigint NOT NULL REFERENCES trafik_kazalari(kaza_id),
  muhatap varchar(30) NOT NULL CHECK (muhatap IN ('KURUM','SURUCU','HER_IKISI')),
  dosya_no varchar(120),
  merci varchar(200),
  teblig_tarihi date,
  odeme_emri_tarihi date,
  son_islem_tarihi date,
  durum varchar(60),
  aciklama text
);

CREATE TABLE hukuki_talepler (
  talep_id bigserial PRIMARY KEY,
  hukuk_id bigint NOT NULL REFERENCES hukuki_icra(hukuk_id),
  talep_turu varchar(60) NOT NULL,
  talep_tutari numeric(14,2) NOT NULL DEFAULT 0,
  odenen_tutar numeric(14,2) NOT NULL DEFAULT 0,
  odeyen_taraf varchar(30) CHECK (odeyen_taraf IN ('KURUM','SURUCU','SIGORTA_KASKO','DIGER')),
  durum varchar(40),
  aciklama text
);

CREATE TABLE trafik_cezalari (
  ceza_id bigserial PRIMARY KEY,
  arac_id uuid NOT NULL REFERENCES araclar(arac_id),
  kaza_id bigint REFERENCES trafik_kazalari(kaza_id),
  ceza_tarihi timestamptz NOT NULL,
  teblig_tarihi date,
  tutanak_no varchar(120),
  kanun_maddesi varchar(80),
  ihlal_turu varchar(160),
  yer text,
  surucu_adi varchar(160),
  surucu_personel_no varchar(80),
  ceza_tutari numeric(14,2) NOT NULL CHECK (ceza_tutari >= 0),
  indirimli_tutar numeric(14,2),
  son_odeme_tarihi date,
  durum varchar(30) NOT NULL DEFAULT 'ODENMEDI'
    CHECK (durum IN ('ODENMEDI','ODENDI','ITIRAZ_EDILDI','IPTAL_EDILDI')),
  odeme_tarihi date,
  odenen_tutar numeric(14,2),
  odeyen_taraf varchar(30),
  itiraz_tarihi date,
  itiraz_dosya_no varchar(120),
  itiraz_mercii varchar(200),
  itiraz_sonucu text,
  aciklama text
);

-- =========================================================
-- 9) TIBBI DONANIM
-- =========================================================
CREATE TABLE tibbi_donanim (
  cihaz_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  cihaz_adi varchar(180) NOT NULL,
  marka varchar(120),
  model varchar(120),
  seri_no varchar(160),
  kunye_no varchar(160),
  durum varchar(30) NOT NULL DEFAULT 'AKTIF'
    CHECK (durum IN ('AKTIF','ARIZALI','SERVISTE','PASIF')),
  aktif_mi boolean NOT NULL DEFAULT true,
  aciklama text
);
CREATE UNIQUE INDEX ux_tibbi_seri ON tibbi_donanim(seri_no) WHERE seri_no IS NOT NULL;
CREATE UNIQUE INDEX ux_tibbi_kunye ON tibbi_donanim(kunye_no) WHERE kunye_no IS NOT NULL;

CREATE TABLE donanim_atamalari (
  atama_id bigserial PRIMARY KEY,
  cihaz_id uuid NOT NULL REFERENCES tibbi_donanim(cihaz_id),
  arac_id uuid NOT NULL REFERENCES araclar(arac_id),
  baslangic_tarihi timestamptz NOT NULL DEFAULT now(),
  bitis_tarihi timestamptz,
  neden text,
  aciklama text,
  CHECK (bitis_tarihi IS NULL OR bitis_tarihi > baslangic_tarihi)
);
CREATE UNIQUE INDEX ux_cihaz_aktif_atama ON donanim_atamalari(cihaz_id) WHERE bitis_tarihi IS NULL;

CREATE TABLE donanim_arizalari (
  donanim_ariza_id bigserial PRIMARY KEY,
  cihaz_id uuid NOT NULL REFERENCES tibbi_donanim(cihaz_id),
  tarih_saat timestamptz NOT NULL DEFAULT now(),
  aciklama text NOT NULL,
  servis_id bigint REFERENCES servisler(servis_id),
  durum varchar(40) NOT NULL DEFAULT 'ACIK'
);

-- =========================================================
-- 10) DEPO / STOK / SAYIM
-- =========================================================
CREATE TABLE depo_malzemeleri (
  malzeme_id bigserial PRIMARY KEY,
  ana_kategori varchar(30) NOT NULL CHECK (ana_kategori IN ('TIBBI_MALZEME','DIGER_MALZEME')),
  alt_kategori varchar(120),
  malzeme_adi varchar(200) NOT NULL,
  birim varchar(40) NOT NULL,
  raf_konum varchar(100),
  kritik_seviye numeric(14,3),
  aktif_mi boolean NOT NULL DEFAULT true,
  aciklama text
);

CREATE TABLE depo_lotlari (
  lot_id bigserial PRIMARY KEY,
  malzeme_id bigint NOT NULL REFERENCES depo_malzemeleri(malzeme_id),
  lot_no varchar(120),
  seri_no varchar(160),
  skt date,
  mevcut_miktar numeric(14,3) NOT NULL DEFAULT 0 CHECK (mevcut_miktar >= 0)
);
CREATE INDEX ix_lot_skt ON depo_lotlari(skt) WHERE skt IS NOT NULL;

CREATE TABLE stok_hareketleri (
  hareket_id bigserial PRIMARY KEY,
  malzeme_id bigint NOT NULL REFERENCES depo_malzemeleri(malzeme_id),
  lot_id bigint REFERENCES depo_lotlari(lot_id),
  hareket_turu varchar(30) NOT NULL CHECK (hareket_turu IN ('GIRIS','KULLANIM_CIKIS','IADE','ZAYI','SAYIM_DUZELTMESI')),
  tarih_saat timestamptz NOT NULL DEFAULT now(),
  miktar numeric(14,3) NOT NULL CHECK (miktar > 0),
  kaynak_tipi varchar(50),
  kaynak_id bigint,
  arac_id uuid REFERENCES araclar(arac_id),
  is_emri_id bigint REFERENCES is_emirleri(is_emri_id),
  aciklama text,
  created_by uuid REFERENCES kullanicilar(kullanici_id)
);
CREATE INDEX ix_stok_malzeme_tarih ON stok_hareketleri(malzeme_id,tarih_saat DESC);

CREATE TABLE sayimlar (
  sayim_id bigserial PRIMARY KEY,
  baslangic_ts timestamptz NOT NULL DEFAULT now(),
  durum varchar(30) NOT NULL DEFAULT 'ACIK' CHECK (durum IN ('ACIK','ONAY_BEKLIYOR','ONAYLANDI','IPTAL')),
  baslatan_id uuid REFERENCES kullanicilar(kullanici_id),
  onaylayan_id uuid REFERENCES kullanicilar(kullanici_id),
  onay_ts timestamptz,
  aciklama text
);

CREATE TABLE sayim_kalemleri (
  sayim_kalem_id bigserial PRIMARY KEY,
  sayim_id bigint NOT NULL REFERENCES sayimlar(sayim_id),
  malzeme_id bigint NOT NULL REFERENCES depo_malzemeleri(malzeme_id),
  lot_id bigint REFERENCES depo_lotlari(lot_id),
  sistem_miktari numeric(14,3) NOT NULL,
  sayilan_miktar numeric(14,3),
  fark numeric(14,3) GENERATED ALWAYS AS (COALESCE(sayilan_miktar,0)-sistem_miktari) STORED,
  aciklama text
);

-- =========================================================
-- 11) YAKIT / LASTIK / GIDER
-- =========================================================
CREATE TABLE yakit_adblue (
  kayit_id bigserial PRIMARY KEY,
  arac_id uuid NOT NULL REFERENCES araclar(arac_id),
  tarih_saat timestamptz NOT NULL,
  km_id bigint REFERENCES km_gecmisi(km_id),
  yakit_turu varchar(50),
  yakit_litre numeric(12,3) CHECK (yakit_litre IS NULL OR yakit_litre >= 0),
  yakit_tutari numeric(14,2) CHECK (yakit_tutari IS NULL OR yakit_tutari >= 0),
  adblue_litre numeric(12,3) CHECK (adblue_litre IS NULL OR adblue_litre >= 0),
  adblue_tutari numeric(14,2) CHECK (adblue_tutari IS NULL OR adblue_tutari >= 0),
  dolum_istasyonu varchar(200),
  aciklama text
);

CREATE TABLE lastik_islemleri (
  lastik_id bigserial PRIMARY KEY,
  arac_id uuid NOT NULL REFERENCES araclar(arac_id),
  tarih date NOT NULL,
  km_id bigint REFERENCES km_gecmisi(km_id),
  marka varchar(120),
  model_desen varchar(120),
  ebat varchar(80),
  adet smallint NOT NULL CHECK (adet > 0),
  lastik_turu varchar(30) CHECK (lastik_turu IN ('YAZLIK','KISLIK','DORT_MEVSIM')),
  neden text,
  birim_fiyat numeric(14,2) NOT NULL DEFAULT 0,
  toplam_tutar numeric(14,2) GENERATED ALWAYS AS (adet*birim_fiyat) STORED,
  servis_id bigint REFERENCES servisler(servis_id),
  firma varchar(200),
  aciklama text
);

CREATE TABLE giderler (
  gider_id bigserial PRIMARY KEY,
  arac_id uuid REFERENCES araclar(arac_id),
  kaynak_tipi varchar(50) NOT NULL,
  kaynak_id bigint,
  gider_turu varchar(80) NOT NULL,
  tarih date NOT NULL,
  tutar numeric(14,2) NOT NULL CHECK (tutar >= 0),
  aciklama text
);
CREATE INDEX ix_gider_arac_tarih ON giderler(arac_id,tarih DESC);

-- =========================================================
-- 12) TAHSIS / ZIMMET
-- =========================================================
CREATE TABLE arac_tahsisleri (
  tahsis_id bigserial PRIMARY KEY,
  arac_id uuid NOT NULL REFERENCES araclar(arac_id),
  birim_id bigint NOT NULL REFERENCES istasyon_birimler(birim_id),
  baslangic_tarihi timestamptz NOT NULL,
  bitis_tarihi timestamptz,
  baslangic_km bigint,
  bitis_km bigint,
  neden text,
  onay_protokol_no varchar(120),
  aciklama text,
  CHECK (bitis_tarihi IS NULL OR bitis_tarihi > baslangic_tarihi)
);
CREATE UNIQUE INDEX ux_arac_aktif_tahsis ON arac_tahsisleri(arac_id) WHERE bitis_tarihi IS NULL;

CREATE TABLE arac_zimmetleri (
  zimmet_id bigserial PRIMARY KEY,
  arac_id uuid NOT NULL REFERENCES araclar(arac_id),
  personel_adi varchar(160) NOT NULL,
  personel_no varchar(80),
  unvan varchar(120),
  birim_id bigint REFERENCES istasyon_birimler(birim_id),
  baslangic_tarihi timestamptz NOT NULL,
  bitis_tarihi timestamptz,
  teslim_km bigint,
  iade_km bigint,
  teslim_eden varchar(160),
  iade_alan varchar(160),
  aciklama text,
  CHECK (bitis_tarihi IS NULL OR bitis_tarihi > baslangic_tarihi)
);
CREATE UNIQUE INDEX ux_arac_aktif_zimmet ON arac_zimmetleri(arac_id) WHERE bitis_tarihi IS NULL;

-- =========================================================
-- 13) DEVIR / TERKIN / DONUSUM / AMBULANS DEGISIM
-- =========================================================
CREATE TABLE arac_devirleri (
  devir_id bigserial PRIMARY KEY,
  arac_id uuid NOT NULL REFERENCES araclar(arac_id),
  devir_turu varchar(20) NOT NULL CHECK (devir_turu IN ('GECICI','KALICI')),
  alan_kurum varchar(250) NOT NULL,
  protokol_no varchar(120),
  protokol_tarihi date,
  bakanlik_onay_no varchar(120),
  bakanlik_onay_tarihi date,
  baslangic_tarihi date,
  bitis_tarihi date,
  fiili_devir_tarihi timestamptz NOT NULL,
  km bigint,
  teslim_eden varchar(160),
  teslim_alan varchar(160),
  durum varchar(40) NOT NULL DEFAULT 'AKTIF',
  aciklama text
);

CREATE TABLE arac_terkinleri (
  terkin_id bigserial PRIMARY KEY,
  arac_id uuid NOT NULL REFERENCES araclar(arac_id),
  neden varchar(160) NOT NULL,
  onay_no varchar(120),
  onay_tarihi date,
  terkin_tarihi date NOT NULL,
  son_km bigint,
  aciklama text
);

CREATE TABLE arac_donusumleri (
  donusum_id bigserial PRIMARY KEY,
  arac_id uuid NOT NULL REFERENCES araclar(arac_id),
  eski_arac_sinifi varchar(30) NOT NULL,
  yeni_arac_sinifi varchar(30) NOT NULL,
  eski_arac_tur_id bigint REFERENCES arac_turleri(arac_tur_id),
  yeni_arac_tur_id bigint REFERENCES arac_turleri(arac_tur_id),
  onay_no varchar(120),
  onay_tarihi date,
  donusum_tarihi date NOT NULL,
  km bigint,
  yapan_firma_birim varchar(200),
  aciklama text
);

CREATE TABLE ambulans_degisimleri (
  degisim_id bigserial PRIMARY KEY,
  tarih_saat timestamptz NOT NULL DEFAULT now(),
  istasyon_birim_id bigint NOT NULL REFERENCES istasyon_birimler(birim_id),
  cikan_arac_id uuid NOT NULL REFERENCES araclar(arac_id),
  cikan_km bigint,
  gelen_arac_id uuid NOT NULL REFERENCES araclar(arac_id),
  gelen_km bigint,
  neden text,
  teslim_eden varchar(160),
  teslim_alan varchar(160),
  aciklama text,
  CHECK (cikan_arac_id <> gelen_arac_id)
);

-- =========================================================
-- 14) ZAMAN CIZELGESI / AUDIT
-- =========================================================
CREATE TABLE arac_zaman_cizelgesi (
  timeline_id bigserial PRIMARY KEY,
  arac_id uuid NOT NULL REFERENCES araclar(arac_id),
  olay_tipi varchar(60) NOT NULL,
  olay_tarihi timestamptz NOT NULL DEFAULT now(),
  kaynak_tipi varchar(60) NOT NULL,
  kaynak_id text NOT NULL,
  ozet text NOT NULL,
  kullanici_id uuid REFERENCES kullanicilar(kullanici_id)
);
CREATE INDEX ix_timeline_arac_tarih ON arac_zaman_cizelgesi(arac_id,olay_tarihi DESC);

CREATE TABLE audit_log (
  audit_id bigserial PRIMARY KEY,
  kullanici_id uuid REFERENCES kullanicilar(kullanici_id),
  tarih_saat timestamptz NOT NULL DEFAULT now(),
  entity_type varchar(60) NOT NULL,
  entity_id text NOT NULL,
  islem varchar(40) NOT NULL,
  eski_json jsonb,
  yeni_json jsonb,
  gerekce text
);
CREATE INDEX ix_audit_entity ON audit_log(entity_type,entity_id,tarih_saat DESC);

-- =========================================================
-- 15) UPDATED_AT TRIGGER
-- =========================================================
CREATE TRIGGER trg_kullanicilar_updated
BEFORE UPDATE ON kullanicilar
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_araclar_updated
BEFORE UPDATE ON araclar
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =========================================================
-- 16) BASLANGIC VERILERI
-- =========================================================
INSERT INTO roller(ad) VALUES
('Sistem Yöneticisi'),('Yönetici'),('Teknik Personel')
ON CONFLICT DO NOTHING;

INSERT INTO arac_durumlari(kod,ad) VALUES
('AKTIF_GOREVDE','Aktif – İstasyonda Görevde'),
('AKTIF_YEDEK','Aktif – Yedekte'),
('ARIZALI_SERVISTE','Arızalı – Serviste'),
('ARIZA_GIDERILDI_TEST','Arıza Giderildi – Test Sürecinde'),
('GECICI_DEVIRDE','Geçici Devirde')
ON CONFLICT DO NOTHING;

INSERT INTO arac_turleri(arac_sinifi,ad) VALUES
('HIZMET_ARACI','Binek'),
('HIZMET_ARACI','Panelvan'),
('HIZMET_ARACI','Kamyonet'),
('HIZMET_ARACI','Minibüs'),
('HIZMET_ARACI','Kamyon'),
('HIZMET_ARACI','Motosiklet'),
('HIZMET_ARACI','Diğer')
ON CONFLICT DO NOTHING;

-- =========================================================
-- 17) YARARLI VIEW'LAR
-- =========================================================
CREATE VIEW v_arac_guncel_kimlik AS
SELECT
 a.arac_id,
 max(CASE WHEN k.alan_tipi='PLAKA' AND k.bitis_tarihi IS NULL THEN k.deger END) AS plaka,
 max(CASE WHEN k.alan_tipi='SASI_NO' AND k.bitis_tarihi IS NULL THEN k.deger END) AS sasi_no,
 max(CASE WHEN k.alan_tipi='MOTOR_NO' AND k.bitis_tarihi IS NULL THEN k.deger END) AS motor_no,
 max(CASE WHEN k.alan_tipi='RUHSAT_SERI_NO' AND k.bitis_tarihi IS NULL THEN k.deger END) AS ruhsat_seri_no
FROM araclar a
LEFT JOIN arac_kimlik_gecmisi k ON k.arac_id=a.arac_id
GROUP BY a.arac_id;

CREATE VIEW v_gayrifaal_gun AS
SELECT gayrifaal_id, arac_id, baslangic_ts, bitis_ts,
       floor(extract(epoch FROM (coalesce(bitis_ts,now())-baslangic_ts))/86400)::integer AS tamamlanmis_gun,
       kaynak_tipi, kaynak_id
FROM gayrifaal_donemler;

CREATE VIEW v_arac_aktif_tahsis AS
SELECT t.*, b.ad AS birim_adi
FROM arac_tahsisleri t
JOIN istasyon_birimler b ON b.birim_id=t.birim_id
WHERE t.bitis_tarihi IS NULL;

COMMIT;

-- UYGULAMA KATMANINDA / SONRAKI MIGRASYONDA EKLENECEK KRITIK KURALLAR:
-- 1. Arac kimlik versiyonu degisirken eski aktif kaydi kapat + yenisini tek transaction'da ac.
-- 2. Eski plaka aramasini arac_kimlik_gecmisi üzerinden yap.
-- 3. Tekrar ariza: ayni arac+kategori+sistem_parca icin son 2 yil kontrolü.
-- 4. Teslim/servis/tahsis hareketlerinde celiskili acik sorumluluklari engelle.
-- 5. Stok hareketlerinde miktar/lot bakiyesini transaction ve row-lock ile koru.
-- 6. Sayim snapshot'ini sayim baslangicinda sabitle; onayda fark kadar SAYIM_DUZELTMESI üret.
-- 7. Audit log için UPDATE/DELETE uygulama rolüne verilmemeli.
-- 8. Belge bitis uyarisi: bitis tarihinden 1 ay önce job/worker ile üret.
-- 9. Dosyalar fiziksel/object storage'da, storage_key ve metadata DB'de tutulmalı.
-- 10. Tarihsel raporlar olay tarihine göre geçerli kimlik/ruhsat/tahsis dönemini çözmeli.

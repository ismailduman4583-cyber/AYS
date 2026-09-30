import uuid
from datetime import datetime
from sqlalchemy import String, Text, Boolean, BigInteger, SmallInteger, ForeignKey, DateTime, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

class Kullanici(Base):
    __tablename__='kullanicilar'; __table_args__={'schema':'aftys'}
    kullanici_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True)
    kullanici_adi: Mapped[str]=mapped_column(String(80),unique=True)
    parola_hash: Mapped[str]=mapped_column(Text)
    ad_soyad: Mapped[str]=mapped_column(String(160))
    aktif_mi: Mapped[bool]=mapped_column(Boolean,default=True)

class Arac(Base):
    __tablename__='araclar'; __table_args__={'schema':'aftys'}
    arac_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,server_default=text('gen_random_uuid()'))
    arac_sinifi: Mapped[str]=mapped_column(String(30))
    arac_tur_id: Mapped[int|None]=mapped_column(BigInteger,nullable=True)
    marka: Mapped[str]=mapped_column(String(100))
    model: Mapped[str|None]=mapped_column(String(120),nullable=True)
    model_yili: Mapped[int|None]=mapped_column(SmallInteger,nullable=True)
    yakit_turu: Mapped[str|None]=mapped_column(String(50),nullable=True)
    renk: Mapped[str|None]=mapped_column(String(60),nullable=True)
    arac_durum_id: Mapped[int|None]=mapped_column(BigInteger,nullable=True)
    gunluk_birim_id: Mapped[int|None]=mapped_column(BigInteger,nullable=True)
    gosterge_km: Mapped[int]=mapped_column(BigInteger,default=0)
    kumulatif_km: Mapped[int]=mapped_column(BigInteger,default=0)
    aciklama: Mapped[str|None]=mapped_column(Text,nullable=True)
    aktif_mi: Mapped[bool]=mapped_column(Boolean,default=True)
    arsiv_mi: Mapped[bool]=mapped_column(Boolean,default=False)

class KimlikGecmisi(Base):
    __tablename__='arac_kimlik_gecmisi'; __table_args__={'schema':'aftys'}
    kimlik_gecmis_id: Mapped[int]=mapped_column(BigInteger,primary_key=True)
    arac_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey('aftys.araclar.arac_id'))
    alan_tipi: Mapped[str]=mapped_column(String(40))
    deger: Mapped[str]=mapped_column(String(180))
    baslangic_tarihi: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow)
    bitis_tarihi: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    degisiklik_tipi: Mapped[str]=mapped_column(String(30),default='ILK_KAYIT')
    neden: Mapped[str|None]=mapped_column(Text,nullable=True)

class KmGecmisi(Base):
    __tablename__='km_gecmisi'; __table_args__={'schema':'aftys'}
    km_id: Mapped[int]=mapped_column(BigInteger,primary_key=True)
    arac_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey('aftys.araclar.arac_id'))
    tarih_saat: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow)
    gosterge_km: Mapped[int]=mapped_column(BigInteger)
    kumulatif_km: Mapped[int]=mapped_column(BigInteger)
    tibbi_donanim_markasi: Mapped[str|None]=mapped_column(String(160),nullable=True)
    adblue_var: Mapped[bool]=mapped_column(Boolean,default=False,server_default=text("false"),nullable=False)
    kaynak_tipi: Mapped[str]=mapped_column(String(60))
    kaynak_id: Mapped[str|None]=mapped_column(Text,nullable=True)
    sayac_degisim_mi: Mapped[bool]=mapped_column(Boolean,default=False)
    aciklama: Mapped[str|None]=mapped_column(Text,nullable=True)

class Ariza(Base):
    __tablename__='arizalar'; __table_args__={'schema':'aftys'}
    ariza_id: Mapped[int]=mapped_column(BigInteger,primary_key=True)
    arac_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey('aftys.araclar.arac_id'))
    tarih_saat: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow)
    km_id: Mapped[int|None]=mapped_column(BigInteger,nullable=True)
    kategori: Mapped[str]=mapped_column(String(30))
    sistem_parca: Mapped[str|None]=mapped_column(String(160),nullable=True)
    aciklama: Mapped[str]=mapped_column(Text)
    durum: Mapped[str]=mapped_column(String(40),default='ACIK')
    tekrar_ariza_mi: Mapped[bool]=mapped_column(Boolean,default=False)

class AracDurumu(Base):
    __tablename__='arac_durumlari'; __table_args__={'schema':'aftys'}
    arac_durum_id: Mapped[int]=mapped_column(BigInteger,primary_key=True)
    kod: Mapped[str]=mapped_column(String(60),unique=True)
    ad: Mapped[str]=mapped_column(String(140))

class IsEmri(Base):
    __tablename__='is_emirleri'; __table_args__={'schema':'aftys'}
    is_emri_id: Mapped[int]=mapped_column(BigInteger,primary_key=True)
    is_emri_no: Mapped[str]=mapped_column(String(30))
    arac_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey('aftys.araclar.arac_id'))
    kaynak_tipi: Mapped[str|None]=mapped_column(String(30),nullable=True)
    kaynak_id: Mapped[int|None]=mapped_column(BigInteger,nullable=True)
    islem_turu: Mapped[str]=mapped_column(String(30))
    talep: Mapped[str]=mapped_column(Text)
    oncelik: Mapped[str]=mapped_column(String(20),default='NORMAL')
    durum: Mapped[str]=mapped_column(String(30),default='ACIK')
    sorumlu_kullanici_id: Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True),nullable=True)
    acilis_tarihi: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow)
    kapanis_tarihi: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    yapilan_islem: Mapped[str|None]=mapped_column(Text,nullable=True)
    sonuc: Mapped[str|None]=mapped_column(Text,nullable=True)

class ServisIslemi(Base):
    __tablename__='servis_islemleri'; __table_args__={'schema':'aftys'}
    servis_islem_id: Mapped[int]=mapped_column(BigInteger,primary_key=True)
    arac_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey('aftys.araclar.arac_id'))
    servis_id: Mapped[int]=mapped_column(BigInteger)
    kaynak_tipi: Mapped[str|None]=mapped_column(String(40),nullable=True)
    kaynak_id: Mapped[int|None]=mapped_column(BigInteger,nullable=True)
    giris_tarihi: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    cikis_tarihi: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    servis_kabul_no: Mapped[str|None]=mapped_column(String(100),nullable=True)
    yapilan_islem: Mapped[str|None]=mapped_column(Text,nullable=True)
    degisen_parcalar: Mapped[str|None]=mapped_column(Text,nullable=True)
    parca_tutari: Mapped[float]=mapped_column(default=0)
    iscilik_tutari: Mapped[float]=mapped_column(default=0)
    diger_tutar: Mapped[float]=mapped_column(default=0)
    durum: Mapped[str]=mapped_column(String(30),default='SERVISTE')

class TeslimTesellum(Base):
    __tablename__='teslim_tesellum'; __table_args__={'schema':'aftys'}
    teslim_id: Mapped[int]=mapped_column(BigInteger,primary_key=True)
    arac_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey('aftys.araclar.arac_id'))
    teslim_turu: Mapped[str]=mapped_column(String(50))
    tarih_saat: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    servis_id: Mapped[int|None]=mapped_column(BigInteger,nullable=True)
    teslim_eden: Mapped[str|None]=mapped_column(String(160),nullable=True)
    teslim_alan: Mapped[str|None]=mapped_column(String(160),nullable=True)
    servis_yetkilisi: Mapped[str|None]=mapped_column(String(160),nullable=True)
    neden: Mapped[str|None]=mapped_column(Text,nullable=True)
    aciklama: Mapped[str|None]=mapped_column(Text,nullable=True)
    created_by: Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True),nullable=True)

class GayrifaalDonem(Base):
    __tablename__='gayrifaal_donemler'; __table_args__={'schema':'aftys'}
    gayrifaal_id: Mapped[int]=mapped_column(BigInteger,primary_key=True)
    arac_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey('aftys.araclar.arac_id'))
    baslangic_ts: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    bitis_ts: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    kaynak_tipi: Mapped[str|None]=mapped_column(String(40),nullable=True)
    kaynak_id: Mapped[int|None]=mapped_column(BigInteger,nullable=True)
    aciklama: Mapped[str|None]=mapped_column(Text,nullable=True)

class AracZamanCizelgesi(Base):
    __tablename__='arac_zaman_cizelgesi'; __table_args__={'schema':'aftys'}
    timeline_id: Mapped[int]=mapped_column(BigInteger,primary_key=True)
    arac_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey('aftys.araclar.arac_id'))
    olay_tipi: Mapped[str]=mapped_column(String(60))
    olay_tarihi: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow)
    kaynak_tipi: Mapped[str]=mapped_column(String(60))
    kaynak_id: Mapped[str]=mapped_column(Text)
    ozet: Mapped[str]=mapped_column(Text)
    kullanici_id: Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True),nullable=True)

class AuditLog(Base):
    __tablename__='audit_log'; __table_args__={'schema':'aftys'}
    audit_id: Mapped[int]=mapped_column(BigInteger,primary_key=True)
    kullanici_id: Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True),nullable=True)
    tarih_saat: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow)
    entity_type: Mapped[str]=mapped_column(String(60))
    entity_id: Mapped[str]=mapped_column(Text)
    islem: Mapped[str]=mapped_column(String(40))
    eski_json: Mapped[dict|None]=mapped_column(__import__('sqlalchemy').dialects.postgresql.JSONB,nullable=True)
    yeni_json: Mapped[dict|None]=mapped_column(__import__('sqlalchemy').dialects.postgresql.JSONB,nullable=True)
    gerekce: Mapped[str|None]=mapped_column(Text,nullable=True)

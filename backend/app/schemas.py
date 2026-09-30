from pydantic import BaseModel, Field
from typing import Literal
from uuid import UUID

class LoginIn(BaseModel):
    kullanici_adi: str
    parola: str

class AracCreate(BaseModel):
    arac_sinifi: Literal['AMBULANS','HIZMET_ARACI']
    plaka: str
    sasi_no: str | None = None
    motor_no: str | None = None
    marka: str
    model: str | None = None
    model_yili: int | None = Field(None, ge=1950, le=2200)
    yakit_turu: str | None = None
    adblue_var: bool = False
    tibbi_donanim_markasi: str | None = None
    renk: str | None = None
    ambulans_tipi: str | None = None
    arac_tur_id: int | None = None
    arac_durum_id: int | None = None
    gunluk_birim_id: int | None = None
    baslangic_km: int = Field(0, ge=0)
    aciklama: str | None = None

class KmCreate(BaseModel):
    gosterge_km: int = Field(ge=0)
    aciklama: str | None = None

class KimlikChange(BaseModel):
    alan_tipi: Literal['PLAKA','SASI_NO','MOTOR_NO','RUHSAT_SERI_NO']
    yeni_deger: str
    degisiklik_tipi: Literal['KAYIT_DUZELTME','RESMI_DEGISIKLIK']
    neden: str

class ArizaCreate(BaseModel):
    kategori: Literal['ARAC_DONANIM','TIBBI_DONANIM','DIGER']
    sistem_parca: str | None = None
    aciklama: str
    gosterge_km: int | None = Field(None, ge=0)

class IsEmriCreate(BaseModel):
    arac_id: UUID
    ariza_id: int | None = None
    islem_turu: Literal['ARIZA','BAKIM','KONTROL','DIGER'] = 'ARIZA'
    talep: str
    oncelik: Literal['DUSUK','NORMAL','YUKSEK','ACIL'] = 'NORMAL'
    sorumlu_kullanici_id: UUID | None = None

class TeknikOnarim(BaseModel):
    yapilan_islem: str

class ServiseGonder(BaseModel):
    servis_id: int
    servis_kabul_no: str | None = None
    teslim_eden: str
    servis_yetkilisi: str | None = None
    neden: str
    aciklama: str | None = None

class ServistenTeslimAl(BaseModel):
    teslim_alan: str
    servis_yetkilisi: str | None = None
    yapilan_islem: str
    degisen_parcalar: str | None = None
    parca_tutari: float = Field(0, ge=0)
    iscilik_tutari: float = Field(0, ge=0)
    diger_tutar: float = Field(0, ge=0)
    aciklama: str | None = None

class TesteAl(BaseModel):
    yapilan_islem: str | None = None

class GoreveDondur(BaseModel):
    test_basarili: bool
    hedef_durum: Literal['GOREVDE','YEDEK'] = 'GOREVDE'
    sonuc: str

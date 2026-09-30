# AFTYS Backend V1 Starter

FastAPI + PostgreSQL başlangıç backend'i.

## Kurulum
1. PostgreSQL'de önce `Ambulans_Filo_Teknik_Yonetim_Sistemi_V1_PostgreSQL.sql` dosyasını çalıştırın.
2. `.env.example` dosyasını `.env` olarak kopyalayın ve bağlantı/secret değerlerini değiştirin.
3. Sanal ortam oluşturun ve `pip install -r requirements.txt` çalıştırın.
4. İlk admin kullanıcısının `parola_hash` değerini Argon2 ile üretip `aftys.kullanicilar` tablosuna ekleyin.
5. `uvicorn app.main:app --reload` ile başlatın.
6. Swagger: `/docs`

## İlk çalışan endpoint'ler
- POST `/api/auth/login`
- GET/POST `/api/araclar`
- GET `/api/araclar/{arac_id}`
- POST `/api/araclar/{arac_id}/km`
- POST `/api/araclar/{arac_id}/kimlik-degisikligi`
- POST `/api/araclar/{arac_id}/arizalar`
- GET `/health`

## Sonraki geliştirme
İş emri, servis/teslim-tesellüm transaction servisleri, rol-yetki middleware, audit/timeline otomasyonu, ruhsat/belge API'leri, depo ve kaza modülleri.

## V1 Teknik Operasyon Akışı
Bu sürümde operasyon router'ı eklenmiştir:
- `POST /api/operasyon/is-emirleri`
- `POST /api/operasyon/is-emirleri/{id}/teknik-onarim`
- `POST /api/operasyon/is-emirleri/{id}/servise-gonder`
- `POST /api/operasyon/servis-islemleri/{id}/teslim-al`
- `POST /api/operasyon/is-emirleri/{id}/teste-al`
- `POST /api/operasyon/is-emirleri/{id}/goreve-dondur`

Servise gönderme işlemi aynı transaction içinde servis kaydı, teslim-tesellüm, gayrifaal başlangıç, araç durumu, zaman çizelgesi ve audit kaydı üretir. Servisten teslim alma aracı test durumuna geçirir. Başarılı test sonrası iş emri kapanır, açık gayrifaal dönem sonlandırılır ve araç Görevde/Yedek durumuna döner. Başarısız testte iş emri tekrar İşlemde durumuna alınır.

# BURSALAW içerik kalite kapısı

Bu klasör, Legal OS tarafından üretilecek yeni hukuk yazılarının yayın öncesi zorunlu kontrollerini tanımlar.

## İş akışı

1. Konu `Fikir` durumunda kuyruğa alınır.
2. Mevzuat ve kararlar doğrulandıktan sonra `Araştırma` tamamlanır.
3. İçerik `Taslak` olarak oluşturulur.
4. Kaynak ve reklam yasağı kontrollerinden sonra `Hukuki İnceleme` durumuna geçer.
5. `hukuki_inceleyen` alanı doldurulmadan `Onaylandı` veya `Yayında` olamaz.
6. Onaylı içerik site üreticisi tarafından HTML'e çevrilir.

## Yeni içerik üstverisi

```yaml
---
sistem_surumu: "1"
seo_basligi: "Başlık"
meta_aciklamasi: "En fazla 165 karakterlik açıklama"
onerilen_url: "/hukuk-alani/slug"
birincil_anahtar_kelime: "arama sorgusu"
ikincil_sorgular:
  - "ikincil sorgu"
son_hukuki_kontrol: "2 Eylül 2026"
yayin_tarihi: "2026-09-02"
hukuk_alani: "İş Hukuku"
yayin_durumu: "Hukuki İnceleme"
hukuki_inceleyen: "Kutay Kaplan"
---
```

## Yerel kontrol

```bash
python3 automation/validate_content.py ../content/blog/yeni-yazi.md
```

Eski içerikler `sistem_surumu: "1"` taşımadığı için raporlanır fakat yeni kalite kurallarına göre başarısız sayılmaz. Yeni üretilen bütün içerikler v1 üstverisini kullanır.


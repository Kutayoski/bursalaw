import tempfile
import unittest
from pathlib import Path

from automation.validate_content import load_policy, validate


def sample_body(extra: str = "") -> str:
    words = " ".join(["hukuk"] * 920)
    return f"""---
sistem_surumu: "1"
seo_basligi: "Test yazısı"
meta_aciklamasi: "Kısa açıklama"
onerilen_url: "/test/test-yazisi"
birincil_anahtar_kelime: "test yazısı"
son_hukuki_kontrol: "2 Eylül 2026"
yayin_tarihi: "2026-09-02"
hukuk_alani: "İş Hukuku"
yayin_durumu: "Hukuki İnceleme"
hukuki_inceleyen: "Kutay Kaplan"
---

# Test yazısı

{words}

### Yargıtay 9. HD 2024/1 E. ve 2025/1 K. sayılı kararı

Karar özeti.

### Yargıtay 9. HD 2024/2 E. ve 2025/2 K. sayılı kararı

Karar özeti.

### Yargıtay 9. HD 2024/3 E. ve 2025/3 K. sayılı kararı

Karar özeti.

## Kararların Soruya Verdiği Net Cevap

Net cevap.

## Kaynakça

- [Mevzuat](https://www.mevzuat.gov.tr/)

{extra}
"""


class ValidationTests(unittest.TestCase):
    def run_validation(self, text: str):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "article.md"
            path.write_text(text, encoding="utf-8")
            return validate(path, load_policy(), strict=False)

    def test_valid_article_passes(self):
        result = self.run_validation(sample_body())
        self.assertEqual([], result.errors)

    def test_advertising_risk_is_blocked(self):
        result = self.run_validation(sample_body("En iyi avukat olduğumuzu söyleriz."))
        self.assertTrue(any("Reklam yasağı" in error for error in result.errors))


if __name__ == "__main__":
    unittest.main()

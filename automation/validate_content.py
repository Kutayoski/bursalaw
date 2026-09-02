#!/usr/bin/env python3
"""BURSALAW Legal OS v1 içerik kalite kapısı."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = Path(__file__).with_name("content_policy.json")
CONTENT_ROOT = ROOT / "content" / "blog"


@dataclass
class Result:
    path: Path
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    skipped: bool = False


def load_policy() -> dict:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def parse_frontmatter(text: str) -> tuple[dict[str, object], str]:
    if not text.startswith("---\n"):
        return {}, text
    _, raw, body = text.split("---", 2)
    meta: dict[str, object] = {}
    current_list: str | None = None
    for raw_line in raw.splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.lstrip().startswith("-") and current_list:
            item = line.split("-", 1)[1].strip().strip("'\"")
            cast = meta.setdefault(current_list, [])
            if isinstance(cast, list):
                cast.append(item)
            continue
        match = re.match(r"^([a-zA-Z0-9_]+):\s*(.*)$", line)
        if not match:
            current_list = None
            continue
        key, value = match.groups()
        value = value.strip().strip("'\"")
        if value:
            meta[key] = value
            current_list = None
        else:
            meta[key] = []
            current_list = key
    return meta, body


def markdown_links(text: str) -> list[str]:
    return re.findall(r"\[[^\]]+\]\((https?://[^)]+)\)", text)


def normalized_heading_present(body: str, expected: str) -> bool:
    headings = re.findall(r"^#{2,3}\s+(.+?)\s*$", body, flags=re.MULTILINE)
    normalize = lambda value: re.sub(r"[^a-z0-9çğıöşü]+", " ", value.casefold()).strip()
    target = normalize(expected)
    return any(target in normalize(heading) for heading in headings)


def validate(path: Path, policy: dict, strict: bool) -> Result:
    result = Result(path)
    text = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)

    if str(meta.get("sistem_surumu", "")) != str(policy["schema_version"]):
        result.skipped = True
        result.warnings.append("Legacy içerik: Legal OS v1 kontrolleri uygulanmadı.")
        return result

    for key in policy["required_frontmatter"]:
        if not meta.get(key):
            result.errors.append(f"Zorunlu üstveri eksik: {key}")

    status = str(meta.get("yayin_durumu", ""))
    if status not in policy["statuses"]:
        result.errors.append(f"Geçersiz yayın durumu: {status or '(boş)'}")

    if status in policy["publishable_statuses"] and not str(meta.get("hukuki_inceleyen", "")).strip():
        result.errors.append("Onaylanabilir içerikte hukuki_inceleyen zorunludur.")

    words = re.findall(r"\b[\wÇĞİÖŞÜçğıöşü]+\b", body, flags=re.UNICODE)
    if len(words) < int(policy["minimum_word_count"]):
        result.errors.append(
            f"Metin kısa: {len(words)} kelime; en az {policy['minimum_word_count']} gerekli."
        )

    for section in policy["required_sections"]:
        if not normalized_heading_present(body, section):
            result.errors.append(f"Zorunlu bölüm eksik: {section}")

    decision_headings = re.findall(
        r"^#{2,4}\s+.*?(?:\d{4}/\d+|sayılı karar|kararı).*$",
        body,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    if len(decision_headings) < int(policy["minimum_verified_decisions"]):
        result.errors.append(
            "Doğrulanmış karar sayısı yetersiz: "
            f"{len(decision_headings)}; en az {policy['minimum_verified_decisions']} gerekli."
        )

    links = markdown_links(body)
    official = {
        domain
        for link in links
        if (domain := (urlparse(link).hostname or "").removeprefix("www."))
        in policy["official_source_domains"]
    }
    if not official:
        result.errors.append("En az bir resmi kaynak bağlantısı gerekli.")

    if re.search(r"\[(?:TODO|TARİH|KARAR|EKLENECEK|[^\]]*\.{3}[^\]]*)\]", body, re.IGNORECASE):
        result.errors.append("Metinde tamamlanmamış yer tutucu bulunuyor.")

    for char in policy["forbidden_characters"]:
        if char in text:
            result.errors.append(f"Kullanılmaması gereken karakter bulundu: {char}")

    folded = text.casefold()
    for phrase in policy["advertising_risk_phrases"]:
        if phrase.casefold() in folded:
            result.errors.append(f"Reklam yasağı riski taşıyan ifade: {phrase}")

    if len(str(meta.get("meta_aciklamasi", ""))) > 165:
        result.warnings.append("Meta açıklaması 165 karakterden uzun.")

    if strict and result.warnings:
        result.errors.extend(f"Strict: {warning}" for warning in result.warnings)
    return result


def discover(paths: list[str]) -> list[Path]:
    if paths:
        return [Path(item).resolve() for item in paths]
    if not CONTENT_ROOT.exists():
        return []
    return sorted(CONTENT_ROOT.glob("*.md"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    policy = load_policy()
    files = discover(args.paths)
    if not files:
        print("Kontrol edilecek Markdown içeriği bulunamadı.")
        return 0

    failed = False
    for path in files:
        result = validate(path, policy, args.strict)
        label = "SKIP" if result.skipped else ("FAIL" if result.errors else "PASS")
        print(f"[{label}] {path}")
        for item in result.errors:
            print(f"  HATA: {item}")
        for item in result.warnings:
            print(f"  UYARI: {item}")
        failed = failed or bool(result.errors)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Merge research/*.json into countries.json (the CoffinRules country dataset).

Usage: python3 tools/build_countries.py [--generated YYYY-MM-DD] [--strict-translations]

- validates every entry against the schema (status, required keys)
- keeps `lead_days` (minimum paperwork time) only when set explicitly, flags private-jet constraints
- reports duplicates, missing countries (vs. the airport dataset) and unknown / low-confidence entries
"""
import argparse
import datetime
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
RESEARCH = ROOT / "research"
OUT = ROOT / "countries.json"
AIRPORTS = ROOT / "state" / "airport_countries.json"
AGREEMENTS = ROOT / "state" / "agreements.json"
# When this repo sits next to the WordPress plugin, also refresh the copy bundled with it.
PLUGIN_COPY = ROOT.parent / "coffinrules" / "data" / "countries.json"

STATUSES = {"requirements", "strict", "unknown"}
TEXT_FIELDS = ["name", "summary", "coffin", "embalming", "consular", "arrival", "pouch", "private_aviation", "export",
               "authority", "last_checked"]
LIST_FIELDS = ["documents", "sources"]
# Private-aviation notes that block or constrain a casket arriving on a private jet.
PRIVATE_JET_ALERT = re.compile(
    r"as cargo only|cargo only|cannot|not (be )?(permitted|allowed|accepted)|prohibited|"
    r"before (take-?off|departure)|landing permit|overflight permit|designated airport",
    re.I)


def lead_days(entry):
    """Minimum paperwork time in working days, only when the research set it explicitly."""
    value = entry.get("lead_days")
    return value if isinstance(value, int) and 0 < value <= 60 else None


DETAIL_KEYS = ("documents", "coffin", "embalming", "consular", "arrival", "pouch", "private_aviation", "export", "authority")
LOCALIZED_KEYS = ("summary", "at_a_glance", "steps", "key_points", "export_points", "private_jet_note")
EDITORIAL_KEYS = ("at_a_glance", "steps", "key_points", "export_points", "private_jet_note")
GLANCE_KEYS = ("death_certificate", "embalming", "coffin", "laissez_passer", "consular", "permit", "arrival")


def editorial_fields(entry):
    """Short, reader-friendly rewrites of the official text (no new facts). All optional."""
    out = {}
    glance = entry.get("at_a_glance")
    if isinstance(glance, dict):
        glance = {k: str(v).strip() for k, v in glance.items() if k in GLANCE_KEYS and v and str(v).strip()}
        if glance:
            out["at_a_glance"] = glance
    steps = [s for s in entry.get("steps") or [] if isinstance(s, dict) and s.get("what")]
    if steps:
        out["steps"] = [{"when": str(s.get("when") or "").strip(), "what": str(s["what"]).strip()} for s in steps]
    for key in ("key_points", "export_points"):
        items = [str(x).strip() for x in entry.get(key) or [] if str(x).strip()]
        if items:
            out[key] = items
    if isinstance(entry.get("private_jet_note"), str) and entry["private_jet_note"].strip():
        out["private_jet_note"] = entry["private_jet_note"].strip()
    return out


def clean(entry, source):
    errors = []
    cc = str(entry.get("cc", "")).upper()
    if not re.fullmatch(r"[A-Z]{2}", cc):
        errors.append("bad cc")
    if entry.get("status") not in STATUSES:
        errors.append(f"bad status {entry.get('status')!r}")
    out = {"cc": cc, "status": entry.get("status")}
    for key in TEXT_FIELDS:
        value = entry.get(key)
        out[key] = value.strip() if isinstance(value, str) and value.strip() else None
    for key in LIST_FIELDS:
        value = entry.get(key) or []
        if isinstance(value, str):
            value = [value]
        out[key] = [str(v).strip() for v in value if str(v).strip()]
    # Only official sources are shown: Elysium Jet's own pages are not cited as sources.
    out["sources"] = [u for u in out["sources"] if re.match(r"https?://", u) and "elysiumjet.com" not in u]
    pouch = entry.get("pouch_accepted")
    out["pouch_accepted"] = pouch if isinstance(pouch, bool) else None
    if out["pouch_accepted"] is not True:
        out["pouch"] = None  # the site only shows pouch conditions where a pouch is accepted
    out["private_jet_alert"] = bool(entry.get("private_jet_alert")) or bool(
        out["private_aviation"] and PRIVATE_JET_ALERT.search(out["private_aviation"]))
    for key, value in editorial_fields(entry).items():
        out[key] = value
    out["confidence"] = entry.get("confidence") if entry.get("confidence") in ("high", "medium", "low") else "low"
    out["lead_days"] = lead_days(entry) if out["status"] != "unknown" else None
    out["region_file"] = source
    if out["status"] != "unknown" and not out["sources"]:
        errors.append("no sources")
    if not out["summary"] and out["status"] != "unknown":
        errors.append("no summary")
    return out, errors


def load_list(path, problems):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        problems.append(f"{path.name}: invalid JSON ({exc})")
        return []
    return data if isinstance(data, list) else data.get("countries", [])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--generated", default=datetime.date.today().isoformat())
    parser.add_argument("--strict-translations", action="store_true",
                        help="fail when any entry is missing an up-to-date translation (use before publishing)")
    args = parser.parse_args()

    countries, problems, overrides = {}, [], []
    # research/*.json are the base files; research/updates/*.json (re-verifications) replace entries by code.
    paths = [(p, False) for p in sorted(RESEARCH.glob("*.json"))] + [(p, True) for p in sorted((RESEARCH / "updates").glob("*.json"))]
    for path, is_update in paths:
        for entry in load_list(path, problems):
            item, errors = clean(entry, path.stem)
            if errors:
                problems.append(f"{path.name} {item['cc'] or '?'}: {', '.join(errors)}")
            if is_update and item["cc"] in countries and item["status"] in STATUSES:
                overrides.append(f"{item['cc']} ({path.stem})")
                countries[item["cc"]] = item
                continue
            if item["cc"] in countries:
                problems.append(f"duplicate {item['cc']} in {path.name} (kept {countries[item['cc']]['region_file']})")
                continue
            if item["cc"] and item["status"] in STATUSES:
                countries[item["cc"]] = item

    # research/editorial/*.json: {cc + editorial fields} merged on top, written from the verified text.
    edited = []
    for path in sorted((RESEARCH / "editorial").glob("*.json")):
        for entry in load_list(path, problems):
            cc = str(entry.get("cc", "")).upper()
            if cc in countries:
                countries[cc].update(editorial_fields(entry))
                edited.append(cc)

    # research/translations/<lang>.json: client-facing texts per language. A translation is only used while
    # the English it was made from (state/translate_source.json) is unchanged.
    snapshot_path = ROOT / "state" / "translate_source.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8")) if snapshot_path.exists() else {}
    stale, translated = set(), {}
    for path in sorted((RESEARCH / "translations").glob("*.json")):
        lang = path.stem
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"translations/{path.name}: invalid JSON ({exc})")
            continue
        for cc, block in data.items():
            item = countries.get(cc)
            if not item or not isinstance(block, dict):
                continue
            current = {k: item[k] for k in LOCALIZED_KEYS if item.get(k)}
            if snapshot.get(cc) != current:
                stale.add(cc)
                continue
            localized = editorial_fields(block)
            if isinstance(block.get("summary"), str) and block["summary"].strip():
                localized["summary"] = block["summary"].strip()
            if localized:
                item.setdefault("i18n", {})[lang] = localized
                translated[lang] = translated.get(lang, 0) + 1

    # research/translations/details/<lang>.json: the full official fields, same staleness rule
    # (baseline: state/translate_details_source.json).
    details_snapshot_path = ROOT / "state" / "translate_details_source.json"
    details_snapshot = json.loads(details_snapshot_path.read_text(encoding="utf-8")) if details_snapshot_path.exists() else {}
    details_translated, details_stale = {}, set()
    for path in sorted((RESEARCH / "translations" / "details").glob("*.json")):
        lang = path.stem
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"translations/details/{path.name}: invalid JSON ({exc})")
            continue
        for cc, block in data.items():
            item = countries.get(cc)
            if not item or not isinstance(block, dict):
                continue
            current = {k: item[k] for k in DETAIL_KEYS if item.get(k)}
            if details_snapshot.get(cc) != current:
                details_stale.add(cc)
                continue
            clean_block = {}
            for k in DETAIL_KEYS:
                v = block.get(k)
                if isinstance(v, str) and v.strip():
                    clean_block[k] = v.strip()
                elif isinstance(v, list) and v and all(isinstance(x, str) for x in v):
                    clean_block[k] = [x.strip() for x in v if x.strip()]
            if clean_block:
                item.setdefault("i18n", {}).setdefault(lang, {}).update(clean_block)
                details_translated[lang] = details_translated.get(lang, 0) + 1

    for item in countries.values():
        item.pop("region_file", None)

    agreements = json.loads(AGREEMENTS.read_text(encoding="utf-8")) if AGREEMENTS.exists() else {}
    dataset = {
        "meta": {
            "schema": 1,
            "generated": args.generated,
            "count": len(countries),
            "strasbourg_1973": sorted(agreements.get("strasbourg_1973", [])),
        },
        "countries": [countries[cc] for cc in sorted(countries)],
    }
    payload = json.dumps(dataset, ensure_ascii=False, separators=(",", ":"))
    OUT.write_text(payload, encoding="utf-8")
    if PLUGIN_COPY.parent.is_dir():
        PLUGIN_COPY.write_text(payload, encoding="utf-8")

    airport_ccs = set(json.loads(AIRPORTS.read_text(encoding="utf-8"))) if AIRPORTS.exists() else set()
    missing = sorted(airport_ccs - set(countries))
    unknown = sorted(cc for cc, c in countries.items() if c["status"] == "unknown")
    low = sorted(cc for cc, c in countries.items() if c["confidence"] == "low" and c["status"] != "unknown")

    print(f"Wrote {OUT.relative_to(ROOT)}: {len(countries)} countries, {OUT.stat().st_size // 1024} KB")
    print("Status: " + ", ".join(f"{s}={sum(c['status'] == s for c in countries.values())}" for s in sorted(STATUSES)))
    print("Confidence: " + ", ".join(f"{s}={sum(c['confidence'] == s for c in countries.values())}" for s in ("high", "medium", "low")))
    print(f"Pouch accepted: {' '.join(sorted(cc for cc, c in countries.items() if c['pouch_accepted']))}")
    print(f"Unknown ({len(unknown)}): {' '.join(unknown)}")
    print(f"Low confidence ({len(low)}): {' '.join(low)}")
    print(f"Countries with airports but no entry ({len(missing)}): {' '.join(missing)}")
    print(f"Editorial rewrites: {len(set(edited))}")
    print("Translations: " + (", ".join(f"{k}={v}" for k, v in sorted(translated.items())) or "none"))
    print("Detail translations: " + (", ".join(f"{k}={v}" for k, v in sorted(details_translated.items())) or "none"))
    if details_stale:
        print(f"Detail translations out of date ({len(details_stale)}): {' '.join(sorted(details_stale))}")
    if stale:
        print(f"Translations out of date ({len(stale)}): {' '.join(sorted(stale))}")
    if overrides:
        print(f"Updated by research/updates ({len(overrides)}): {' '.join(overrides)}")
    status = 0
    if args.strict_translations:
        langs = sorted({p.stem for p in (RESEARCH / "translations").glob("*.json")})
        missing_tr = []
        for cc, c in countries.items():
            if c["status"] == "unknown" or c["confidence"] == "low":
                continue  # shown as "check with operations" in every language
            for lang in langs:
                block = (c.get("i18n") or {}).get(lang) or {}
                if not any(k in block for k in LOCALIZED_KEYS):
                    missing_tr.append(f"{lang}:{cc}")
                elif any(c.get(k) for k in DETAIL_KEYS) and not any(k in block for k in DETAIL_KEYS):
                    missing_tr.append(f"{lang}:{cc}(details)")
        if missing_tr or not langs:
            print(f"STRICT: {len(missing_tr)} missing translations, not publishable: {' '.join(missing_tr[:30])}")
            status = 2
        else:
            print("STRICT: every entry is translated in " + ", ".join(langs))
    if problems:
        print("Problems:")
        for p in problems:
            print("  -", p)
    if any("invalid JSON" in p for p in problems):
        status = status or 1
    return status


if __name__ == "__main__":
    sys.exit(main())

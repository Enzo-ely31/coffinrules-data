# CoffinRules data

Requirements to fly human remains (casket / coffin or human remains pouch) **into** and **out of** each country, used by the Elysium Jet **CoffinRules** WordPress plugin (coffin flight page). Same organisation as `petrules-data`.

- `countries.json` — the published dataset (the plugin reads it daily from `raw.githubusercontent.com`).
- `research/*.json` — source research by region; edit these, never `countries.json` directly.
- `research/updates/*.json` — re-verified full entries replacing base ones (alphabetical order, later wins; weekly runs use `w-YYYY-MM-DD.json`).
- `research/editorial/*.json` — short client-facing rewrites (`at_a_glance`, `steps`, `key_points`, `export_points`, `private_jet_note`) merged on top; no new facts.
- `research/translations/<lang>.json` — client texts in fr, es, it, de, ar, ru. Used only while the English they were
  translated from (`state/translate_source.json`) is unchanged; full official fields are in `research/translations/details/`.
  `tools/translations.py delta|commit` manages updates. Never publish before `build_countries.py --strict-translations` passes:
  a non-English page never shows English text.
- `state/agreements.json` — parties to the Strasbourg Agreement on the transfer of corpses (1973, CETS 080).
- Only information backed by official sources is shown; low-confidence entries display "check with Elysium Jet operations".
- `tools/build_countries.py` — validates `research/` and rebuilds `countries.json` (`python3 tools/build_countries.py`).
- `tools/watch_sources.py` — weekly GitHub Action: hashes every official page cited and opens a
  `[source-changed] CC` issue when one changes.
- A weekly research run re-verifies changed, stale and low-confidence countries, updates `research/`,
  rebuilds and closes the matching issues.

## Entry schema

| Field | Meaning |
| --- | --- |
| `cc`, `name` | ISO 3166-1 alpha-2 code and English name |
| `status` | `requirements`, `strict` (heavy procedure: ministry or prosecutor approval, long delays) or `unknown` (no reliable official info: check with Elysium Jet operations) |
| `summary` | Essential path to bring a casket **into** the country, in one or two sentences |
| `documents[]` | Documents usually required on entry |
| `coffin` | Casket rules (hermetic sealing, zinc lining, sealing witnessed by whom, outer case) |
| `embalming` | Embalming / conservation rules (required, refused, alternatives such as dry ice) |
| `consular` | Consulate role: transfer permit, mortuary laissez-passer, legalisation / apostille, translations |
| `arrival` | Customs and health clearance on arrival, who collects, burial or cremation deadlines |
| `pouch_accepted`, `pouch` | Whether a human remains pouch (body bag, often on an air tray / combination tray) is accepted instead of a sealed casket: `true`, `false` or `null` (not verified); `pouch` explains the conditions when accepted |
| `private_aviation`, `private_jet_alert`, `private_jet_note` | Private / charter flight specifics (ports of entry, customs on arrival, permits) and whether they constrain a private flight |
| `export`, `export_points[]` | Leaving the country: permits, who issues them, sealing, typical delay |
| `at_a_glance` | Short tiles: `death_certificate`, `embalming`, `coffin`, `laissez_passer`, `consular`, `permit`, `arrival` (≤ 8 words each) |
| `steps[]` | `{when, what}` timeline for an incoming repatriation |
| `key_points[]` | Short good-to-know bullets |
| `lead_days` | Typical minimum working days to complete the paperwork for an incoming casket |
| `authority`, `sources[]`, `confidence`, `last_checked` | Provenance: official URLs actually read, `high`/`medium`/`low`, `YYYY-MM` |

Information only: rules change often. Always confirm with the consulate and the competent authorities before the flight.

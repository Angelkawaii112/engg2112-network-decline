"""Download only selected historical SA2 ERP vintages and ASGS2021 boundaries."""
from settings import ROOT, SOURCE, check_source, PACKAGE
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen



def assets():
    pages = json.loads((ROOT / "data/sources/abs_page_catalog.json").read_text(encoding="utf-8"))
    specifications = [
        ("erp_2021_initial", "regional_2021", "32180DS0001_2001-21.xlsx", "2022-07-26", 2021),
        ("erp_2022_initial", "regional_2022", "32180DS0001_2021-22.xlsx", "2023-04-20", 2022),
        ("erp_2022_revised", "regional_2022", "32180DS0001_2021-22r.xlsx", "2023-08-31", 2022),
        ("erp_2023", "regional_2023", "32180DS0001_2022-23.xlsx", "2024-03-26", 2023),
        ("erp_2024", "regional_2024", "32180DS0001_2023-24.xlsx", "2025-03-27", 2024),
        ("sa2_2021", "boundaries", "SA2_2021_AUST_SHP_GDA2020.zip", "2021-07-20", None),
    ]
    for key, page, filename, published, year in specifications:
        matching = [u for u in pages[page]["downloads"] if u.endswith("/" + filename)]
        if len(matching) != 1:
            raise ValueError(f"No unique published download link for {filename}")
        yield dict(key=key, source_page=pages[page]["url"], url=matching[0],
                   path=f"data/abs/{filename}", published=published, erp_year=year,
                   publication_evidence=f"data/sources/{page}.txt",
                   date_policy="ABS initial release date, or explicit post-release change date for revised workbook")


def download(asset):
    path = ROOT / asset["path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        partial = path.with_suffix(path.suffix + ".partial")
        with urlopen(asset["url"], timeout=120) as response, partial.open("wb") as stream:
            while chunk := response.read(1024 * 1024):
                stream.write(chunk)
        partial.replace(path)
    asset["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    asset["bytes"] = path.stat().st_size
    expected = json.loads((PACKAGE / 'provenance/abs_sources.json').read_text())
    pinned = next(item for item in expected['assets'] if item['key'] == asset['key'])
    if asset['sha256'] != pinned['sha256']:
        raise ValueError(f"Source bytes changed for {asset['key']}; do not compare to archived metrics")
    print(f"Downloaded/verified {asset['key']}: {asset['bytes']:,} bytes", flush=True)
    return asset


if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=3) as pool:
        downloaded = list(pool.map(download, assets()))
    out = ROOT / "data/abs/manifest.json"
    out.write_text(json.dumps(dict(retrieved_utc=datetime.now(timezone.utc).isoformat(), assets=downloaded), indent=2), encoding="utf-8")

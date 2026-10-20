"""Archive ABS publication pages and list their downloadable data assets."""
from settings import ROOT, SOURCE, check_source
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urljoin, unquote
from urllib.request import urlopen

PAGES = {
    "regional_2021": "https://www.abs.gov.au/statistics/people/population/regional-population/2021",
    "regional_2022": "https://www.abs.gov.au/statistics/people/population/regional-population/2021-22",
    "regional_2023": "https://www.abs.gov.au/statistics/people/population/regional-population/2022-23",
    "regional_2024": "https://www.abs.gov.au/statistics/people/population/regional-population/2023-24",
    "age_sex_latest": "https://www.abs.gov.au/statistics/people/population/regional-population-age-and-sex/latest-release",
    "boundaries": "https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs/edition-3-july-2021-june-2026/access-and-downloads/digital-boundary-files",
}


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        if data.strip():
            self.parts.append(data.strip())


def main():
    folder = ROOT / "data" / "sources"
    folder.mkdir(parents=True, exist_ok=True)
    result = {}
    for key, url in PAGES.items():
        with urlopen(url, timeout=90) as response:
            html = response.read().decode("utf-8")
            final_url = response.url
        (folder / f"{key}.html").write_text(html, encoding="utf-8")
        text = Text()
        text.feed(html)
        plain = "\n".join(text.parts)
        (folder / f"{key}.txt").write_text(plain, encoding="utf-8")
        links = sorted(set(urljoin(final_url, link.replace("&amp;", "&"))
                       for link in re.findall(r'href=[\"\']([^\"\']+)', html)
                       if re.search(r'\.(xlsx|zip)(?:[?#]|$)', link, re.I)))
        result[key] = dict(url=url, final_url=final_url, downloads=links)
        print(key, final_url, flush=True)
        print("DATES:", re.findall(r'.{0,100}(?:\d{2}/\d{2}/\d{4}|Post-release changes).{0,220}', plain))
        for link in links:
            print(" ", unquote(link))
    (folder / "abs_page_catalog.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

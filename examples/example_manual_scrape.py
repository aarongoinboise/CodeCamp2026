import requests
from bs4 import BeautifulSoup
from pprint import pprint

url = "https://www.sports-reference.com/cbb/boxscores/2026-04-06-20-michigan.html"

res = requests.get(url)
soup = BeautifulSoup(res.text, "html.parser")

tables = []

tables = soup.find_all("table")

for table in tables:
    thead = table.find("thead")
    if not thead:
        continue

    headers = [th.get("data-stat") for th in thead.find_all("th")]

    for row in table.find("tbody").find_all("tr"):
        if not row.find("td"):
            continue

        cells = row.find_all(["th", "td"])
        data = {}

        for i, cell in enumerate(cells):
            key = headers[i] if i < len(headers) else f"col_{i}"
            data[key] = cell.text.strip()
        pprint(data)
        exit(1)
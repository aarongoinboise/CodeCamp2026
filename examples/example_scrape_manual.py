import requests
from bs4 import BeautifulSoup
from pprint import pprint

url = "https://www.sports-reference.com/cbb/boxscores/2026-04-06-20-michigan.html"

res = requests.get(url)
soup = BeautifulSoup(res.text, "html.parser")

for table in soup.find_all("table"):
    tbody = table.find("tbody")
    if not tbody:
        continue

    for row in tbody.find_all("tr"):
        cells = row.find_all(["th", "td"])
        if not cells:
            continue

        data = {}

        for cell in cells:
            key = cell.get("data-stat")
            if not key:
                continue

            data[key] = cell.get_text(strip=True)

        if data:
            pprint(data)
            exit(1)
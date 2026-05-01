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

    # grab headers from thead
    headers = []
    thead = table.find("thead")
    if thead:
        for th in thead.find_all(["th", "td"]):
            headers.append(th.get_text(strip=True))

    for row in tbody.find_all("tr"):
        cells = row.find_all(["th", "td"])
        if not cells:
            continue

        values = [cell.get_text(strip=True) for cell in cells]
        data = dict(zip(headers, values))

        if data:
            pprint(data)
            break
"""Read-only HTTP smoke: python3 scripts/smoke.py [--backend URL] [--frontend URL]."""
import argparse
import json
from urllib.parse import urljoin
from urllib.request import urlopen
from html.parser import HTMLParser


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and attrs.get("src"):
            self.urls.append(attrs["src"])
        if tag == "link" and attrs.get("rel") == "stylesheet":
            self.urls.append(attrs["href"])


def read(url):
    with urlopen(url, timeout=10) as response:
        assert response.status == 200
        return response.read().decode("utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", default="http://127.0.0.1:8000")
    parser.add_argument("--frontend", default="http://127.0.0.1:5173")
    args = parser.parse_args()
    health = json.loads(read(args.backend + "/api/v1/health"))
    assert health == {"status": "ok", "database": "ok"}
    schema = json.loads(read(args.backend + "/openapi.json"))
    assert "/api/v1/health" in schema["paths"]
    assert "swagger-ui" in read(args.backend + "/docs")
    page_url = args.frontend.rstrip("/") + "/"
    assert json.loads(read(urljoin(page_url, "api/v1/health"))) == health
    page = read(page_url)
    assert page.count('id="cqa-app"') == 1
    assets = Assets()
    assets.feed(page)
    assert assets.urls
    for asset in assets.urls:
        assert not asset.startswith("/"), f"Expected relative asset path: {asset}"
        assert read(urljoin(page_url, asset))
    print(f"PASS: DB-backed health, frontend API proxy, OpenAPI, docs, single frontend root, {len(assets.urls)} relative assets")


if __name__ == "__main__":
    main()

import json
import re

from fastapi.testclient import TestClient

from tiktokenizer_py import catalogue


def _page_data(html: str) -> dict[str, object]:
    match = re.search(r'<script id="page-data" type="application/json">(.*?)</script>', html, re.S)
    assert match
    data: dict[str, object] = json.loads(match.group(1))
    return data


def test_index_embeds_catalogue(client: TestClient) -> None:
    res = client.get("/")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/html")
    assert catalogue.DEFAULT_MODEL in res.text
    data = _page_data(res.text)
    assert data["catalogue"]["default"] == catalogue.DEFAULT_MODEL  # type: ignore[index]
    assert len(data["examples"]) == 11  # type: ignore[arg-type]
    assert data["intro_example"] == "intro"
    assert data["roles"] == ["system", "developer", "user", "assistant"]


def test_page_data_is_html_safe(client: TestClient) -> None:
    html = client.get("/").text
    script = html.split('id="page-data"', 1)[1]
    # Example texts contain "<|im_start|>"; tojson must escape "<" inside the script tag.
    assert "<|im_start|>" not in script.split("</script>", 1)[0]


def test_page_scripts_and_styles_are_served(client: TestClient) -> None:
    html = client.get("/").text
    for path in ("css/app.css", "js/main.js", "vendor/alpinejs-3.17.5/cdn.min.js"):
        assert f'"/static/{path}"' in html
        res = client.get(f"/static/{path}")
        assert res.status_code == 200
        # Browsers revalidate every time, so an update never runs stale modules.
        assert res.headers["cache-control"] == "no-cache"


def test_every_js_module_import_resolves() -> None:
    from tiktokenizer_py.web import STATIC_DIR

    for module in (STATIC_DIR / "js").rglob("*.js"):
        for target in re.findall(r'from "(\.{1,2}/[^"]+)"', module.read_text()):
            assert (module.parent / target).resolve().is_file(), f"{module.name} imports {target}"


def test_static_alpine(client: TestClient) -> None:
    res = client.get("/static/vendor/alpinejs-3.17.5/cdn.min.js")
    assert res.status_code == 200
    assert "javascript" in res.headers["content-type"]


def test_static_css_has_full_palette(client: TestClient) -> None:
    css = client.get("/static/css/app.css").text
    for i in range(19):
        assert f"--seg-{i}:" in css
        assert f".c{i} " in css
    # One value per theme: light-dark() follows the system setting or the theme button.
    assert "color-scheme: light dark" in css
    for theme in ("light", "dark"):
        assert f':root[data-theme="{theme}"]' in css


def test_every_glossary_link_has_an_entry(client: TestClient) -> None:
    from tiktokenizer_py.glossary import GLOSSARY

    html = client.get("/").text
    linked = set(re.findall(r"openGlossary\('([a-z-]+)'\)", html))
    assert linked
    assert linked <= {g.id for g in GLOSSARY}


def test_project_name_is_shown(client: TestClient) -> None:
    html = client.get("/").text
    assert "<title>tiktokenizer-py</title>" in html
    assert '<h1 class="brand">tiktokenizer-py</h1>' in html
    assert client.get("/openapi.json").json()["info"]["title"] == "tiktokenizer-py"


def test_api_docs_use_only_local_files(client: TestClient) -> None:
    html = client.get("/docs").text
    assert "/openapi.json" in html
    assert "https://" not in html
    for url in re.findall(r'(?:src|href)="(/static/[^"]+)"', html):
        assert client.get(url).status_code == 200
    assert client.get("/redoc").status_code == 404

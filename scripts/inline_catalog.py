
import re
import os

catalog_path = "web/catalog.json"
index_path = "web/index.html"

with open(catalog_path, "r", encoding="utf-8") as f:
    catalog_json = f.read()

with open(index_path, "r", encoding="utf-8") as f:
    index_html = f.read()

before_lines = len(index_html.splitlines())
print(f"Lines before: {before_lines}")

def replacer(match):
    return match.group(1) + catalog_json + match.group(3)

pattern = r"(<script id=\"inlineCatalog\" type=\"application/json\">)(.*?)(</script>)"
new_html = re.sub(pattern, replacer, index_html, flags=re.DOTALL)

with open(index_path, "w", encoding="utf-8") as f:
    f.write(new_html)

after_lines = len(new_html.splitlines())
print(f"Lines after: {after_lines}")


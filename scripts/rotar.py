import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
links = json.loads((ROOT / "links.json").read_text(encoding="utf-8"))


def elegir(carpeta, n):
    nombres = random.sample(sorted(links[carpeta]), n)
    return [(carpeta, nombre, links[carpeta][nombre]) for nombre in nombres]


azul = elegir("azul", 2)
rosa = elegir("rosa", 2)
huecos = [azul[0], rosa[0], rosa[1], azul[1]]  # posiciones 1, 2, 3, 4

texto = (ROOT / "README.template.md").read_text(encoding="utf-8")
for i, (carpeta, nombre, url) in enumerate(huecos, start=1):
    texto = texto.replace(f"{{{{IMG{i}}}}}", f"/media/{carpeta}/{nombre}")
    texto = texto.replace(f"{{{{URL{i}}}}}", url)
    texto = texto.replace(f"{{{{ALT{i}}}}}", Path(nombre).stem)

(ROOT / "README.md").write_text(texto, encoding="utf-8")
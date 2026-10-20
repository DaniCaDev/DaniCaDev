"""
build.py · Genera los SVG del README de perfil.

1. Fuente: incrusta Press Start 2P (base64) en los SVG de src/. GitHub
   muestra los SVG como <img> y en ese modo no pueden cargar recursos
   externos, así que la fuente tiene que ir dentro.

2. Títulos: genera las cintas de cada sección (lista TITULOS).

3. Habilidades: genera el inventario a partir de habilidades.json y
   plantillas/habilidades.svg. Los logos salen de iconos/ (Simple Icons);
   los que faltan se descargan y se guardan en caché.

4. Estadísticas: genera el panel "PARTIDA GUARDADA" a partir de
   datos/estadisticas.json (lo crea estadisticas.py).

5. Redes: genera un botón por cada entrada de redes.json y reescribe el
   bloque del README que va entre <!-- REDES:INICIO --> y <!-- REDES:FIN -->.

Uso:
    python build.py

assets/ es la salida: se regenera en cada ejecución.
"""

import base64
import json
import math
import re
import urllib.request
from datetime import date, timedelta
from html import escape
from pathlib import Path

RAIZ = Path(__file__).parent
FUENTE = RAIZ / "fonts" / "press-start-2p.woff2"
ORIGEN = RAIZ / "src"
DESTINO = RAIZ / "assets"
PLANTILLAS = RAIZ / "plantillas"
ICONOS = RAIZ / "iconos"
README = RAIZ / "README.md"
MARCA_FUENTE = "/*FUENTE*/"

# Logos de Simple Icons (https://simpleicons.org). Si no están en iconos/,
# se descargan de aquí y se guardan para la próxima vez.
URL_ICONO = "https://cdn.jsdelivr.net/npm/simple-icons@latest/icons/{nombre}.svg"

# Iconos dibujados a mano para lo que no tiene logo en Simple Icons.
# Mismo formato: un <path> en un cuadrado de 24x24. Los huecos se hacen
# dibujando la forma interior en sentido contrario (regla "nonzero").
ICONOS_PROPIOS = {
    # Cilindro de base de datos: tapa elíptica + dos "rodajas"
    "basedatos": (
        "M4 5a8 3 0 1 0 16 0a8 3 0 1 0 -16 0z"
        "M4 7.5v4c0 1.66 3.58 3 8 3s8-1.34 8-3v-4c0 1.66-3.58 3-8 3s-8-1.34-8-3z"
        "M4 14v4.5c0 1.66 3.58 3 8 3s8-1.34 8-3V14c0 1.66-3.58 3-8 3s-8-1.34-8-3z"
    ),
    # "in" de LinkedIn (la marca no está en Simple Icons)
    "linkedin": (
        "M4.5 6.5a2 2 0 1 0 4 0a2 2 0 1 0 -4 0z"
        "M4.75 9.5h3.5v10h-3.5z"
        "M10.5 9.5h3.3v1.4c.6-1 1.9-1.7 3.4-1.7c2.7 0 3.8 1.7 3.8 4.6v5.7h-3.5v-5.1"
        "c0-1.3-.4-2.2-1.7-2.2s-2 .9-2 2.2v5.1h-3.3z"
    ),
    # Sobre: marco con la solapa rellena
    "email": "M2 5h20v14H2z M4 7.2v9.8h16V7.2l-8 6.2z",
    # Globo terráqueo: anillo + meridiano + ecuador
    "web": (
        "M2 12a10 10 0 1 1 20 0a10 10 0 1 1 -20 0z"
        "M3.8 12a8.2 8.2 0 1 0 16.4 0a8.2 8.2 0 1 0 -16.4 0z"
        "M8 12a4 10 0 1 1 8 0a4 10 0 1 1 -8 0z"
        "M9.6 12a2.4 8.4 0 1 0 4.8 0a2.4 8.4 0 1 0 -4.8 0z"
        "M2 11.1h20v1.8H2z"
    ),
}

FONDO_CASILLA = "#14123a"

# Gema de 7x7 "píxeles": se usa si algo no tiene icono
GEMA = "M3 0h1v1h1v1h1v1h1v1H6v1H5v1H4v1H3V6H2V5H1V4H0V3h1V2h1V1h1z"


# ---------------------------------------------------------------------
# Utilidades comunes
# ---------------------------------------------------------------------

def guardar(nombre: str, contenido: str) -> None:
    (DESTINO / nombre).write_text(contenido, encoding="utf-8")
    print(f"  ok {nombre:<28} {len(contenido) / 1024:5.1f} KB")


def rellenar(plantilla: str, valores: dict) -> str:
    """Sustituye cada marca {{CLAVE}} (y la de la fuente) por su valor."""
    texto = (PLANTILLAS / plantilla).read_text(encoding="utf-8")
    for marca, valor in valores.items():
        texto = texto.replace(marca, str(valor))
    return texto


def cargar_icono(nombre: str) -> str | None:
    """
    Devuelve el dibujo (el atributo d del <path>) del icono, o None si no existe.
    Orden de búsqueda: iconos propios -> carpeta iconos/ -> descarga de internet.
    """
    if nombre in ICONOS_PROPIOS:
        return ICONOS_PROPIOS[nombre]

    archivo = ICONOS / f"{nombre}.svg"
    if not archivo.exists():
        try:
            with urllib.request.urlopen(URL_ICONO.format(nombre=nombre), timeout=10) as r:
                ICONOS.mkdir(exist_ok=True)
                archivo.write_bytes(r.read())
            print(f"  descargado icono '{nombre}'")
        except Exception:
            print(f"  ! no encuentro el icono '{nombre}': se dibuja una gema")
            print(f"    nombres disponibles en https://simpleicons.org")
            return None

    # Cada logo de Simple Icons es un único <path> en un cuadrado de 24x24.
    coincidencia = re.search(r'<path d="([^"]+)"', archivo.read_text(encoding="utf-8"))
    return coincidencia.group(1) if coincidencia else None


def color_que_contrasta(fondo_hex: str) -> str:
    """
    Blanco u oscuro según lo claro que sea el fondo.
    Luminancia relativa de WCAG: 0 = negro, 1 = blanco.
    """
    r, g, b = (int(fondo_hex.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))

    def lineal(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    luminancia = 0.2126 * lineal(r) + 0.7152 * lineal(g) + 0.0722 * lineal(b)
    return "#0b0a24" if luminancia > 0.35 else "#ffffff"


def ficha(x: float, y: float, lado: int, lado_logo: int, color: str,
          icono: str | None, id_recorte: str, retraso: float) -> str:
    """
    Ficha cuadrada del color de la marca con el logo centrado:
      - relieve pixel (luz arriba/izquierda, sombra abajo/derecha)
      - esquinas "mordidas", como en los sprites antiguos
      - un destello que la cruza de vez en cuando
    Se usa en el inventario y en los botones de redes.
    """
    tinta = color_que_contrasta(color)
    partes = [
        f'<clipPath id="{id_recorte}"><rect x="{x}" y="{y}" width="{lado}" height="{lado}"/></clipPath>',
        f'<rect x="{x}" y="{y}" width="{lado}" height="{lado}" fill="{color}"/>',
        f'<rect x="{x}" y="{y}" width="{lado}" height="4" fill="#ffffff" opacity="0.3"/>',
        f'<rect x="{x}" y="{y}" width="4" height="{lado}" fill="#ffffff" opacity="0.3"/>',
        f'<rect x="{x}" y="{y + lado - 4}" width="{lado}" height="4" fill="#000000" opacity="0.3"/>',
        f'<rect x="{x + lado - 4}" y="{y}" width="4" height="{lado}" fill="#000000" opacity="0.3"/>',
    ]

    dibujo = cargar_icono(icono) if icono else None
    if dibujo:
        desplazamiento = (lado - lado_logo) / 2
        escala = lado_logo / 24  # los iconos miden 24x24
        partes.append(
            f'<g transform="translate({x + desplazamiento} {y + desplazamiento}) scale({escala:.4f})">'
            f'<path d="{dibujo}" fill="{tinta}"/></g>'
        )
    else:
        escala_gema = lado_logo / 7
        inicio = (lado - lado_logo) / 2
        partes.append(
            f'<g class="gema" transform="translate({x + inicio} {y + inicio}) scale({escala_gema:.3f})">'
            f'<path d="{GEMA}" fill="{tinta}"/></g>'
        )

    # Destello: franja blanca inclinada; cada ficha arranca con un retraso
    # distinto para que no brillen todas a la vez.
    partes.append(
        f'<g clip-path="url(#{id_recorte})">'
        f'<path class="destello" style="animation-delay: {retraso:.1f}s" '
        f'd="M{x - 30} {y + lado} l20 -{lado} h12 l-20 {lado}z" fill="#ffffff" opacity="0.35"/>'
        f'</g>'
    )

    for cx, cy in [(x, y), (x + lado - 4, y), (x, y + lado - 4), (x + lado - 4, y + lado - 4)]:
        partes.append(f'<rect x="{cx}" y="{cy}" width="4" height="4" fill="{FONDO_CASILLA}"/>')

    return "".join(partes)


# ---------------------------------------------------------------------
# 1) Fuente
# ---------------------------------------------------------------------

def incrustar_fuente(fuente_base64: str) -> None:
    for svg in sorted(ORIGEN.glob("*.svg")):
        texto = svg.read_text(encoding="utf-8")
        if MARCA_FUENTE not in texto:
            print(f"  ! {svg.name}: no tiene la marca {MARCA_FUENTE}, se copia tal cual")
        guardar(svg.name, texto.replace(MARCA_FUENTE, fuente_base64))


# ---------------------------------------------------------------------
# 2) Títulos de sección
# ---------------------------------------------------------------------

# (archivo, nivel, texto). Sin tildes: esta fuente dibuja las mayúsculas
# acentuadas como minúsculas. Máximo unos 18 caracteres.
TITULOS = [
    ("habilidades", "1-1", "HABILIDADES"),
    ("estadisticas", "1-2", "ESTADISTICAS"),
    ("contacto", "1-3", "MULTIJUGADOR"),
]


def generar_titulos(fuente_base64: str) -> None:
    for archivo, nivel, texto in TITULOS:
        svg = rellenar("titulo.svg", {
            "{{TITULO}}": escape(texto),
            "{{NIVEL}}": escape(nivel),
            MARCA_FUENTE: fuente_base64,
        })
        guardar(f"titulo-{archivo}.svg", svg)


# ---------------------------------------------------------------------
# 3) Inventario de habilidades
# ---------------------------------------------------------------------

HABILIDADES = RAIZ / "habilidades.json"

COLUMNAS = 2
CASILLAS_MINIMAS = 4      # siempre al menos 2 filas
ANCHO_CASILLA = 372
ALTO_CASILLA = 104
SEPARACION = 24
MARGEN_X = 36             # (840 - 2*372 - 24) / 2
INICIO_Y = 98             # debajo del título "INVENTARIO"
TEXTO_X = 108             # inicio del texto, a la derecha de la ficha


# Rango que acompaña a cada nivel de dominio (1-5)
RANGOS = {1: "NOVATO", 2: "APRENDIZ", 3: "INTERMEDIO", 4: "AVANZADO", 5: "MAESTRO"}


def barra_de_nivel(nivel: int, color: str) -> str:
    """'NV', 5 bloques (se rellenan tantos como el nivel) y el rango."""
    nivel = max(1, min(5, nivel))
    partes = [f'<text class="pixel" x="{TEXTO_X}" y="90" font-size="8" fill="#8f8bd6">NV</text>']
    for i in range(5):
        relleno = color if i < nivel else "#2a2860"
        partes.append(f'<rect x="{TEXTO_X + 26 + i * 14}" y="82" width="11" height="8" fill="{relleno}"/>')
    # Rango en el color de la habilidad; si es muy oscuro, en lila para que se lea
    color_rango = color if color_que_contrasta(color) == "#0b0a24" else "#b9b6ff"
    partes.append(
        f'<text class="pixel" x="{TEXTO_X + 106}" y="90" font-size="8" fill="{color_rango}">{RANGOS[nivel]}</text>'
    )
    return "".join(partes)


def casilla_llena(habilidad: dict, x: int, y: int, indice: int) -> str:
    nombre = habilidad["nombre"]
    tipo = habilidad.get("tipo", "")
    color = habilidad.get("color", "#7df9ff")
    nivel = habilidad.get("nivel")  # opcional, 1-5

    # Fuente monoespaciada: cada letra mide lo mismo que el tamaño de letra.
    ancho_texto = ANCHO_CASILLA - TEXTO_X - 16
    tamano = min(18, ancho_texto // max(len(nombre), 1))

    barra = barra_de_nivel(int(nivel), color) if nivel else ""
    simbolo = ficha(16, 16, 72, 40, color, habilidad.get("icono"), f"ficha-{indice}", indice * 0.7)

    return f"""
    <g transform="translate({x} {y})">
      <rect x="1.5" y="1.5" width="{ANCHO_CASILLA - 3}" height="{ALTO_CASILLA - 3}" fill="{FONDO_CASILLA}" stroke="{color}" stroke-width="3"/>
      {simbolo}
      <text class="pixel" x="{TEXTO_X}" y="48" font-size="{tamano}" fill="#ffffff">{escape(nombre)}</text>
      <text class="pixel" x="{TEXTO_X}" y="68" font-size="9" fill="#8f8bd6">{escape(tipo)}</text>
      {barra}
    </g>"""


def casilla_vacia(x: int, y: int) -> str:
    return f"""
    <g transform="translate({x} {y})">
      <rect x="2" y="2" width="{ANCHO_CASILLA - 4}" height="{ALTO_CASILLA - 4}" fill="none" stroke="#3a3780" stroke-width="3" stroke-dasharray="6 4"/>
      <text class="pixel" x="{ANCHO_CASILLA // 2}" y="50" font-size="10" fill="#6f6bc8" text-anchor="middle">VACIO</text>
      <text class="pixel" x="{ANCHO_CASILLA // 2}" y="70" font-size="8" fill="#4d4a99" text-anchor="middle">+ NUEVA HABILIDAD</text>
    </g>"""


def generar_habilidades(fuente_base64: str) -> None:
    habilidades = json.loads(HABILIDADES.read_text(encoding="utf-8"))

    # Redondeo al múltiplo de COLUMNAS para completar la última fila
    total = max(CASILLAS_MINIMAS, math.ceil(len(habilidades) / COLUMNAS) * COLUMNAS)
    filas = total // COLUMNAS

    casillas = []
    for i in range(total):
        fila, columna = divmod(i, COLUMNAS)
        x = MARGEN_X + columna * (ANCHO_CASILLA + SEPARACION)
        y = INICIO_Y + fila * (ALTO_CASILLA + SEPARACION)
        if i < len(habilidades):
            casillas.append(casilla_llena(habilidades[i], x, y, i))
        else:
            casillas.append(casilla_vacia(x, y))

    alto = INICIO_Y + filas * ALTO_CASILLA + (filas - 1) * SEPARACION + 40

    guardar("habilidades.svg", rellenar("habilidades.svg", {
        "{{ALTO}}": alto,
        "{{ALTO_MARCO}}": alto - 8,
        "{{ALTO_CLIP}}": alto - 16,
        "{{CONTADOR}}": f"{len(habilidades)}/{total}",
        "{{LISTA}}": escape(", ".join(h["nombre"] for h in habilidades)),
        "{{CASILLAS}}": "".join(casillas),
        MARCA_FUENTE: fuente_base64,
    }))


# ---------------------------------------------------------------------
# 4) Panel de estadísticas ("PARTIDA GUARDADA")
# ---------------------------------------------------------------------

DATOS_ESTADISTICAS = RAIZ / "datos" / "estadisticas.json"

# Colores de la cuadrícula, de "nada" (0) a "mucho" (4): morado -> rosa -> amarillo
COLORES_NIVEL = ["#1c1a44", "#3b2a7a", "#7a2f8f", "#d63f9c", "#ffe066"]
MESES = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]

CELDA = 11                # lado de cada cuadrado
PASO = 14                 # celda + hueco
CUADRICULA_Y = 220
ALTO_ESTADISTICAS = 375

# Iconos pixel de 7x7 para las tarjetas
ICONO_BLOQUE = "M1 0h5v1h1v5H6v1H1V6H0V1h1z"
ICONO_LLAMA = "M3 0h1v1h1v1h1v2h1v3H6v1H1V7H0V4h1V3h1V1h1z"
ICONO_CORONA = "M0 1h1v2h1V1h1v2h1V1h1v2h1V1h1v6H0z"
ICONO_CARPETA = "M0 1h3v1h4v5H0z"


def tarjeta(x: int, etiqueta: str, valor: int, sufijo: str, color: str, icono: str) -> str:
    """Marcador: etiqueta pequeña arriba, número grande abajo."""
    ancho, alto = 180, 80
    numero = str(valor)
    if sufijo == "DIAS" and valor == 1:
        sufijo = "DIA"
    sufijo_svg = ""
    if sufijo:
        # Fuente monoespaciada: cada letra mide lo mismo que el tamaño de letra
        x_sufijo = 16 + len(numero) * 22 + 8
        sufijo_svg = f'<text class="pixel" x="{x_sufijo}" y="64" font-size="9" fill="{color}">{sufijo}</text>'
    return f"""
    <g transform="translate({x} 98)">
      <rect x="1.5" y="1.5" width="{ancho - 3}" height="{alto - 3}" fill="{FONDO_CASILLA}" stroke="{color}" stroke-width="3"/>
      <g transform="translate({ancho - 37} 14) scale(3)"><path d="{icono}" fill="{color}"/></g>
      <text class="pixel" x="16" y="30" font-size="8" fill="#8f8bd6">{etiqueta}</text>
      <text class="pixel" x="16" y="64" font-size="22" fill="{color}">{numero}</text>
      {sufijo_svg}
    </g>"""


def generar_estadisticas(fuente_base64: str) -> None:
    if not DATOS_ESTADISTICAS.exists():
        print("  - sin datos/estadisticas.json: ejecutar 'python estadisticas.py --demo'")
        return

    d = json.loads(DATOS_ESTADISTICAS.read_text(encoding="utf-8"))
    niveles = d["niveles"]
    inicio = date.fromisoformat(d["inicio"])

    tarjetas = "".join([
        tarjeta(36,  "CONTRIBUCIONES", d["total"],        "",     "#ffe066", ICONO_BLOQUE),
        tarjeta(232, "RACHA ACTUAL",   d["racha_actual"], "DIAS", "#ff4fa3", ICONO_LLAMA),
        tarjeta(428, "MEJOR RACHA",    d["mejor_racha"],  "DIAS", "#7df9ff", ICONO_CORONA),
        tarjeta(624, "REPOSITORIOS",   d["repos"],        "",     "#7cff6b", ICONO_CARPETA),
    ])

    # Igual que GitHub: una columna por semana y una fila por día (domingo arriba).
    # Si el primer día no es domingo, la primera columna empieza más abajo.
    # date.weekday() devuelve lunes=0 ... domingo=6; lo paso a domingo=0.
    desfase = (inicio.weekday() + 1) % 7
    columnas = (desfase + len(niveles) + 6) // 7
    ancho_cuadricula = columnas * PASO - (PASO - CELDA)
    x0 = MARGEN_X + (768 - ancho_cuadricula) // 2

    celdas, meses = [], []
    ultima_columna_con_mes = -10
    for i, nivel in enumerate(niveles):
        columna, fila = divmod(desfase + i, 7)
        x = x0 + columna * PASO
        y = CUADRICULA_Y + fila * PASO
        clase = ' class="hoy"' if i == len(niveles) - 1 else ""
        celdas.append(f'<rect{clase} x="{x}" y="{y}" width="{CELDA}" height="{CELDA}" fill="{COLORES_NIVEL[nivel]}"/>')

        dia = inicio + timedelta(days=i)
        if dia.day == 1 and columna - ultima_columna_con_mes >= 3 and columna < columnas - 1:
            meses.append(f'<text class="pixel" x="{x}" y="{CUADRICULA_Y - 10}" font-size="8" fill="#8f8bd6">{MESES[dia.month - 1]}</text>')
            ultima_columna_con_mes = columna

    y_pie = ALTO_ESTADISTICAS - 30
    leyenda = [f'<text class="pixel" x="699" y="{y_pie}" font-size="8" fill="#8f8bd6" text-anchor="end">MENOS</text>']
    for n, color in enumerate(COLORES_NIVEL):
        leyenda.append(f'<rect x="{705 + n * 14}" y="{y_pie - 9}" width="{CELDA}" height="{CELDA}" fill="{color}"/>')
    leyenda.append(f'<text class="pixel" x="780" y="{y_pie}" font-size="8" fill="#8f8bd6">MAS</text>')

    if d.get("demo"):
        pie = f'<text class="pixel" x="36" y="{y_pie}" font-size="8" fill="#ff4fa3">DATOS DE EJEMPLO · SE ACTUALIZA SOLO EN GITHUB</text>'
    else:
        fecha = date.fromisoformat(d["actualizado"]).strftime("%d/%m/%Y")
        pie = f'<text class="pixel" x="36" y="{y_pie}" font-size="8" fill="#8f8bd6">ACTUALIZADO {fecha}</text>'

    resumen = (f"{d['total']} contribuciones en el último año. "
               f"Racha actual: {d['racha_actual']} días. Mejor racha: {d['mejor_racha']} días.")

    guardar("estadisticas.svg", rellenar("estadisticas.svg", {
        "{{ALTO}}": ALTO_ESTADISTICAS,
        "{{ALTO_MARCO}}": ALTO_ESTADISTICAS - 8,
        "{{ALTO_CLIP}}": ALTO_ESTADISTICAS - 16,
        "{{COLUMNAS}}": columnas,
        "{{ANIO}}": "365 DIAS",
        "{{RESUMEN}}": escape(resumen),
        "{{TARJETAS}}": tarjetas,
        "{{MESES}}": "\n".join(meses),
        "{{CUADRICULA}}": "\n".join(celdas),
        "{{LEYENDA}}": "".join(leyenda),
        "{{PIE}}": pie,
        MARCA_FUENTE: fuente_base64,
    }))


# ---------------------------------------------------------------------
# 5) Redes sociales
# ---------------------------------------------------------------------

REDES = RAIZ / "redes.json"
MARCA_INICIO = "<!-- REDES:INICIO -->"
MARCA_FIN = "<!-- REDES:FIN -->"
ANCHO_BOTON_README = 240

# Catálogo: nombre visible, color, icono, URL y texto bajo el nombre.
# {u} se sustituye por el "usuario" de redes.json.
CATALOGO = {
    "web":         ("WEB",         "#7df9ff", "web",         "https://{u}",                        "{u}"),
    "email":       ("EMAIL",       "#ffe066", "email",       "mailto:{u}",                         "{u}"),
    "github":      ("GITHUB",      "#e6e6ff", "github",      "https://github.com/{u}",             "@{u}"),
    "linkedin":    ("LINKEDIN",    "#0a66c2", "linkedin",    "https://www.linkedin.com/in/{u}",    "in/{u}"),
    "twitter":     ("X / TWITTER", "#e6e6ff", "x",           "https://x.com/{u}",                  "@{u}"),
    "x":           ("X / TWITTER", "#e6e6ff", "x",           "https://x.com/{u}",                  "@{u}"),
    "twitch":      ("TWITCH",      "#9146ff", "twitch",      "https://www.twitch.tv/{u}",          "@{u}"),
    "instagram":   ("INSTAGRAM",   "#ff0069", "instagram",   "https://www.instagram.com/{u}",      "@{u}"),
    "youtube":     ("YOUTUBE",     "#ff0000", "youtube",     "https://www.youtube.com/@{u}",       "@{u}"),
    "tiktok":      ("TIKTOK",      "#fe2c55", "tiktok",      "https://www.tiktok.com/@{u}",        "@{u}"),
    "discord":     ("DISCORD",     "#5865f2", "discord",     "https://discord.gg/{u}",             "discord.gg/{u}"),
    "bluesky":     ("BLUESKY",     "#0285ff", "bluesky",     "https://bsky.app/profile/{u}",       "@{u}"),
    "mastodon":    ("MASTODON",    "#6364ff", "mastodon",    "{u}",                                "{u}"),
    "threads":     ("THREADS",     "#e6e6ff", "threads",     "https://www.threads.net/@{u}",       "@{u}"),
    "kick":        ("KICK",        "#53fc18", "kick",        "https://kick.com/{u}",               "@{u}"),
    "steam":       ("STEAM",       "#66c0f4", "steam",       "https://steamcommunity.com/id/{u}",  "{u}"),
    "anilist":     ("ANILIST",     "#02a9ff", "anilist",     "https://anilist.co/user/{u}",        "@{u}"),
    "myanimelist": ("MYANIMELIST", "#2e51a2", "myanimelist", "https://myanimelist.net/profile/{u}", "@{u}"),
    "letterboxd":  ("LETTERBOXD",  "#00e054", "letterboxd",  "https://letterboxd.com/{u}",         "@{u}"),
    "spotify":     ("SPOTIFY",     "#1db954", "spotify",     "https://open.spotify.com/user/{u}",  "{u}"),
    "reddit":      ("REDDIT",      "#ff4500", "reddit",      "https://www.reddit.com/user/{u}",    "u/{u}"),
    "kofi":        ("KO-FI",       "#ff5e5b", "kofi",        "https://ko-fi.com/{u}",              "@{u}"),
    "itchio":      ("ITCH.IO",     "#fa5c5c", "itchdotio",   "https://{u}.itch.io",                "{u}.itch.io"),
}

ANCHO_TEXTO_BOTON = 152   # hueco para texto entre la ficha y la flecha


def boton_red(entrada: dict, indice: int, fuente_base64: str) -> tuple[str, str, str] | None:
    """Genera el SVG de un botón. Devuelve (archivo, url, texto alternativo)."""
    red = entrada.get("red", "").lower()
    usuario = str(entrada.get("usuario", "")).strip()

    if red not in CATALOGO:
        print(f"  ! red '{red}' desconocida. Disponibles: {', '.join(CATALOGO)}")
        return None
    if not usuario or usuario.upper().startswith("TU_"):
        print(f"  - {red}: sin usuario, se omite")
        return None

    nombre, color, icono, plantilla_url, plantilla_mostrar = CATALOGO[red]
    nombre = entrada.get("nombre", nombre).upper()
    color = entrada.get("color", color)
    url = entrada.get("url") or plantilla_url.format(u=usuario)
    if red == "web" and usuario.startswith("http"):
        url = usuario
    mostrar = entrada.get("mostrar") or plantilla_mostrar.format(u=usuario)
    mostrar = re.sub(r"^https?://", "", mostrar)

    # Si no cabe ni a 6px, mejor un texto genérico que uno ilegible
    if len(mostrar) * 6 > ANCHO_TEXTO_BOTON:
        mostrar = "VER PERFIL"

    tamano_nombre = min(12, ANCHO_TEXTO_BOTON // max(len(nombre), 1))
    tamano_mostrar = min(8, ANCHO_TEXTO_BOTON // max(len(mostrar), 1))

    svg = rellenar("red.svg", {
        "{{NOMBRE}}": escape(nombre),
        "{{MOSTRAR}}": escape(mostrar),
        "{{COLOR}}": color,
        "{{TAMANO_NOMBRE}}": tamano_nombre,
        "{{TAMANO_MOSTRAR}}": tamano_mostrar,
        "{{FICHA}}": ficha(12, 11, 48, 26, color, icono, "ficha", indice * 0.5),
        MARCA_FUENTE: fuente_base64,
    })
    archivo = f"red-{indice + 1}-{red}.svg"
    guardar(archivo, svg)
    return archivo, url, f"{nombre.title()}: {mostrar}"


def generar_redes(fuente_base64: str) -> None:
    if not REDES.exists():
        return

    # Borro los botones anteriores por si se ha quitado alguna red
    for viejo in DESTINO.glob("red-*.svg"):
        viejo.unlink()

    entradas = json.loads(REDES.read_text(encoding="utf-8"))
    botones = [b for i, e in enumerate(entradas) if (b := boton_red(e, i, fuente_base64))]

    lineas = ['<p align="center">']
    for archivo, url, alt in botones:
        lineas.append(
            f'  <a href="{escape(url)}"><img src="assets/{archivo}" '
            f'width="{ANCHO_BOTON_README}" alt="{escape(alt)}"></a>'
        )
    lineas.append("</p>")
    bloque = "\n".join(lineas)

    texto = README.read_text(encoding="utf-8")
    if MARCA_INICIO not in texto or MARCA_FIN not in texto:
        print(f"  ! README.md sin las marcas {MARCA_INICIO} / {MARCA_FIN}: no se toca")
        return

    antes, resto = texto.split(MARCA_INICIO, 1)
    _, despues = resto.split(MARCA_FIN, 1)
    nuevo = f"{antes}{MARCA_INICIO}\n{bloque}\n{MARCA_FIN}{despues}"
    if nuevo != texto:
        README.write_text(nuevo, encoding="utf-8")
        print(f"  ok README.md (bloque de redes, {len(botones)} botones)")


# ---------------------------------------------------------------------

def main() -> None:
    fuente_base64 = base64.b64encode(FUENTE.read_bytes()).decode("ascii")
    DESTINO.mkdir(exist_ok=True)
    incrustar_fuente(fuente_base64)
    generar_titulos(fuente_base64)
    generar_habilidades(fuente_base64)
    generar_estadisticas(fuente_base64)
    generar_redes(fuente_base64)


if __name__ == "__main__":
    main()
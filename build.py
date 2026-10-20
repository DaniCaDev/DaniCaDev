"""
build.py · Genera los SVG del README de perfil.

1. Fuente: incrusta Press Start 2P (base64) en los SVG de src/. GitHub
   muestra los SVG como <img> y en ese modo no pueden cargar recursos
   externos, así que la fuente tiene que ir dentro.

2. Habilidades: genera el inventario a partir de habilidades.json y
   plantillas/habilidades.svg. Los logos salen de iconos/ (Simple Icons);
   los que faltan se descargan y se guardan en caché.

3. Estadísticas: genera el panel "PARTIDA GUARDADA" a partir de
   datos/estadisticas.json (lo crea estadisticas.py).

Uso:
    python build.py

assets/ es la salida: se regenera entera en cada ejecución.
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
HABILIDADES = RAIZ / "habilidades.json"
PLANTILLA_HABILIDADES = RAIZ / "plantillas" / "habilidades.svg"
ICONOS = RAIZ / "iconos"
MARCA_FUENTE = "/*FUENTE*/"

# Logos de Simple Icons (https://simpleicons.org). Si no están en iconos/,
# se descargan de aquí y se guardan para la próxima vez.
URL_ICONO = "https://cdn.jsdelivr.net/npm/simple-icons@latest/icons/{nombre}.svg"

# Iconos dibujados a mano para cosas que no tienen logo de marca.
# Mismo formato que Simple Icons: un <path> en un cuadrado de 24x24.
ICONOS_PROPIOS = {
    # Cilindro de base de datos: tapa elíptica + dos "rodajas"
    "basedatos": (
        "M4 5a8 3 0 1 0 16 0a8 3 0 1 0 -16 0z"
        "M4 7.5v4c0 1.66 3.58 3 8 3s8-1.34 8-3v-4c0 1.66-3.58 3-8 3s-8-1.34-8-3z"
        "M4 14v4.5c0 1.66 3.58 3 8 3s8-1.34 8-3V14c0 1.66-3.58 3-8 3s-8-1.34-8-3z"
    ),
}

# Medidas del inventario (en píxeles del SVG)
COLUMNAS = 2
CASILLAS_MINIMAS = 4      # siempre se dibujan al menos 2 filas
ANCHO_CASILLA = 372
ALTO_CASILLA = 104
SEPARACION = 24
MARGEN_X = 36             # (840 - 2*372 - 24) / 2
INICIO_Y = 98             # debajo del título "INVENTARIO"

# La ficha del icono, dentro de cada casilla
FICHA_X, FICHA_Y, FICHA_LADO = 16, 16, 72
LADO_LOGO = 40
TEXTO_X = 108             # donde empieza el texto, a la derecha de la ficha
FONDO_CASILLA = "#14123a"

# Gema de 7x7 "píxeles": se usa si una habilidad no tiene icono
GEMA = "M3 0h1v1h1v1h1v1h1v1H6v1H5v1H4v1H3V6H2V5H1V4H0V3h1V2h1V1h1z"


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
# 2) Inventario de habilidades
# ---------------------------------------------------------------------

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
            print(f"    busca el nombre exacto en https://simpleicons.org")
            return None

    # Cada logo de Simple Icons es un único <path> en un cuadrado de 24x24.
    coincidencia = re.search(r'<path d="([^"]+)"', archivo.read_text(encoding="utf-8"))
    return coincidencia.group(1) if coincidencia else None


def color_que_contrasta(fondo_hex: str) -> str:
    """
    Elige blanco u oscuro para que el logo se vea sobre su color de fondo.
    Usa la "luminancia relativa" de la norma WCAG: 0 = negro, 1 = blanco.
    """
    r, g, b = (int(fondo_hex.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))

    def lineal(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    luminancia = 0.2126 * lineal(r) + 0.7152 * lineal(g) + 0.0722 * lineal(b)
    return "#0b0a24" if luminancia > 0.35 else "#ffffff"


def ficha_del_simbolo(habilidad: dict, color: str, indice: int) -> str:
    """
    Ficha cuadrada del color de la tecnología, con:
      - relieve pixel: borde claro arriba/izquierda y oscuro abajo/derecha
      - esquinas "mordidas", como en los sprites antiguos
      - el logo centrado
      - un destello que la cruza de vez en cuando (animación CSS)
    """
    x, y, lado = FICHA_X, FICHA_Y, FICHA_LADO
    tinta = color_que_contrasta(color)
    id_recorte = f"ficha-{indice}"

    partes = [
        # Recorte para que el destello no se salga de la ficha
        f'<clipPath id="{id_recorte}"><rect x="{x}" y="{y}" width="{lado}" height="{lado}"/></clipPath>',
        # Fondo
        f'<rect x="{x}" y="{y}" width="{lado}" height="{lado}" fill="{color}"/>',
        # Relieve: luz arriba e izquierda, sombra abajo y derecha
        f'<rect x="{x}" y="{y}" width="{lado}" height="4" fill="#ffffff" opacity="0.3"/>',
        f'<rect x="{x}" y="{y}" width="4" height="{lado}" fill="#ffffff" opacity="0.3"/>',
        f'<rect x="{x}" y="{y + lado - 4}" width="{lado}" height="4" fill="#000000" opacity="0.3"/>',
        f'<rect x="{x + lado - 4}" y="{y}" width="4" height="{lado}" fill="#000000" opacity="0.3"/>',
    ]

    # Logo (o gema si no hay), centrado en la ficha
    dibujo = cargar_icono(habilidad["icono"]) if habilidad.get("icono") else None
    if dibujo:
        desplazamiento = (lado - LADO_LOGO) / 2
        escala = LADO_LOGO / 24  # los iconos miden 24x24
        partes.append(
            f'<g transform="translate({x + desplazamiento} {y + desplazamiento}) scale({escala:.4f})">'
            f'<path d="{dibujo}" fill="{tinta}"/></g>'
        )
    else:
        partes.append(
            f'<g class="gema" transform="translate({x + lado / 2 - 14} {y + lado / 2 - 14}) scale(4)">'
            f'<path d="{GEMA}" fill="{tinta}"/></g>'
        )

    # Destello: una franja blanca inclinada que cruza la ficha.
    # Cada casilla empieza con un retraso distinto para que no brillen a la vez.
    partes.append(
        f'<g clip-path="url(#{id_recorte})">'
        f'<path class="destello" style="animation-delay: {indice * 0.7:.1f}s" '
        f'd="M{x - 30} {y + lado} l20 -{lado} h12 l-20 {lado}z" fill="#ffffff" opacity="0.35"/>'
        f'</g>'
    )

    # Esquinas mordidas (se pintan del color de la casilla)
    for cx, cy in [(x, y), (x + lado - 4, y), (x, y + lado - 4), (x + lado - 4, y + lado - 4)]:
        partes.append(f'<rect x="{cx}" y="{cy}" width="4" height="4" fill="{FONDO_CASILLA}"/>')

    return "".join(partes)


def barra_de_nivel(nivel: int, color: str) -> str:
    """'NV' y 5 bloquecitos debajo del nombre; se rellenan tantos como el nivel."""
    partes = [f'<text class="pixel" x="{TEXTO_X}" y="90" font-size="8" fill="#8f8bd6">NV</text>']
    for i in range(5):
        relleno = color if i < nivel else "#2a2860"
        partes.append(f'<rect x="{TEXTO_X + 26 + i * 14}" y="82" width="11" height="8" fill="{relleno}"/>')
    return "".join(partes)


def casilla_llena(habilidad: dict, x: int, y: int, indice: int) -> str:
    nombre = habilidad["nombre"]
    tipo = habilidad.get("tipo", "")
    color = habilidad.get("color", "#7df9ff")
    nivel = habilidad.get("nivel")  # opcional: un número del 1 al 5

    # En esta fuente cada letra mide lo mismo que el tamaño de letra.
    # Hay unos 248px de hueco para el texto: los nombres largos se encogen.
    ancho_texto = ANCHO_CASILLA - TEXTO_X - 16
    tamano = min(18, ancho_texto // max(len(nombre), 1))

    barra = barra_de_nivel(int(nivel), color) if nivel else ""

    return f"""
    <g transform="translate({x} {y})">
      <rect x="1.5" y="1.5" width="{ANCHO_CASILLA - 3}" height="{ALTO_CASILLA - 3}" fill="{FONDO_CASILLA}" stroke="{color}" stroke-width="3"/>
      {ficha_del_simbolo(habilidad, color, indice)}
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

    svg = PLANTILLA_HABILIDADES.read_text(encoding="utf-8")
    reemplazos = {
        "{{ALTO}}": str(alto),
        "{{ALTO_MARCO}}": str(alto - 8),
        "{{ALTO_CLIP}}": str(alto - 16),
        "{{CONTADOR}}": f"{len(habilidades)}/{total}",
        "{{LISTA}}": escape(", ".join(h["nombre"] for h in habilidades)),
        "{{CASILLAS}}": "".join(casillas),
        MARCA_FUENTE: fuente_base64,
    }
    for marca, valor in reemplazos.items():
        svg = svg.replace(marca, valor)

    guardar("habilidades.svg", svg)


# ---------------------------------------------------------------------
# 3) Panel de estadísticas ("PARTIDA GUARDADA")
# ---------------------------------------------------------------------

DATOS_ESTADISTICAS = RAIZ / "datos" / "estadisticas.json"
PLANTILLA_ESTADISTICAS = RAIZ / "plantillas" / "estadisticas.svg"

# Colores de la cuadrícula, de "nada" (0) a "mucho" (4): morado -> rosa -> amarillo
COLORES_NIVEL = ["#1c1a44", "#3b2a7a", "#7a2f8f", "#d63f9c", "#ffe066"]
MESES = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]

CELDA = 11                # lado de cada cuadradito
PASO = 14                 # celda + hueco
CUADRICULA_Y = 220        # donde empieza la cuadrícula
ALTO_ESTADISTICAS = 375

# Iconos pixel de 7x7 para las tarjetas
ICONO_BLOQUE = "M1 0h5v1h1v5H6v1H1V6H0V1h1z"
ICONO_LLAMA = "M3 0h1v1h1v1h1v2h1v3H6v1H1V7H0V4h1V3h1V1h1z"
ICONO_CORONA = "M0 1h1v2h1V1h1v2h1V1h1v2h1V1h1v6H0z"
ICONO_CARPETA = "M0 1h3v1h4v5H0z"


def tarjeta(x: int, etiqueta: str, valor: int, sufijo: str, color: str, icono: str) -> str:
    """Un marcador: etiqueta pequeña arriba, número grande abajo."""
    ancho, alto = 180, 80
    numero = str(valor)
    if sufijo == "DIAS" and valor == 1:
        sufijo = "DIA"  # singular
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
        print("  - sin datos/estadisticas.json: ejecuta 'python estadisticas.py --demo'")
        return

    d = json.loads(DATOS_ESTADISTICAS.read_text(encoding="utf-8"))
    niveles = d["niveles"]
    inicio = date.fromisoformat(d["inicio"])

    # --- Tarjetas -------------------------------------------------------
    tarjetas = "".join([
        tarjeta(36,  "CONTRIBUCIONES", d["total"],        "",     "#ffe066", ICONO_BLOQUE),
        tarjeta(232, "RACHA ACTUAL",   d["racha_actual"], "DIAS", "#ff4fa3", ICONO_LLAMA),
        tarjeta(428, "MEJOR RACHA",    d["mejor_racha"],  "DIAS", "#7df9ff", ICONO_CORONA),
        tarjeta(624, "REPOSITORIOS",   d["repos"],        "",     "#7cff6b", ICONO_CARPETA),
    ])

    # --- Cuadrícula -----------------------------------------------------
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
        posicion = desfase + i
        columna, fila = divmod(posicion, 7)
        x = x0 + columna * PASO
        y = CUADRICULA_Y + fila * PASO
        es_hoy = i == len(niveles) - 1
        clase = ' class="hoy"' if es_hoy else ""
        celdas.append(f'<rect{clase} x="{x}" y="{y}" width="{CELDA}" height="{CELDA}" fill="{COLORES_NIVEL[nivel]}"/>')

        # Nombre del mes encima de la columna donde empieza cada mes
        dia = inicio + timedelta(days=i)
        if dia.day == 1 and columna - ultima_columna_con_mes >= 3 and columna < columnas - 1:
            meses.append(f'<text class="pixel" x="{x}" y="{CUADRICULA_Y - 10}" font-size="8" fill="#8f8bd6">{MESES[dia.month - 1]}</text>')
            ultima_columna_con_mes = columna

    # --- Leyenda y pie --------------------------------------------------
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

    svg = PLANTILLA_ESTADISTICAS.read_text(encoding="utf-8")
    reemplazos = {
        "{{ALTO}}": str(ALTO_ESTADISTICAS),
        "{{ALTO_MARCO}}": str(ALTO_ESTADISTICAS - 8),
        "{{ALTO_CLIP}}": str(ALTO_ESTADISTICAS - 16),
        "{{COLUMNAS}}": str(columnas),
        "{{ANIO}}": "365 DIAS",
        "{{RESUMEN}}": escape(resumen),
        "{{TARJETAS}}": tarjetas,
        "{{MESES}}": "\n".join(meses),
        "{{CUADRICULA}}": "\n".join(celdas),
        "{{LEYENDA}}": "".join(leyenda),
        "{{PIE}}": pie,
        MARCA_FUENTE: fuente_base64,
    }
    for marca, valor in reemplazos.items():
        svg = svg.replace(marca, valor)

    guardar("estadisticas.svg", svg)


# ---------------------------------------------------------------------

def guardar(nombre: str, contenido: str) -> None:
    (DESTINO / nombre).write_text(contenido, encoding="utf-8")
    print(f"  ok {nombre:<24} {len(contenido) / 1024:5.1f} KB")


def main() -> None:
    fuente_base64 = base64.b64encode(FUENTE.read_bytes()).decode("ascii")
    DESTINO.mkdir(exist_ok=True)
    incrustar_fuente(fuente_base64)
    generar_habilidades(fuente_base64)
    generar_estadisticas(fuente_base64)


if __name__ == "__main__":
    main()

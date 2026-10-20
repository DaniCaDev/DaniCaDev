"""
estadisticas.py · Descarga las contribuciones de GitHub y calcula las rachas.

Guarda el resultado en datos/estadisticas.json, que luego usa build.py
para dibujar el panel (assets/estadisticas.svg).

Está separado de build.py a propósito: este necesita red y token, y
build.py no, así que el diseño se puede regenerar sin tocar la API.

Uso:
    GITHUB_TOKEN=xxxx python estadisticas.py USUARIO   # datos reales
    python estadisticas.py --demo                      # datos de prueba

En el repo lo ejecuta a diario .github/workflows/estadisticas.yml.
"""

import json
import os
import random
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).parent
SALIDA = RAIZ / "datos" / "estadisticas.json"

# Una sola consulta GraphQL con solo los campos que necesito.
CONSULTA = """
query($login: String!) {
  user(login: $login) {
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100) {
      totalCount
      nodes { stargazerCount }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays { date contributionCount contributionLevel }
        }
      }
    }
  }
}
"""

# GitHub devuelve el nivel de cada día como texto; lo paso a 0-4.
NIVELES = {
    "NONE": 0,
    "FIRST_QUARTILE": 1,
    "SECOND_QUARTILE": 2,
    "THIRD_QUARTILE": 3,
    "FOURTH_QUARTILE": 4,
}


def pedir_a_github(usuario: str, token: str) -> dict:
    cuerpo = json.dumps({"query": CONSULTA, "variables": {"login": usuario}}).encode()
    peticion = urllib.request.Request(
        "https://api.github.com/graphql",
        data=cuerpo,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "readme-retro",
        },
    )
    try:
        with urllib.request.urlopen(peticion, timeout=30) as respuesta:
            datos = json.load(respuesta)
    except urllib.error.HTTPError as error:
        if error.code == 401:
            raise SystemExit("Token no válido: revisa GITHUB_TOKEN")
        raise SystemExit(f"GitHub respondió con el error {error.code}")

    if datos.get("errors"):
        raise SystemExit(f"GitHub devolvió un error: {datos['errors'][0]['message']}")
    if not datos["data"]["user"]:
        raise SystemExit(f"No existe el usuario '{usuario}'")
    return datos["data"]["user"]


def calcular_rachas(cuentas: list[int]) -> tuple[int, int]:
    """
    Racha = días seguidos con al menos una contribución.
    - Mejor racha: el tramo más largo de días con cuenta > 0.
    - Racha actual: hacia atrás desde hoy. Si hoy todavía no hay
      contribuciones, se empieza desde ayer para no romperla a las 00:01.
    """
    mejor = seguidos = 0
    for cuenta in cuentas:
        seguidos = seguidos + 1 if cuenta > 0 else 0
        mejor = max(mejor, seguidos)

    i = len(cuentas) - 1
    if i >= 0 and cuentas[i] == 0:
        i -= 1
    actual = 0
    while i >= 0 and cuentas[i] > 0:
        actual += 1
        i -= 1

    return actual, mejor


def datos_reales(usuario: str, token: str) -> dict:
    u = pedir_a_github(usuario, token)
    calendario = u["contributionsCollection"]["contributionCalendar"]

    # Las semanas vienen anidadas: las aplano en una lista de días.
    dias = [d for semana in calendario["weeks"] for d in semana["contributionDays"]]
    actual, mejor = calcular_rachas([d["contributionCount"] for d in dias])

    return {
        "usuario": usuario,
        "actualizado": date.today().isoformat(),
        "demo": False,
        "total": calendario["totalContributions"],
        "commits": u["contributionsCollection"]["totalCommitContributions"],
        "prs": u["contributionsCollection"]["totalPullRequestContributions"],
        "repos": u["repositories"]["totalCount"],
        "estrellas": sum(r["stargazerCount"] for r in u["repositories"]["nodes"]),
        "racha_actual": actual,
        "mejor_racha": mejor,
        "inicio": dias[0]["date"],
        "niveles": [NIVELES[d["contributionLevel"]] for d in dias],
    }


def datos_demo() -> dict:
    """Año aleatorio (semilla fija) para probar el diseño sin conexión."""
    azar = random.Random(7)
    hoy = date.today()
    inicio = hoy - timedelta(days=364)
    cuentas = [azar.choice([0, 0, 0, 1, 2, 3, 5, 8]) for _ in range(365)]
    niveles = [0 if c == 0 else 1 if c < 2 else 2 if c < 4 else 3 if c < 7 else 4 for c in cuentas]
    actual, mejor = calcular_rachas(cuentas)
    return {
        "usuario": "demo",
        "actualizado": hoy.isoformat(),
        "demo": True,
        "total": sum(cuentas),
        "commits": 0,
        "prs": 0,
        "repos": 0,
        "estrellas": 0,
        "racha_actual": actual,
        "mejor_racha": mejor,
        "inicio": inicio.isoformat(),
        "niveles": niveles,
    }


def main() -> None:
    if "--demo" in sys.argv:
        datos = datos_demo()
    else:
        if len(sys.argv) < 2:
            raise SystemExit("Uso: python estadisticas.py TU_USUARIO   (o --demo)")
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise SystemExit("Falta la variable de entorno GITHUB_TOKEN")
        datos = datos_reales(sys.argv[1], token)

    SALIDA.parent.mkdir(exist_ok=True)
    SALIDA.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  ok {SALIDA.name}: {datos['total']} contribuciones, "
          f"racha {datos['racha_actual']} (mejor {datos['mejor_racha']})"
          + ("  [DEMO]" if datos["demo"] else ""))


if __name__ == "__main__":
    main()

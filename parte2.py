"""Laboratorio 7, parte 2. Solo requiere la biblioteca estándar de Python."""

import argparse
import json
import multiprocessing as mp
import os
from pathlib import Path
import statistics
import time
from queue import Empty

TAMANOS = (1, 10, 100, 1000, 10000, 100000, 1000000)


def algoritmo_a(n):
    counter = 0
    i = n // 2  # División entera, como en el código original en C.
    while i <= n:
        j = 1
        while j + n // 2 <= n:
            k = 1
            while k <= n:
                counter += 1
                k = k * 2
            j += 1
        i += 1
    return counter


def algoritmo_b(n, salida):
    if n <= 1:
        return
    i = 1
    while i <= n:
        j = 1
        while j <= n:
            print("Sequence", file=salida)
            break
        i += 1


def algoritmo_c(n, salida):
    i = 1
    while i <= n // 3:
        j = 1
        while j <= n:
            print("Sequence", file=salida)
            j += 4
        i += 1


def conteo(nombre, n):
    """Conteo exacto por sentencias/condiciones; ver el modelo en README.md."""
    if nombre == "a":
        i = n - n // 2 + 1
        j = n - n // 2
        k = n.bit_length()
        return 3 + 4 * i + 4 * i * j + 3 * i * j * k, i * j * k
    if nombre == "b":
        return (2, 0) if n <= 1 else (3 + 6 * n, n)
    if nombre == "c":
        i = n // 3
        j = (n + 3) // 4
        return 2 + 4 * i + 3 * i * j, i * j
    raise ValueError("Algoritmo desconocido")


def trabajador(nombre, n, repeticiones, cola):
    # Abrir el destino y crear el proceso quedan fuera de la medición.
    with open(os.devnull, "w", encoding="utf-8") as salida:
        cola.put(("listo", None))
        for _ in range(repeticiones):
            inicio = time.perf_counter_ns()
            if nombre == "a":
                algoritmo_a(n)
            elif nombre == "b":
                algoritmo_b(n, salida)
            else:
                algoritmo_c(n, salida)
            salida.flush()
            cola.put(("muestra", (time.perf_counter_ns() - inicio) / 1e9))


def medir(nombre, n, repeticiones, limite):
    contexto = mp.get_context("spawn")
    cola = contexto.Queue()
    proceso = contexto.Process(target=trabajador, args=(nombre, n, repeticiones, cola))
    muestras = []
    estado = "completo"
    proceso.start()
    try:
        # La importación inicial no consume el límite de ejecución del algoritmo.
        tipo, _ = cola.get(timeout=30)
        if tipo != "listo":
            raise RuntimeError("El proceso no pudo inicializarse")
        for _ in range(repeticiones):
            try:
                _, segundos = cola.get(timeout=limite)
                muestras.append(segundos)
            except Empty:
                estado = "limite de tiempo"
                break
    finally:
        if proceso.is_alive():
            proceso.join(timeout=0.1)
        if proceso.is_alive():
            proceso.terminate()
        proceso.join()
        cola.close()
    return {
        "algoritmo": nombre, "n": n, "estado": estado,
        "tiempo_mediano_s": statistics.median(muestras) if estado == "completo" else None,
        "muestras_s": muestras, "limite_s": limite,
        "operaciones": conteo(nombre, n)[0],
        "operaciones_basicas": conteo(nombre, n)[1],
    }


def grafica(filas, destino):
    """SVG con dos paneles logarítmicos; no mezcla segundos con operaciones."""
    import math
    colores = {"a": "#2563eb", "b": "#b45309", "c": "#15803d"}
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="510" viewBox="0 0 1100 510">',
           '<rect width="1100" height="510" fill="white"/>',
           '<g font-family="Arial,sans-serif" font-size="13" fill="#172033">',
           '<text x="55" y="30" font-size="21">Parte 2: tiempos medidos y conteos exactos</text>']
    for panel, campo, titulo in ((0, "tiempo_mediano_s", "Tiempo mediano (segundos)"),
                                  (1, "operaciones", "Operaciones (modelo de sentencias)")):
        x0, y0, ancho, alto = 85 + 545 * panel, 85, 410, 310
        valores = [r[campo] for r in filas if r[campo] is not None and r[campo] > 0]
        lo = math.floor(math.log10(min(valores))) if valores else -6
        hi = math.ceil(math.log10(max(valores))) if valores else 0
        hi = max(hi, lo + 1)
        def xy(n, v):
            return x0 + math.log10(n) / 6 * ancho, y0 + alto - (math.log10(v) - lo) / (hi - lo) * alto
        svg.append(f'<text x="{x0}" y="65" font-size="16">{titulo}</text>')
        for ex in range(lo, hi + 1):
            y = xy(1, 10 ** ex)[1]
            svg.append(f'<path d="M{x0} {y}h{ancho}" stroke="#e2e8f0"/><text x="{x0-52}" y="{y+4}">10^{ex}</text>')
        for ex in range(7):
            x = x0 + ex / 6 * ancho
            svg.append(f'<text x="{x-12}" y="420">10^{ex}</text>')
        for nombre, color in colores.items():
            puntos = []
            for r in filas:
                if r["algoritmo"] != nombre or r[campo] is None or r[campo] <= 0:
                    continue
                x, y = xy(r["n"], r[campo])
                puntos.append(f"{x},{y}")
                svg.append(f'<circle cx="{x}" cy="{y}" r="4" fill="{color}"/>')
            svg.append(f'<polyline points="{" ".join(puntos)}" fill="none" stroke="{color}" stroke-width="2"/>')
        svg.append(f'<text x="{x0+150}" y="447">Tamaño de entrada n</text>')
    for idx, (nombre, color) in enumerate(colores.items()):
        svg.append(f'<text x="{85+idx*150}" y="480" fill="{color}">Algoritmo {nombre}</text>')
    svg.append('<text x="550" y="480">Sin punto de tiempo: ejecución no completada.</text></g></svg>')
    destino.write_text("\n".join(svg), encoding="utf-8")


def guardar(filas, carpeta, repeticiones):
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "resultados.json").write_text(json.dumps(filas, indent=2), encoding="utf-8")
    lineas = ["# Resultados de la parte 2", "",
              f"Mediana de {repeticiones} ejecuciones completas. Salida de print dirigida a os.devnull.",
              "Un límite alcanzado NO representa un tiempo total medido. El conteo es analítico exacto.", "",
              "| Algoritmo | n | Tiempo mediano (s) | Operaciones | Operación básica | Estado |",
              "|---|---:|---:|---:|---:|---|"]
    for r in filas:
        t = r["tiempo_mediano_s"]
        tiempo = f"{t:.9f}" if t is not None else f"No completado (límite {r['limite_s']:g} s)"
        lineas.append(f"| {r['algoritmo']} | {r['n']} | {tiempo} | {r['operaciones']} | {r['operaciones_basicas']} | {r['estado']} |")
    lineas.extend(["", "![Comparación de tiempo y operaciones](grafica.svg)", "",
                   "Los paneles usan escalas logarítmicas. Segundos y operaciones tienen unidades diferentes.",
                   "Los tiempos pequeños son sensibles al ruido del sistema; no prueban por sí solos la complejidad."])
    (carpeta / "resultados.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    grafica(filas, carpeta / "grafica.svg")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limite", type=float, default=2, help="Segundos máximos por repetición (predeterminado: 2)")
    parser.add_argument("--repeticiones", type=int, default=3)
    parser.add_argument("--salida", type=Path, default=Path("resultados"))
    args = parser.parse_args()
    if args.limite <= 0 or args.repeticiones <= 0:
        parser.error("El límite y las repeticiones deben ser positivos")
    filas = []
    for nombre in "abc":
        for n in TAMANOS:
            print(f"Algoritmo {nombre}, n={n}...", flush=True)
            fila = medir(nombre, n, args.repeticiones, args.limite)
            filas.append(fila)
            print(f"  {fila['estado']}; tiempo={fila['tiempo_mediano_s']}; operaciones={fila['operaciones']}")
            guardar(filas, args.salida, args.repeticiones)
    print(f"Resultados guardados en {args.salida.resolve()}")


if __name__ == "__main__":
    main()

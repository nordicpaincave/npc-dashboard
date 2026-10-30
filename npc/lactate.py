"""Cálculo de limiares de lactato a partir de um teste incremental.

Métodos (os mesmos usados na análise do R1 de bike do Bruno, 28/10/2026):
  LT1  Basal + 0,5 mmol      — Faude, Kindermann & Meyer 2009 (revisão de conceitos)
  LT1  Basal + 1,0 mmol      — idem
  LT1  Log-log (Beaver 1985) — quebra de duas retas em log(carga) × log(lactato)
  LT2  Dmax Modificado       — Bishop, Jenkins & Mackinnon 1998 (validado vs MLSS: Jamnick 2018)
  LT2  Dmax clássico         — Cheng et al. 1992
  LT2  OBLA 4,0 mmol         — Sjödin & Jacobs 1981 (interpolação linear entre degraus)

Curva ajustada: polinômio de 3º grau lactato × carga, só com os degraus (sem o pré-teste).
Basal = MENOR lactato medido (coleta pré-teste ou degrau), regra NPC de 30/10/2026: na corrida
o 1º degrau leve costuma ficar abaixo do repouso (remoção > produção), e o LT1 oficial passou a ser
basal + 0,5 mmol lido na curva ajustada — o critério mais conservador, igual para bike e corrida.
Carga = potência (W) na bike, velocidade (km/h) na corrida.
Sem numpy: tudo em Python puro para rodar no GitHub Actions sem dependências.
"""
import math


def _polyfit3(xs, ys):
    """Mínimos quadrados de grau 3 (equações normais, eliminação de Gauss)."""
    n = 4
    A = [[sum(x ** (i + j) for x in xs) for j in range(n)] for i in range(n)]
    b = [sum(y * x ** i for x, y in zip(xs, ys)) for i in range(n)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(A[r][c]))
        A[c], A[p] = A[p], A[c]; b[c], b[p] = b[p], b[c]
        for r in range(c + 1, n):
            f = A[r][c] / A[c][c]
            for k in range(c, n):
                A[r][k] -= f * A[c][k]
            b[r] -= f * b[c]
    coef = [0.0] * n
    for r in range(n - 1, -1, -1):
        coef[r] = (b[r] - sum(A[r][k] * coef[k] for k in range(r + 1, n))) / A[r][r]
    return coef  # c0 + c1 x + c2 x² + c3 x³


def _ev(c, x):
    return c[0] + c[1] * x + c[2] * x * x + c[3] * x ** 3


def _solve_on_curve(c, target, lo, hi, step=0.05):
    """Primeira carga em [lo,hi] onde a curva ajustada atinge `target`."""
    x, prev = lo, _ev(c, lo)
    while x <= hi:
        x2 = x + step
        v = _ev(c, x2)
        if (prev - target) * (v - target) <= 0:
            return x + step * (target - prev) / (v - prev) if v != prev else x
        x, prev = x2, v
    return None


def _dmax(c, x0, y0, x1, y1, step=0.05):
    """Ponto da curva com maior distância perpendicular à reta (x0,y0)-(x1,y1)."""
    dx, dy = x1 - x0, y1 - y0
    norm = math.hypot(dx, dy)
    best, bx = -1, None
    x = x0
    while x <= x1:
        d = abs(dy * x - dx * _ev(c, x) + x1 * y0 - y1 * x0) / norm
        if d > best:
            best, bx = d, x
        x += step
    return bx


def _loglog(xs, ys):
    """Beaver 1985: quebra que minimiza a soma dos resíduos de duas retas em log-log."""
    lx = [math.log(x) for x in xs]; ly = [math.log(y) for y in ys]

    def fit(a, b):
        n = len(a); ma = sum(a) / n; mb = sum(b) / n
        sxx = sum((u - ma) ** 2 for u in a)
        s = sum((u - ma) * (v - mb) for u, v in zip(a, b)) / sxx if sxx else 0
        i = mb - s * ma
        return s, i, sum((v - (i + s * u)) ** 2 for u, v in zip(a, b))

    best = None
    for k in range(2, len(xs) - 1):          # pelo menos 2 pontos em cada reta
        s1, i1, r1 = fit(lx[:k], ly[:k]); s2, i2, r2 = fit(lx[k - 1:], ly[k - 1:])
        if s1 == s2:
            continue
        xb = (i2 - i1) / (s1 - s2)           # interseção das duas retas
        if not (lx[0] <= xb <= lx[-1]):
            continue
        if best is None or r1 + r2 < best[0]:
            best = (r1 + r2, math.exp(xb))
    return best[1] if best else None


def _obla(xs, ys, target=4.0):
    for (xa, ya), (xb, yb) in zip(zip(xs, ys), zip(xs[1:], ys[1:])):
        if ya <= target <= yb and yb != ya:
            return xa + (xb - xa) * (target - ya) / (yb - ya)
    return None


def analyze(baseline, loads, lactates):
    """loads/lactates = degraus válidos em ordem crescente. Retorna métodos e curva."""
    xs, ys = list(map(float, loads)), list(map(float, lactates))
    if len(xs) < 4:
        return None
    c = _polyfit3(xs, ys)
    lo, hi = xs[0], xs[-1]
    # basal = menor lactato medido (pré-teste ou degrau) — regra NPC 30/10/2026
    baseline = min(ys) if baseline is None else min(baseline, min(ys))
    out = {"lt1": [], "lt2": [], "fit": [round(v, 6) for v in c]}
    if baseline is not None:
        for add in (0.5, 1.0):
            v = _solve_on_curve(c, baseline + add, lo, hi)
            out["lt1"].append({"method": f"Basal + {str(add).replace('.', ',')} mmol",
                               "ref": "Faude 2009", "value": v,
                               "detail": f"carga onde a curva atinge {str(round(baseline + add, 1)).replace('.', ',')} mmol"})
    out["lt1"].append({"method": "Log-log", "ref": "Beaver 1985", "value": _loglog(xs, ys),
                       "detail": "quebra de duas retas em log(carga) × log(lactato)"})
    # Dmax Modificado: reta do último degrau ANTES de um aumento > 0,4 mmol até o último degrau
    start = None
    for i in range(1, len(ys)):
        if ys[i] - ys[i - 1] > 0.4:
            start = i - 1
            break
    if start is not None:
        # âncoras nos PONTOS medidos (Bishop 1998), curva ajustada para a distância
        out["lt2"].append({"method": "Dmax Modificado", "ref": "Bishop 1998 · Jamnick 2018", "value": _dmax(c, xs[start], ys[start], hi, ys[-1]),
                           "detail": "ponto da curva mais distante da reta que vai do degrau anterior ao 1º aumento > 0,4 mmol até o último degrau"})
    out["lt2"].append({"method": "Dmax clássico", "ref": "Cheng 1992", "value": _dmax(c, lo, _ev(c, lo), hi, _ev(c, hi)),
                       "detail": "ponto da curva mais distante da reta entre o 1º e o último degrau"})
    out["lt2"].append({"method": "OBLA 4,0 mmol", "ref": "Sjödin & Jacobs 1981", "value": _obla(xs, ys),
                       "detail": "carga a 4,0 mmol, interpolação linear entre degraus"})
    curve = []
    x = lo
    while x <= hi + 1e-9:
        curve.append([round(x, 2), round(_ev(c, x), 3)])
        x += (hi - lo) / 60
    out["curve"] = curve
    return out

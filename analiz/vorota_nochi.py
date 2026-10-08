# -*- coding: utf-8 -*-
"""
ВОРОТА НОЧИ: решают по замеру, пускать ли ночное обучение после разминки.

Читают свежую ленту замера (замороженный мозг после разминки, смесь 50/50),
считают опоры по типам и печатают ОДНУ строку-решение:
    GO <порог>   — обе опоры в норме; порог сторожа посчитан перебором
    STOP <почему> — разминка не подняла дуэль или уронила простого

Пороги решения (названы до запуска, менять по ходу ночи нельзя):
  * дуэль   >= 55%  (до показа была 49.1%; показ обязан дать заметный сдвиг)
  * простой >= 85%  (до показа 97.2%; ниже 85% значит разминка стёрла старое)
Порог сторожа для ночи: максимум из перебора с нулём ложных остановок на
замере, минус 0.05 запаса (урок смеси: хвост длиннее опоры), пол 0.30.
"""

import re
import sys
from pathlib import Path

LENTA = Path(__file__).parent.parent / "lenta.log"

b = []
for s in LENTA.read_text(encoding="utf-8").splitlines():
    m = re.search(r"бой #\d+: (\S+).*против (\S+)", s)
    if m:
        b.append((m[1] == "УБИЛ", m[2]))

if len(b) < 60:
    print(f"STOP замер слишком короткий: {len(b)} боёв")
    sys.exit(0)

duel = [x[0] for x in b if x[1] == "мечник"]
prost = [x[0] for x in b if x[1] == "простой"]
p_duel = sum(duel) / max(len(duel), 1)
p_prost = sum(prost) / max(len(prost), 1)
print(f"# замер: дуэль {sum(duel)}/{len(duel)} = {100*p_duel:.1f}%, "
      f"простой {sum(prost)}/{len(prost)} = {100*p_prost:.1f}%", file=sys.stderr)

if p_duel < 0.55:
    print(f"STOP дуэль после разминки {100*p_duel:.0f}% < 55% — показ не поднял")
    sys.exit(0)
if p_prost < 0.85:
    print(f"STOP простой после разминки {100*p_prost:.0f}% < 85% — разминка стёрла старое")
    sys.exit(0)

ish = [x[0] for x in b]
luchshij = 0.30
for porog_i in range(60, 29, -5):
    porog = porog_i / 100
    stopy = 0
    podryad = 0
    for i in range(30, len(ish) + 1):
        if sum(ish[i - 30:i]) / 30 < porog:
            podryad += 1
        else:
            podryad = 0
        if podryad >= 3:
            stopy += 1
            podryad = 0
    if stopy == 0:
        luchshij = porog
        break
porog_nochi = max(0.30, luchshij - 0.05)
print(f"GO {porog_nochi:.2f}")

# -*- coding: utf-8 -*-
"""
Широкие глаза: извлекатель признаков для зрения с растянутым первым ядром.

Штатный NatureCNN на входе крупнее 64 строит conv1 8x8/4 и линейный слой под
разросшийся flatten. Пересаженный мозг несёт растянутое первое ядро, чтобы
выход ствола остался прежним (15x15 -> 6x6 -> 4x4, flatten 1024 — как у
исходного 64-мозга), поэтому при загрузке сеть обязана рождаться сразу с
такой геометрией: PPO.load пересобирает сеть по пространствам и только потом
льёт веса. Этот класс сохраняется внутри zip мозга (policy_kwargs), так что
все загрузки — обучение, замеры, вскрытия — получают правильную форму сами.

Геометрия выбирается по форме входа (класс один для всех поколений глаз,
старые zip продолжают грузиться):
  * 128x128 (после peresadit_zrenie.py): ядро 16x16, шаг 8x8 —
    пространственное растяжение 2x2 квадратного 64-ядра 8x8/4;
  * 128x224 (после rasshirit_vzglyad.py): ядро 16x28, шаг 8x14 —
    горизонталь дотянута ещё в 7/4 раза, потому что окно игры 16:9 и
    квадратный кадр ужимал ширину сильнее высоты. 224 = 128*7/4 даёт
    целые ядро и шаг, и тот же выход 15x15.
"""

import torch as th
from stable_baselines3.common.torch_layers import CombinedExtractor

# (высота, ширина) входа -> (ядро, шаг) первого слоя. Вход сюда приходит
# уже каналами вперёд (C, H, W).
GEOMETRIYA = {
    (128, 128): ((16, 16), (8, 8)),
    (128, 224): ((16, 28), (8, 14)),
}


class GlazaShirokie(CombinedExtractor):
    def __init__(self, observation_space, cnn_output_dim=256, **kw):
        super().__init__(observation_space, cnn_output_dim=cnn_output_dim, **kw)
        vysota, shirina = observation_space["pov"].shape[-2:]
        yadro, shag = GEOMETRIYA[(vysota, shirina)]
        pov = self.extractors["pov"]
        pov.cnn[0] = th.nn.Conv2d(pov.cnn[0].in_channels, 32,
                                  kernel_size=yadro, stride=shag)
        pov.linear[0] = th.nn.Linear(1024, cnn_output_dim)

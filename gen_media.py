# -*- coding: utf-8 -*-
"""生成翻书音效与纸张纹理（纯程序合成，无外部素材依赖）。

产物：
  app/assets/sfx/turn.wav       翻页（正向）
  app/assets/sfx/turn_back.wav  翻页（回翻）
  app/assets/sfx/open.wav       开卷
  app/assets/sfx/close.wav      合卷
  app/assets/sfx/tick.wav       按钮轻响
  app/assets/paper.png          可平铺纸张纹理
"""
import math
import struct
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
SFX = ROOT / "app" / "assets" / "sfx"
SFX.mkdir(parents=True, exist_ok=True)
SR = 44100


def _noise(n, seed):
    rng = np.random.default_rng(seed)
    return rng.standard_normal(n)


def _lowpass(x, k):
    """简单一阶低通，k 越小越闷。"""
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc += k * (v - acc)
        y[i] = acc
    return y


def _fast_lowpass(x, k):
    # 用指数加权移动平均的向量化近似（cumsum 差分），避免逐样本循环过慢
    a = 1.0 - k
    idx = np.arange(len(x))
    # 分段近似：先用卷积核做窗平均，再与一阶结果混合
    win = max(5, int(1.0 / max(k, 1e-4) / 8))
    win = min(win, 64)
    kern = np.hanning(win + 2)[1:-1]  # 去掉两端 0，保证核和不为 0
    kern /= kern.sum()
    return np.convolve(x, kern, mode="same")


def paper_swish(dur=0.44, seed=7, bright=0.55, flap=1.0):
    n = int(SR * dur)
    t = np.arange(n) / SR
    noise = _noise(n, seed)
    body = _fast_lowpass(noise, 0.35) * (1 - bright) + _fast_lowpass(noise, 0.9) * bright
    # 纸张"刷"的三段包络：起手、掠过、落定
    env = np.exp(-((t - 0.10) ** 2) / (2 * 0.045 ** 2)) * 0.9
    env += np.exp(-((t - 0.22) ** 2) / (2 * 0.070 ** 2)) * 0.55
    env += np.exp(-((t - 0.34) ** 2) / (2 * 0.055 ** 2)) * 0.35 * flap
    # 起手一记低频"扑"
    thump = np.sin(2 * math.pi * 92 * t) * np.exp(-t / 0.028) * 0.55
    sig = body * env * 0.9 + thump
    # 结尾快速收干，避免爆音
    tail = np.ones(n)
    fade = int(SR * 0.05)
    tail[-fade:] = np.linspace(1, 0, fade)
    return sig * tail


def open_book():
    n = int(SR * 0.75)
    t = np.arange(n) / SR
    noise = _noise(n, 21)
    leather = _fast_lowpass(noise, 0.18) * np.exp(-t / 0.09) * 0.7
    thump = np.sin(2 * math.pi * 68 * t) * np.exp(-t / 0.05) * 0.6
    swish = _fast_lowpass(_noise(n, 33), 0.6) * np.exp(-((t - 0.34) ** 2) / (2 * 0.09 ** 2)) * 0.45
    return leather + thump + swish


def close_book():
    n = int(SR * 0.5)
    t = np.arange(n) / SR
    thump = np.sin(2 * math.pi * 74 * t) * np.exp(-t / 0.045) * 0.75
    slap = _fast_lowpass(_noise(n, 44), 0.25) * np.exp(-t / 0.03) * 0.5
    return thump + slap


def tick():
    n = int(SR * 0.07)
    t = np.arange(n) / SR
    return (_noise(n, 5) * np.exp(-t / 0.006) * 0.5 +
            np.sin(2 * math.pi * 1650 * t) * np.exp(-t / 0.012) * 0.25)


def write_wav(path, sig, gain=0.62):
    sig = np.asarray(sig, dtype=np.float64)
    peak = float(np.max(np.abs(sig))) or 1.0
    sig = sig / peak * gain
    pcm = np.clip(sig * 32767, -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return path.stat().st_size


def paper_texture(size=512, seed=3):
    """米色纸浆纤维纹理，可平铺（用低频噪声 + 纤维条纹 + 细颗粒）。"""
    rng = np.random.default_rng(seed)
    # 低频：多层缩放噪声模拟纸浆厚薄
    base = np.zeros((size, size))
    for scale, amp in [(8, 1.0), (16, 0.6), (32, 0.35), (64, 0.25)]:
        small = rng.standard_normal((scale, scale))
        # 双线性放大
        xi = np.linspace(0, scale - 1, size)
        yi = np.linspace(0, scale - 1, size)
        x0 = np.floor(xi).astype(int); x1 = np.minimum(x0 + 1, scale - 1)
        y0 = np.floor(yi).astype(int); y1 = np.minimum(y0 + 1, scale - 1)
        fx = (xi - x0)[None, :]; fy = (yi - y0)[:, None]
        top = small[y0][:, x0] * (1 - fx) + small[y0][:, x1] * fx
        bot = small[y1][:, x0] * (1 - fx) + small[y1][:, x1] * fx
        base += (top * (1 - fy) + bot * fy) * amp
    base /= 6.0
    # 纤维：横向短条纹
    fibers = np.zeros((size, size))
    for _ in range(260):
        y = rng.integers(0, size)
        x = rng.integers(0, size)
        ln = rng.integers(12, 70)
        amp = rng.normal(0, 0.9)
        xs = (np.arange(ln) + x) % size
        fibers[y, xs] += amp * np.hanning(ln)
    grain = rng.standard_normal((size, size)) * 0.55
    v = base * 6.0 + fibers * 1.4 + grain
    v = (v - v.mean()) / (v.std() or 1.0)
    # 映射到米色纸面
    v = np.clip(v, -2.6, 2.6) / 2.6
    rgb = np.stack([
        250 + v * 5.0,   # R 250
        247 + v * 5.5,   # G 247
        238 + v * 6.5,   # B 238
    ], axis=-1)
    return np.clip(rgb, 0, 255).astype(np.uint8)


def write_png(path, rgb):
    from PySide6.QtGui import QImage
    h, w, _ = rgb.shape
    data = np.ascontiguousarray(rgb).tobytes()
    img = QImage(data, w, h, w * 3, QImage.Format_RGB888)
    img.copy().save(str(path), "PNG")
    return path.stat().st_size


def main():
    sizes = {}
    sizes["turn.wav"] = write_wav(SFX / "turn.wav", paper_swish(0.44, 7, 0.55, 1.0))
    sizes["turn_back.wav"] = write_wav(SFX / "turn_back.wav", paper_swish(0.40, 13, 0.42, 0.7)[::-1].copy())
    sizes["open.wav"] = write_wav(SFX / "open.wav", open_book(), 0.55)
    sizes["close.wav"] = write_wav(SFX / "close.wav", close_book(), 0.5)
    sizes["tick.wav"] = write_wav(SFX / "tick.wav", tick(), 0.35)
    sizes["paper.png"] = write_png(ROOT / "app" / "assets" / "paper.png", paper_texture())
    for k, v in sizes.items():
        print(f"{k:14s} {v/1024:7.1f} KB")


if __name__ == "__main__":
    main()

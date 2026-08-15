from __future__ import annotations

import numpy as np
from scipy.signal import savgol_filter


def smooth_counts(counts: np.ndarray, window: int = 7, polyorder: int = 2) -> np.ndarray:
    window = max(5, int(window) | 1)
    if window >= len(counts):
        window = len(counts) - 1 if len(counts) % 2 == 0 else len(counts)
    return savgol_filter(counts, window_length=window, polyorder=min(polyorder, window - 1), mode="interp")


def snip_background(counts: np.ndarray, iterations: int = 40) -> np.ndarray:
    y = np.log(np.log(np.sqrt(np.maximum(counts, 0) + 1) + 1) + 1)
    bg = y.copy()
    n = len(bg)
    for k in range(1, min(iterations, n // 2) + 1):
        left = bg[:-2 * k]
        right = bg[2 * k:]
        middle = bg[k:n - k]
        bg[k:n - k] = np.minimum(middle, (left + right) / 2)
    return (np.exp(np.exp(bg) - 1) - 1) ** 2 - 1


def corrected_counts(counts: np.ndarray, smooth_window: int = 7, snip_iterations: int = 40) -> tuple[np.ndarray, np.ndarray]:
    smoothed = smooth_counts(counts, smooth_window)
    background = snip_background(smoothed, snip_iterations)
    corrected = np.maximum(smoothed - background, 0)
    return corrected, background

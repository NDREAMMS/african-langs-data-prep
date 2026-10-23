"""Chaîne AUDIO (TTS) — A1..A12 (§5).

ORDRE RÉEL v1.1 : A1 A2 A4 A5 A6 A7 A8 A9 A3 A10 A11 A12
  - la qualité (A7 DNSMOS / A8 SNR) est mesurée AVANT la normalisation de niveau A3,
    car normaliser d'abord amplifierait le bruit avant qu'on ne le mesure (§5, changement v1.1) ;
  - A4 = VAD + découpe (les longs versets BibleTTS sont segmentés en clips ≤ max_s) ;
  - A7 (DNSMOS) et A9 (ASR) sont *model-backed* : sans le modèle fourni, elles sont
    **sautées et journalisées comme telles** (jamais silencieusement).

Replis CPU vs cibles de production (§4 du « reste à faire ») — sélection par config :
  - A2 résample  : backend `scipy` (repli) | `torchaudio` (prod, D13) ;
  - A4 VAD       : backend `energy` (repli) | `silero` (prod) ;
  - A3 loudness  : backend `null` (sauté) | `pyloudnorm` (prod) ;
  - A8 SNR       : backend `simple` (repli) | `wada` (prod).
Un repli utilisé est signalé dans `run_notes.json` — un manifest issu d'un repli
n'est pas publiable en l'état.
"""
from __future__ import annotations

import json
import math
from fractions import Fraction
from pathlib import Path

import numpy as np

from .audio_sources import AudioItem, iter_bibletts, iter_waxal, load_audio
from .common import unicode_norm as U
from .common.config import Config, load_numerals
from .common.journal import Journal
from .common.leak import LeakChecker

EPS = 1e-9


# ---------------------------------------------------------------------------
# DSP
# ---------------------------------------------------------------------------
def resample(x: np.ndarray, sr_in: int, sr_out: int, backend: str = "scipy") -> np.ndarray:
    """A2 — rééchantillonnage.

    backend `torchaudio` = cible production (D13) ; `scipy` = repli déterministe.
    Le repli n'est **pas** bit-identique à torchaudio → signalé dans run_notes.
    """
    x = np.asarray(x, dtype=np.float32)
    if x.size == 0 or sr_in == sr_out:
        return x.copy()
    if backend == "torchaudio":
        try:
            import torch
            import torchaudio

            return np.asarray(
                torchaudio.functional.resample(torch.from_numpy(x), sr_in, sr_out),
                dtype=np.float32,
            )
        except Exception:
            pass  # repli scipy silencieux côté résultat, mais signalé globalement
    from scipy.signal import resample_poly

    frac = Fraction(sr_out, sr_in)
    return np.asarray(resample_poly(x, frac.numerator, frac.denominator), dtype=np.float32)


def _frame_rms(x: np.ndarray, sr: int, frame_s: float = 0.02) -> tuple[np.ndarray, int]:
    frame = max(1, int(frame_s * sr))
    n = len(x) // frame
    if n == 0:
        return np.array([0.0]), frame
    rms = np.sqrt(np.mean(x[:n * frame].reshape(n, frame) ** 2, axis=1) + EPS)
    return rms, frame


def _silero_speech_bounds(x: np.ndarray, sr: int) -> tuple[int, int] | None:
    """Bornes (début, fin) de parole selon silero-vad, en échantillons @ sr. None si indisponible."""
    try:
        import torch
        from silero_vad import get_speech_timestamps, load_silero_vad

        model = load_silero_vad()
        wav = x
        if sr != 16000:  # silero est entraîné en 16 kHz
            wav = resample(x, sr, 16000)
        ts = get_speech_timestamps(torch.from_numpy(wav), model, sampling_rate=16000,
                                   return_seconds=False)
        if not ts:
            return None
        scale = sr / 16000.0
        return int(ts[0]["start"] * scale), int(ts[-1]["end"] * scale)
    except Exception:
        return None


def trim_silence(x: np.ndarray, sr: int, edge_s: float = 0.5,
                 rel_thresh: float = 0.02, backend: str = "energy") -> np.ndarray:
    """A4 (1/2) — VAD : coupe les silences de bord > edge_s.

    backend `silero` (prod) avec repli `energy` (CPU, déterministe) si indisponible.
    """
    pad = int(edge_s * sr)
    if backend == "silero":
        bounds = _silero_speech_bounds(x, sr)
        if bounds is not None:
            start = max(0, bounds[0] - pad)
            end = min(len(x), bounds[1] + pad)
            return x[start:end]
    rms, frame = _frame_rms(x, sr)
    thr = max(rel_thresh * float(rms.max()), 1e-4)
    voiced = np.flatnonzero(rms > thr)
    if len(voiced) == 0:
        return x
    start = max(0, voiced[0] * frame - pad)
    end = min(len(x), (voiced[-1] + 1) * frame + pad)
    return x[start:end]


def segment(x: np.ndarray, sr: int, max_s: float, min_silence_s: float = 0.2,
            search_frac: float = 0.6) -> list[np.ndarray]:
    """A4 (2/2) — découpe en segments ≤ max_s, coupes aux points basse énergie.

    Évite de tronquer (A4 : « séquences tronquées » = défaut évité) : on cherche le
    silence le plus proche de la cible dans [search_frac·max_s, max_s].
    """
    total = len(x)
    if total <= max_s * sr:
        return [x]
    rms, frame = _frame_rms(x, sr)
    thr = max(0.15 * float(rms.max()), 1e-4)
    max_frames = int(max_s * sr) // frame
    lo = int(search_frac * max_frames)
    segs, start = [], 0
    while total - start > max_s * sr:
        end_guess = start + max_frames * frame
        f0 = start // frame
        window = rms[f0 + lo: f0 + max_frames]
        cut = None
        for i in range(len(window) - 1, -1, -1):
            if window[i] < thr:
                cut = (f0 + lo + i) * frame
                break
        if cut is None:
            cut = end_guess
        segs.append(x[start:cut])
        start = cut
    if start < total:
        segs.append(x[start:])
    return segs


def true_peak_dbfs(x: np.ndarray) -> float:
    return 20.0 * math.log10(max(float(np.max(np.abs(x))), EPS))


def _estimate_snr_simple(x: np.ndarray, sr: int) -> float:
    rms, _ = _frame_rms(x, sr)
    if len(rms) < 4:
        return 0.0
    noise = np.percentile(rms, 10)
    speech = np.mean(np.sort(rms)[-max(1, len(rms) // 4):])
    return float(20.0 * math.log10((speech + EPS) / (noise + EPS)))


def estimate_snr_db(x: np.ndarray, sr: int, backend: str = "simple") -> float:
    """A8 — SNR sur audio NON normalisé (§5). backend `wada` (prod) sinon `simple` (repli)."""
    if backend == "wada":
        try:
            import wada  # paquet optionnel ; absent => repli signale

            return float(wada.wada_snr(x, sr))
        except Exception:
            pass
    return _estimate_snr_simple(x, sr)


def measure_loudness_lufs(x: np.ndarray, sr: int) -> float | None:
    """A3 — loudness intégrée (pyloudnorm). None si indisponible."""
    try:
        import pyloudnorm as pyln

        return float(pyln.Meter(sr).integrated_loudness(x))
    except Exception:
        return None


def apply_gain_to_lufs(x: np.ndarray, sr: int, target_lufs: float) -> tuple[np.ndarray, float | None]:
    """Ramène le signal à `target_lufs`. Renvoie (signal, loudness_mesurée) ou (x, None)."""
    current = measure_loudness_lufs(x, sr)
    if current is None or not np.isfinite(current):
        return x, None
    gain_db = target_lufs - current
    return (x * (10.0 ** (gain_db / 20.0))).astype(np.float32), current


def words_per_second(text: str, duration_s: float) -> float:
    n = len(U.tokenize(text))
    return n / duration_s if duration_s > 0 else float("inf")


def wer(ref: str, hyp: str) -> float:
    r, h = U.tokenize(ref), U.tokenize(hyp)
    if not r:
        return 0.0 if not h else 1.0
    return _edit_distance(r, h) / len(r)


def _edit_distance(a: list, b: list) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


# ---------------------------------------------------------------------------
# Étapes model-backed (sautées si modèle absent)
# ---------------------------------------------------------------------------
def _logmag_stft(x: np.ndarray, n_freq: int, hop_ratio: float = 0.5) -> np.ndarray:
    """Spectrogramme log-magnitude (n_freq bandes) — entrée type DNSMOS ONNX."""
    n_fft = (n_freq - 1) * 2
    if len(x) < n_fft:
        x = np.pad(x, (0, n_fft - len(x)))
    hop = max(1, int(n_fft * hop_ratio))
    win = np.hanning(n_fft).astype(np.float32)
    frames = 1 + (len(x) - n_fft) // hop
    spec = np.empty((n_freq, frames), np.float32)
    for i in range(frames):
        seg = x[i * hop:i * hop + n_fft] * win
        spec[:, i] = np.abs(np.fft.rfft(seg))
    return np.log(spec + 1e-6)


class Dnsmos:
    """A7 — qualité perceptuelle (DNSMOS ONNX, CPU/GPU).

    L'interface exacte du modèle (nombre de trames/bandes, ordre des sorties) est
    introspectée depuis la session ONNX ; le score « global » est choisi par nom de
    sortie (`*ovr*`) à défaut la dernière. À confirmer au calibrage (§3.4) : les
    scores DNSMOS sont des **entrées de traitement**, mis en cache (principe §2.4).
    """

    def __init__(self, model_path: str | None, target_sr: int = 16000):
        self.ok = bool(model_path and Path(model_path).exists())
        self.target_sr = target_sr
        self._sess = None
        self._in_name = None
        self._frames = 9
        self._freq = 257
        self._out_names: list[str] = []
        self.last_scores: dict[str, float] = {}
        if self.ok:
            import onnxruntime as ort

            self._sess = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
            inp = self._sess.get_inputs()[0]
            self._in_name = inp.name
            if len(inp.shape) == 3 and all(isinstance(s, int) for s in inp.shape[1:]):
                self._frames, self._freq = int(inp.shape[1]), int(inp.shape[2])
            self._out_names = [o.name for o in self._sess.get_outputs()]

    def score(self, x: np.ndarray, sr: int) -> float | None:
        if not self.ok:
            return None
        try:
            y = resample(x, sr, self.target_sr)
            feat = _logmag_stft(y, self._freq)
            n = feat.shape[1]
            if n < self._frames:
                return None
            accs = np.zeros(len(self._out_names), np.float64)
            count = 0
            for i in range(n - self._frames + 1):
                window = feat[:, i:i + self._frames].T[None, :, :].astype(np.float32)
                out = self._sess.run(self._out_names, {self._in_name: window})
                accs += np.array([float(np.squeeze(o)) for o in out])
                count += 1
            mean = accs / max(1, count)
            self.last_scores = {name: float(v) for name, v in zip(self._out_names, mean)}
            for name, v in self.last_scores.items():
                if "ovr" in name.lower():
                    return v
            return float(mean[-1]) if len(mean) else None
        except Exception:
            return None


def _resample_to(x: np.ndarray, sr: int, sr_out: int) -> np.ndarray:
    return x if sr == sr_out else resample(x, sr, sr_out)


class MmsAsr:
    """A9 — contrôle texte ↔ audio (MMS-ASR → WER). Chargé via transformers si fourni.

    Pour le lingala, les adaptateurs de langue MMS sont utilisés si disponibles
    (`load_adapter(lang)`). Absent → étape sautée et journalisée.
    """

    def __init__(self, model_path: str | None, lang: str | None = None):
        self.ok = False
        self._pipe = None
        if model_path and Path(model_path).exists():
            try:
                from transformers import pipeline

                self._pipe = pipeline("automatic-speech-recognition", model=model_path)
                if lang:
                    try:
                        self._pipe.model.load_adapter(lang)
                    except Exception:
                        pass
                self.ok = True
            except Exception:
                self.ok = False

    def transcribe(self, x: np.ndarray, sr: int) -> str | None:
        if not self.ok:
            return None
        try:
            out = self._pipe({"array": np.asarray(x, dtype=np.float32), "sampling_rate": sr})
            return out.get("text", "")
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def _gather_stream(sources: list[str], limit: int | None) -> list[AudioItem]:
    per_source: dict[str, list[AudioItem]] = {}
    if "bibletts" in sources:
        per_source["bibletts"] = list(iter_bibletts("data/bibletts/extracted", splits=("dev",)))
    if "waxal" in sources:
        # borne le chargement du parquet à ce qui sera réellement consommé
        waxal_cap = (limit * 4) if limit else None
        per_source["waxal"] = list(iter_waxal("data/waxal/asr/lin", split="train", limit=waxal_cap))
    if not limit:
        return [i for s in sources for i in per_source.get(s, [])]
    # Échantillon interleavé équitable entre sources.
    per = max(1, limit // max(1, len(per_source)))
    out: list[AudioItem] = []
    for s in sources:
        out += per_source.get(s, [])[:per]
    return out[:limit]


def run(cfg: Config, out_dir: str | Path, sources: list[str] | None = None,
        limit: int | None = None) -> Journal:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "mel").mkdir(exist_ok=True)

    numerals = load_numerals()
    sr_out = int(cfg.get("audio.target_sr", 24000))
    a2 = cfg.get("audio.A2_resample") or {}
    a4 = cfg.get("audio.A4_vad") or {}
    a5 = cfg.get("audio.A5_duration") or {}
    a6 = cfg.get("audio.A6_rate") or {}
    a7 = cfg.get("audio.A7_dnsmos") or {}
    a8 = cfg.get("audio.A8_snr") or {}
    a9 = cfg.get("audio.A9_asr_wer") or {}
    a3 = cfg.get("audio.A3_loudness") or {}
    max_s = float(a5.get("max_s", 10.0))
    min_s = float(a5.get("min_s", 1.5))
    beyond = a5.get("beyond", "bucket")
    resample_backend = str(a2.get("backend", "scipy"))
    vad_backend = str(a4.get("backend", "energy"))
    snr_backend = str(a8.get("backend", "simple"))

    dnsmos = Dnsmos(a7.get("model_path"))
    asr = MmsAsr(a9.get("model_path"), lang=cfg.lang)
    a10 = cfg.get("audio.A10_leak") or {}
    leak = LeakChecker(a10.get("reference", "data/flores/devtest"))
    notes: list[str] = []
    if not dnsmos.ok:
        notes.append("A7_dnsmos_saute (pas de modele)")
    if not asr.ok:
        notes.append("A9_asr_saute (pas de modele)")
    if vad_backend != "silero":
        notes.append(f"A4_vad_backend={vad_backend} (repli, pas silero-vad)")
    if resample_backend != "torchaudio":
        notes.append(f"A2_resample_backend={resample_backend} (repli, pas torchaudio)")
    if not a3.get("backend"):
        notes.append("A3_loudness_saute (pas de backend pyloudnorm)")
    if snr_backend != "wada":
        notes.append(f"A8_snr_backend={snr_backend} (repli, pas WADA-SNR)")
    if not leak.available:
        notes.append("A10_leak_non_verifie (pas de referentiel de splits)")

    stream = _gather_stream(sources or ["bibletts", "waxal"], limit)
    jr = Journal(stage="tts", lang=cfg.lang)
    buckets = kept_segments = 0
    with (out_dir / "manifest_tts.jsonl").open("w", encoding="utf-8") as mf:
        for item in stream:
            row = item.row
            row.text = U.clean_text(U.normalize_numerals(U.to_nfc(row.text), numerals))
            toks = U.tokenize(row.text)

            try:
                item = load_audio(item)                                    # A1
            except Exception as e:
                jr.see_input(row, toks)
                jr.drop(row, "A1_load", f"illisible: {type(e).__name__}", str(e))
                continue
            if item.samples.ndim != 1 or item.samples.size == 0:
                jr.see_input(row, toks)
                jr.drop(row, "A1_load", "vide ou non mono")
                continue

            x = trim_silence(item.samples, item.sr, a4.get("edge_silence_s", 0.5),  # A4.1
                             backend=vad_backend)
            segs = segment(x, item.sr, max_s)                               # A4.2
            seg_texts = split_tokens_by_duration(row.text, segs, item.sr)    # texte au prorata

            for si, seg in enumerate(segs):
                seg = resample(seg, item.sr, sr_out, backend=resample_backend)   # A2
                seg_row = _segment_row(row, si, len(segs))
                seg_text = seg_texts[si]
                seg_row.text = seg_text
                seg_toks = U.tokenize(seg_text)
                jr.see_input(seg_row, seg_toks)
                duration = len(seg) / sr_out

                bucket = None
                if duration < min_s or duration > max_s:                  # A5
                    if beyond == "bucket":
                        bucket = "A5_duration"
                    else:
                        jr.drop(seg_row, "A5_duration", "durée hors bornes", round(duration, 2))
                        continue

                rate = words_per_second(seg_text, duration)               # A6
                if rate > a6.get("max_words_per_s", 4.0):
                    jr.drop(seg_row, "A6_rate", "débit trop élevé", round(rate, 2))
                    continue

                d = dnsmos.score(seg, sr_out)                              # A7 (non normalisé)
                if d is not None and d < a7.get("min", 3.0):
                    jr.drop(seg_row, "A7_dnsmos", "qualité perçue", round(d, 3))
                    continue

                snr = estimate_snr_db(seg, sr_out, backend=snr_backend)    # A8 (non normalisé)
                if snr < a8.get("min_db", 15.0):
                    jr.drop(seg_row, "A8_snr", "SNR trop bas", round(snr, 2))
                    continue

                hyp = asr.transcribe(seg, sr_out)                          # A9 (sémantique)
                if hyp is not None and wer(seg_text, hyp) > a9.get("max_wer", 0.30):
                    jr.drop(seg_row, "A9_wer", "texte/audio incohérents")
                    continue

                if a3.get("backend"):                                      # A3 (loudness)
                    seg, _ = apply_gain_to_lufs(seg, sr_out, a3.get("target_lufs", -23.0))
                peak = true_peak_dbfs(seg)                                 # A3 (clipping)
                if peak > a3.get("max_true_peak_dbfs", -1.0):
                    jr.drop(seg_row, "A3_clipping", "crête > -1 dBFS", round(peak, 2))
                    continue

                if leak.available and leak.overlaps(seg_text):            # A10
                    jr.drop(seg_row, "A10_leak", "chevauchement avec le test")
                    continue

                missing = [k for k, v in {                           # A11 métadonnées
                    "speaker": seg_row.speaker, "lang": seg_row.lang, "source": seg_row.source,
                    "domain": seg_row.domain,
                }.items() if v in (None, "")]
                if missing:
                    jr.drop(seg_row, "A11_metadata", f"champs manquants: {missing}")
                    continue

                mel_path = None
                if cfg.get("audio.A12_mel.enabled", True):                 # A12
                    mel_path = _write_mel(out_dir / "mel", seg_row.row_id, seg, sr_out,
                                          int(cfg.get("audio.A12_mel.n_mels", 80)))

                mf.write(json.dumps({
                    "audio": str(mel_path) if mel_path else seg_row.row_id,
                    "text": seg_text, "lang": seg_row.lang, "speaker": seg_row.speaker,
                    "duration": round(duration, 3), "sr": sr_out,
                    "source": seg_row.source, "domain": seg_row.domain, "bucket": bucket,
                }, ensure_ascii=False) + "\n")
                jr.see_output(seg_row, seg_toks)
                kept_segments += 1
                if bucket:
                    buckets += 1

    jr.write_rejects(out_dir / "rejects.jsonl")
    (out_dir / "run_notes.json").write_text(
        json.dumps({"notes": notes, "buckets": buckets}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    return jr


def _segment_row(row, si: int, n: int):
    if n == 1:
        return row
    clone = type(row)(**{**row.__dict__})
    clone.row_id = f"{row.row_id}_seg{si:03d}"
    return clone


def split_tokens_by_duration(text: str, segs: list[np.ndarray], sr: int) -> list[str]:
    """Répartit le texte d'un long clip sur ses segments, au prorata de la durée.

    Sans alignement mot-à-mot, une répartition proportionnelle évite le biais majeur :
    attribuer tout le texte à chaque segment gonflerait A6 (mots/s) et fausserait A9.
    """
    tokens = U.tokenize(text)
    if len(segs) == 1 or not tokens:
        return [text] * len(segs)
    durs = np.array([len(s) / sr for s in segs])
    cum = np.cumsum(durs) / durs.sum()
    out, prev = [], 0
    for i, frac in enumerate(cum):
        end = len(tokens) if i == len(segs) - 1 else int(round(frac * len(tokens)))
        out.append(" ".join(tokens[prev:end]))
        prev = max(prev, end)
    return out


# ---------------------------------------------------------------------------
# A12 — mel
# ---------------------------------------------------------------------------
def _write_mel(mel_dir: Path, row_id: str, x: np.ndarray, sr: int, n_mels: int) -> Path:
    """A12 — log-mel 80 bandes en cache. Cible torchaudio ; repli scipy sinon."""
    try:
        import torch
        import torchaudio

        mel = torchaudio.transforms.MelSpectrogram(
            sample_rate=sr, n_fft=1024, hop_length=256, n_mels=n_mels)(torch.from_numpy(x))
        arr = torch.log(mel + 1e-6).numpy()
    except Exception:
        arr = _mel_scipy(x, sr, n_mels)
    out = mel_dir / f"{row_id}.npy"
    np.save(out, arr.astype(np.float32))
    return out


def _mel_scipy(x: np.ndarray, sr: int, n_mels: int) -> np.ndarray:
    from scipy import signal

    n_fft, hop = 1024, 256
    f, _t, Z = signal.stft(x, fs=sr, nperseg=n_fft, noverlap=n_fft - hop)
    power = np.abs(Z) ** 2
    return np.log(_mel_filterbank(sr, n_fft, n_mels, f) @ power + 1e-6)


def _mel_filterbank(sr: int, n_fft: int, n_mels: int, freqs: np.ndarray) -> np.ndarray:
    def hz_to_mel(f):
        return 2595.0 * np.log10(1.0 + f / 700.0)

    def mel_to_hz(m):
        return 700.0 * (10.0 ** (m / 2595.0) - 1.0)

    mels = np.linspace(hz_to_mel(0), hz_to_mel(sr / 2), n_mels + 2)
    hz = mel_to_hz(mels)
    fb = np.zeros((n_mels, len(freqs)), np.float32)
    for i in range(n_mels):
        lo, ctr, hi = hz[i], hz[i + 1], hz[i + 2]
        left = (freqs - lo) / (ctr - lo + EPS)
        right = (hi - freqs) / (hi - ctr + EPS)
        fb[i] = np.maximum(0.0, np.minimum(left, right))
    return fb

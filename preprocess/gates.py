"""Gates automatiques de publication — décision « sans relecteur » (D-f).

Sans annotation humaine, on ne peut pas mesurer une « précision des rejets ».
On vérifie donc la **forme** du résultat : rétention, sources/locuteurs non vidés,
part du filtre dominant, taux de clipping. Ces gates peuvent rétrograder un manifest
même si sa configuration est auto-calibrée.
"""
from __future__ import annotations

from .common.config import Config


def _check(ok: bool, value, bound) -> dict:
    return {"ok": bool(ok), "value": value, "bound": bound}


def evaluate(report: dict, cfg: Config) -> dict:
    """Évalue les gates sur un `report` de `Journal` + la politique `validation.gates`."""
    g = cfg.get("validation.gates") or {}
    retention = report.get("retention") or {}
    drops = report.get("drops") or {}
    read = int(report.get("read") or 0)
    kept = int(report.get("kept") or 0)
    checks: dict[str, dict] = {}

    checks["kept_nonzero"] = _check(kept > 0, kept, "> 0")

    v = retention.get("tokens")
    checks["retention_tokens"] = _check(
        v is None or float(v) >= float(g.get("min_retention_tokens", 0.80)),
        v, f">= {g.get('min_retention_tokens', 0.80)}",
    )

    v = retention.get("vocab_unique")
    checks["retention_vocab"] = _check(
        v is None or float(v) >= float(g.get("min_retention_vocab", 0.50)),
        v, f">= {g.get('min_retention_vocab', 0.50)}",
    )

    by_source = retention.get("by_source") or {}
    min_source = min(by_source.values()) if by_source else None
    checks["source_retention"] = _check(
        min_source is None or float(min_source) >= float(g.get("min_source_retention", 0.20)),
        min_source, f">= {g.get('min_source_retention', 0.20)}",
    )

    wiped = (retention.get("speakers") or {}).get("wiped") or []
    if g.get("require_no_wiped_speakers", True):
        checks["no_wiped_speakers"] = _check(not wiped, wiped, "[]")

    max_drop = max((int(n) for n in drops.values()), default=0)
    share = max_drop / read if read else 0.0
    checks["single_filter_share"] = _check(
        share <= float(g.get("max_single_filter_share", 0.50)),
        round(share, 4), f"<= {g.get('max_single_filter_share', 0.50)}",
    )

    clip_rate = (int(drops.get("A3_clipping", 0)) / read) if read else 0.0
    checks["clipping_rate"] = _check(
        clip_rate <= float(g.get("max_clipping_rate", 0.01)),
        round(clip_rate, 4), f"<= {g.get('max_clipping_rate', 0.01)}",
    )

    failures = [name for name, c in checks.items() if not c["ok"]]
    return {"ok": not failures, "checks": checks, "failures": failures}

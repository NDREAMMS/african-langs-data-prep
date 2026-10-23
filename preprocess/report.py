"""Assemblage de report.json + configuration figée (§7, §8).

`report.json` enrichi v1.1 : décompte de lignes + rétentions + provenance des seuils.
`config_snapshot.yaml` : preprocess.yaml figé (provenance incluse).
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from .common.config import Config
from .common.journal import Journal


def write_report(cfg: Config, jr: Journal, out_dir: str | Path) -> dict:
    out_dir = Path(out_dir)
    report = jr.report()
    report["publishable"] = cfg.publishable
    report["cfg_hash"] = cfg.hash
    report["uncalibrated"] = cfg.uncalibrated()
    report["seuils"] = {
        block: {"valeur": cfg.raw[section][block], "provenance":
                (cfg.raw[section][block] or {}).get("provenance")}
        for section in ("text", "audio")
        for block in cfg.raw.get(section, {})
        if isinstance(cfg.raw[section][block], dict)
        and "provenance" in (cfg.raw[section][block] or {})
    }
    (out_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.copyfile(cfg.path, out_dir / "config_snapshot.yaml")
    return report


def log_clearml(cfg: Config, report: dict, out_dir: str | Path, stage: str):
    """§8 — un task ClearML par étape ; wrap défensif (l'agent peut être absent en local)."""
    out_dir = Path(out_dir)
    try:
        from clearml import Task

        task = Task.init(project_name="langues", task_name=f"prep_{stage}_{cfg.hash}",
                         auto_connect_frameworks=False)
        task.connect(cfg.raw)
        for name, n in report.get("drops", {}).items():
            task.get_logger().report_scalar(f"drop/{stage}", name, n, iteration=0)
        for name, value in report.get("retention", {}).items():
            if isinstance(value, float):
                task.get_logger().report_scalar(f"retention/{stage}", name, value, iteration=0)
        task.upload_artifact("report", artifact_object=str(out_dir / "report.json"))
        if (out_dir / "rejects.jsonl").exists():
            task.upload_artifact("rejects", artifact_object=str(out_dir / "rejects.jsonl"))
        task.close()
        return task
    except Exception as e:  # agent/serveur indisponible : ne pas casser le run local
        print(f"[clearml] suivi distant indisponible ({type(e).__name__}); run local terminé.")
        return None

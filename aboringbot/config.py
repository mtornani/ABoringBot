import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(path=None, local=None):
    cfg = tomllib.loads(Path(path or ROOT / "config" / "girone_d.toml").read_text())
    lp = Path(local or ROOT / "config" / "local.toml")
    cfg["exclusions"] = tomllib.loads(lp.read_text()).get("exclusions", {}) if lp.exists() else {}
    cfg["club_names"] = {int(k): v for k, v in cfg.get("club_names", {}).items()}
    return cfg


def output_columns(cfg):
    base = list(cfg["output"]["columns"])
    i = base.index("gs_squadra")
    return base[:i] + list(cfg["exclusions"].keys()) + base[i:]

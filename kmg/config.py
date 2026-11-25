import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_yaml(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_env():
    """Read .env into os.environ without printing anything (values are secrets)."""
    p = ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def models():
    return load_yaml(ROOT / "config" / "models.yaml")


def chapter(cfg_path):
    c = load_yaml(cfg_path)
    c.setdefault("language", "ru")
    c.setdefault("domain_pack", "geology")
    return c


def domain_pack(name):
    d = ROOT / "domain" / name
    pack = {"name": name, "dir": str(d)}
    for f in sorted(d.glob("*.yaml")):
        pack[f.stem] = load_yaml(f)
    return pack

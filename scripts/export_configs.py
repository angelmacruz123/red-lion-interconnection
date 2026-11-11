"""
Exporta por consola todas las configuraciones de un fabricante a configs_out/
(útil para CI/CD o para cargarlas en GNS3/EVE-NG sin abrir la interfaz).

    python scripts/export_configs.py --vendor Cisco --floors 15 --hosts 600
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.ipam import build_address_plan  # noqa: E402
from core.state import VENDORS, ProjectConfig  # noqa: E402
from core.topology import build_topology  # noqa: E402
from generators import render_all  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vendor", choices=VENDORS, default="Cisco")
    ap.add_argument("--floors", type=int, default=15)
    ap.add_argument("--hosts", type=int, default=600)
    ap.add_argument("--base", default="10.20.0.0/16")
    ap.add_argument("--vpn", default="IPsec")
    a = ap.parse_args()
    cfg = ProjectConfig(floors=a.floors, hosts_total=a.hosts, ipv4_base=a.base, vpn_type=a.vpn, vendor=a.vendor)
    plan = build_address_plan(cfg)
    out = ROOT / "configs_out" / a.vendor.lower()
    out.mkdir(parents=True, exist_ok=True)
    for c in render_all(cfg, plan, build_topology(cfg, plan), a.vendor):
        (out / c.filename).write_text(c.text, encoding="utf-8")
    print(f"{len(list(out.glob('*.txt')))} archivos en {out}")


if __name__ == "__main__":
    main()

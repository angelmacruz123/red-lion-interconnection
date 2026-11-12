"""
Genera docs/pruebas.md con el porcentaje de confianza del sistema (Corte 3).

    python scripts/generate_test_report.py            # escribe el reporte
    python scripts/generate_test_report.py --min 90   # falla (exit 1) si la confianza < 90 % (útil en CI)
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import quality  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--min", type=float, default=0.0, help="Confianza mínima exigida (0-100).")
    args = ap.parse_args()

    report = quality.build_report()
    path = quality.write_report(report)
    print(f"Pruebas superadas: {report.passed} de {len(report.tests)} = {report.confidence:g}% de confianza "
          f"· Controles de seguridad: {sum(c.ok for c in report.checks)}/{len(report.checks)}")
    print(f"Reporte: {path}")
    return 0 if report.confidence >= args.min else 1


if __name__ == "__main__":
    raise SystemExit(main())

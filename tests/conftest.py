"""Configuración común de pytest: raíz del proyecto en sys.path y fixtures de diseño."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.ipam import build_address_plan  # noqa: E402
from core.state import ProjectConfig  # noqa: E402
from core.topology import build_topology  # noqa: E402


@pytest.fixture
def cfg():
    return ProjectConfig()  # edificio de 15 pisos, 600 hosts, 10.20.0.0/16


@pytest.fixture
def plan(cfg):
    return build_address_plan(cfg)


@pytest.fixture
def topo(cfg, plan):
    return build_topology(cfg, plan)

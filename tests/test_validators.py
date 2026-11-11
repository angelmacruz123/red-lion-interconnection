"""M6 · Validación estricta de entradas (anti-inyección y anti-errores de sintaxis)."""

import pytest

from core.state import ProjectConfig
from core.validators import (ValidationError, escape_output, is_destructive, parse_command_batch,
                             slugify_hostname, validate_command, validate_hostname, validate_ipv4_network,
                             validate_ipv6_network, validate_project_name, validate_target_host)


@pytest.mark.parametrize("cmd", ["show ip int brief", "show run | include hostname",
                                 "display current-configuration | include sysname", "/ip address print",
                                 "get system status", "ping 10.20.7.1"])
def test_comandos_legitimos_aceptados(cmd):
    assert validate_command(cmd) == cmd


@pytest.mark.parametrize("cmd", ["show ver ; reload", "show ver && reload", "show `id`", "show $(whoami)",
                                 "show run > /tmp/x", "show ver\nreload", "show ver\rreload",
                                 "show\x00ver", "a" * 300, "", "   "])
def test_inyecciones_bloqueadas(cmd):
    with pytest.raises(ValidationError):
        validate_command(cmd)


@pytest.mark.parametrize("cmd", ["reload", "write erase", "erase startup-config", "reset saved-configuration",
                                 "execute factoryreset", "/system reset-configuration", "delete flash:x"])
def test_destructivos_detectados(cmd):
    assert is_destructive(cmd)


def test_lote_rechaza_destructivo_sin_confirmacion():
    with pytest.raises(ValidationError, match="destructivo"):
        parse_command_batch("show ver\nreload")
    assert parse_command_batch("show ver\nreload", allow_destructive=True) == ["show ver", "reload"]


def test_lote_ignora_comentarios_y_limita_tamano():
    assert parse_command_batch("# hola\n! cisco\n\nshow ver") == ["show ver"]
    with pytest.raises(ValidationError, match="Máximo"):
        parse_command_batch("\n".join(["show ver"] * 51))


def test_lote_fail_closed_indica_linea():
    with pytest.raises(ValidationError, match="Línea 2"):
        parse_command_batch("show ver\nshow ver; reload\nshow clock")


@pytest.mark.parametrize("cidr", ["10.20.0.0/16", "172.16.0.0/12", "192.168.0.0/22", "100.64.0.0/16"])
def test_redes_base_validas(cidr):
    assert str(validate_ipv4_network(cidr, 8, 26)) == cidr


@pytest.mark.parametrize("cidr", ["10.20.0.5/16", "8.8.8.0/24", "10.0.0.0/30", "hola", "300.1.1.0/24", ""])
def test_redes_base_invalidas(cidr):
    with pytest.raises(ValidationError):
        validate_ipv4_network(cidr, 8, 26)


def test_ipv6_valida_e_invalida():
    assert validate_ipv6_network("2001:db8:acad::/48").prefixlen == 48
    for bad in ("2001:db8::1/48", "2001:db8::/64", "zz::/48"):
        with pytest.raises(ValidationError):
            validate_ipv6_network(bad)


def test_nombres_y_hostnames():
    assert validate_project_name("Torre Corporativa Bogotá") == "Torre Corporativa Bogotá"
    for bad in ("ab", "x" * 60, "<script>alert(1)</script>", "Proyecto; DROP TABLE"):
        with pytest.raises(ValidationError):
            validate_project_name(bad)
    assert slugify_hostname("Torre Ñandú / Sede #2") == "TORRE-NANDU-SEDE-2"
    assert validate_hostname("R-CORE-01") == "R-CORE-01"
    with pytest.raises(ValidationError):
        validate_hostname("router core")


def test_destinos_ssh():
    assert validate_target_host("10.20.6.130") == "10.20.6.130"
    assert validate_target_host("core01.corp.local") == "core01.corp.local"
    for bad in ("10.0.0.1; rm -rf /", "host name", "-oProxyCommand=x", "a..b"):
        with pytest.raises(ValidationError):
            validate_target_host(bad)


def test_escape_html_previene_xss():
    out = escape_output('<img src=x onerror="alert(1)">')
    assert "<" not in out and "&lt;img" in out and "&quot;" in out


def test_config_global_reporta_todos_los_errores():
    cfg = ProjectConfig(project_name="x", floors=0, ipv4_base="8.8.8.0/24", vpn_type="PPTP")
    errors = cfg.validate()
    assert len(errors) >= 4

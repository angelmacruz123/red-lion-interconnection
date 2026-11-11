# Mapa de entregables por corte

Relación entre lo que se evalúa en cada corte y los archivos del repositorio que lo evidencian.
Ajuste los nombres de los criterios a la rúbrica exacta que publique el docente.

## Corte 2 — Diseño, direccionamiento y configuración

| Criterio | Evidencia en el repositorio | Cómo demostrarlo en clase |
|---|---|---|
| Levantamiento de requerimientos y escenario | `views/m1_requirements.py`, `core/state.py`, `core/capacity.py` | Cambiar de 15 a 8 pisos y mostrar que todo se recalcula |
| Plan de direccionamiento IPv4/IPv6 con VLSM | `core/ipam.py`, `docs/plan-direccionamiento.md` | Calculadora del Módulo 2 vs. cálculo a mano de un /26 |
| Enlaces WAN /30 | `core/ipam.py::P2PLink`, pestaña “Enlaces WAN” | Mostrar 2 IP útiles por enlace, contiguas |
| Topología jerárquica | `core/topology.py`, Módulo 3, exportación .svg/.dot | Diagrama generado (no dibujado a mano) |
| Configuración multi-marca | `generators/cisco.py`, `huawei.py`, `fortinet.py`, `mikrotik.py` | Descargar el .zip y cargar un archivo en Packet Tracer / eNSP |
| Documento de arquitectura | `docs/arquitectura.md` | Decisiones técnicas y limitaciones |
| Manual de uso | `README.md` (sección “Uso por módulo”) | — |

## Corte 3 — Automatización, seguridad y pruebas

| Criterio | Evidencia en el repositorio | Cómo demostrarlo en clase |
|---|---|---|
| Consola NetDevOps SSH/Telnet | `netdevops/ssh_client.py`, `telnet_client.py`, Módulo 5 (pestaña Terminal) | Lote en simulación y, si hay laboratorio, contra un router real/GNS3 |
| Configuración automática de equipos | `netdevops/deploy.py`, Módulo 5 (Despliegue guiado), `tests/test_deploy.py` | Desplegar nombre, VLAN, IP y puertos en un switch simulado (de fábrica → configurado) y en GNS3/EVE-NG por SSH |
| Validaciones y anti-inyección | `core/validators.py`, pestaña “Laboratorio de validación” | Probar `show ver ; reload` y ver el bloqueo |
| Anti-fuga de credenciales | `.env.example`, `.gitignore`, `core/quality.py::security_checks`, `docs/seguridad.md` | Mostrar que `.env` no está en git y la redacción de secretos |
| Pruebas automatizadas | `tests/` (pytest + `streamlit.testing.AppTest`) | `pytest -q` en vivo |
| % de confianza | `docs/pruebas.md` (generado por `scripts/generate_test_report.py`) | Botón del Módulo 6 |
| Políticas de IA | `docs/politicas-ia.md` (completar la declaración) | — |

## Estructura sugerida de ramas y etiquetas (git)

```
main            ← solo código que pasa las pruebas
├── corte-2     ← tag v2.0 al cerrar el Corte 2 (M1–M4 + docs de diseño)
└── corte-3     ← tag v3.0 al cerrar el Corte 3 (M5–M6 + pruebas + políticas)
```

Comandos:

```bash
git tag -a v2.0 -m "Entrega Corte 2: diseño, IPAM, topología y configuraciones"
git tag -a v3.0 -m "Entrega Corte 3: NetDevOps, ciberdefensa y pruebas"
git push --tags
```

# Políticas de uso de Inteligencia Artificial

Documento del Corte 3. Define cómo se usó y cómo se controla el uso de herramientas de IA generativa
en el desarrollo de RED-LION-INTERCONNECTION, de acuerdo con las normas de integridad académica de la
institución. **El equipo debe completar la sección 5 con información veraz antes de entregar.**

## 1. Principios

1. **Transparencia.** Todo uso de IA en código, documentación o diseño se declara (sección 5). No se
   presenta como propio contenido generado que no se haya entendido, revisado y adaptado.
2. **Responsabilidad humana.** Los integrantes del equipo son responsables de cada línea entregada:
   deben poder explicarla, modificarla y defenderla en la sustentación.
3. **Verificación obligatoria.** Ningún resultado de IA se acepta sin pruebas. La batería automatizada
   (`docs/pruebas.md`) y la verificación manual de subredes (`docs/plan-direccionamiento.md`) son el
   control de calidad.
4. **Confidencialidad.** Nunca se envían a servicios de IA contraseñas, llaves, configuraciones reales de
   producción, direcciones públicas de la organización ni datos personales.

## 2. Usos permitidos

- Generar borradores de código, plantillas o documentación que luego se revisan línea por línea.
- Explicar conceptos (VLSM, OSPF, IPsec, paramiko) y proponer alternativas de diseño.
- Sugerir casos de prueba y revisar código en busca de errores o vulnerabilidades.
- Mejorar la redacción de documentos escritos por el equipo.

## 3. Usos prohibidos

- Entregar código o texto generado por IA sin revisión, sin pruebas o sin declararlo.
- Usar IA para responder evaluaciones individuales donde el docente lo haya prohibido.
- Pegar en un chat de IA el archivo `.env`, salidas de `show running-config` con secretos o datos de
  clientes reales.
- Inventar resultados de pruebas, capturas o métricas. El porcentaje de confianza solo puede provenir
  de `scripts/generate_test_report.py`.

## 4. Controles técnicos implementados en el proyecto

| Riesgo | Control | Dónde |
|---|---|---|
| Código generado con errores de cálculo | Pruebas unitarias contra cálculos manuales de subred | `tests/test_ipam.py` |
| Código generado inseguro (inyección) | Lista blanca de caracteres, tokens prohibidos, comandos destructivos con confirmación | `core/validators.py`, `tests/test_validators.py` |
| Fuga de credenciales hacia la IA o hacia git | `.env` fuera de git, marcadores `<<…>>`, escáner de secretos, enmascarado de salidas | `.gitignore`, `core/quality.py`, `tests/test_security.py` |
| Resultados "inventados" | El reporte de confianza se genera ejecutando pytest; no se edita a mano | `core/quality.py` |
| Configuraciones CLI alucinadas | Pruebas por fabricante que verifican sintaxis clave y que cada IP proviene del plan | `tests/test_generators.py` |

## 5. Declaración de uso (completar por el equipo)

| Campo | Respuesta |
|---|---|
| Herramienta(s) de IA utilizadas | *(p. ej. asistente de IA conversacional, autocompletado en el editor)* |
| Fechas / período de uso | |
| Partes del proyecto en que se usó | *(p. ej. estructura inicial del código, plantillas CLI, borrador de documentación)* |
| Qué se modificó o verificó manualmente | |
| Partes desarrolladas sin IA | |
| Integrante(s) que revisaron el resultado | |

**Declaración:** Los abajo firmantes declaramos que hemos revisado, comprendido y probado todo el
contenido entregado, y que la información de esta sección es veraz.

| Nombre | Firma | Fecha |
|---|---|---|
| | | |
| | | |

## 6. Referencias de buenas prácticas

- Normas de integridad académica y propiedad intelectual de la institución.
- OWASP Top 10 (inyección, exposición de datos sensibles) para los controles de la sección 4.

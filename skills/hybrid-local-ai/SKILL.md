---
name: hybrid-local-ai
description: Flujo híbrido para ahorrar tokens de Claude delegando trabajo acotado a modelos locales en la RX 9070 XT (Strata con Inkling-2-Mini SQ-15, Ollama qwen-rtl / qwen-vl) y a codewhale (deepseek-flash). Usar en tareas cotidianas de FPGA (openFPGA/Quartus), DevOps/IaC (Terraform, K8s/Helm, Ansible, CI/CD) y plugins de audio VST3/CLAP en Rust (nih-plug), o cuando el usuario pida ahorrar tokens, resumir/leer muchos archivos o generar boilerplate.
---

# Flujo híbrido Claude + Strata + Ollama + codewhale

Claude es el arquitecto: decide, revisa y verifica. Los modelos locales hacen el trabajo acotado (0 tokens cloud) y DeepSeek hace el trabajo delegable que exige razonamiento o mucho contexto.

## 1. Inventario (RX 9070 XT 16 GB VRAM, 64 GB RAM, Arch)

| Herramienta | Modelo | Memoria | Para qué |
| --- | --- | --- | --- |
| `strata-local ask` | Inkling-2-Mini SQ-15 (Strata 0.1.67, 26.4B MoE / 3.4B activos, 64K ctx, puerto 8080) | ~14 GB (100% VRAM + ~0.4 GB RAM) | Minion diario general: código, 68k→C, IaC, Rust, resúmenes, tool calling |
| `qwen-rtl` | qwen2.5-coder-14b-fpga (Ollama Vulkan) | ~16 GB VRAM, 0 RAM | Inventario RTL; respaldo mientras Quartus compila |
| `qwen-vl` | qwen2.5vl:7b (Ollama) | ~6 GB VRAM | Capturas, diagramas, UI (no hex pixelado ni conteo de ciclos) |
| `codewhale exec` | deepseek-flash (remoto) | — | Timing/protocolos, multi-archivo autónomo, >64K ctx |

**Nota de selección (2026-11-25):** Se reemplazó `Qwen3.6-35B-A3B` (que a 128K dejaba solo 17/256 expertos en VRAM y caía a ~24 tok/s con timeouts en Hermes) y se descartó `Qwen3.8-Flash-Next IQ3_S` (~51 GB RAM → pausas de GPU y HTTP 503 bajo carga). `Inkling-2-Mini SQ-15` corre a **~62–78 tok/s** constantes 100% en VRAM con ~45 GB de RAM libre. Usar `reasoning_effort=none` para resúmenes/preguntas rápidas y `low` para generación/edición de código (con `max_tokens >= 4096`).

**La VRAM es exclusiva:** Strata u Ollama, nunca ambos. `strata-local start` descarga Ollama solo; antes de `qwen-rtl`/`qwen-vl` hacer `strata-local stop`.

## 2. Cuándo usar cada uno

1. `strata-local status`. Si está ACTIVO → Strata para tareas acotadas. Si no, y no hay Quartus/memtester y hay ≥24 GB RAM libre, se puede arrancar (`strata-local start`) para lotes; si hay compilación en curso → `qwen-rtl` (no usa RAM) o codewhale.
2. **Strata (`strata-local ask`)** — una tarea, uno o pocos archivos, ≤32K tokens, salida que Claude revisará:
   - `--sum -f a b c` resúmenes de archivos o logs largos antes de que Claude los lea.
   - `--rtl -f mod.sv` inventario estructural (mismas reglas que `qwen-rtl`).
   - `--iac` módulos Terraform/OpenTofu, `tfvars`, Helm values, Ansible, workflows de CI.
   - `--rust` boilerplate de nih-plug: structs `Params`, `Cargo.toml`, `xtask`, GUI (egui/vizia), tests.
   - `--review -f diff.patch` primer pase de revisión (Claude confirma cada hallazgo).
   - Mensajes de commit, docs, traducciones, regex, scripts bash/python sencillos.
3. **codewhale --profile strata** (agente local) solo con `--max-turns 8` o menos y alcance de un archivo. En investigación abierta divaga (medido 2026-11-16: 52 llamadas en 15 min); eso va a DeepSeek.
4. **codewhale (deepseek-flash)** — timing ciclo a ciclo, CDC, protocolos de bus, lógica de testbench, refactors multi-archivo, contexto >32K, depuración que requiere ejecutar comandos.
5. **Claude se queda con:** arquitectura, decisiones, `.sdc`/`.qsf`/timing closure, JSON de openFPGA, diseño DSP y seguridad realtime en Rust (`unsafe`, lock-free, SIMD), IAM/red/seguridad en cloud, y la verificación final.

## 3. Reglas por dominio

### FPGA (openFPGA / Cyclone V)
- Local solo estructural: puertos, parámetros, FSM, dependencias, esqueletos de TB. Nada de timing, fases de reloj ni protocolos (medido 2026-11-17, `psk_sram.sv`).
- Verificar: `verilator --lint-only`, `iverilog`, `quartus_sh --flow compile`. **Detener Strata antes de compilar Quartus** (`strata-local stop`) y no afinar Strata mientras compila.

### DevOps / IaC / FinOps
- Ver además las skills `multicloud-iac-architect` y `multicloud-finops-costing`. Strata reemplaza a `qwen3:14b`/`Qwen2.5-Coder-14B` para generación cotidiana cuando está activo; nunca inventa precios (siempre `infracost breakdown`).
- Verificar: `terraform fmt -check -recursive && terraform validate` (o `tofu`), `tflint`, `helm lint`, `ansible-lint`, `actionlint`.

### Rust VST3/CLAP (nih-plug)
- Delegar boilerplate y andamiaje; el contenido de `process()` lo revisa Claude: sin asignaciones, locks, I/O ni `println!` en el hilo de audio; parámetros con smoothers/atómicos.
- Verificar: `cargo fmt --check`, `cargo clippy --all-targets -- -D warnings`, `cargo test`, `cargo xtask bundle <plugin> --release`, y si existe `clap-validator validate` / `pluginval`.

## 3b. Medido el 2026-11-18 (Qwen3.6-35B-A3B UD-Q4_K_XL, 81/256 expertos por capa en VRAM)

- Velocidad: ~80 tok/s de salida, ~3,500 tok/s de lectura de prompt. **`ask` usa `reasoning_effort=none` por defecto**: con razonamiento el modelo gastaba ~3,000 tokens ocultos (47 s → 5.6 s al quitarlo). `--think` solo cuando la tarea lo amerite.
- **RTL (`--rtl`, `sound_i2s.sv`):** inventario correcto (puertos, parámetros, relojes, instancia `sync_fifo`, señal sin uso `audgen_nextsamp`). Fiable para estructura.
- **IaC (`--iac`, S3 en AWS v5):** recursos separados correctos (versioning, SSE, public access block, lifecycle). `terraform fmt -check` y `terraform validate` (v1.15.9) pasaron sin cambios. Le faltó el bloque `provider` con `default_tags`: revisar que cumpla todo lo pedido.
- **Rust/nih-plug (`--rust`):** **sin contexto inventa la API** (PluginSettings, AudioBuffers, CLAP_ID…), incluso con `--think`. Con un archivo real de nih-plug pasado con `-f` acierta la estructura, pero aún inventó 2 llamadas (`formatters::s2v_f32_rounded`, `buffer.as_mut()`) y la ley de paneo salió mal (con pan=0 el canal derecho quedaba mudo). Regla: pasar siempre con `-f` un archivo real del proyecto o de `~/.cargo/git/checkouts/nih-plug-*/*/plugins/examples/`, compilar con `cargo check` y la matemática DSP la revisa Claude.

## 3c. Depuración FPGA larga (medido 2026-11-18, LittleInstinct / cpu_pocket.vhd)

Lección: en una sesión de depuración Claude delegó casi nada y gastó tokens leyendo archivos que Strata podía resumir. Patrón obligatorio desde ahora:

**Ciclo de trabajo con Quartus**
1. Al empezar análisis/simulación: `strata-local status`; si no hay Quartus, `strata-local start` en background.
2. Antes de `quartus_sh` / `tools/build_*.sh`: `strata-local stop`.
3. Mientras el usuario prueba en hardware o se espera resultado: volver a arrancarlo para el siguiente lote.

**Delegar a Strata por defecto (sin pedir permiso):**
- "¿Qué señal/campo es X?" en archivos de >150 líneas: extraer el rango con `sed -n` a un archivo y `--sum -f`. Funcionó bien (mapa de filas del overlay `ki_debug_screen.sv` → señales `d_*`). **Pasar el rango completo**: lo que no está en el fragmento lo marca "Not in snippet", no lo deduce.
- Resumir logs de Quartus/GHDL/sim (`--sum`): solo warnings nuevos, timing (slack por esquina), recursos, errores.
- Scripts desechables: parseo de traces, sweeps, generadores de ROM/estímulos sencillos, conversiones hex/bin. Claude los ejecuta y verifica la salida.
- Mensajes de commit, comentarios de código, notas de release, CHANGELOG.

**`--review` en RTL: solo con contexto completo y pregunta concreta.**
- Con un diff parcial (solo hunks) dio 3 de 3 hallazgos FALSOS: "writeena nunca se activa" (la línea estaba fuera del hunk), "write_done llega un ciclo tarde" (era combinacional), "deadlock" (no lo hay). Regla: pasar el `process` completo o el archivo, y preguntar algo específico ("¿hay ruta donde stall4 no se libere si X?"). Sus hallazgos son hipótesis: Claude confirma cada uno con grep/sim antes de citarlo.
- No sirve para pipeline hazards, forwarding, stalls ciclo a ciclo (confirmado otra vez): eso es Claude o codewhale.

**codewhale (deepseek-flash) en FPGA:** dar un testbench existente que ya funcione para modificar, nunca pedir uno desde cero (2026-11-18: escribió un bench que nunca corrió — se colgaba en el fetch — y su ranking de causas fue erróneo). Pedir salida verificable (comando + PASS/FAIL esperado).

**No delegar pruebas de mutación de RTL mientras Quartus compila**: un agente que edita temporalmente un `.sv`/`.vhd` (mutante para demostrar que un test "tiene dientes") puede coincidir con la lectura de fuentes de Analysis & Synthesis y el bitstream sale con el mutante. 2026-11-18: hubo que recompilar V192 por esto. Pedir el mutante sobre una copia, o lanzarlo después de que termine la síntesis (`*.map.rpt` escrito).

**Visión:** las capturas del overlay de depuración (fuente pixelada 320x240) las lee Claude directamente; `qwen-vl` no es fiable para hex.

## 4. Invocación

> Para el detalle de **cómo pasar archivos** (siempre `-f`, revisión con bloque completo, verificación por dominio, antipatrones medidos) usar la skill **`qwen-file-handoff`**. Esa es la referencia; esta sección es el resumen.

```bash
strata-local status | start | stop | logs | plan
strata-local ask --sum  -f src/lib.rs -f src/dsp.rs "qué expone y qué riesgos ves"
strata-local ask --rtl  -f rtl/core_top.sv
strata-local ask --iac  "módulo Terraform AWS VPC 3 AZ con tags FinOps"
strata-local ask --rust -f src/lib.rs "añade un parámetro FloatParam 'drive' 0..24 dB con smoother"
git diff | strata-local ask --review
codewhale --profile strata exec --max-turns 6 --auto --sandbox read-only "<un archivo, una pregunta>"
codewhale exec --auto --sandbox workspace-write "<prompt con criterios de verificación>"
```

## 5. Verificación (obligatoria)

Toda salida local o de DeepSeek es borrador: Claude lee el resultado o el `git diff`, ejecuta el linter/test del dominio y solo entonces reporta. Si la salida local es incorrecta dos veces seguidas en una tarea, escalar a codewhale o hacerla en Claude.

## 6. Seguridad operativa

- `strata-local start` se niega si corre `memtester` o Quartus, o si hay <24 GB de RAM disponible (`--force` solo con permiso del usuario).
- 2026-11-17 Strata se retiró tras un archivo corrupto en btrfs; se reinstaló el 2026-11-18 por pedido del usuario. Si vuelve a aparecer corrupción (`dmesg | grep -i btrfs`, `btrfs scrub status /`), detener Strata y avisar al usuario.
- No combinar `--tune` con otros cambios de opciones. Afinar aparte: `strata launch --preset daily --tune quick --save-preset daily` con la máquina en reposo.
- No usar `pkill -f 'codewhale ...'` ni `pkill -f strata` desde Bash; matar por PID.

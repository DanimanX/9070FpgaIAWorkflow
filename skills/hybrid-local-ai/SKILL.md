---
name: hybrid-local-ai
description: Flujo híbrido para ahorrar tokens de Claude delegando trabajo acotado a modelos locales en la RX 9070 XT (Strata con Qwen3.6-35B-A3B, Ollama qwen-rtl / qwen-vl) y a codewhale (deepseek-flash). Usar en tareas cotidianas de FPGA (openFPGA/Quartus), DevOps/IaC (Terraform, K8s/Helm, Ansible, CI/CD) y plugins de audio VST3/CLAP en Rust (nih-plug), o cuando el usuario pida ahorrar tokens, resumir/leer muchos archivos o generar boilerplate.
---

# Flujo híbrido Claude + Strata + Ollama + codewhale

Claude es el arquitecto: decide, revisa y verifica. Los modelos locales hacen el trabajo acotado (0 tokens cloud) y DeepSeek hace el trabajo delegable que exige razonamiento o mucho contexto.

## 1. Inventario (RX 9070 XT 16 GB VRAM, 64 GB RAM, Arch)

| Herramienta | Modelo | Memoria | Para qué |
| --- | --- | --- | --- |
| `strata-local ask` | Qwen3.6-35B-A3B UD-Q4_K_XL (Strata, MoE 3B activos, 32K ctx, puerto 8080) | VRAM completa + ~12–16 GB RAM | Minion diario general: código, IaC, Rust, resúmenes, español |
| `qwen-rtl` | qwen2.5-coder-14b-fpga (Ollama Vulkan) | ~16 GB VRAM, 0 RAM | Inventario RTL; respaldo mientras Quartus compila |
| `qwen-vl` | qwen2.5vl:7b (Ollama) | ~6 GB VRAM | Capturas, diagramas, UI (no hex pixelado ni conteo de ciclos) |
| `codewhale exec` | deepseek-flash (remoto) | — | Timing/protocolos, multi-archivo autónomo, >32K ctx |

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

## 4. Invocación

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

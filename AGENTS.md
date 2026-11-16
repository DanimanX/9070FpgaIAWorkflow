# Reglas de Proyecto: openFPGA + Intel Quartus Prime

## 1. Enrutamiento de Modelos (`agy`)

### Usar `local-fpga` (Strata `Qwen3.6-35B-A3B` en RX 9070 XT):
- Generación y mantenimiento de **testbenches** (SystemVerilog / VHDL) y scripts para Verilator o Questa.
- **Módulos auxiliares:** contadores, divisores de frecuencia, registros de desplazamiento, tablas LUT (`.mif` / `.hex`) y mapeo de controles (`cont1_key`).
- **Corrección rápida de warnings** de Quartus (`width mismatch`, señales sin conectar, inferencia de registros).
- Scripts de automatización (`Makefile`, `build.sh`, empaquetado de `.rbf`).

### Escalar a `cloud-pro` (Hydrogen Pro):
- Diseño de **arquitectura RTL**, pipelines de vídeo/audio, controladores SDRAM/CRAM y decodificación de buses.
- **Cruces de dominio de reloj (CDC):** FIFOs asíncronos (`dcfifo`) y sincronizadores multi-etapa entre relojes de sistema y `video_rgb_clock`.
- Configuración de plataforma **openFPGA** (`core.json`, `video.json`, `data.json`, `interact.json`), pines (`.qsf`) y restricciones **TimeQuest** (`.sdc`).
- Diagnóstico profundo de reportes `.sta.rpt` y `.fit.rpt` para resolución de *Timing Closure*.

---

## 2. Reglas Estrictas de Síntesis (Intel Cyclone V / Quartus Prime)
1. **Target Hardware:** Intel Cyclone V (ej. `5CEBA4F23C8` / `5CEFA7F27C8`). Prohibido usar primitivas o directivas de Xilinx/Vivado (`BUFG`, `MMCME2`, `XPM_*`).
2. **Primitivas Intel:** Instanciar megafunciones estándar (`altpll`, `altsyncram`, `dcfifo`) o utilizar inferencia RTL limpia reconocida por `quartus_map`.
3. **Cero Latches:** Toda lógica combinacional (`always_comb` en SV o `process` combinacional en VHDL) debe asignar un valor por defecto a todas sus salidas al inicio del bloque o cubrir todas las ramas `if`/`case`.
4. **Interfaz openFPGA:** Respetar los puertos estándar de `core_top` (`bridge_*`, `video_rgb`, `video_hs`, `video_vs`, `video_de`, `video_skip`, `audio_l`, `audio_r`).
5. **Validación:** Antes de dar por cerrado un cambio RTL complejo, indicar el comando de verificación correspondiente (`verilator --lint-only` o `quartus_sh --flow compile`).

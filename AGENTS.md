# Project Rules: openFPGA + Intel Quartus Prime

## 0. Hybrid Local Minion: Strata (all domains)

- **`strata-local ask`** (Strata `0.1.67`, Inkling-2-Mini SQ-15, 26.4B MoE / 3.4B active, 64K ctx, `http://127.0.0.1:8080/v1`, 100% VRAM + ~0.4 GB RAM, ~62–78 tok/s) is the default local minion for bounded work in **FPGA, DevOps/IaC and Rust VST3/CLAP**: summaries (`--sum`), structural RTL inventory (`--rtl`, same limits as `qwen-rtl`), IaC boilerplate (`--iac`), nih-plug boilerplate (`--rust`), first-pass reviews (`--review`).
- **Rules learned from benchmarking:** **always `max_tokens >= 4096`** (with 1024 it burns the budget thinking and returns empty `content`); use `reasoning_effort=none` for fast `ask` summaries and `reasoning_effort=low` for code/agent tasks (`hermes` / `codewhale --profile strata`). Always pass `-f` a real file for Rust/nih-plug.
- **VRAM is exclusive** between Strata and Ollama (`qwen-rtl`, `qwen-vl`). **Stop the local minion before Quartus compiles** (`strata-local stop`); during compiles use `qwen-rtl` (VRAM only, no system RAM).
- Agent use only as `codewhale --profile strata exec --max-turns 8` or `hermes chat -q "..." --oneshot`, one file / one routine at a time (`--parallel 1`). Full rules: [`skills/hybrid-local-ai/SKILL.md`](./skills/hybrid-local-ai/SKILL.md).

## 1. Model Routing (`qwen-rtl` & `codewhale`)

### Use local `qwen-rtl` (`qwen2.5-coder-14b-fpga` via Ollama Vulkan on RX 9070 XT, 100% GPU) ONLY for structural / inventory work:
- **RTL reading & structural auditing:** summarizing ports, parameters, clock/reset domains, FSM state lists, dependencies, and lint-style checks (latches, width mismatches) (`qwen-rtl --audit -f <file>`).
- **Testbench skeletons & boilerplate:** SystemVerilog/Verilog (`qwen-rtl --tb -f <file>`) and `cocotb` (`qwen-rtl --cocotb -f <file>`), where Claude or `codewhale` (`deepseek-flash`) fills in timing-dependent checks.
- **Auxiliary modules:** counters, frequency dividers, shift registers, LUT tables (`.mif` / `.hex`), and controller mapping (`cont1_key`).
- **Quick fixes for Quartus warnings** (`width mismatch`, unconnected signals, register inference) and automation scripts (`Makefile`, `build.sh`, `.rbf` packaging).
- **Strict Boundary:** **Do NOT use Qwen for timing, cycle-by-cycle behaviour of registered logic, clock/phase reasoning, or bus protocols** (measured 2026-11-17 on `psk_sram.sv`: structural inventory was accurate, but the cycle trace ignored the one-clock register delay and invented `OE#`/bus contention).

### Escalate to Remote (`codewhale` `deepseek-flash` / Claude Code):
- **Timing & protocol reasoning:** cycle-by-cycle analysis of registered logic, protocol/waveform reasoning, and testbench checking logic.
- Autonomous read-only audits (`codewhale exec --auto --sandbox read-only`), multi-file edits (`codewhale exec --auto --sandbox workspace-write`), or contexts exceeding 32K tokens.
- **RTL architecture** design, video/audio pipelines, SDRAM/CRAM controllers, and bus decoding.
- **Clock Domain Crossing (CDC):** asynchronous FIFOs (`dcfifo`) and multi-stage synchronizers between system clocks and `video_rgb_clock`.
- **openFPGA** platform configuration (`core.json`, `video.json`, `data.json`, `interact.json`), pinouts (`.qsf`), and **TimeQuest** constraints (`.sdc`).
- In-depth analysis of `.sta.rpt` and `.fit.rpt` reports for *Timing Closure* resolution.

---

## 2. Strict Synthesis Rules (Intel Cyclone V / Quartus Prime)
1. **Target Hardware:** Intel Cyclone V (e.g., `5CEBA4F23C8` / `5CEFA7F27C8`). Strictly forbidden to use Xilinx/Vivado primitives or directives (`BUFG`, `MMCME2`, `XPM_*`).
2. **Intel Primitives:** Instantiate standard megafunctions (`altpll`, `altsyncram`, `dcfifo`) or use clean RTL inference recognized by `quartus_map`.
3. **Zero Latches:** All combinational logic (`always_comb` in SV or combinational `process` in VHDL) must assign a default value to all outputs at the beginning of the block or cover all `if`/`case` branches.
4. **openFPGA Interface:** Adhere to standard `core_top` ports (`bridge_*`, `video_rgb`, `video_hs`, `video_vs`, `video_de`, `video_skip`, `audio_l`, `audio_r`).
5. **Validation:** Before finalizing a complex RTL change, provide and run the corresponding verification command (`verilator --lint-only` or `quartus_sh --flow compile`).

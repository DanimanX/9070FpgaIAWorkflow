# Project Rules: openFPGA + Intel Quartus Prime

## 1. Model Routing (`codewhale`)

### Use `local-fpga` (`codewhale --profile strata` / Strata `Qwen3.8-Flash-Next Coder IQ1_M` on RX 9070 XT):
- Generation and maintenance of **testbenches** (SystemVerilog / VHDL) and scripts for Verilator or Questa.
- **Auxiliary modules:** counters, frequency dividers, shift registers, LUT tables (`.mif` / `.hex`), and controller mapping (`cont1_key`).
- **Quick fixes for Quartus warnings** (`width mismatch`, unconnected signals, register inference).
- Automation scripts (`Makefile`, `build.sh`, `.rbf` packaging).

### Escalate to Cloud / Remote (`deepseek-flash` or Hydrogen Pro):
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
5. **Validation:** Before finalizing a complex RTL change, provide the corresponding verification command (`verilator --lint-only` or `quartus_sh --flow compile`).

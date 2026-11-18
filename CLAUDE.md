# Claude Code Project Instructions

Follow all rules in [`AGENTS.md`](./AGENTS.md).

## Token-Saving Delegation via `qwen-rtl` & `codewhale`

To save Claude tokens on this project, offload heavy reading, structural inventories, and delegable tasks via `Bash`:

- **Use `qwen-rtl` ONLY for structural / inventory work** (local `qwen2.5-coder-14b-fpga` via Ollama Vulkan on RX 9070 XT, ~16 GB VRAM with 32K ctx, 0 cloud tokens, direct stdin/CLI without tool-calling overhead):
  - Inventories and summaries of RTL modules (`.sv`, `.v`, `.vhd`): ports, parameters, clocks/resets, FSM state lists, dependencies, and lint-style checks (latches, width mismatches): `qwen-rtl --audit -f <file>`
  - Boilerplate, auxiliary modules (counters, dividers, shift registers, LUTs, `cont1_key` mapping), and **testbench skeletons** (Claude or DeepSeek fills in timing-dependent checks): `qwen-rtl --tb -f <file>`, `qwen-rtl --cocotb -f <file>`
  - Focused questions via stdin or files: `qwen-rtl -f <file> "<focused question>"`
  - Manage VRAM lifecycle: `qwen-local status`, `qwen-local subir`, `qwen-local bajar` (free VRAM after batch work).
  - **Do NOT use Qwen for timing, cycle-by-cycle behaviour of registered logic, clock/phase reasoning, or bus protocols.** (Measured 2026-11-17 on `psk_sram.sv`: structural inventory was accurate, but the cycle trace was wrong — it ignored the one-clock register delay and invented `OE#`/bus contention.)
- **Use `qwen-vl` for local image/screenshot analysis** (`qwen2.5vl:7b` on Ollama Vulkan, ~6.2 GB VRAM with `num_ctx=16384`, 0 cloud tokens):
  - General UI captures, block diagrams/schematics, and crisp normal-font text/logs: `qwen-vl --ocr -f img.png`, `qwen-vl --diagram -f img.png`, `qwen-vl --ui -f img.png`.
  - Automatically unloads `qwen2.5-coder-14b-fpga` before running and uses `keep_alive=60s` (pass `--restore` to reload the 14B coder afterward).
  - **Do NOT use `qwen-vl` for exact hex/register OCR in pixelated console/Analogue Pocket fonts or cycle-by-cycle waveform counting** in GTKWave/SignalTap captures. (Measured 2026-11-17 on `IMG_20261115_172933.jpg`: `qwen2.5vl:7b` extracted all 15 lines, but misread similar pixelated hex glyphs such as `8`/`0`, `D`/`0`, `V`/`U`, `HDD`/`ABBT`, `PC`/`PLX`.) Inspect those directly in Claude or export `.vcd`/`.csv`.
- **Use `codewhale` (default profile `deepseek-flash`)** for everything delegable that Qwen must not do:
  - Timing / cycle-level analysis, protocol and waveform reasoning, and testbench checking logic.
  - Autonomous multi-file tool-calling (`read`/`edit`/`bash`) and context exceeding ~32K tokens.
  - Claude still makes the final diagnosis and decisions and verifies DeepSeek's output against the code and simulations.
  - Note: Do **not** use `codewhale --profile qwen exec` for autonomous tool-calling (Ollama's Go template parser does not unwrap Qwen2.5-Coder's fenced JSON tool calls); use `qwen-rtl` instead for local work.
- **Keep in Claude** (high-value architectural reasoning & final verification):
  - Complex RTL architecture, CDC (`dcfifo`), openFPGA platform JSONs, `.qsf`/`.sdc` constraints, `.sta.rpt` timing closure, and final verification against code and simulations (`verilator --lint-only`, `iverilog`, `quartus_sh`).

### Quick Invocation
```bash
# Check / preload / unload local VRAM
qwen-local status
qwen-local subir
qwen-local bajar

# Local RTL structural audit, testbench skeleton & focused question
qwen-rtl --audit -f rtl/mod.sv
qwen-rtl --tb -f rtl/mod.sv > tb/tb_mod.sv
qwen-rtl -f rtl/mod.sv "<focused question>"

# Remote read-only audit / large multi-file analysis (deepseek-flash)
codewhale exec --auto --sandbox read-only "<focused prompt with file paths/line ranges>"

# Remote workspace edits / refactoring (deepseek-flash)
codewhale exec --auto --sandbox workspace-write "<focused prompt with verification criteria>"

# Resume a previous Codewhale session
codewhale exec --resume <SESSION_ID> --auto --sandbox workspace-write "<follow-up>"
```

### Verification Rule
After writing or generating any code/testbench (via `qwen-rtl` or `codewhale`):
1. Inspect the output / `git diff` to verify correctness.
2. Run relevant linters/tests (e.g., `verilator --lint-only`, `iverilog`, `quartus_sh`).
3. Summarize the verified result concisely to the user.

### Operational Notes
- **Do NOT use `pkill -f 'codewhale ...'` from Bash:** the pattern matches the shell itself and kills it (exit 144). Kill by PID instead.

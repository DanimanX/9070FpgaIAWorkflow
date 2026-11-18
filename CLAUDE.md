# Claude Code Project Instructions

Follow all rules in [`AGENTS.md`](./AGENTS.md).

## Token-Saving Delegation via `qwen-rtl` & `codewhale`

To save Claude tokens on this project:
- **Delegate to `qwen-rtl`** (local `qwen2.5-coder-14b-fpga` via Ollama Vulkan on RX 9070 XT, 0 cloud tokens, direct stdin/CLI without tool-calling overhead) for:
  - Reading/auditing large RTL files or logs (`qwen-rtl --audit -f <file>`)
  - Generating SystemVerilog/Verilog testbenches (`qwen-rtl --tb -f <file>`) or `cocotb` (`qwen-rtl --cocotb -f <file>`)
  - Auxiliary modules (counters, dividers, shift registers, LUTs, `cont1_key` mapping)
  - Quick fixes for Quartus warnings (`width mismatch`, unconnected signals, register inference)
- **Use `codewhale`** (default `deepseek-flash`) when autonomous multi-file tool-calling (`read`/`edit`/`bash`) or >32K token context is needed.
  - Note: Do **not** use `codewhale --profile qwen exec` for autonomous tool-calling (Ollama's Go parser does not unwrap Qwen2.5-Coder's fenced JSON tool calls); use `qwen-rtl` instead for local work.
- **Keep in Claude** (high-value architectural reasoning & verification):
  - Complex RTL architecture, CDC (`dcfifo`), openFPGA platform JSONs, `.qsf`/`.sdc` constraints, `.sta.rpt` timing closure, and running `verilator --lint-only` / `quartus_sh`.

### Quick Invocation
```bash
# Check / preload local VRAM
qwen-local status
qwen-local subir

# Local RTL audit & testbench generation
qwen-rtl --audit -f rtl/mod.sv
qwen-rtl --tb -f rtl/mod.sv > tb/tb_mod.sv

# Remote autonomous edit (deepseek-flash)
codewhale exec --auto --sandbox workspace-write "<prompt>"
```

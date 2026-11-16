# Claude Code Project Instructions

Follow all rules in [`AGENTS.md`](./AGENTS.md).

## Token-Saving Delegation via `codewhale`

To save Claude tokens on this project:
- **Delegate to `codewhale --profile strata`** (local **Strata** `Qwen3.8-Flash-Next Coder IQ1_M` on RX 9070 XT, 0 cloud tokens) for:
  - Reading/analyzing large RTL files or logs
  - Generating/maintaining testbenches (SystemVerilog / VHDL) and Verilator/Questa scripts
  - Auxiliary modules (counters, dividers, shift registers, LUTs, `cont1_key` mapping)
  - Quick fixes for Quartus warnings (`width mismatch`, unconnected signals, register inference)
  - Build/packaging scripts (`Makefile`, `build.sh`, `.rbf`)
- **Fallback to `codewhale`** (default `deepseek-flash`) if Strata (`http://127.0.0.1:8080/v1`) is not running.
- **Keep in Claude** (high-value architectural reasoning):
  - Complex RTL architecture, CDC (`dcfifo`), openFPGA platform JSONs, `.qsf`/`.sdc` constraints, and `.sta.rpt` timing closure.

### Quick Invocation
```bash
# Check if Strata is ready
curl -sf http://127.0.0.1:8080/v1/models >/dev/null 2>&1

# Read-only analysis
codewhale --profile strata exec --auto --sandbox read-only "<prompt>"

# Workspace edit + verify git diff
codewhale --profile strata exec --auto --sandbox workspace-write "<prompt>"
```

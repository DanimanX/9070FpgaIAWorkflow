# Claude Code Project Instructions

Follow all rules in [`AGENTS.md`](./AGENTS.md). The hybrid delegation workflow is defined in the skill [`hybrid-local-ai`](./skills/hybrid-local-ai/SKILL.md) (installed at `~/.claude/skills/hybrid-local-ai/`); load it whenever delegating. It covers **FPGA, DevOps/IaC/FinOps and Rust VST3/CLAP plugins**.

## Hybrid Delegation: RustingStrata + `qwen-rtl` / `qwen-vl` + `codewhale`

Claude is the lead architect: it decides, reviews and verifies. Bounded work goes local (0 cloud tokens); delegable reasoning and large context go to `codewhale`.

- **RustingStrata (`strata-local ask`) — default local minion** (RustingStrata 1.3.7 Vulkan, `Qwen3.6-35B-A3B UD-Q4_K_XL`, 35B MoE / 3B active, 32K ctx, `http://127.0.0.1:8080/v1` alias `qwen3.6-35b-a3b`, ~88% experts in VRAM + CPU experts, ~0.2 GB RAM + ~21 GB reclaimable page cache, ~100–130 tok/s; switched from Inkling on 2026-11-26, see README benchmark):
  - Summaries of files/logs (`--sum`), structural RTL inventory (`--rtl`), Terraform/Helm/Ansible/CI boilerplate (`--iac`), nih-plug boilerplate (`--rust`), first-pass reviews (`--review`), commit messages and docs.
  - Defaults: `ask` runs with thinking off (`enable_thinking=false`; `--think` opts in); Hermes and `codewhale --profile strata` use `reasoning_effort=low` (`max_tokens >= 4096`). **Rust: always pass a real nih-plug file with `-f`** (without it the API is invented) and verify with `cargo check` — DSP math stays in Claude.
  - Lifecycle: `strata-local status | start | stop | logs | plan | calibrate`. `start` unloads Ollama and refuses while Quartus or `memtester` run or with <16 GB RAM available. **Stop the minion before Quartus compiles.** Fallback: `STRATA_ENGINE=inkling strata-local start` (Inkling-2-Mini SQ-15, 100% VRAM, 64K ctx; `codewhale --profile inkling`).
  - If `strata-local logs` shows hundreds of `timed out and resumed` waits, NaN logits, or `dmesg` shows an amdgpu reset: switch to the Inkling fallback and tell the user.
  - As an agent: `codewhale --profile strata exec --max-turns 8 ...` or `hermes chat -q "..." --oneshot`, one file / one routine at a time (`--parallel 1`).
- **`qwen-rtl` (Ollama Vulkan, `qwen2.5-coder-14b-fpga`, VRAM only)** — structural RTL inventory and TB skeletons when the local minion is down, especially **during Quartus compiles** (it uses no system RAM): `qwen-rtl --audit|--tb|--cocotb -f <file>`; VRAM with `qwen-local status|subir|bajar`.
- **`qwen-vl` (`qwen2.5vl:7b`)** — UI captures, diagrams, crisp text: `qwen-vl --ocr|--diagram|--ui -f img.png`. Not for pixelated hex/register fonts or waveform cycle counting (measured 2026-11-17 on `IMG_20261115_172933.jpg`).
- **VRAM is exclusive:** local minion OR Ollama. Run `strata-local stop` before `qwen-rtl` / `qwen-vl`.
- **No local model does timing, cycle-by-cycle behaviour of registered logic, clock/phase reasoning or bus protocols.** (Measured 2026-11-17 on `psk_sram.sv`: structural inventory accurate, cycle trace wrong — ignored the one-clock register delay and invented `OE#`/bus contention.)
- **`codewhale` (default `deepseek-flash`)** — timing/protocol/waveform reasoning, testbench checking logic, CDC, autonomous multi-file edits, >32K context. Do **not** use `codewhale --profile qwen exec` for tool-calling.
- **Keep in Claude:** RTL architecture, CDC (`dcfifo`), openFPGA JSONs, `.qsf`/`.sdc`, `.sta.rpt` timing closure, DSP design and realtime safety in Rust, cloud IAM/network/security, and final verification.

### Quick Invocation
```bash
strata-local status
strata-local start                      # batches only; never during Quartus
strata-local ask --rtl  -f rtl/mod.sv
strata-local ask --iac  "Terraform module: AWS VPC 3 AZ with FinOps tags"
strata-local ask --rust -f src/lib.rs "add FloatParam 'drive' 0..24 dB with smoother"
git diff | strata-local ask --review
strata-local stop                       # before quartus_sh / qwen-rtl / qwen-vl

qwen-rtl --audit -f rtl/mod.sv
qwen-rtl --tb -f rtl/mod.sv > tb/tb_mod.sv

codewhale exec --auto --sandbox read-only "<focused prompt with file paths/line ranges>"
codewhale exec --auto --sandbox workspace-write "<focused prompt with verification criteria>"
codewhale exec --resume <SESSION_ID> --auto --sandbox workspace-write "<follow-up>"
```

### Verification Rule
All local/DeepSeek output is a draft. Inspect the output or `git diff`, then run:
- FPGA: `verilator --lint-only`, `iverilog`, `quartus_sh`.
- IaC: `terraform fmt -check -recursive` + `terraform validate` (or `tofu`), `tflint`, `helm lint`, `ansible-lint`, `actionlint`.
- Rust: `cargo fmt --check`, `cargo clippy --all-targets -- -D warnings`, `cargo test`, `cargo xtask bundle <plugin> --release`.
If a local model is wrong twice on the same task, escalate to `codewhale` or do it in Claude. Summarize the verified result concisely.

### Operational Notes
- **Do NOT use `pkill -f 'codewhale ...'`, `pkill -f strata` or `pkill -f rustingstrata` from Bash:** the pattern matches the shell itself (exit 144). Kill by PID.
- **Strata & btrfs:** retired 2026-11-17 after a corrupted file on the OS btrfs; reinstalled 2026-11-18 at the user's request. If corruption reappears (`dmesg | grep -i btrfs`, `btrfs scrub status /`), stop Strata and tell the user.
- **Strata (Inkling fallback) tuning:** never combine `--tune` with other option changes; tune separately on an idle machine (`strata launch --preset daily --tune quick --save-preset daily`).

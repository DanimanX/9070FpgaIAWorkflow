---
name: hybrid-local-ai
description: Hybrid AI workflow offloading bounded tasks to the local minion (RustingStrata + Qwen3.6-35B-A3B on RX 9070 XT, Vulkan) and escalating complex/multi-file work to codewhale (deepseek-flash). Use for openFPGA/Quartus, DevOps/IaC (Terraform, Helm, Ansible, CI), and Rust VST3/CLAP (nih-plug) tasks to save cloud tokens.
---

# Hybrid Workflow: Claude + RustingStrata + Hermes + codewhale

Claude acts as the lead architect (design, decisions, final verification). The local minion (**RustingStrata `1.3.7` + `Qwen3.6-35B-A3B`**, `strata-local`) handles bounded tasks at zero cloud cost, and **`codewhale` (`deepseek-flash`)** handles timing-sensitive or multi-file escalation.

## 1. Model Inventory (RX 9070 XT 16 GB VRAM, 64 GB RAM)

| Tool | Model | Memory | Role |
| --- | --- | --- | --- |
| `strata-local ask` | `qwen3.6-35b-a3b` (RustingStrata 1.3.7 Vulkan, Qwen3.6-35B-A3B UD-Q4_K_XL, 35B MoE / 3B active, 128K ctx, `:8080/v1`) | ~15.5 GB VRAM (~6.5k/10.2k experts + q8 KV) + CPU experts; ~0.2 GB RAM + ~21 GB reclaimable page cache | Daily minion (~110–120 tok/s): summaries, structural RTL, IaC/Rust boilerplate, reviews |
| `hermes chat --oneshot` | `qwen3.6-35b-a3b` (`reasoning_effort=low`, 128K ctx) | Same local server | Bounded single-file local tool-calling |
| `claude --model sonnet` | Claude Sonnet (CLI) | — | Mid-tier token-saving cloud delegation for coding, reviews, and bounded reasoning |
| `codewhale exec` | `deepseek-flash` (remote) | — | Timing/protocols, CDC, testbench checks, multi-file edits, >128K ctx |

## 2. Routing Rules

1. **Check status:** Run `strata-local status`. Start with `strata-local start` if idle (refuses if Quartus/`memtester` is running or <16 GB RAM is free). **Always run `strata-local stop` before Quartus compiles (`quartus_sh`).** Fallback engine: `STRATA_ENGINE=inkling strata-local start` (Inkling-2-Mini SQ-15, 64K ctx) if RustingStrata misbehaves (hundreds of `timed out and resumed` in `strata-local logs`, NaN logits, amdgpu reset in `dmesg`).
2. **Use `strata-local ask`** for single-file / bounded tasks (`<=128K` tokens):
   - `--sum -f <files>` — summarize large files, diffs, or Quartus/Verilator build logs.
   - `--rtl -f <mod.sv>` — structural inventory only (ports, parameters, clock/reset domains, FSM states, dependencies).
   - `--iac` — Terraform/OpenTofu modules, Helm values, Ansible, CI workflows.
   - `--rust -f <real_file.rs>` — `nih-plug` boilerplate (`Params`, `Cargo.toml`, `xtask`). Always pass a real project/example file via `-f` so it does not invent APIs.
   - `--review -f <file>` — first-pass review of a complete function/process/file (verify every finding before citing).
3. **Use `codewhale --profile strata --max-turns 8`** only for single-file local agent tasks.
4. **Use `claude --model sonnet`** (e.g., `claude -p "<task>" --model sonnet`) when the local minion is insufficient for code edits or reasoning, to save tokens vs. heavier cloud models.
5. **Escalate to `codewhale` (`deepseek-flash`) or Claude** for cycle-by-cycle timing, clock/phase reasoning, bus protocols, CDC, `.sdc`/`.qsf` timing closure, DSP math, real-time audio-thread safety, or multi-file refactors.

## 3. Invocation

```bash
strata-local status | start | stop | logs | plan | calibrate
strata-local ask --sum  -f src/lib.rs "summarize exports and risks"
strata-local ask --rtl  -f rtl/core_top.sv
strata-local ask --iac  "Terraform AWS VPC module with FinOps tags"
strata-local ask --rust -f src/lib.rs "add FloatParam 'drive' 0..24 dB with smoother"
strata-local ask --review -f rtl/mod.sv "check for latches or missing reset"
hermes chat -q "summarize rtl/core_top.sv" --oneshot
claude -p "refactor module X and add unit tests" --model sonnet
codewhale --profile strata exec --max-turns 8 --auto --sandbox read-only "<single-file task>"
codewhale exec --auto --sandbox workspace-write "<multi-file task with verification criteria>"
```

## 4. Verification & Operational Safety

- Treat all local and remote drafts as unverified until Claude checks the `git diff` and runs domain checks (`verilator --lint-only`, `iverilog`, `quartus_sh`, `terraform fmt -check && terraform validate`, `cargo clippy --all-targets -- -D warnings`, `cargo test`).
- Use `max_tokens >= 4096`; `strata-local ask` runs with thinking off (`enable_thinking=false`; `--think` opts in). Contexts above 128K tokens go to `codewhale`.
- Never use `pkill -f 'codewhale ...'`, `pkill -f strata` or `pkill -f rustingstrata`; `strata-local stop` kills by PID.

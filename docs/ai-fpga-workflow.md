# Hybrid openFPGA + Intel Quartus Prime Development Workflow

Agent-assisted development architecture where **Claude Code** acts as the lead architect, offloading bounded reading, summaries, structural RTL inventory, and boilerplate to **[RustingStrata](https://github.com/RustingStudio/RustingStrata)** (**`Qwen3.6-35B-A3B UD-Q4_K_XL`** on the **RX 9070 XT 16 GB** via **Vulkan**, `1.3.7`), running **Hermes Agent** or `codewhale --profile strata` for bounded local tool-calling, escalating timing/protocol reasoning and autonomous multi-file tasks (>128K context) to **`codewhale`** (`deepseek-flash`), and running local toolchains (**Verilator / Icarus Verilog / Questa / Intel Quartus Prime**) on **64 GB DDR5 RAM**.

---

## 1. Integration Architecture (`Claude Code + RustingStrata + Hermes + codewhale`)

**RustingStrata** serves **`Qwen3.6-35B-A3B`** (128K context, alias `qwen3.6-35b-a3b`) with ~6.5k of 10.2k MoE experts resident in VRAM and the rest computed on the CPU (~0.2 GB process RAM + ~21 GB reclaimable page cache), at **~110–120 tok/s** decode. It replaced Strata + `Inkling-2-Mini SQ-15` on 2026-11-26 after a same-method A/B ([README benchmark](../README.md#benchmark-rustingstrata-vs-strata-on-the-rx-9070-xt)); Inkling remains as fallback (`STRATA_ENGINE=inkling`).

> [!IMPORTANT]
> **Structural-Only Boundary for Local Models:** The local minion (`Qwen3.6-35B-A3B` on RustingStrata, or the Inkling fallback) is used **only** for summaries, structural/inventory work, boilerplate, and first-pass reviews. It must **not** be used for timing, cycle-by-cycle behaviour of registered logic, clock/phase reasoning, or bus protocols. All timing/protocol reasoning routes to `codewhale` (`deepseek-flash`) or Claude Code.

![Strata Hybrid AI Workflow](./assets/strata-hybrid-workflow.gif)

```mermaid
flowchart LR
    Dev(["Developer"]) -->|"Prompt / Objective"| Claude["Claude Code (Lead Architect)"]
    Dev -->|"hermes chat --oneshot (128K ctx)"| Hermes["Hermes Agent<br/>:8080/v1 (reasoning=low)"]

    subgraph LocalGPU["Local Inference - RX 9070 XT (16 GB VRAM)"]
        Strata["RustingStrata 1.3.7 Vulkan: Qwen3.6-35B-A3B<br/>(daily minion: FPGA / IaC / Rust VST, 128K ctx, ~6.5k/10.2k experts in VRAM)"]
    end

    subgraph CloudAPI["Remote Escalation"]
        CW["codewhale (deepseek-flash)<br/>Autonomous multi-file / >128K ctx"]
    end

    subgraph Toolchain["Arch Linux Host (64 GB RAM, CPU-side experts)"]
        FS["Project Repository (RTL / JSON / .qsf / .sdc / *.tf / *.rs)"]
        Sim["Verilator / Questa"]
        Quartus["Intel Quartus Prime (quartus_sh)"]
    end

    Hermes <-->|"OpenAI API (:8080/v1, 128K)"| Strata
    Claude <-->|"strata-local ask (--sum / --rtl / --iac / --rust / --review)"| Strata
    CW -.->|"--profile strata --max-turns 8 (one file)"| Strata
    Claude <-->|"codewhale exec (complex/multi-file)"| CW
    Claude -->|"Applies edits & checks AGENTS.md"| FS
    CW -->|"Autonomous workspace-write"| FS
    Claude -->|"Runs lint & testbenches"| Sim
    Claude -->|"Runs synthesis, Fitter & TimeQuest"| Quartus
```

---

## 2. Process & Interaction Diagram

```mermaid
sequenceDiagram
    actor Dev as Developer
    participant Hermes as Hermes Agent (128K)
    participant Claude as Claude Code (Architect)
    participant Strata as RustingStrata (Qwen3.6-35B-A3B)
    participant CW as codewhale (deepseek-flash)
    participant Tools as Verilator / Quartus / terraform / cargo

    opt Direct Hermes Agent session
        Dev->>Hermes: Runs hermes chat --oneshot (128K context, reasoning=low)
        Hermes->>Strata: OpenAI API (:8080/v1, qwen3.6-35b-a3b)
        Strata-->>Hermes: Response (~110-120 tok/s)
    end

    Dev->>Claude: Requests RTL, IaC or Rust VST change, or build
    Claude->>Claude: Checks AGENTS.md + skill hybrid-local-ai, routes task
    Claude->>Strata: strata-local status

    alt Bounded task and Strata ACTIVE (summary / RTL inventory / IaC / Rust with real -f context / review)
        Claude->>Strata: strata-local ask --sum / --rtl / --iac / --rust / --review (reasoning off)
        Strata-->>Claude: Draft (~2-10 s)
        Claude->>Claude: Reviews draft (Rust: API + DSP math checked by Claude)
    else Timing / Protocol / Multi-file / >128K ctx / CDC / .sdc
        Claude->>CW: Escalates via codewhale exec --sandbox read-only / workspace-write
        CW-->>Claude: Returns analysis, checking logic, constraints, or patch
        Claude->>Claude: Verifies DeepSeek output against code & simulations
    end

    Claude->>Tools: Inspects git diff & runs domain checks
    Note over Tools: FPGA: verilator / iverilog<br/>IaC: terraform fmt + validate<br/>Rust: cargo check / clippy / test

    alt Failure
        Tools-->>Claude: Reports errors
        Claude->>Strata: Requests quick fix with the error as context
        Strata-->>Claude: Corrected snippet (wrong twice -> escalate to CW or Claude)
    else OK (FPGA)
        Claude->>Strata: strata-local stop (free GPU/RAM/page cache)
        Claude->>Tools: Runs quartus_sh --flow compile
        Tools-->>Claude: Returns .fit.rpt, .sta.rpt, and warnings
        opt Timing Violation (Setup/Hold) or Fitter error
            Claude->>Claude: Analyzes .sta.rpt / .fit.rpt for Timing Closure
        end
        Claude-->>Dev: Delivers validated core.rbf / plan / plugin bundle and summary
    end
```

---

## 3. Decision and Synthesis Flow

```mermaid
flowchart TD
    Dev(["Developer / Prompt in Claude Code or Hermes"]) -->|"hermes chat --oneshot (128K)"| Hermes["Hermes Agent (:8080/v1)"]
    Hermes --> Strata
    Dev --> Claude{"Claude Code (AGENTS.md + hybrid-local-ai)"}

    Claude -->|"Timing / Cycle Trace / Bus Protocols / TB Checks / CDC / .sta.rpt / .sdc / >128K"| Arch["Claude Code + codewhale (deepseek-flash)"]
    Claude -->|"Bounded task, Strata ACTIVE: summaries / RTL inventory / IaC / Rust (with -f context) / reviews"| Strata["RustingStrata - Qwen3.6-35B-A3B (Vulkan, ~110-120 tok/s, 128K)"]

    Arch --> Code["Source: rtl/*.sv | core.json | .sdc | .qsf | *.tf | Helm | src/*.rs"]
    Strata --> Code

    Code --> Domain{"Domain?"}
    Domain -->|"IaC"| TF["terraform fmt -check + validate / tflint / helm lint"]
    Domain -->|"Rust VST"| Cargo["cargo check / clippy -D warnings / test / xtask bundle"]
    TF -->|"Fails"| Strata
    Cargo -->|"Fails (API / DSP)"| Arch
    TF -->|"OK"| Done(["Verified result to Developer"])
    Cargo -->|"OK"| Done

    Domain -->|"FPGA"| Sim{"Unit Simulation?"}
    Sim -->|"Yes"| Verilator["Verilator / Questa"]
    Verilator -->|"Logic failure"| Strata
    Verilator -->|"OK"| Stop["strata-local stop (free GPU + RAM)"]
    Sim -->|"No / Direct to HW"| Stop
    Stop --> Quartus["Intel Quartus Prime (quartus_sh) - Synthesis, Fitter & TimeQuest"]

    Quartus --> Check{"Compilation Result?"}
    Check -->|"Setup/Hold violation or Fitter error"| Arch
    Check -->|"Timing Clean & Bitstream OK"| Bitstream(["core.rbf ready for Analogue Pocket / openFPGA"])
```

---

## Hardware Resource Allocation (Arch Linux)

| Component | Allocated Resource | Role in Pipeline |
| :--- | :--- | :--- |
| **AMD RX 9070 XT (16 GB)** | ~15.5 GB VRAM | **RustingStrata** (`Qwen3.6-35B-A3B`, ~6.5k of 10.2k experts + q8 KV 1.36 GB in VRAM, 128K ctx) via `strata-local`, Hermes Agent, or `codewhale --profile strata` |
| **Intel i7-14700KF / i9-14900K** | CPU Compute | CPU-side MoE experts while the minion runs; RTL simulation (Verilator/Questa) and Quartus Place & Route |
| **64 GB DDR5 RAM** | ~0.2 GB + ~21 GB reclaimable page cache (GGUF) | Free for Quartus once the cache is reclaimed; still stop the minion before Quartus compiles |
| **Claude Code + `codewhale`** | Remote API | Lead architecture, CDC, `.sdc`, `.sta.rpt` / `.fit.rpt` analysis, and multi-file edits (`deepseek-flash`) |

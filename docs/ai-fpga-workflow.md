# Hybrid openFPGA + Intel Quartus Prime Development Workflow

Agent-assisted development architecture where **Claude Code** acts as the lead architect, offloading structural RTL reading and testbench skeletons to **`qwen-rtl`** (**`qwen2.5-coder-14b-fpga`** running 100% on **RX 9070 XT 16 GB VRAM** via **Ollama Vulkan**), escalating timing/protocol reasoning and autonomous multi-file tasks (>32K context) to **`codewhale`** (`deepseek-flash`), and running local toolchains (**Verilator / Icarus Verilog / Questa / Intel Quartus Prime**) on **i7-14700KF + 64 GB DDR5 RAM**.

---

## 1. Integration Architecture (`Claude Code + qwen-rtl + codewhale`)

**Ollama Vulkan** serves **`qwen2.5-coder-14b-fpga`** (`Q5_K_M`, 32K context) 100% in VRAM. **`qwen-rtl`** sends RTL files/stdin directly to Ollama's `/api/chat` endpoint and returns structural summaries or testbench skeletons to Claude Code, avoiding tool-calling overhead while keeping all ~62 GB of system RAM free for Quartus Prime.

> [!IMPORTANT]
> **Structural-Only Boundary for `qwen-rtl`:** Qwen is used **only** for structural/inventory work, boilerplate, and testbench skeletons. It must **not** be used for timing, cycle-by-cycle behaviour of registered logic, clock/phase reasoning, or bus protocols (measured 2026-11-17 on `psk_sram.sv`: structural inventory was accurate, but its cycle trace ignored the one-clock register delay and invented `OE#`/bus contention). All timing/protocol reasoning routes to `codewhale` (`deepseek-flash`) or Claude Code.

```mermaid
flowchart LR
    Dev(["Developer"]) -->|"Prompt / Objective"| Claude["Claude Code (Lead Architect)"]

    subgraph LocalGPU["Local Inference - RX 9070 XT (16 GB VRAM, Swapped)"]
        Strata["Strata HIP: Qwen3.6-35B-A3B UD-Q4_K_XL<br/>(daily minion: FPGA / IaC / Rust VST, 32K ctx, VRAM+RAM)"]
        Qwen["Ollama Vulkan: qwen2.5-coder-14b-fpga<br/>(Q5_K_M, 100% GPU, 32K ctx)"]
        QwenVL["Ollama Vulkan: qwen2.5vl:7b<br/>(Vision OCR/Diagrams/UI, ~5.4 GB, 60s TTL)"]
    end

    subgraph CloudAPI["Remote Escalation"]
        CW["codewhale (deepseek-flash)<br/>Autonomous multi-file / >32K ctx"]
    end

    subgraph Toolchain["Arch Linux Host (i7-14700KF + 64 GB RAM)"]
        FS["openFPGA Repository (RTL / JSON / .qsf / .sdc)"]
        Sim["Verilator / Questa"]
        Quartus["Intel Quartus Prime (quartus_sh)"]
    end

    Claude <-->|"strata-local ask (--sum / --rtl / --iac / --rust / --review)"| Strata
    Strata -.->|"Exclusive VRAM: unloads Ollama"| Qwen
    Claude <-->|"qwen-rtl (--audit / --tb / -f)"| Qwen
    Claude <-->|"qwen-vl (--ocr / --diagram / --ui)"| QwenVL
    QwenVL -.->|"Auto-unloads 14B coder"| Qwen
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
    participant Claude as Claude Code (Architect)
    participant Strata as Strata (Qwen3.6-35B-A3B)
    participant Qwen as qwen-rtl (RX 9070 XT, 14B)
    participant QwenVL as qwen-vl (RX 9070 XT, 7B VL)
    participant CW as codewhale (deepseek-flash)
    participant Tools as Verilator / Quartus / terraform / cargo

    Dev->>Claude: Requests RTL, IaC or Rust VST change, image analysis, or build
    Claude->>Claude: Checks AGENTS.md + skill hybrid-local-ai, routes task
    Claude->>Strata: strata-local status

    alt Bounded task and Strata ACTIVE (summary / RTL inventory / IaC / Rust with real -f context / review)
        Claude->>Strata: strata-local ask --sum / --rtl / --iac / --rust / --review (reasoning off)
        Strata-->>Claude: Draft (~5-10 s)
        Claude->>Claude: Reviews draft (Rust: API + DSP math checked by Claude)
    else Structural RTL while Quartus compiles (Strata stopped)
        Claude->>Qwen: Runs qwen-rtl --audit / --tb -f rtl/mod.sv
        Qwen-->>Claude: Returns port/FSM inventory or SV/cocotb skeleton
    else Image / Screenshot (OCR / Diagrams / UI, non-waveform timing)
        Claude->>Strata: strata-local stop (exclusive VRAM)
        Claude->>QwenVL: Runs qwen-vl --ocr / --diagram / --ui -f img.png
        QwenVL-->>Claude: Returns extracted text / diagram / UI summary (60s TTL)
    else Timing / Protocol / Multi-file / >32K ctx / CDC / .sdc
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
        Claude->>Strata: strata-local stop (free RAM/VRAM)
        Claude->>Tools: Runs quartus_sh --flow compile
        Tools-->>Claude: Returns .fit.rpt, .sta.rpt, and warnings
        opt Minor warnings
            Claude->>Qwen: Cleans bit-width or signal warnings
        end
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
    Dev(["Developer / Prompt in Claude Code"]) --> Claude{"Claude Code (AGENTS.md + hybrid-local-ai)"}

    Claude -->|"Timing / Cycle Trace / Bus Protocols / TB Checks / CDC / .sta.rpt / .sdc / >32K"| Arch["Claude Code + codewhale (deepseek-flash)"]
    Claude -->|"Bounded task, Strata ACTIVE: summaries / RTL inventory / IaC / Rust (with -f context) / reviews"| Strata["Strata - Qwen3.6-35B-A3B UD-Q4_K_XL (VRAM + RAM, ~80 tok/s)"]
    Claude -->|"Structural RTL while Quartus compiles"| Local["qwen-rtl - qwen2.5-coder-14b-fpga (Ollama Vulkan, VRAM only)"]
    Claude -->|"Images / Screenshots / OCR / Block Diagrams"| LocalVL["qwen-vl - qwen2.5vl:7b (60s TTL)"]
    LocalVL --> Claude

    Arch --> Code["Source: rtl/*.sv | core.json | .sdc | .qsf | *.tf | Helm | src/*.rs"]
    Strata --> Code
    Local --> Code

    Code --> Domain{"Domain?"}
    Domain -->|"IaC"| TF["terraform fmt -check + validate / tflint / helm lint"]
    Domain -->|"Rust VST"| Cargo["cargo check / clippy -D warnings / test / xtask bundle"]
    TF -->|"Fails"| Strata
    Cargo -->|"Fails (API / DSP)"| Arch
    TF -->|"OK"| Done(["Verified result to Developer"])
    Cargo -->|"OK"| Done

    Domain -->|"FPGA"| Sim{"Unit Simulation?"}
    Sim -->|"Yes"| Verilator["Verilator / Questa on i7-14700KF"]
    Verilator -->|"Logic failure"| Strata
    Verilator -->|"OK"| Stop["strata-local stop (free RAM + VRAM)"]
    Sim -->|"No / Direct to HW"| Stop
    Stop --> Quartus["Intel Quartus Prime (quartus_sh) - Synthesis, Fitter & TimeQuest"]

    Quartus --> Check{"Compilation Result?"}
    Check -->|"Minor warnings / Bit-width"| Local
    Check -->|"Setup/Hold violation or Fitter error"| Arch
    Check -->|"Timing Clean & Bitstream OK"| Bitstream(["core.rbf ready for Analogue Pocket / openFPGA"])
```

---

## Hardware Resource Allocation (Arch Linux)

| Component | Allocated Resource | Role in Pipeline |
| :--- | :--- | :--- |
| **AMD RX 9070 XT (16 GB)** | ~16 GB VRAM, exclusive | **Strata** (Qwen3.6-35B-A3B, 81/256 experts per layer in VRAM) via `strata-local`, **or** Ollama Vulkan (`qwen2.5-coder-14b-fpga`, `qwen2.5vl:7b`) via `qwen-rtl` / `qwen-vl` |
| **Intel i7-14700KF (20 cores)** | CPU Compute | RTL simulation (Verilator/Questa) and Quartus Place & Route |
| **64 GB DDR5 RAM** | ~12-16 GB to Strata while running | Remaining Strata experts; stop Strata before Quartus so compilation gets the full RAM |
| **Claude Code + `codewhale`** | Remote API | Lead architecture, CDC, `.sdc`, `.sta.rpt` / `.fit.rpt` analysis, and multi-file edits (`deepseek-flash`) |

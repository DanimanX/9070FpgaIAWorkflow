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
    participant Qwen as qwen-rtl (RX 9070 XT, 14B)
    participant QwenVL as qwen-vl (RX 9070 XT, 7B VL)
    participant CW as codewhale (deepseek-flash)
    participant Tools as Verilator / Quartus (i7-14700KF)

    Dev->>Claude: Requests RTL change, testbench, image analysis, or build
    Claude->>Claude: Checks AGENTS.md and routes task

    alt Local Structural Task (RTL Inventory / Testbench Skeleton / Auxiliary / Warnings)
        Claude->>Qwen: Runs qwen-rtl --audit / --tb -f rtl/mod.sv
        Qwen-->>Claude: Returns port/FSM inventory or SV/cocotb skeleton
        Claude->>Claude: Reviews & fills timing-dependent checks (or escalates to CW)
    else Local Image / Screenshot Task (OCR / Diagrams / UI, non-waveform timing)
        Claude->>QwenVL: Runs qwen-vl --ocr / --diagram / --ui -f img.png
        QwenVL->>Qwen: Auto-unloads 14B coder from VRAM
        QwenVL-->>Claude: Returns extracted text / diagram / UI summary (60s TTL)
    else Timing / Protocol / Multi-file Task (Cycle trace / >32K ctx / Architecture / CDC / .sdc)
        Claude->>CW: Escalates via codewhale exec --sandbox read-only / workspace-write
        CW-->>Claude: Returns timing analysis, checking logic, constraints, or patch
        Claude->>Claude: Verifies DeepSeek output against code & simulations
    end

    Claude->>Tools: Inspects git diff & runs verilator --lint-only / iverilog / simulation

    alt Logic or syntax failure
        Tools-->>Claude: Reports errors
        Claude->>Qwen: Requests quick fix via stdin/CLI
        Qwen-->>Claude: Corrected snippet
    else Simulation OK
        Claude->>Tools: Runs quartus_sh --flow compile
        Tools-->>Claude: Returns .fit.rpt, .sta.rpt, and warnings
        opt Minor warnings
            Claude->>Qwen: Cleans bit-width or signal warnings
        end
        opt Timing Violation (Setup/Hold) or Fitter error
            Claude->>Claude: Analyzes .sta.rpt / .fit.rpt for Timing Closure
        end
        Claude-->>Dev: Delivers validated core.rbf and summary of results
    end
```

---

## 3. Decision and Synthesis Flow

```mermaid
flowchart TD
    Dev(["Developer / Prompt in Claude Code"]) --> Claude{"Claude Code (AGENTS.md)"}

    %% Cloud / Architect Branch
    Claude -->|"Timing / Cycle Trace / Bus Protocols / TB Checks / CDC / .sta.rpt / .sdc"| Arch["Claude Code + codewhale (deepseek-flash) - Timing, protocols & >32K ctx"]

    %% Local Branches
    Claude -->|"Structural Inventory / TB Skeletons / Auxiliary modules / Warning cleanup"| Local["qwen-rtl (RX 9070 XT - 16 GB VRAM) - qwen2.5-coder-14b-fpga (Ollama Vulkan)"]
    Claude -->|"Images / Screenshots / OCR / Block Diagrams (non-waveform timing)"| LocalVL["qwen-vl (RX 9070 XT - ~5.4 GB, auto-swap) - qwen2.5vl:7b (60s TTL)"]
    LocalVL --> Claude

    %% Convergence in code
    Arch --> RTL["Source Code & Configuration: rtl/*.sv | rtl/*.vhd | core.json | .sdc | .qsf"]
    Local --> RTL

    %% Verification & Synthesis Flow
    RTL --> Sim{"Unit Simulation?"}
    Sim -->|"Yes"| Verilator["Simulator (Verilator / Questa) on i7-14700KF"]
    Verilator -->|"Logic failure"| Local
    Verilator -->|"OK"| Quartus

    Sim -->|"No / Direct to HW"| Quartus["Intel Quartus Prime (quartus_sh) - Synthesis, Fitter & TimeQuest (64 GB RAM)"]

    Quartus --> Check{"Compilation Result?"}
    Check -->|"Minor warnings / Bit-width"| Local
    Check -->|"Setup/Hold violation or Cyclone V Fitter error"| Arch
    Check -->|"Timing Clean & Bitstream OK"| Bitstream(["core.rbf ready for Analogue Pocket / openFPGA"])
```

---

## Hardware Resource Allocation (Arch Linux)

| Component | Allocated Resource | Role in Pipeline |
| :--- | :--- | :--- |
| **AMD RX 9070 XT (16 GB)** | ~16 GB VRAM (100% GPU) | Local inference with **Ollama Vulkan** (`qwen2.5-coder-14b-fpga` `Q5_K_M`, 32K ctx) via `qwen-rtl` |
| **Intel i7-14700KF (20 cores)** | CPU Compute | RTL simulation (Verilator/Questa) and Quartus Place & Route |
| **64 GB DDR5 RAM** | 100% available for CPU | Cyclone V compilation without swapping (no model spill from GPU) |
| **Claude Code + `codewhale`** | Remote API | Lead architecture, CDC, `.sdc`, `.sta.rpt` / `.fit.rpt` analysis, and multi-file edits (`deepseek-flash`) |

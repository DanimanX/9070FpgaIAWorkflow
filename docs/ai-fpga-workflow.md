# Hybrid openFPGA + Intel Quartus Prime Development Workflow

Agent-assisted development architecture where **Strata** interfaces with **`codewhale`** and **`codewhale` acts as the central orchestrator**, coordinating local reasoning in **Strata** (**RX 9070 XT 16 GB VRAM**), cloud escalation (**Remote / Cloud Models**), and local tool execution (**Verilator / Questa / Intel Quartus Prime**) on **i7-14700KF + 64 GB DDR5 RAM**.

---

## 1. Integration Architecture (`Strata -> codewhale`)

**Strata** exposes the local model (`Qwen3.6-35B-A3B` on the RX 9070 XT) to **`codewhale`**, so that **`codewhale`** centralizes project rules parsing ([`AGENTS.md`](../AGENTS.md)), task routing, file editing, and the execution of builds and simulations.

```mermaid
flowchart LR
    Dev(["Developer"]) -->|"Prompt / Objective"| CW["codewhale (Central Orchestrator)"]

    subgraph LocalGPU["Local Inference - RX 9070 XT (16 GB VRAM)"]
        Strata["Strata (Qwen3.6-35B-A3B)"]
    end

    subgraph CloudAPI["Remote Escalation"]
        Cloud["Hydrogen Pro / Remote (cloud-pro)"]
    end

    subgraph Toolchain["Arch Linux Host (i7-14700KF + 64 GB RAM)"]
        FS["openFPGA Repository (RTL / JSON / .qsf / .sdc)"]
        Sim["Verilator / Questa"]
        Quartus["Intel Quartus Prime (quartus_sh)"]
    end

    Strata <-->|"Local endpoint / profile for codewhale"| CW
    CW <-->|"Complex tasks: Architecture / CDC / Timing"| Cloud
    CW -->|"Reads AGENTS.md rules & edits files"| FS
    CW -->|"Runs lint & testbenches"| Sim
    CW -->|"Runs synthesis, Fitter & TimeQuest"| Quartus
    Sim -->|"Logs / Errors"| CW
    Quartus -->|"Reports .sta.rpt / .fit.rpt / core.rbf"| CW
```

---

## 2. Process & Interaction Diagram (Orchestrated by `codewhale`)

```mermaid
sequenceDiagram
    actor Dev as Developer
    participant CW as codewhale (Orchestrator)
    participant Strata as Strata (RX 9070 XT)
    participant Cloud as Hydrogen Pro (cloud-pro)
    participant Tools as Verilator / Quartus (i7-14700KF)

    Dev->>CW: Requests RTL change, testbench, or build
    CW->>CW: Reads AGENTS.md and routes task

    alt Local Task (Testbench / Auxiliary module / Warnings / Scripts)
        CW->>Strata: Delegates generation or fix (local-fpga profile)
        Strata-->>CW: Proposes SV/VHDL code or scripts
    else Complex Task (Architecture / CDC / .sdc / openFPGA JSON)
        CW->>Cloud: Escalates design or deep reasoning (cloud-pro)
        Cloud-->>CW: Returns architecture, constraints, or diagnosis
    end

    CW->>CW: Applies changes to workspace
    CW->>Tools: Runs verilator --lint-only / simulation

    alt Logic or syntax failure
        Tools-->>CW: Reports errors
        CW->>Strata: Requests quick fix
        Strata-->>CW: Corrected patch
    else Simulation OK
        CW->>Tools: Runs quartus_sh --flow compile
        Tools-->>CW: Returns .fit.rpt, .sta.rpt, and warnings
        opt Minor warnings
            CW->>Strata: Cleans bit-width or signal warnings
        end
        opt Timing Violation (Setup/Hold) or Fitter error
            CW->>Cloud: Analyzes .sta.rpt / .fit.rpt for Timing Closure
        end
        CW-->>Dev: Delivers validated core.rbf and summary of results
    end
```

---

## 3. Decision and Synthesis Flow

```mermaid
flowchart TD
    Dev(["Developer / Prompt in codewhale"]) --> CW{"codewhale Orchestrator (AGENTS.md)"}

    %% Cloud Branch
    CW -->|"RTL Architecture / FSM / CDC / Timing Closure .sta.rpt / openFPGA JSON / .sdc"| Cloud["cloud-pro (Hydrogen Pro) - Long context & deep reasoning"]

    %% Local Branch
    CW -->|"SV/VHDL Testbenches / Auxiliary modules / LUTs / Warning cleanup"| Local["local-fpga (RX 9070 XT - 16 GB VRAM) - Strata (Qwen3.6-35B-A3B)"]

    %% Convergence in code
    Cloud --> RTL["Source Code & Configuration: rtl/*.sv | rtl/*.vhd | core.json | .sdc | .qsf"]
    Local --> RTL

    %% Verification & Synthesis Flow
    RTL --> Sim{"Unit Simulation?"}
    Sim -->|"Yes"| Verilator["Simulator (Verilator / Questa) on i7-14700KF"]
    Verilator -->|"Logic failure"| Local
    Verilator -->|"OK"| Quartus

    Sim -->|"No / Direct to HW"| Quartus["Intel Quartus Prime (quartus_sh) - Synthesis, Fitter & TimeQuest (64 GB RAM)"]

    Quartus --> Check{"Compilation Result?"}
    Check -->|"Minor warnings / Bit-width"| Local
    Check -->|"Setup/Hold violation or Cyclone V Fitter error"| Cloud
    Check -->|"Timing Clean & Bitstream OK"| Bitstream(["core.rbf ready for Analogue Pocket / openFPGA"])
```

---

## Hardware Resource Allocation (Arch Linux)

| Component | Allocated Resource | Role in Pipeline |
| :--- | :--- | :--- |
| **AMD RX 9070 XT (16 GB)** | ~14–15 GB VRAM | Local inference with **Strata** (`Qwen3.6-35B-A3B`) connected to `codewhale` |
| **Intel i7-14700KF (20 cores)** | CPU Compute | Orchestration (`codewhale`), RTL simulation (Verilator/Questa), and Quartus Place & Route |
| **64 GB DDR5 RAM** | ~12–16 GB Quartus + Offload | Cyclone V compilation without swapping + Strata MoE layer offload |
| **Hydrogen (Pro Account)** | Remote API | Escalation from `codewhale` for architecture, CDC, `.sdc`, and `.sta.rpt` / `.fit.rpt` analysis |

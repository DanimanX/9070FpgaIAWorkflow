# Flujo Híbrido de Desarrollo openFPGA + Intel Quartus Prime

Arquitectura de desarrollo asistido por agentes (`agy` / Antigravity) combinando razonamiento en la nube (**Hydrogen Pro**) e inferencia local de baja latencia con **Strata** (**RX 9070 XT 16 GB VRAM + 64 GB RAM + i7-14700KF**).

## Diagrama de Procesos y Enrutamiento

```mermaid
flowchart TD
    Dev(["Desarrollador / Prompt en agy"]) --> Router{"Clasificador de Tarea (AGENTS.md)"}

    %% Rama Cloud Pro
    Router -->|"Arquitectura RTL / FSM / CDC / Timing Closure .sta.rpt / JSON openFPGA / .sdc"| Cloud["cloud-pro (Hydrogen Pro) - Contexto largo y razonamiento profundo"]

    %% Rama Local RX 9070 XT con Strata
    Router -->|"Testbenches SV/VHDL / Módulos auxiliares / LUTs / Limpieza de Warnings"| Local["local-fpga (RX 9070 XT - 16GB VRAM) - Strata (Qwen3.6-35B-A3B)"]

    %% Convergencia en código
    Cloud --> RTL["Código Fuente y Configuración: rtl/*.sv | rtl/*.vhd | core.json | .sdc | .qsf"]
    Local --> RTL

    %% Flujo de Verificación y Síntesis
    RTL --> Sim{"¿Simulación Unitaria?"}
    Sim -->|"Sí"| Verilator["Simulador (Verilator / Questa) en i7-14700KF"]
    Verilator -->|"Fallo lógico"| Local
    Verilator -->|"OK"| Quartus

    Sim -->|"No / Directo a HW"| Quartus["Intel Quartus Prime (quartus_sh) - Síntesis, Fitter y TimeQuest (64 GB RAM)"]

    Quartus --> Check{"¿Resultado Compilación?"}
    Check -->|"Warnings menores / Bit-width"| Local
    Check -->|"Violación Setup/Hold o Error Fitter Cyclone V"| Cloud
    Check -->|"Timing Clean y Bitstream OK"| Bitstream(["core.rbf listo para Analogue Pocket / openFPGA"])
```

## Distribución de Recursos de Hardware (Arch Linux)

| Componente | Recurso Asignado | Función en el Pipeline |
| :--- | :--- | :--- |
| **AMD RX 9070 XT (16 GB)** | ~14–15 GB VRAM | Inferencia local con **Strata** (`Qwen3.6-35B-A3B`) |
| **Intel i7-14700KF (20 cores)** | Cómputo CPU | Simulación RTL (Verilator/Questa) y Place & Route de Quartus |
| **64 GB DDR5 RAM** | ~12–16 GB Quartus + Offload | Compilación Cyclone V sin swapping + capas MoE excedentes de Strata |
| **Hydrogen (Cuenta Pro)** | API Remota | Diseño de arquitectura, CDC, `.sdc` y análisis de `.sta.rpt` / `.fit.rpt` |

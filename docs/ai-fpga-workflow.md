# Flujo Híbrido de Desarrollo openFPGA + Intel Quartus Prime

Arquitectura de desarrollo asistido por agentes donde **Strata** se conecta/apunta a **`agy` (Antigravity)** y **`agy` actúa como orquestador central**, coordinando el razonamiento local en **Strata** (**RX 9070 XT 16 GB VRAM**), el escalado en la nube (**Hydrogen Pro**) y la ejecución de herramientas locales (**Verilator / Questa / Intel Quartus Prime**) sobre **i7-14700KF + 64 GB DDR5 RAM**.

---

## 1. Arquitectura de Integración (`Strata -> agy`)

**Strata** expone el modelo local (`Qwen3.6-35B-A3B` en la RX 9070 XT) apuntando hacia **`agy`**, de modo que **`agy`** centraliza la lectura del proyecto (`AGENTS.md`), el enrutamiento de tareas, la edición de archivos y la ejecución de compilaciones y simulaciones.

```mermaid
flowchart LR
    Dev(["Desarrollador"]) -->|"Prompt / Objetivo"| Agy["agy (Orquestador Central)"]

    subgraph LocalGPU["Inferencia Local - RX 9070 XT (16 GB VRAM)"]
        Strata["Strata (Qwen3.6-35B-A3B)"]
    end

    subgraph CloudAPI["Escalado Remoto"]
        Cloud["Hydrogen Pro (cloud-pro)"]
    end

    subgraph Toolchain["Host Arch Linux (i7-14700KF + 64 GB RAM)"]
        FS["Repositorio openFPGA (RTL / JSON / .qsf / .sdc)"]
        Sim["Verilator / Questa"]
        Quartus["Intel Quartus Prime (quartus_sh)"]
    end

    Strata <-->|"Endpoint / Proveedor local apuntando a agy"| Agy
    Agy <-->|"Tareas complejas: Arquitectura / CDC / Timing"| Cloud
    Agy -->|"Lee reglas AGENTS.md y edita archivos"| FS
    Agy -->|"Ejecuta lint y testbenches"| Sim
    Agy -->|"Ejecuta síntesis, Fitter y TimeQuest"| Quartus
    Sim -->|"Logs / Errores"| Agy
    Quartus -->|"Reportes .sta.rpt / .fit.rpt / core.rbf"| Agy
```

---

## 2. Diagrama de Procesos e Interacción (Orquestación por `agy`)

```mermaid
sequenceDiagram
    actor Dev as Desarrollador
    participant Agy as agy (Orquestador)
    participant Strata as Strata (RX 9070 XT)
    participant Cloud as Hydrogen Pro (cloud-pro)
    participant Tools as Verilator / Quartus (i7-14700KF)

    Dev->>Agy: Solicita cambio RTL, testbench o compilación
    Agy->>Agy: Lee AGENTS.md y clasifica la tarea

    alt Tarea local (Testbench / Módulo auxiliar / Warnings / Scripts)
        Agy->>Strata: Delega generación o corrección (local-fpga)
        Strata-->>Agy: Propone código SV/VHDL o scripts
    else Tarea compleja (Arquitectura / CDC / .sdc / JSON openFPGA)
        Agy->>Cloud: Escala diseño o análisis profundo (cloud-pro)
        Cloud-->>Agy: Devuelve arquitectura, restricciones o diagnóstico
    end

    Agy->>Agy: Aplica cambios en el workspace
    Agy->>Tools: Ejecuta verilator --lint-only / simulación

    alt Fallo lógico o de sintaxis
        Tools-->>Agy: Reporta errores
        Agy->>Strata: Solicita corrección rápida
        Strata-->>Agy: Patch corregido
    else Simulación OK
        Agy->>Tools: Ejecuta quartus_sh --flow compile
        Tools-->>Agy: Devuelve .fit.rpt, .sta.rpt y warnings
        opt Warnings menores
            Agy->>Strata: Limpia warnings de ancho o señales
        end
        opt Violación de Timing (Setup/Hold) o error de Fitter
            Agy->>Cloud: Analiza .sta.rpt / .fit.rpt para Timing Closure
        end
        Agy-->>Dev: Entrega core.rbf validado y resumen de resultados
    end
```

---

## 3. Flujo de Decisión y Síntesis

```mermaid
flowchart TD
    Dev(["Desarrollador / Prompt en agy"]) --> Agy{"agy Orquestador (AGENTS.md)"}

    %% Rama Cloud Pro
    Agy -->|"Arquitectura RTL / FSM / CDC / Timing Closure .sta.rpt / JSON openFPGA / .sdc"| Cloud["cloud-pro (Hydrogen Pro) - Contexto largo y razonamiento profundo"]

    %% Rama Local RX 9070 XT con Strata
    Agy -->|"Testbenches SV/VHDL / Módulos auxiliares / LUTs / Limpieza de Warnings"| Local["local-fpga (RX 9070 XT - 16GB VRAM) - Strata (Qwen3.6-35B-A3B)"]

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

---

## Distribución de Recursos de Hardware (Arch Linux)

| Componente | Recurso Asignado | Función en el Pipeline |
| :--- | :--- | :--- |
| **AMD RX 9070 XT (16 GB)** | ~14–15 GB VRAM | Inferencia local con **Strata** (`Qwen3.6-35B-A3B`) conectado a `agy` |
| **Intel i7-14700KF (20 cores)** | Cómputo CPU | Orquestación (`agy`), simulación RTL (Verilator/Questa) y Place & Route de Quartus |
| **64 GB DDR5 RAM** | ~12–16 GB Quartus + Offload | Compilación Cyclone V sin swapping + capas MoE excedentes de Strata |
| **Hydrogen (Cuenta Pro)** | API Remota | Escalado desde `agy` para arquitectura, CDC, `.sdc` y análisis de `.sta.rpt` / `.fit.rpt` |

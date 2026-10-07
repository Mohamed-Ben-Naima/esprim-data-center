# 03_Network – Réseau du Data Center Casablanca (GNS3)

Lab GNS3 du Data Center TIA-942 Rated-3 : configuration complète, tests de résilience et rapport.

| Path | Contents |
|---|---|
| `DC_Casablanca_TIA942_R3.gns3` | GNS3 project (runs on the GNS3 VM, compute `vm`) |
| `DC_Casablanca_TIA942_R3_wiring.csv` | Cabling plan (role, endpoints, interfaces) |
| `plans/` | Execution plan (`PLAN_01_GNS3_Configuration.md`) |
| `inventory/` | Single source of truth (`dc_casa.yaml`) |
| `automation/` | Generators, GNS3 API / console driver, resilience tests |
| `configs/` | Generated device configurations |
| `docker/` | Custom service images (built inside the GNS3 VM) |
| `screenshots/` | Numbered screenshots used by the report |
| `report/` | French report: `content/*.md` → `Rapport_Reseau_GNS3_DC_Casablanca.docx/.pdf` |
| `fixgns3.ps1` | Repairs an unreachable VMware GNS3 VM (see report, "Mise en œuvre") |
| `gen_gns3.py` | Generates the topology file |

## Build the report

```powershell
powershell -ExecutionPolicy Bypass -File 03_Network\report\build.ps1
```
Needs Node.js (installs `docx` on first run) and Microsoft Word (TOC refresh + PDF export).

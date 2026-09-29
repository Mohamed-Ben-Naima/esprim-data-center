# Architecture decisions

Each decision follows the same short format: context, decision, why, consequences.
All figures are **design assumptions** for an academic project; they must be validated with the
supervisor before the network and interior phases build on them.

The course (*Objectif 1 – Qu'est-ce qu'un Data Center ?*) sets four critical challenges that every
decision must answer:

| Code | Challenge (course wording) | Meaning |
|---|---|---|
| E1 | Continuité électrique | IT equipment never loses power |
| E2 | Maîtrise du froid | IT rooms stay between 20 and 25 °C |
| E3 | Sécurisation | Only authorised people reach the equipment |
| E4 | Haute disponibilité | Any single component can fail or be serviced without stopping the service |

---

## ADR-01 – Target level: Tier III

**Context.** We need a clear availability target to size power, cooling and the network.

**Decision.** Design to the Uptime Institute **Tier III** level: *concurrently maintainable*,
N+1 on every component, two distribution paths (one active, one alternate), 99.982 % availability
(about 1.6 h of downtime per year).

**Why.** Tier III is the usual target for enterprise and colocation data centers. Tier IV (fully
fault-tolerant, 2N everywhere) roughly doubles the power and cooling plant for a small gain that an
academic scenario does not need. Tier II would not satisfy E4.

**Consequences.** Every piece of equipment has a spare (N+1). Every rack receives two power feeds (A and B).
Maintenance can take one path offline at a time.

## ADR-02 – Capacity: about 1 MW of IT load, about 200 racks

**Decision.** 200 racks at an average of 5 kW each, giving 1 MW of IT load. White space of about
1,500 m² inside a 70 × 40 m IT building. Target PUE 1.4–1.5, giving a total facility load of about 1.4–1.5 MW.

**Why.** This is a medium-size facility, well above the 185 m² threshold the course gives for half of
all IT rooms. It is big enough to justify the three-building layout and small enough to stay realistic.

**Consequences.** It sizes everything downstream: transformers, generators, UPS, chillers, and the number
of access switches in phase 4.

## ADR-03 – Three separate buildings

**Decision.** Split the campus into the three buildings described in the course:

| Building | Role | Why separate |
|---|---|---|
| Bâtiment informatique | Racks, storage, network (white room) | Windowless, highest security zone, clean environment |
| Bâtiment technique | Power conversion and distribution, UPS, chillers | Keeps heat, noise, fuel and fire risk away from the IT equipment |
| Bâtiment logistique | NOC, offices, meeting rooms, break rooms | People work here without entering the secure zones |

Covered links join the IT building to the technical building (cable and pipe route) and to the
logistique building (staff route).

**Why.** Separating risks is a core principle: a fire in a battery room or a generator incident must
not spread to the white room, and daily staff traffic must not cross the secure zones.

## ADR-04 – Two independent high-voltage feeds (E1, E4)

**Decision.** Two separate HV lines (feed A from the north-east, feed B from the east-south-east), each
with its own transformer: TR-A and TR-B, 2.5 MVA each.

**Why.** One transformer carries the whole site (1.5 MW at a power factor of 0.8 is about 1.9 MVA,
under 2.5 MVA). Either feed can fail or be serviced without an outage.

**Consequences.** The substation yard needs two gantries and two transformer bays. It is placed on the east
edge of the site, closest to the lines.

## ADR-05 – Generators N+1 and fuel storage (E1)

**Decision.** Six diesel generators (G1–G6) of 500 kVA (400 kW) each. Five carry the full facility load
(5 × 400 kW = 2 MW, above 1.5 MW); the sixth is the spare. Two fuel tanks of 50 m³ each sit inside a
concrete retention bund.

**Why.** Consumption at full load is about 0.25 L/kWh × 1,450 kW ≈ 360 L/h. With 100 m³ on site the
autonomy is about 275 h (11 days), far above the 12 h minimum usually required for Tier III.

**Consequences.** Automatic transfer switches (ATS) start the generators in under 15 s. The UPS covers that gap.

## ADR-06 – UPS: two systems, modular N+1 (E1, E4)

**Decision.** UPS A and UPS B, each built from 5 × 250 kW modules (4 needed + 1 spare), each able to carry
the full 1 MW IT load, with batteries for about 10 minutes.

**Why.** 10 minutes covers generator start-up with a wide margin and allows a clean shutdown if
everything fails. Two systems match the A/B paths required by Tier III.

## ADR-07 – Cooling: chilled water, hot/cold aisles, free cooling (E2)

**Decision.**
- In the white room: racks face-to-face in **cold aisles** and back-to-back in **hot aisles**, with
  containment. CRAH units (N+1) cool the air to 20–25 °C.
- Chilled-water loop fed by **4 chillers of 400 kW (3 + 1)** on the roof of the technical building.
- **21 dry coolers** on the roof of the IT building reject the heat outdoors and allow **free cooling**:
  when the outdoor air is cool enough (Tunisian winter nights), they chill the water alone and the
  chillers stop.

**Why.** Aisle containment is the cheapest efficiency gain in a data center. Free cooling lowers the PUE.
In Tunisia it only works part of the year, so the chillers stay mandatory.

## ADR-08 – Physical security in five zones (E3)

**Decision.** Defence in depth, with each zone adding one control:

| Zone | Area | Control |
|---|---|---|
| 0 | Public road | None |
| 1 | Fenced perimeter | Single guarded entrance, barriers, anti-ram bollards, 10 CCTV cameras |
| 2 | Buildings | Personal badge, entrance airlock |
| 3 | White room, technical rooms | Badge + biometrics |
| 4 | Rack | Key or code, access logged |

**Consequences.** There is one vehicle entrance only. The parking is inside the fence but next to the gate, so
visitors never drive near the buildings.

## ADR-09 – Location assumption: outskirts of Greater Tunis

The course ranks location criteria in this order: physical security, energy availability, network
connectivity, climate, and proximity of technical teams. We assume an industrial zone on the outskirts of
Greater Tunis:

| Criterion | Assessment |
|---|---|
| Physical security | Industrial zone, no flood-prone river bed, away from airports and hazardous sites |
| Energy | Close to the national HV grid, which allows two independent feeds |
| Connectivity | Close to national fibre backbones and to the submarine cable landing stations on the northern coast |
| Climate | Hot summers are the weak point: cooling is sized for 40 °C+ days. Free cooling is possible in winter |
| Teams | Engineering schools and IT companies nearby (ESPRIM, El Ghazala technology park) |

This is a scenario, not a real site study. It explains the dry landscape around the campus in the renders.

## ADR-10 – Tooling

| Choice | Why |
|---|---|
| **Blender 5.2** for the 3D model | Free, scriptable in Python. The whole campus is generated by code (`dc_lib.py`), so it is reproducible |
| **Cycles** for stills, **EEVEE** for the video | Cycles is physically accurate but takes about 3–5 min per frame on an RTX 2050. EEVEE takes about 10 s per frame, which makes a 34 s video possible |
| **Git + Git LFS**, private GitHub repo | Version history for every file. Large binaries (`.blend`, images, video) are stored in LFS so the repo stays fast |
| **GNS3** for the network (phase 4) | Runs real network operating systems, closer to production than Packet Tracer |

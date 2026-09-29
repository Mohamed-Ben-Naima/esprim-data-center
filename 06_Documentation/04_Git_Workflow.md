# Git workflow

Repository: **https://github.com/Mohamed-Ben-Naima/esprim-data-center** (private)

## First-time setup (each team member)

```bash
git lfs install                 # once per computer, before cloning
git clone https://github.com/Mohamed-Ben-Naima/esprim-data-center.git
```

Ask the repository owner to add you under *Settings → Collaborators* first.

## What is stored how

| Type | Storage |
|---|---|
| Markdown, Python, GNS3 `.gns3` project files | Normal Git (text, diffable) |
| `.blend`, images, video, Office files, PDF, `.gns3project`, `.pkt` | **Git LFS** (see `.gitattributes`) |
| Blender backups (`.blend1`), render frame sequences, GNS3 VM disks, packet captures | **Ignored** (see `.gitignore`) |

GitHub's free plan includes 10 GB of LFS storage. Commit final renders and scene versions, not every test render.

## Daily routine

```bash
git pull                        # start of session
# ... work ...
git add -A
git commit -m "blender: add white-room racks"
git push                        # end of session
```

## Commit message prefixes

| Prefix | For |
|---|---|
| `blender:` | 3D scenes, scripts, renders |
| `network:` | GNS3 projects, configs, IP plan |
| `docs:` | Documentation and planning |
| `report:` | The report and presentation |
| `code:` | Automation scripts |

## Binary files cannot be merged

Git cannot merge two people's changes to the same `.blend` or `.docx` file. To avoid conflicts:

- Announce in the team chat before editing a `.blend` or the report.
- Save a new version number (`DC_Interior_v01.blend`) instead of editing someone else's open file.
- Pull before you start, push as soon as you finish.

## Versioning rule

Scene files keep a version number in the name (`DC_Exterior_v01 … v04`) **and** are committed. The number
shows the milestone at a glance; Git keeps the full history.

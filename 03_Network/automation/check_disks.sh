#!/bin/bash
# Check every node disk image of the lab project (runs inside the GNS3 VM, nodes may be running or stopped).
#   python automation/gns3vm.py --sudo -f automation/check_disks.sh
# Use after any host disk incident (see report: write errors on the external disk, 12 Oct 2026).
PROJECT=0803de83-273e-4e22-b628-b2b2424ed74a          # DC_Casablanca_TIA942_R3
cd "/opt/gns3/projects/$PROJECT/project-files/qemu" || exit 1
bad=0
for f in */*.qcow2; do
    r=$(sudo qemu-img check "$f" 2>&1)
    use=""
    # a running node holds the write lock: check it read-only (-U, shared); "Failed to get shared write lock" was
    # counted as a problem before (9 false alarms on 10 Nov 2026)
    case "$r" in *"write\" lock"*|*"write lock"*) r=$(sudo qemu-img check -U "$f" 2>&1); use=" (in use, read-only check)" ;; esac
    r=$(echo "$r" | grep -E 'No errors|errors|corrupt|leaked|Could not' | head -1)
    echo "${f%%/*} ${f##*/}: $r$use"
    case "$r" in "No errors"*) ;; *) bad=$((bad + 1)) ;; esac
done
echo "images with problems: $bad"

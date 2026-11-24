"""Final narration: acts 0/1 (night 23-24), 1b NOC live (24 Nov), 1c old takes (T2, 12/12), 2 compute, 3 NAS."""
from pathlib import Path
import sys
import yaml

p = Path(r"C:\Users\ASUS\Documents\ESPRIM\Data Center\03_Network\automation\demo_video\narration.yaml")
s = p.read_text(encoding="utf-8")
head = s[:s.index("segments:")]
head = "\n".join(l for l in head.splitlines() if not l.startswith("# PLAN_06 D9") and not l.startswith("# act 1b uses")) + "\n"
cur = {x["id"]: x for x in yaml.safe_load(s)["segments"]}
have = set(sys.argv[1:])          # recordings that exist (A1b_switch A1_noc ... A3_nas)


def seg(id, act, rec, mark, node, role, test, vo, jury=False, jury_vo=None, **kw):
    d = dict(id=id, act=act, rec=rec, mark=mark, node=node, role=role, test=test, vo=vo)
    if jury:
        d["jury"] = True
    if jury_vo:
        d["jury_vo"] = jury_vo
    d.update(kw)
    return d


new = {}
new["a1b_switch"] = seg("a1b_switch", "1b", "A1b_switch", "a1b_switch", "GNS3 · profil supervision",
                        "démarrage d'un profil réduit, depuis GNS3", "clic droit › Start sur chaque nœud",
                        "Acte supervision, filmé en direct. Pour tenir dans la mémoire du PC, la VM GNS3 a été redémarrée "
                        "et on ne démarre que ce qu'il faut : FW-A, CORE-A, les deux commutateurs de la salle B, la GTB, "
                        "le DCIM, SYSLOG et le serveur de supervision. Clic droit, Start, directement dans GNS3. Accéléré.",
                        until="a1b_done", speed="auto")
new["a1_zabbix"] = seg("a1_zabbix", "1b", "A1_noc", "a1_zabbix", "SRV-MON-01 · Zabbix",
                       "supervision : Zabbix + Grafana + MariaDB", "hôtes, puis problèmes",
                       "SRV-MON-01 porte la supervision : Zabbix, Grafana et la base MariaDB. Test : la liste des hôtes, "
                       "puis les problèmes ouverts. Résultat : {zbx_result}.")
new["a1_grafana"] = seg("a1_grafana", "1b", "A1_grafana", "a1_grafana", "Grafana · tableau NOC",
                        "vue d'ensemble du NOC", "énergie A/B, baies, PUE, températures",
                        "Le tableau de bord du NOC dans Grafana, en direct : {grafana_result}.", jury=True,
                        jury_vo="Le NOC dans Grafana, en direct : {grafana_result}.")
new["a1_bms"] = seg("a1_bms", "1b", "A1_grafana", "a1_bms", "BMS-SIM · SRV-DCIM-01",
                    "gestion technique du bâtiment (GTB) et DCIM", "pages en direct",
                    "Le non-IT : la GTB surveille l'énergie et le refroidissement, le DCIM suit les 96 baies. Résultat : "
                    "les deux chemins électriques sont alimentés, et les baies sont toutes en état normal.")
new["a1_t6"] = seg("a1_t6", "1b", "A1_t6", "a1_t6", "Panne T6 · chemin A", "redondance électrique 2 chemins",
                   "coupure réseau + onduleur + groupe du chemin A",
                   "Panne provoquée T6 : on coupe tout le chemin électrique A, réseau, onduleur et groupe. Résultat : "
                   "l'alarme se lève, les baies passent en mode dégradé, et le chemin B porte seul la charge. Puis on "
                   "rétablit.", jury=True,
                   jury_vo="Panne T6 : tout le chemin électrique A est coupé. Alarme, baies en dégradé, le chemin B porte "
                           "seul la charge. Puis retour.")
new["a1_acl"] = seg("a1_acl", "1b", "A1_acl", "a1_acl", "CORE-A · ACL", "cloisonnement des VLAN",
                    "supervision (VLAN 60) → administration en SSH",
                    "Le cloisonnement. Test : depuis le serveur de supervision, VLAN 60, on tente le SSH vers le poste "
                    "d'administration. Résultat : {acl_result}.", jury=True,
                    jury_vo="Le cloisonnement : la supervision tente le SSH vers l'administration. Résultat : {acl_result}.")
new["a1_lock"] = seg("a1_lock", "1b", "A1_lock", "a1_lock", "SYSLOG · visionneuse", "protection contre la force brute",
                     "6 mauvais mots de passe depuis SRV-MON-01",
                     "Et contre la force brute : six mauvais mots de passe sur la visionneuse de journaux. Résultat : "
                     "{lock_result}.")
new["a1b_proof"] = seg("a1b_proof", "1b", "A1b_proof", "a1b_proof", "demo_check.py", "preuve automatique",
                       "demo_check.py --profile noc2",
                       "La preuve automatique de ce profil : {noc_ok} contrôles sur {noc_total}, dont Zabbix, Grafana et "
                       "la GTB.", speed="auto")
t2 = dict(cur["a1_t2"])
t2.update(act="1c", vo=("Pour la bascule du pare-feu, il faut les deux pare-feux et tout le profil démo : cette prise "
                        "vient du 23 novembre. Panne T2 : on arrête le pare-feu maître FW-A, pendant qu'une sonde "
                        "interroge la GTB toutes les demi-secondes. Résultat : FW-B devient maître, coupure mesurée : "
                        "{t2} secondes."))
pr = dict(cur["a1_proof"])
pr.update(act="1c", vo=("Et la preuve sur le profil démo complet, le même matin : demo_check rejoue douze contrôles. "
                        "Résultat : {demo_ok} sur {demo_total}. L'attente est accélérée."))
new["a2_switch"] = seg("a2_switch", 2, "A2_switch", "a2_switch", "GNS3 · profil calcul", "changement de profil",
                       "clic droit › Start : salle A",
                       "Deuxième acte, le calcul, en direct. Nouveau redémarrage de la VM GNS3, puis dans GNS3 : FW-A, "
                       "CORE-A, les deux commutateurs de la salle A, le site web et deux serveurs de calcul. Accéléré.",
                       until="a2_done", speed="auto")
new["a2_leafa"] = seg("a2_leafa", 2, "A2_net", "a2_leafa", "LEAF-A1", "commutateur d'accès, salle A",
                      "show interfaces trunk · show interfaces status",
                      "LEAF-A1 dessert la salle A ; chaque serveur y est relié deux fois, à LEAF-A1 et à LEAF-A2. Test : "
                      "les trunks et les ports. Résultat : {leafa_result}.")
new["a2_cmp"] = seg("a2_cmp", 2, "A2_net", "a2_cmp", "SRV-CMP-01 / 02", "calcul : service applicatif sur VIP keepalived",
                    "qui porte la VIP 10.20.0.10 ?",
                    "SRV-CMP-01 et 02 portent le service applicatif, sur une adresse virtuelle gérée par keepalived. Test : "
                    "qui porte la VIP ? Résultat : {vip_result}.")
new["a2_t5"] = seg("a2_t5", 2, "A2_t5", "a2_t5", "Panne T5 · SRV-CMP-01", "haute disponibilité applicative",
                   "arrêt de SRV-CMP-01, sonde toutes les 0,5 s depuis la DMZ",
                   "Panne T5 : on arrête SRV-CMP-01 pendant que le site web interroge le service toutes les demi-secondes. "
                   "Résultat : {t5_result}. L'attente est accélérée.", speed="auto", jury=True,
                   jury_vo="Panne T5 : SRV-CMP-01 arrêté sous sonde. Résultat : {t5_result}.")
new["a2_proof"] = seg("a2_proof", 2, "A2_proof", "a2_proof", "demo_check.py", "preuve automatique",
                      "demo_check.py --profile cmp2",
                      "La preuve automatique de ce profil : {cmp_ok} contrôles sur {cmp_total}.", speed="auto")
new["a3_switch"] = seg("a3_switch", 3, "A3_switch", "a3_switch", "GNS3 · profil NAS", "changement de profil",
                       "clic droit › Start : SRV-BCK-01",
                       "Troisième acte, la sauvegarde, en direct. VM GNS3 redémarrée, puis on démarre le chemin "
                       "d'administration et le NAS TrueNAS, qui à lui seul demande 3 Go. Accéléré.",
                       until="a3_done", speed="auto")
new["a3_nas"] = seg("a3_nas", 3, "A3_nas", "a3_nas", "SRV-BCK-01 · TrueNAS", "NAS de sauvegarde en mode pull",
                    "truenas_setup.py status : pool, snapshots, tâches",
                    "SRV-BCK-01 est le NAS de sauvegarde, TrueNAS. Il tire lui-même les sauvegardes : les serveurs n'ont "
                    "aucun accès vers lui. Test : l'état du pool et des tâches. Résultat : {nas_result}.", jury=True,
                    jury_vo="Le NAS TrueNAS tire lui-même les sauvegardes. Résultat : {nas_result}.")
new["a3_restore"] = seg("a3_restore", 3, "A3_nas", "a3_restore", "SRV-BCK-01 · restauration", "preuve de restauration",
                        "fichier relu depuis le snapshot ZFS",
                        "Une sauvegarde ne vaut que si on sait la relire. Test : le même fichier, dans la copie et dans le "
                        "dernier snapshot ZFS. Résultat : {restore_result}.")
fin = dict(cur["fin"])
fin["vo"] = ("Tout ce que vous avez vu est réel et rejouable : les configurations sont générées depuis l'inventaire, et la "
             "campagne complète verify_lab compte 59 tests réussis, zéro échec. Merci.")

rec_of = {k: v.get("rec") for k, v in new.items()}
order = ["intro", "a0_boot", "a1_console", "a1_edge", "a1_ospf", "a1_leaf", "a1_adminws", "a1_fw_carp", "a1_fw_rules",
         "a1_web", "a1_soc", "a1b_switch", "a1_zabbix", "a1_grafana", "a1_bms", "a1_t6", "a1_acl", "a1_lock", "a1b_proof",
         "a1_t2", "a1_proof", "a2_switch", "a2_leafa", "a2_cmp", "a2_t5", "a2_proof", "a3_switch", "a3_nas", "a3_restore", "fin"]
out = []
for k in order:
    if k in new:
        if rec_of[k] not in have:
            print("skip (not recorded):", k)
            continue
        out.append(new[k])
    elif k == "a1_t2":
        out.append(t2)
    elif k == "a1_proof":
        out.append(pr)
    elif k == "fin":
        out.append(fin)
    else:
        out.append(cur[k])
for x in out:
    if x["id"] in ("a1_zabbix", "a1_grafana", "a1_t6", "a1_acl"):
        x.pop("src", None)
        x.pop("still", None)
p.write_text(head + yaml.safe_dump({"segments": out}, allow_unicode=True, sort_keys=False, width=118), encoding="utf-8")
print(len(out), "segments")

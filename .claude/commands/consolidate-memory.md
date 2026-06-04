# /consolidate-memory

Consolide la mémoire du projet en lisant les logs Claude des dernières 24h et en mettant à jour les 3 fichiers de mémoire persistante.

## Instructions

Tu es en train d'exécuter la consolidation de mémoire pour le projet SwiftClick_MyWhoosh.

### Étape 1 — Lire les logs des dernières 24h

Exécute ce bloc PowerShell pour lister les fichiers de session récents :

```powershell
$cutoff = (Get-Date).AddHours(-24)
$logsDir = "$env:USERPROFILE\.claude\projects\c--Users-lilia-Documents-SwiftClick-MyWhoosh"
Get-ChildItem -Path $logsDir -Filter "*.jsonl" -Recurse |
  Where-Object { $_.LastWriteTime -gt $cutoff } |
  Select-Object FullName, LastWriteTime |
  Sort-Object LastWriteTime
```

### Étape 2 — Parser les décisions clés

Pour chaque fichier `.jsonl` trouvé, lis son contenu et identifie :

**Pour `recent-memory.md` (48h glissant) :**
- Nouvelles décisions techniques prises dans la session
- Actions réalisées (fichiers créés/modifiés, bugs corrigés)
- Contexte notable de conversation (langue, environnement, outils)
- Supprime toutes les entrées datant de plus de 48h en comparant les horodatages

**Pour `long-term-memory.md` (préférences confirmées) :**
- Corrections faites par l'utilisateur ("non pas ça", "arrête de", "ne fais pas")
- Préférences confirmées ("oui exactement", "parfait", validation silencieuse d'un choix)
- Décisions d'architecture répétées ou explicitées
- N'ajoute que ce qui est non-évident et réutilisable dans de futures sessions

**Pour `project-memory.md` (état actif) :**
- Statut des tâches (en cours → terminé, nouvelle tâche apparue)
- Problèmes découverts ou résolus
- Changements d'architecture ou de structure de fichiers
- Remplace l'ancienne info par la nouvelle (c'est un état courant, pas un historique)

### Étape 3 — Mettre à jour les fichiers

Lis d'abord chaque fichier cible, puis applique les mises à jour chirurgicalement :
- `memory/recent-memory.md`
- `memory/long-term-memory.md`
- `memory/project-memory.md`

### Étape 4 — Rapport de consolidation

Termine avec un résumé court :
- Nombre d'entrées ajoutées par fichier
- Nombre d'entrées expirées supprimées de `recent-memory.md`
- Toute décision ou préférence notable extraite

## Règles

- Ne jamais inventer des décisions non présentes dans les logs
- Dater toutes les nouvelles entrées avec la date absolue (format AAAA-MM-JJ)
- Convertir les dates relatives ("hier", "la semaine dernière") en dates absolues
- Si les logs sont vides ou inaccessibles, signale-le sans modifier les fichiers
- Garder `recent-memory.md` sous 200 lignes (supprimer d'abord les plus anciennes)
- Garder `long-term-memory.md` sous 150 lignes (fusionner les doublons)

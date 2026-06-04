# /skills/research-review

Promeut les trouvailles confirmées (score 4–5) de `new_learning.md`
vers `long-term-memory.md`. À utiliser chaque dimanche ou manuellement.

## Étape 1 — Lecture et filtrage

Lis `memory/new_learning.md`.

Identifie les entrées avec simultanément :
- Score **[4/5]** ou **[5/5]**
- **Statut** : `nouveau` (pas encore `promu`)

Si aucune → réponds : "Rien à promouvoir cette semaine." et arrête.

## Étape 2 — Analyse des patterns

Groupe les entrées sélectionnées et identifie des patterns réutilisables :

| Catégorie | Quand l'utiliser |
|-----------|-----------------|
| **Bibliothèque** | Nouvelle lib utile ou mise à jour d'une lib existante |
| **Pattern** | Technique ou approche réutilisable dans le projet |
| **Évitement** | Bug connu, deprecation, anti-pattern à éviter |
| **Outil** | Outil externe utile (debug, profiling, test) |
| **API** | Endpoint ou intégration découverte |
| **Workflow** | Amélioration du processus de développement |

Règle : n'extraire que ce qui est **non-évident** et **directement applicable** au projet.
Ne pas dupliquer ce qui est déjà dans `long-term-memory.md`.

## Étape 3 — Mise à jour de long-term-memory.md

Lis `memory/long-term-memory.md`.

Ajoute en bas (ou fusionne avec une section existante sur le même sujet) :

```markdown
## Veille promue — YYYY-MM-DD
> N trouvaille(s) score 4–5 consolidées

- **[Catégorie]** : description actionnable courte (Source — URL si utile)
- **[Catégorie]** : ...
```

## Étape 4 — Marquage des entrées traitées

Dans `memory/new_learning.md`, pour chaque entrée promue :

Remplacer :
```
- **Statut** : nouveau
```
Par :
```
- **Statut** : promu
```

## Rapport final

```
Review terminée : N patterns promus depuis X entrées.
Fichiers mis à jour : long-term-memory.md (+N lignes), new_learning.md (X statuts → promu).
```

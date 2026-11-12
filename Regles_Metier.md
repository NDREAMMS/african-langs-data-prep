# Règles métier — Application d'apprentissage de langues africaines

**Langues cibles MVP :** Wolof · Lingala · Bambara
**Version :** 2.0 — synthèse des décisions de cadrage et de design
**Statut :** validée — sert de base au schéma relationnel et au contrat d'API

> **Changements v1 → v2**
> - Stack actée : Fastify (Node/TypeScript) + Prisma + ts-fsrs (remplace FastAPI/py-fsrs)
> - Cœurs **conservés**, adossés à une **économie XP** (achat de cœurs, streak freeze)
> - Nouvelle section Gamification : XP, niveaux, streak, badges (§6)
> - Nouvelle section Audio & TTS (§14)
> - Temps actif : plafonds **par type d'exercice** + accumulation **incrémentale** (§9.2)
> - Test de placement : le point de départ est déterminé par l'auto-évaluation (§10)
> - Mode jeu : conçu maintenant, construit en Phase 4+ (§8)
> - RGPD : cascade de suppression complète (§15)

---

## 1. Architecture — principes transversaux

Trois principes guident toutes les décisions techniques ci-dessous :

1. **Le serveur est l'unique source de vérité de l'algorithme.** Le client n'envoie jamais un état pré-calculé (FSRS, XP, cœurs, temps actif) — seulement les actions brutes de l'utilisateur (bonne/mauvaise réponse). Ça garantit une seule implémentation de la logique, une évolution possible sans republier l'app, et un anti-triche gratuit.
2. **Résilience réseau mobile d'abord.** Chaque appel critique est idempotent (un retry ne double-compte ni XP, ni review, ni achat de cœur).
3. **Coûts sous contrôle par conception.** Aucune clé API sensible ne vit côté client ; tout appel externe payant (TTS) passe par le serveur, qui cache et limite.

**Stack retenue** : React Native (Expo) · Fastify (Node/TypeScript) · Prisma (ORM) · PostgreSQL 16 sur VPS · Supabase Auth (JWT) · Replicate (TTS, pay-per-call) · ts-fsrs.

⚠️ Le pipeline de fine-tuning TTS (Colab, notebooks) reste en Python — projet indépendant du serveur API, non concerné par ce choix de langage.

---

## 2. Authentification

- Auth déléguée à **Supabase Auth** (email/password + OAuth Google/Apple), JWT émis côté client.
- Le serveur Fastify vérifie la signature du JWT (JWKS ou secret partagé HS256) à chaque appel.
- **Provisionnement paresseux** : premier appel valide → upsert de l'utilisateur dans la table locale à partir des claims du JWT (`sub`, `email`). Pas de webhook nécessaire.
- Aucune donnée sensible (mot de passe) stockée côté application — tout vit chez Supabase.
- ⚠️ Risque connu : Supabase met en pause les projets gratuits après ~7 jours d'inactivité API (auth en panne tant que non réactivé). Ping régulier en beta, plan Pro avant lancement public.

---

## 3. Moteur d'apprentissage — FSRS

**Algorithme retenu** : FSRS (Free Spaced Repetition Scheduler), via `ts-fsrs` (implémentation de l'écosystème open-spaced-repetition ; vérification de maintenance et de fidélité aux derniers paramètres publiés avant intégration définitive). Préféré à SM-2 car il s'adapte individuellement à chaque item/utilisateur et surperforme SM-2 sur la rétention.

Chaque item appris stocke, par utilisateur :

| Champ | Rôle |
|---|---|
| `difficulty` | Complexité intrinsèque du mot/phrase |
| `stability` | Nombre de jours avant que la probabilité de rappel tombe sous 90 % — détermine l'intervalle de révision |
| `retrievability` | Probabilité actuelle de rappel à l'instant t |
| `last_review` / `next_review` | Horodatages de planification |
| `reps`, `lapses` | Compteurs de révisions et d'échecs |

**Règles de session :**
- Nouveaux items introduits par jour : **10 maximum** (au-delà, la charge de révision devient insoutenable).
- Une session type dure 10-15 minutes, 20-30 items (**révisions dues en priorité**, puis nouveaux items).
- Items appris = mots isolés **et** phrases contextualisées, pas uniquement du vocabulaire isolé.

**Mapping rating FSRS (MVP)** : réponse correcte → `Good`, réponse incorrecte → `Again`. Le choix à 4 niveaux (Again/Hard/Good/Easy) est écarté au MVP — mapping automatique serveur, extensible plus tard (latence → Hard/Easy) sans changer le contrat d'API.

---

## 4. Curriculum & progression

### 4.1 Structure

- Un **module** = `unite` dans le schéma (terminologie conservée, pas de renommage).
- Chaque module contient **2-4 leçons** de **8-12 items** chacune (mots + phrases contextualisées).
- Chaque item est rattaché à un seul module (pas de doublons inter-modules ; un mot récurrent dans un nouveau contexte = nouvelle phrase, pas nouveau mot).
- Contenu culturel écrit **indépendamment par langue**, jamais traduit depuis une version pivot (le vocabulaire du marché, des transports ou des proverbes diffère fortement entre Dakar, Kinshasa et Bamako).

### 4.2 Plan de contenu — 8 blocs, 36 modules

| Bloc | Modules | Contenu | Statut |
|---|---|---|---|
| **1 — Survie sociale** | 1-4 | Salutations, se présenter, nombres, au marché | MVP |
| **2 — Monde concret** | 5-10 | Famille, nourriture, animaux, couleurs, maison, corps | MVP (partiel) |
| **3 — Vie quotidienne** | 11-14 | Temps, actions, déplacements, vêtements/météo | Post-MVP proche |
| **4 — Autonomie** | 15-18 | Émotions, santé, école/travail, communication de survie | Post-MVP proche |
| **5 — Vie sociale approfondie** | 19-23 | Inviter, relations, fêtes, religion courante, marché avancé | Post-MVP (priorité) |
| **6 — Vie pratique élargie** | 24-28 | Argent/mobile money, téléphone, voyage longue distance, logement, administration | Post-MVP |
| **7 — Expression & nuance** | 29-32 | Idiomes, proverbes, registres de politesse, humour/familier | Nécessite locuteur natif dédié |
| **8 — Autonomie avancée** | 33-36 | Métiers, médias, histoire/géo locale, dialogues étendus | Long terme |

**MVP retenu** : les **8 à 10 premiers modules** (blocs 1-2), le reste implémenté progressivement.

**Volume et rétention** : 18 modules ≈ 540 items, épuisés en ~54 jours au rythme de 10 nouveaux items/jour — risque de churn en semaine 8-10. Les 36 modules (~1080 items) repoussent l'épuisement à 4-5 mois. Cible long terme : 1500-2000 items. **La production de contenu est un flux continu post-lancement, pas un livrable one-shot.**

### 4.3 Déblocage de leçon — seuil des 80 %

```
score = items_corrects_premiere_tentative / total_items_leçon
```
- Seuil de déblocage de la leçon **suivante** : `score ≥ 0.8`.
- Seule la *première tentative* de chaque item compte (empêche de valider par élimination). La première tentative = la review effectuée quand l'item est présenté comme nouveau (dérivable du journal : première review de l'item par l'utilisateur).
- En cas d'échec (`score < 0.8`) : la leçon tentée n'est pas reverrouillée, l'utilisateur la refait librement — seul le déblocage de la suivante est retardé. Pas de pénalité punitive.

### 4.4 Grammaire

**Implicite uniquement en MVP** (phrases modèles, pas de règles explicites) — une grammaire explicite fiable nécessite une expertise linguistique validée par langue, reportée à une phase avec locuteur natif dédié (rejoint le Bloc 7).

---

## 5. Types d'exercices

| Type | Format | Niveau |
|---|---|---|
| Introduction (carte mot) | Mot + audio + image + traduction, exposition passive, aucune interaction | Passif |
| QCM écoute → traduction | Audio, 4 choix de traduction | Facile |
| QCM traduction → mot | Mot français affiché, 4 choix en langue cible | Facile |
| Association image | Grille d'images et de mots à relier | Facile-moyen |
| Reconstitution de phrase | Mots-étiquettes à replacer dans l'ordre | Moyen |
| Complétion à trous | Phrase à trous, banque de mots proposés | Moyen |
| Traduction libre (tapée) | Champ de saisie libre, tolérance Levenshtein (voir ci-dessous) | Difficile |
| Vrai/Faux rapide | Une traduction proposée, à valider/rejeter en un tap | Facile, rythme rapide |
| Écoute & répétition | Écoute puis répétition à voix haute, pas d'évaluation de prononciation | Phase 2 — hors MVP |

**Structure d'une leçon** : introduction passive du nouveau mot → renforcement immédiat (2-3 formats différents dans la même leçon) → consolidation finale mélangeant tous les mots vus.

**Traduction libre — scoring Levenshtein** (distance normalisée par la longueur attendue) :
- `< 10 %` → correct (✅ + XP)
- `10-30 %` → « Presque ! » — la différence est montrée, compté comme incorrect
- `> 30 %` → incorrect, bonne réponse affichée

**Retry / indices** : aucun en MVP. Une réponse incorrecte affiche directement la bonne réponse ; l'utilisateur passe à l'item suivant, qui repasse naturellement plus tôt via FSRS (stabilité abaissée) et coûte un cœur (§7).

---

## 6. Gamification — XP, niveaux, streak, badges

### 6.1 Deux mesures orthogonales

> **FSRS mesure la rétention** (qualité de l'ancrage, par item) · **XP mesure l'effort** (quantité de travail fourni, global).
> L'XP ne mesure pas la compétence — il valorise l'investissement. C'est pourquoi il coexiste avec le moteur FSRS sans doublon.

### 6.2 Revenus XP

| Source | XP | Garde-fou |
|---|---|---|
| Bonne réponse en leçon | **+10** | — |
| Bonus si streak active | **+5** par bonne réponse | — |
| Session de jeu terminée (Phase 4+) | 20-50 selon score | **Plafond 100 XP/jour** — les jeux restent un complément, pas une usine à XP |

### 6.3 XP = portefeuille, pas compteur

L'XP étant dépensable (§7), il est tenu en **journal de transactions** : table `xp_transactions` (montant signé, motif, horodatage, référence idempotente). Solde = somme du journal. Calcul et dépenses **côté serveur uniquement** ; tout achat est idempotent.

### 6.4 Niveaux utilisateur (MVP)

Paliers d'XP cumulés → « Niveau N » affiché au profil. Sentiment de croissance globale, indépendant du curriculum. Table de paliers en constante serveur (ajustable sans migration). Aucun effet mécanique : pure progression visible.

### 6.5 Streak

- **Jour actif** = ≥ 1 review avec XP dans la journée **locale** de l'utilisateur (`users.timezone`, IANA, captée à l'onboarding). Jamais UTC brut.
- **Streak freeze** : achetable **200 XP**, max **2 en stock**, consommation automatique le jour manqué. Protège *avant* la rupture.
- **Réparation de streak** (après rupture, dans les 48 h) : 500 XP, 1 fois/mois max — **post-MVP**.
- Streak brisée sans freeze → message encourageant (« Pas grave, on recommence ! »), jamais culpabilisant.

### 6.6 Badges

| Badge | Condition | MVP |
|---|---|---|
| Streak 7 / 30 / 100 jours | Streak atteint le palier | Oui (7 j visible en beta) |
| Unité franchie | Module terminé | Oui |
| XP cumulés (1 000, 5 000…) | Solde atteint | Post-MVP |

Table `user_badges` (user, badge, décerné_le) — décernement serveur, idempotent.

### 6.7 Ce que l'XP ne fera jamais

- **Débloquer du contenu pédagogique** (ça relève de la maîtrise ≥ 80 % — sinon incitation au farming).
- **Influencer le FSRS** (sinon on pousse à répondre vite plutôt que juste).
- Servir de monnaie échangeable contre de l'argent ou des avantages hors liste (§7).

---

## 7. Cœurs & économie XP

### 7.1 Paramètres

| Paramètre | Valeur |
|---|---|
| Cœurs maximum | **5** |
| Coût d'une erreur (leçons) | **-1 cœur** |
| Régénération naturelle | **+1 cœur / 4 h** jusqu'au maximum, calculée à la volée (`coeurs` + `derniere_maj_coeurs`, pas de cron) |
| Recharge par publicité récompensée | **+2 cœurs**, plafonnée à **4 publicités / jour** (compteur quotidien en heure locale) |
| Achat avec XP | **1 cœur = 100 XP** |
| Abonnement premium | Cœurs illimités |

### 7.2 Portée — la règle la plus importante

- Les cœurs concernent **les leçons uniquement** — jamais les jeux (bonus pur).
- **Les révisions dues restent toujours accessibles à 0 cœur.** Les cœurs ne bloquent que l'introduction de *nouveaux* items. Sans cette règle, un utilisateur à 0 cœur verrait ses révisions FSRS glisser et sa streak mourir — le pire scénario devient « je révise aujourd'hui, nouveaux mots demain ».

### 7.3 Boucle de déblocage — personne n'est jamais hard-stuck

```
Bloqué à 0 cœur ?  →  révise (toujours accessible)
                   →  regarde une pub (+2 cœurs)
                   →  dépense de l'XP (1 cœur = 100 XP)
                   →  [Phase 4+] joue aux jeux pour gagner de l'XP
                   →  [premium] cœurs illimités
```

Une bonne session (~25 items, 80 % réussite, streak active) rapporte ~300 XP → rachète ~3 cœurs : l'utilisateur diligent s'auto-suffit. Une session ratée (5 cœurs perdus, ~150 XP) ne rachète qu'1-1,5 cœur : la friction se sent, les alternatives gratuites existent, le premium garde son attrait. **L'erreur coûte de l'effort différé, jamais de l'argent obligatoire.**

### 7.4 Blocage

À 0 cœur : impossible d'introduire de nouveaux items dans une leçon. L'écran affiche systématiquement les voies de récupération (attendre la régénération, pub, XP) avec le temps restant.

---

## 8. Mode jeu — Phase 4+ (conçu maintenant, construit plus tard)

**Principe** : bonus pur, découplé du moteur d'apprentissage.

- **Aucun impact FSRS** — pas de `review_id`, pas de mise à jour d'état. Seul effet : XP crédité (calculé serveur, plafonné §6.2).
- **Sélection des mots** : uniquement parmi les items **maîtrisés**, défini par `stability ≥ 15` jours. (Définition unique de « maîtrisé » dans toute l'app ; le 80 % du §4.3 reste un score de *déblocage de leçon*, distinct.)
- **Déblocage** : après le module 3-4, puis un nouveau jeu tous les 3-4 modules.
- **Pas assez de mots maîtrisés** → jeu verrouillé, message explicite (« encore 3 mots à maîtriser pour débloquer Mémoire »). Seuil minimal par type de jeu (`seuil_min_jeu`), pas de valeur globale.
- **Rôle dans l'économie** : les jeux sont la voie ludique de revenu d'XP (donc de cœurs). Construits en Phase 4+ : avant la semaine 3, aucun utilisateur n'a de mot maîtrisé (stability ≥ 15 j) — les jeux seraient des portes verrouillées pendant toute la beta.

| Jeu | Mécanique |
|---|---|
| Mémoire (paires) | Grille de cartes face cachée, retrouver les paires mot/traduction |
| Mots mêlés | Grille de lettres, retrouver des mots appris cachés dedans |
| Pendu linguistique | Deviner un mot lettre par lettre à partir de sa traduction/image |
| Contre-la-montre | Enchaîner un maximum de QCM en 60 secondes |

---

## 9. Sessions — cycle de vie

### 9.1 Machine à états

```
POST /sessions → [active] ──POST /complete──▶ [completed]
                     │
                     │ cron : silence > 45-60 min
                     ▼
                [abandoned]   (reviews et XP déjà comptabilisés, rien n'est perdu)
```

- **Invariant** : une seule session active par utilisateur. Une nouvelle session abandonne automatiquement la précédente.
- **Horodatage serveur** : `started_at` posé à la création ; l'horloge du client n'est jamais utilisée.
- **Clôture explicite** (`POST /sessions/{id}/complete`) : `status = completed`, totaux **recalculés depuis le journal** (`items_vus = COUNT(reviews)`, `xp_gagne = SUM(...)`), jamais reçus du client.
- **Cron de purge** : session `active` sans review depuis 45-60 min → `abandoned`, `ended_at` = dernière review. Seuil dérivé de la durée cible (10-15 min) majorée d'une pause légitime.
- Chaque `/review` étant idempotent et créditant immédiatement, **la survie des données ne dépend jamais d'une clôture** — seule la qualité métrique en dépend.

### 9.2 Temps actif réel (hors pauses)

L'objectif quotidien mesure le **temps actif**, pas la durée wall-clock (une pause de 20 min au milieu d'une leçon n'est pas de l'apprentissage).

- **Accumulation incrémentale à chaque `/review`**, dans la même transaction que la mise à jour FSRS — la barre « 3/10 min » de l'accueil est toujours à jour, et la clôture comme le cron n'ont aucun calcul à faire.
- Formule : `temps_actif_sec += min(review[i+1].created_at − review[i].created_at, PLAFOND(type_exercice))` ; premier item : `min(review[0].created_at − started_at, PLAFOND)`.
- **Plafonds par type d'exercice** (constantes serveur) : QCM **60 s** · association **60 s** · reconstitution/complétion **90 s** · traduction libre **150 s**. Le plafond borne le temps de réflexion plausible ; au-delà, c'est une interruption.
- `temps_actif_sec` (colonne matérialisée sur `sessions`) est dérivable des reviews : un changement de plafond reste applicable rétroactivement.
- La durée wall-clock (`ended_at − started_at`) reste réservée au cron d'abandon.

### 9.3 Timezone

- Capturée automatiquement à l'onboarding (`Intl.DateTimeFormat().resolvedOptions().timeZone` côté Expo), stockée dans `users.timezone` (IANA), modifiable via le profil.
- Tous les calculs de « jour » (streak, objectif quotidien, quota de nouveaux items, compteur de pubs) utilisent cette timezone, jamais UTC brut.
- Changement de fuseau : les streaks passées ne sont **jamais** recalculées rétroactivement — seuls les calculs futurs utilisent la nouvelle timezone.

---

## 10. Test de placement

**Point de départ déterminé par l'auto-évaluation de l'onboarding :**

| Auto-évaluation | Module de départ du test |
|---|---|
| Débutant complet | Module 1 |
| Quelques notions | Module médian du MVP |
| Bases solides | Module médian + 2 (borné au dernier module disponible) |

**Marche adaptative** (pas de modèle IRT complet — suffisant au MVP) :

```
1. Question tirée du module de départ
2. Bonne réponse   → question du module suivant (plus difficile)
3. Mauvaise réponse → question du module précédent (plus facile)
4. 3 échecs consécutifs → arrêt, placement au dernier module où une réponse est correcte
5. Maximum 15 questions
```

Le résultat place l'utilisateur dans le curriculum (module de départ des leçons). Les questions de placement sont des items réels du curriculum (audio inclus).

---

## 11. Changement de langue cible

- Progression **indépendante par langue** : `user_items` est scopé par `langue` en plus de `user_id`/`item_id`.
- L'utilisateur change sa « langue active » librement dans les paramètres ; la progression des langues déjà commencées est conservée.
- **Gratuit** : une seule langue active à la fois.
- **Premium** : plusieurs langues actives simultanément (§12).

---

## 12. Monétisation

| Levier | Détail |
|---|---|
| **Économie XP** | Voie gratuite n°1 de récupération de cœurs (§7) — récompense l'effort |
| **Publicités récompensées** | Voie gratuite n°2 (+2 cœurs, 4/jour) — génère du revenu même sur les utilisateurs qui ne paieront jamais |
| **Abonnement premium** | **3-4 $/mois** de référence, pricing géographique par pays via App/Play Store (écart de pouvoir d'achat Afrique / diaspora) |

**Contenu premium** : cœurs illimités · multi-langues simultané · zéro publicité · mode hors-ligne (une fois implémenté) · statistiques avancées.

**Principe directeur** : aucune fonctionnalité pédagogique de base (leçons, modules) n'est jamais verrouillée derrière un paiement — la monétisation repose sur le confort, jamais sur la frustration de l'apprentissage.

**Calendrier** : mécanique serveur (solde XP, cœurs, compteurs) conçue dès le MVP ; intégration SDK pub et achats in-app en Phase 4.

---

## 13. Mode hors-ligne

**Statut MVP : structure de données prévue, implémentation reportée.**

- `items.audio_size_bytes` — estimation du poids d'un pack de téléchargement.
- Le statut hors-ligne est **dérivé du statut d'abonnement validé côté serveur** (jamais un booléen stocké localement, sinon désynchronisation avec les achats in-app).
- La complexité réelle (synchronisation des reviews hors-ligne, conflits multi-appareils) n'est **pas** modélisée au MVP.

---

## 14. Audio & TTS

- **Vocabulaire core (500 mots fréquents)** : enregistrements humains natifs en priorité (`items.audio_url` pré-rempli).
- **Contenu dynamique** : TTS XTTS-v2 fine-tuné via Replicate en fallback — **clé API serveur uniquement**, jamais dans l'app.
- **Cache déterministe** : `hash = sha256(langue | texte | voix)` nomme le fichier sur le disque VPS ; cache hit → URL statique servie par Caddy sans régénération ; cache miss → appel Replicate, stockage, retour. Aucun état à gérer.
- **Pré-génération batch** : le curriculum est synthétisé à l'ingestion du contenu, pas à la volée — coût marginal production quasi nul ; l'appel live ne sert qu'aux cas imprévus.
- **Rate limiting par utilisateur** sur l'endpoint TTS = plafond de coûts.
- **Pas d'évaluation de prononciation** (STT non fiable pour ces langues) — hors MVP.

---

## 15. RGPD & gestion du compte

Non négociable dès le MVP (public diaspora européenne explicitement ciblé) :

- `DELETE /users/me` — suppression en cascade **complète** : `users`, `user_items`, `sessions`, `reviews`, `xp_transactions`, `user_badges`, état cœurs + suppression du compte côté Supabase Auth.
- Export des données sur demande — export JSON (`user_items`, `sessions`, `reviews`), sans système sophistiqué au lancement.
- **Hébergement VPS en UE** (Hetzner/OVH) — simplifie la conformité, évite les transferts hors UE.

---

## 16. Points explicitement hors périmètre MVP

Récapitulatif des reports, pour éviter toute ambiguïté :

- **Mode jeu** (conçu §8, construction Phase 4+)
- **Réparation de streak** après rupture (le freeze, lui, est MVP)
- **Classement / ligues** (onglet 🏆 — post-MVP ; l'XP MVP se limite à feedback + niveaux)
- Écoute & répétition avec évaluation de prononciation (pas de STT fiable)
- Grammaire explicite (micro-leçons dédiées)
- Retry / indices sur exercice raté
- Mode hors-ligne fonctionnel (structure seulement)
- Génération de contenu par IA en temps réel côté utilisateur (IA = assistant de production uniquement, toujours validée par un locuteur natif)
- Modèle de placement IRT complet
- Intégration SDK publicités / achats in-app (Phase 4 — la mécanique serveur est prête dès le MVP)

# NOTE TECHNIQUE — v1.1

## Pilot Lingala — cadrage, stratégie tonale, protocole d'annotation & design d'évaluation

Application d'apprentissage des langues africaines — première tranche verticale sur le **lingala (lin)**

---

**STATUT DU DOCUMENT**

Révision de la note de pilot v1.0 après revue technique. Complète le registre des décisions techniques **v1.1** (D6 à D14), en particulier **D8 — couche tonale**. Ne modifie aucune décision existante ; amende/précise les décisions de pilot **L1 à L5** et en ajoute **L6 à L8**.

**Décisions de pilot soumises à arbitrage** : L1 (variante), L2 (stratégie tonale), L3 (registre TTS), L4 (code-switching), L5 (verrou tonal), L6 (orthographe), L7 (gate NMT), L8 (juridique).

8 octobre 2026 — document de conception, usage interne projet
Sources : Registre v1.1 (D6–D14) · Note de prétraitement v1.1 · Règles métier v2 · Cahier des charges design · BibleTTS OpenSLR SLR129 · WAXAL arXiv:2602.02734 · africa-g2p 0.3.2 · MADLAD-400 · FLORES-200 · Revue technique du pilot v1.0

**RÉVISION DU 2 NOVEMBRE 2026 — décision « sans relecteur natif ».** Aucun locuteur natif, linguiste ni annotateur n'est disponible. En conséquence : **L1** devient une hypothèse non vérifiée, **L2**, **L5** et **L7** sont **non applicables** (voir §6bis), le **gold set tonal (§8)** et le **design L5 (§9)** ne sont pas exécutés, et les jalons **M2/M4/M5/M7** sont retirés du périmètre. Les gates de qualité deviennent automatiques. Cette révision est consignée comme entrée au registre des décisions, conformément à la règle de fin de document.

---

**Changements v1.0 → v1.1**

| # | Point relevé en revue | Traitement |
|---|---|---|
| 1 | Étiquetage tonal par seuil F0 = **phonétique, pas phonologique** (downstep, déclinaison, abaissement final) | §4.3 étape 4 réécrite : **détendance de la déclinaison par phrase**, étiquetage **relatif aux voisins**, et surtout ton traité comme **variable latente** (HMM/CRF sur la séquence de syllabes) **amorcé par le gold set**. Encodage explicite du **downstep**. |
| 2 | Le **gold set** arrive trop tard ; un seuil non calibré n'a pas de sens | Gold set **remonté en M1–M2** (§5, §8) ; **deux annotateurs** + kappa ; mots **en contexte de phrase** ; **tirage aléatoire** ajouté au tirage par fréquence. Protocole complet §8. |
| 3 | Pas de **baseline TTS sans ton** ; le pipeline tonal doit prouver sa valeur | Nouveau jalon **M3 — baseline sans conditionnement tonal**, **go/no-go** (§5, §9). L5 réécrite : **comparaison contrôlée**, métrique et seuil **pré-enregistrés** avant résultats. |
| 4 | **Conflit A5** (1,5–10 s) avec les versets BibleTTS longs | Alignement forcé **segmente les versets en sous-clips avant A5** ; rétention signalée explicitement (renvoi prétraitement §5). |
| 5 | Orthographe **archaïque / e-o vs ɛ-ɔ** ; variété du locuteur non prouvée | **Étape de normalisation orthographique** Bible → moderne (L6) ; **vérification de la variété** du locuteur studio avant de figer L1 (§2, L1). |
| 6 | « Aucun blocage de licence » **exagéré** : CC BY-SA = **copyleft** | §2 et §7 corrigés : CC BY-SA = partage à l'identique ; **droits du texte biblique** distincts de l'audio ; **revue juridique** avant M7 (L8). |
| 7 | Lexique **mot-clé** conflit des formes verbales (TAM + objet) | Lexique **clé morphème** et pour les verbes **mot + catégorie TAM** (§4.3 étape 5, L6). |
| 8 | Fine-tuning NMT sur bible = **effondrement de domaine** ; risque de lingala faux | **Gate humain** sur le vocabulaire core ; NMT = **brouillon** (§3, L7). |

---

## 1. Objet et justification du choix

Le pilot prend le **lingala comme première tranche verticale** : construire la chaîne complète FR → lingala (NMT, G2P segmental, couche tonale, TTS, cache audio) sur une seule langue avant d'étendre au wolof et au bambara.

1. **Couverture d'actifs** — le lingala dispose d'un corpus TTS aligné volumineux (BibleTTS, 71,6 h studio), d'un corpus ASR (WAXAL `lin_asr`), d'un modèle NMT permissif qui le couvre (MADLAD-400) et d'un G2P segmental (africa-g2p).
2. **Levée de blocages** — le lingala **neutralise 3 des 4 blocages** du registre v1.1 (licences An ka taa/Corbama, statut tonal du wolof, datasets gated). Aucune source lingala n'est gated — mais **une réserve juridique subsiste** (§2, L8).
3. **Risque résiduel concentré** — le seul point dur est **le ton**, qui est aussi le cœur de D8. Le traiter sur la langue la mieux dotée est le moyen le moins coûteux de valider ou d'invalider la couche tonale — **à condition de prouver qu'elle apporte quelque chose** au-delà d'un TTS sans ton (M3, §9).

**Ce que cette note couvre** : actifs (§2), périmètre (§3), stratégie tonale (§4), jalons (§5), décisions de pilot (§6), dépendances (§7), **protocole d'annotation gold (§8)**, **design d'évaluation L5 (§9)**.
**Ce qu'elle ne couvre pas** : wolof et bambara, le produit applicatif (D-a→D-d), l'infrastructure ClearML (D12).

---

## 2. Actifs lingala vérifiés

| Brique | Source | Volume / détail | Licence | Statut |
|---|---|---|---|---|
| TTS (aligné) | **BibleTTS** (`lin`) | **71,6 h** alignées — 15 117 versets, FLAC 48 kHz / 24 bit, 1 locuteur studio | **CC BY-SA 4.0** (copyleft) | ⚠️ commercial-compatible **sous conditions** (L8) |
| TTS (bonus) | BibleTTS (`lin`, non aligné) | +151,7 h non alignées | CC BY-SA 4.0 | ⚠️ idem |
| Parole / ASR | **WAXAL** `lin_asr` | ~89 000 clips, 16 kHz, multi-locuteurs | **CC BY 4.0** | ✅ |
| NMT | **MADLAD-400** (3B) | couvre `lin_Latn` | **Apache-2.0** | ✅ (D6) |
| Évaluation NMT | **FLORES-200 devtest** `lin_Latn` | jeu d'éval standard | CC BY-SA 4.0 | ✅ |
| G2P segmental | **africa-g2p** 0.3.2 | couvre `lin`, multigraphes conservés | **MIT** | ✅ (D9) |
| Lexique tonal | — | **aucune source ouverte** | — | ⛔ **trou principal** |
| G2P (baseline) | LanguageNet / espeak-ng | pas de FST lingala, pas de voix | MIT | ❌ inutilisable |

**Réserve juridique (corrige v1.0).** CC BY-SA 4.0 n'est pas « permissif » : c'est un **copyleft**, dont la clause de **partage à l'identique** peut se propager à des **artefacts dérivés** — en particulier le **lexique tonal** issu de l'audio Bible (bootstrap §4.3), s'il est publié ou embarqué. S'ajoute la distinction **droits de l'audio vs droits du texte biblique** : la licence du corpus ne couvre pas nécessairement l'usage commercial du **texte** dans l'app. → **Revue juridique requise avant mise en production** (L8).

**Variété du locuteur (L1).** La vérification que le locuteur studio BibleTTS est bien de **variété Kinshasa** n'est pas faite. Tant qu'elle ne l'est pas, L1 énonce une **hypothèse**, pas un fait.

**Conclusion actifs** : tout est disponible **sauf le ton**, et le lingala porte une réserve juridique sur le dérivé. Le ton est le verrou technique, le copyleft est le verrou juridique.

---

## 3. Périmètre de la tranche lingala

```
[Texte FR] ─► [D6 MADLAD-400] ─► [Texte lin] ─┬─► [D9 africa-g2p] ─► [L6 normalisation orthogr.] ─► [D8 couche tonale lin] ─► phonèmes + tons
                                               │                                                                        │
                                               │                                                                        ├─► TTS : [acoustique] ─► [vocodeur] ─► audio
                                               │                                                                        └─► affichage prononciation écrite
                                               └─► texte affiché (contrôles automatiques du core, L7 → auto)
                                                            cache audio  sha256("lin|texte|voix")
```

Sous-MVP : **NMT FR→lin**, **prononciation écrite**, **audio TTS** pour un vocabulaire core, servis depuis le cache.

**Gate humain (L7).** Le fine-tuning NMT sur données parallèles bibliques risque un **effondrement de domaine** ; un lingala faux **enseigne du faux lingala**. Donc : pour le **vocabulaire core**, les entrées sont **revues par un humain** ; le NMT sert de **brouillon** (proposition à valider), jamais de vérité exposée telle quelle sur le core.

**Hors périmètre** : STT/scoring (§14), variantes régionales multiples, ClearML hébergement (D12).

---

## 4. Le problème tonal lingala

### 4.1 Faits linguistiques retenus

- Le lingala est **tonal** : opposition **haut (H) / bas (L)** sur le noyau syllabique, ton **descendant**, tons **portés par les morphèmes verbaux**, **paires minimales** documentées (`mutu/mutú`, `kokoma/kokóma`).
- **L'orthographe standard ne marque pas le ton** : le texte courant n'encode pas l'information tonale.
- La réalisation est façonnée par la **prosodie de phrase** : **déclinaison** (baisse progressive de F0), **downstep** (abaissement d'un H après un L flottant), **abaissement final**. → Ces effets rendent tout étiquetage « F0 absolu » **phonétique, pas phonologique** (§4.3).
- Le ton obéit à un **sandhi au niveau phrase** (D8).

### 4.2 Pourquoi aucun outil existant ne le fournit

| Outil | Comportement | Pourquoi insuffisant |
|---|---|---|
| `africa-g2p` (lin) | G2P segmental ; supprime le ton en IPA | Le champ `tones` **documente la convention d'écriture** (bas non marqué / aigu `á` / circonflexe descendant / caron montant), **pas un prédicteur** |
| LanguageNet / espeak-ng | pas de FST nigala, pas de voix | — |
| MADLAD-400 | émet du **texte**, non toné | Le ton n'est pas dans la cible texte |

**Conséquence** : le ton n'est récupérable ni du texte normalisé, ni des G2P existants.

### 4.3 Stratégie retenue — bootstrapper le lexique tonal depuis l'audio

> **Non exécuté** — décision « sans relecteur natif » (§6bis, 2026-11-02). Le lexique tonal et le labeler HMM/CRF sont retirés du périmètre ; régime segmental A.

Le ton existe dans **l'audio parlé**. BibleTTS fournit 71,6 h alignées, **un seul locuteur**, studio 48 kHz — conditions favorables — **avec deux pièges** : (a) la prosodie de lecture biblique est très régulière, ce qui peut donner des étiquettes **plus propres qu'elles ne le sont** ; (b) un seul locuteur = une variété.

Pipeline en six étapes (révisé) :

1. **Segmentation / alignement forcé** — phonémiser le texte avec `africa-g2p`, puis aligner texte ↔ audio au niveau phonème (modèle auto-supervisé type wav2vec2/MMS, ou MFA si un dictionnaire suffisant est dérivé en amont). **Segmente les versets longs en sous-clips** (correctif A5, §5).
2. **Syllabification** — découpe en syllabes selon les règles CV du lingala (noyau vocalique, attaque, multigraphes `ny`, `mb`, `kp`).
3. **Extraction F0** — F0 par trame (pYIN / CREPE / torchaudio), F0 par syllabe sur le noyau, normalisation **par locuteur** (log-F0 centré/réduit), voisé/non voisé.
4. **Étiquetage tonal — réécrit.** Traiter le ton comme **variable latente** : **détendance de la déclinaison** (baseline spline/linéaire sur la phrase), étiquetage **relatif aux syllabes voisines**, et **modèle de séquence (HMM ou CRF) sur la suite de syllabes** qui encodent déclinaison et **downstep** — plutôt qu'un seuil F0 par syllabe. Le modèle est **amorcé par le gold set humain** (§8) et sert à étendre l'annotation.
5. **Lexique — réécrit.** Agrégation **par morphème** ; pour les **verbes**, entrée **mot + catégorie TAM** (temps-aspect-mode), car le ton verbal dépend du TAM **et de l'objet** : un lexique clé-mot **conflit** les formes. Chaque entrée porte `{graphemes, phonemes, ton par syllabe, TAM, fréquence, dispersion}`.
6. **Prédicteur + sandhi** — modèle texte → séquence de tons pour les OOV, **sandhi au niveau phrase** en entrée du modèle acoustique (D8). Le sandhi **seul ne suffit pas** si le lexique confond les formes (correctif étape 5).

**Conflit avec D8 (à acter).** D8 écartait « tons appris implicitement par le seul TTS ». La revue le conteste : un TTS de 71 h peut apprendre **une partie** de la hauteur implicitement. → On ne tranche pas par principe : on **mesure** (M3, §9). Si le baseline implicite fait jeu égal, la couche tonale n'est **pas déployée** pour le lingala.

### 4.4 Validation de la qualité tonale

- Gold set (§8) : **mots en contexte de phrase**, **deux annotateurs**, kappa sur H/L.
- Test sur **paires minimales** (D8 : `mutu/mutú`, `kokoma/kokóma`) et formes verbales TAM.
- Métriques : **F1 par classe (H, L)**, **exactitude tonale au niveau mot**, **vs baseline majoritaire « tout L »** (l'exactitude par syllabe est **faussée** par le déséquilibre de classe — H plus rare).

### 4.5 Risques

| Risque | Impact | Mitigation |
|---|---|---|
| Étiquetage phonétique pris pour phonologique | Faux tons systématiques | Variable latente HMM/CRF, détendance, downstep (§4.3 étape 4) |
| **Prosodie de lecture biblique trop régulière** | Labels plus propres qu'en parole réelle | Contrôle sur un échantillon WAXAL (parole spontanée) avant de généraliser |
| **Registre biblique étroit**, 1 narrateur | Lexique non représentatif | Compléter par vocabulaire fréquent WAXAL ; documenter `domain` |
| **Orthographe archaïque** / `e-o` vs `ɛ-ɔ` | Casse le G2P et le filtre T7 ; ne colle pas à la sortie MADLAD | Étape de **normalisation orthographique** (L6), validation G2P sur échantillon |
| **Code-switching FR↔lin** | Non couvert au pilot | Politique L4, périmètre assumé |
| **Conflit de formes verbales** | Sens faux | Lexique clé-morphème / mot+TAM (étape 5) |
| **Dérive mono-locuteur** | Biais de variété | Variété de référence, pas vérité générale (L1) |
| **Copyleft CC BY-SA** sur les dérivés | Blocage juridique | Revue juridique (L8) avant mise en production |

### 4.6 Verrou de sortie (décision L5)

Trois régimes possibles (A = sans ton, B = ton explicite, C = affichage toné sans TTS conditionné). L5 **pré-enregistre** la métrique et le seuil **avant** de voir les résultats, et exige que **B batte A** de façon démontrable (§9) pour justifier le pipeline tonal. Sinon, régime A.

**Révision 2026-11-02** : L5 est **non applicable** — l'ABX/MOS natif n'est pas possible ; le pipeline tonal est abandonné au profit du **régime A (segmental)**. Voir §6bis.

---

## 5. Jalons (revus : gold set et baseline remontés)

| Jalon | Objet | Dépend de | Livrable |
|---|---|---|---|
| **M0** | Étape 0 prétraitement (smoke test `sm_120` + calibrage) ; manifests lin ; **segmentation versets → sous-clips** | — | `report.json` lin (rétention, `domain`, locuteurs) |
| **M1** | G2P segmental lin + **normalisation orthographique** Bible→moderne | M0 | phonémisation `africa-g2p` validée ; tables orthographiques (L6) |
| **M2** | ~~Gold set tonal annoté~~ — **retiré (sans relecteur)** | — | — |
| **M3** | **Baseline TTS sans conditionnement tonal** — **go/no-go** | M0, GPU | modèle A entraîné + UTMOS/WER (automatique) |
| **M4** | ~~Bootstrap tonal (HMM/CRF)~~ — **retiré (sans relecteur)** | — | — |
| **M5** | ~~Prédicteur texte→ton + sandhi~~ — **retiré (sans relecteur)** | — | — |
| **M6** | NMT FR→lin (+ **contrôles automatiques** du core) | M0 | MADLAD-400 fine-tuné, scores FLORES `lin_Latn` (L7 → auto) |
| **M7** | ~~TTS conditionné au ton + éval L5~~ — **retiré (sans relecteur)** | — | — |
| **M8** | Assemblage tranche | M6, M7 | chaîne FR→lin + cache + endpoint |

**Décision structurante** : **M3 est un go/no-go**. Si le baseline implicit-tone (A) atteint le seuil de perception native, **on arrête le pipeline tonal** (M4–M5, M7-B) et le pilot sort en régime A. Ne construire M4–M7 qu'après un M3 négatif.

**Prérequis dur** : M0 ne démarre qu'après l'**étape 0** de la note de prétraitement (smoke test `sm_120`, calibrage). Aucun seuil figé avant.

---

## 6. Décisions de pilot (L1–L8)

| # | Décision | Options | Recommandation | Arbitre |
|---|---|---|---|---|
| **L1** | Variante de référence | Kinshasa / autre | **Kinshasa** — **hypothèse non vérifiée** (pas de relecteur) | Produit |
| **L2** | Stratégie tonale | (a) bootstrap audio, labeler **HMM/CRF** · (b) dictionnaire licencié · (c) tonless définitif | **non applicable** — sans relecteur, le ton n'est pas développé (régime A) | ML |
| **L3** | Registre TTS | (a) BibleTTS seul · (b) mix BibleTTS + WAXAL | **(a)** au pilot, WAXAL pour le vocabulaire courant | Produit + ML |
| **L4** | Code-switching FR↔lin | (a) ignorer · (b) tolérer · (c) rejeter | **(a)** au pilot, paramétrable (prétraitement T7) | Produit |
| **L5** | Verrou de sortie tonal | (a) comparaison contrôlée A vs B, **métrique+seuil pré-enregistrés** · (b) exposer sans seuil | **non applicable** — ABX/MOS natif impossibles ; régime A retenu | Produit |
| **L6** | Normalisation orthographique | (a) table Bible→moderne + validation G2P · (b) aucune | **(a)** : sinon G2P/T7 cassés et désalignement avec MADLAD | ML + linguiste |
| **L7** | Gate NMT sur le core | (a) revue humaine des entrées core · (b) NMT exposé brut | **remplacé** : contrôles automatiques (back-translation + chrF/COMET), cf. §6bis | Produit |
| **L8** | Revue juridique | (a) avant mise en production · (b) plus tard | **(a)** : copyleft CC BY-SA sur les dérivés (voix, lexique) + droits du **texte** biblique | Juridique |

### 6bis. Révision du 2026-11-02 — sans relecteur natif

Décision consignée au registre (remplace l'exigence d'arbitrage natif de L1/L2/L5/L7) :

| Sujet | Décision | Conséquence |
|---|---|---|
| L1 — variété | Kinshasa **assumé par défaut**, non vérifié | documenté comme hypothèse ; pas de blocage |
| L2 — stratégie tonale | **non applicable** | pas de lexique tonal ni de labeler ; régime **A** |
| L5 — verrou tonal | **non applicable** | pas d'ABX/MOS natif ; pipeline tonal abandonné |
| L7 — gate NMT | **remplacé** | back-translation + chrF/COMET + couverture lexicale |
| M2/M4/M5/M7 | **retirés** | le pilot sort en régime segmental |
| §8 gold set / §9 design L5 | **non exécutés** | conservés comme archive de conception |
| MOS natif de M2 | **remplacé** | UTMOS/DNSMOS + WER via M3 |
| Calibration M3 | **remplacée** | natif vs audio corrompu |

**Règle** : toute décision exigeant un jugement natif est hors périmètre. Les décisions restantes (L3, L4, L6, L8) tiennent.

---

## 7. Dépendances et prochaines étapes

**Dépendances**

- **Étape 0 prétraitement** (smoke test `sm_120` + calibrage) — bloquante pour M0.
- **Locuteur natif** — **non disponible** (décision §6bis) ; M2/gold set retirés, L1/L2/L5 non applicables.
- **Revue juridique** (L8) — avant mise en production.
- **Aucun blocage de licence *gated*** pour le lingala ; **réserve copyleft** sur le dérivé (corrige v1.0).

**Prochaines étapes (ordre retenu en revue)**

1. ~~Protocole d'annotation du gold set (§8)~~ — **retiré** (sans relecteur).
2. ~~Design d'évaluation L5 (§9)~~ — **retiré** (sans relecteur).
3. Arbitrer **L3, L4, L6, L8** (L1/L2/L5/L7 tranchés par §6bis).
4. Exécuter **M0 → M1 → M3 (go/no-go)** ; M2/M4/M5/M7 retirés.

---

## 8. Protocole d'annotation du gold set tonal

> **Non exécuté** — décision « sans relecteur natif » (§6bis, 2026-11-02). Conservé comme archive de conception.

### 8.1 Principe

Le gold set est **l'instrument de mesure** du pilot : il calibre le labeler (§4.3 étape 4) **et** évalue le baseline sans ton (§9). Il est donc produit **en M2, avant M3 et M4**, pas après.

Unité d'annotation : le **mot en contexte de phrase** (jamais le mot isolé), avec, pour chaque syllabe, un **niveau tonal** à attribuer.

### 8.2 Composition (échantillonnage stratifié)

| Stratum | Taille cible | Rôle |
|---|---|---|
| Mots **fréquents** | ~300 (contexte d'occurrence réel) | Couvre le cœur, mais **biaisé** vers fonctionnels et formes verbales |
| Tirage **aléatoire** | ~200 | Corrige le biais du tirage par fréquence |
| **Paires minimales** | ~20 paires (D8 : `mutu/mutú`, `kokoma/kokóma`) | Discrimine H/L au seuil de perception |
| **Formes verbales TAM** | ~80 (mêmes racines, TAM différents) | Valide la clé « mot+TAM » (§4.3 étape 5) |

Total indicatif : **~600 items annotés** (mots en contexte). Chaque item : audio, phrase, mot cible, découpage syllabique, phonèmes (`africa-g2p`), tons attendus (formulaire vide).

### 8.3 Outil et consignes d'annotation

- Interface : **waveform + segmentation syllabique + courbe F0 superposée** sur l'audio.
- Saisie : **H / L / descendant / incertain** par syllabe ; marquage **voisé/non voisé** ; saisie **aveugle** au label automatique (pas de suggestion de la machine au premier passage).
- **Deux passes** par annotateur (test-retest intra-annotateur).

### 8.4 Formation des annotateurs

Le locuteur natif **n'est pas habitué à rendre le ton explicite**. Avant production :

1. Séance de **calibration** sur des paires minimales connues (`mutu/mutú`), avec l'affichage F0.
2. **Guide d'annotation** (conventions H/L, gestion du descendant, cas incertains).
3. **Tour d'essai** non compté, avec retour.

### 8.5 Qualité et accord

- **Deux annotateurs** indépendants sur tout l'échantillon.
- **Kappa de Cohen** sur H/L (cible : **≥ 0,80** ; sinon réviser le guide et re-annoter les zones discordantes).
- **Arbitrage** des désaccords par un **linguiste** (ou troisième natif formé).
- Report des taux de désaccord **par stratum** (les paies TAM et les fonctionnels désaccordent plus).

### 8.6 Sortie (`gold_tonal.jsonl`)

```
{ id, phrase, mot_cible, span_audio, syllabes[],
  phonemes[], tons[] (H|L|desc|null), tam|null,
  annotateurs[], kappa, statut (consensus|arbitre) }
```

### 8.7 Usages

- **M2** : produire le gold (§8.6).
- **M4** : **amorcer** le labeler latent (HMM/CRF) et le **valider** sur la partie non-amorcée (split train/éval par item).
- **M3/M7** : servir de **référence** au test d'écoute et aux métriques L5 (§9).

---

## 9. Design d'évaluation L5 (pré-enregistré)

> **Non exécuté** — L5 est non applicable sans relecteur natif (§6bis). Conservé comme archive de conception.

### 9.1 Question

**Le conditionnement tonal explicite (B) fait-il mieux qu'un TTS apprenant la hauteur implicitement (A) ?** Si non, le pipeline tonal n'est pas déployé.

### 9.2 Bras

| Bras | Description |
|---|---|
| **A** | TTS end-to-end sur BibleTTS **sans** entrée tonale (texte/segmental seuls) — **M3** |
| **B** | Même TTS **conditionné** aux tons produits par D8 (M7) |
| **C** (optionnel) | Affichage toné sans conditionnement acoustique (pédagogie) |

Mêmes données, même architecture, même seed ; seule l'entrée tonale change.

### 9.3 Métriques (pré-enregistrées)

**Automatiques** (sur le gold §8, split éval) :
- **F1 par classe H et L** (pas l'exactitude globale) ;
- **exactitude tonale au niveau mot** ;
- **écart au baseline majoritaire « tout L »** (obligatoire : sans lui, un score élevé peut n'être que du déséquilibre de classe).

**Perception** (locuteurs natifs) :
- **ABX / paires minimales tonales** (D8) : préférence/correctitude B vs A ;
- **MOS-like** (ou MUSHRA léger) sur la naturalité, avec distracteurs.

### 9.4 Seuil et règle de décision (fixés **avant** le run)

- B doit **dépasser A** sur **F1(H)** **et** sur l'**ABX** natif, avec **borne inférieure d'intervalle de confiance** au-dessus du seuil de non-infériorité fixé au préalable ;
- le tout **au-dessus** du baseline all-L ;
- sinon → **régime A**, pipeline tonal gelé, décision consignée.

### 9.5 Contrôles

- Ne **jamais** rapporter l'exactitude par syllabe seule (gonflée par le déséquilibre).
- Intervalles de confiance sur toutes les métriques ; taille d'échantillon d'écoute justifiée.
- **Pré-enregistrement** de la métrique, du seuil et de la règle **dans ClearML** (D12) **avant** M3/M7.

*Fin de la note de pilot v1.1 (révisée le 2026-11-02 — décision « sans relecteur natif », §6bis). Toute évolution de L1–L8 doit donner lieu à une nouvelle version ou à une entrée au registre des décisions.*

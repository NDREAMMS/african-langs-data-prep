# NOTE TECHNIQUE — Reste à faire

## Pipeline de prétraitement — ce qu'il reste à mettre en place

Application d'apprentissage des langues africaines — Wolof · Lingala · Bambara

---

**STATUT du DOCUMENT**

Compagnon de `Pretraitement_Donnees_v1.1.md` et de `Decisions_Techniques_v1.1_Architecture_ML.md`.
Décrit ce qui **reste à mettre en place** autour du code de la pipeline, désormais écrit et
exécutable pour le lingala (`ml/preprocess/`).

**Date** : 16 octobre 2026 — rév. 18 octobre 2026 : décisions D-a→D-e tranchées + audit licences —
rév. 2 novembre 2026 : décision D-f (validation auto) + `calibrate auto`. Document de conception, usage interne projet.

---

## 1. Où on en est

Le **code** de la chaîne de prétraitement est en place (`ml/preprocess/`), conformément au §9 du
document de prétraitement :

| Composant | État | Fichier |
|---|---|---|
| Config unique + politique de validation (`human`/`auto`) | ✅ | `configs/preprocess.yaml`, `common/config.py` |
| Journal des rejets + rétentions (§2.3, §7) | ✅ | `common/journal.py` |
| Chaîne texte T1→T11 | ✅ (T6/T9 sautés sans modèle) | `text_nmt.py` |
| Chaîne audio A1→A12 (ordre v1.1) | ✅ (A7/A9 sautés sans modèle) | `audio_tts.py` |
| Chaîne G2P G1→G7 | ⛔ tonal bloqué (D8/D14) ; segmental via `africa-g2p` non branché | `text_g2p.py` |
| Calibrage humain + automatique (`auto`, preuves) | ✅ | `calibrate.py` |
| Gates automatiques de publication | ✅ | `gates.py` |
| Rapports + ClearML | ✅ | `report.py` |
| Tests golden | ✅ 46 tests | `tests/golden/` |

**Ce qui manque n'est pas du code** : ce sont des **entrées externes** — seuils calibrés, modèles,
données de référence et décisions produit. Chaque absence est déjà tracée dans `run_notes.json` ;
rien n'est silencieux.

> Politique de validation (D-f) : en mode `human`, un seuil sans `provenance: calibrage_<lang>_<date>`
> bloque la publication. En mode `auto`, `auto_<lang>_<date>` et, pour les blocs whitelistés
> (`T8_minhash`, `A3_loudness`), `hypothese_*` sont admis ; le manifest reste non publiable si les
> gates automatiques échouent ou si un bloc n'a aucune provenance. `--allow-draft` force un run
> d'inspection (`publishable: false`).

---

## 2. Étape 0 — bloquante (à faire EN PREMIER)

### 2.1 Smoke test `sm_120` (technique)

**But** : éviter d'écrire tout le reste et de découvrir que la chaîne audio ne tourne pas sur Blackwell.

- Compiler/charger sur la **RTX 5090** : `torchaudio` (résample + mel), ONNX **DNSMOS**, **XLS-R-300m (M3)** — MMS exclu (D6).
- Version imposée : PyTorch ≥ 2.7 (wheels cu128) / CUDA 12.8+ (D13).
- **Sortie = Go / No-Go.** No-Go → ajuster D7/D13 **avant** de continuer.

### 2.2 Calibrage des seuils (données)

**But** : remplacer chaque hypothèse par une valeur mesurée, par langue.

| Étape | Détail |
|---|---|
| Échantillon texte | 300 lignes/lang annotées : `lang_id_ok`, `pair_ok`, `in_alphabet` |
| Échantillon audio | 100 clips/source/lang annotés : `quality_ok`, `text_match_ok` |
| Règle | viser **≥ 95 % de précision sur les rejets** (sauf A9 : détecter les mauvais appariements) |
| Vérif. couverture | rappel réel de `fasttext lid.176`, WER de réf. M3, cosinus SONAR, scores DNSMOS |
| Sortie | `preprocess.yaml` (chaque seuil avec `provenance: calibrage_<lang>_<date>`) + `configs/calibration_<lang>.md` |

Depuis **D-f**, le calibrage humain n'est plus le seul chemin : `python -m ml.preprocess.calibrate auto`
calcule les seuils par percentiles sur données réelles (ou norme LUFS / hypothèses whitelistées),
écrit `calibration_auto.json` + preuves, puis `apply --auto` les reporte avec
`provenance: auto_<lang>_<date>`. Le calibrage humain reste la référence quand un échantillon annoté existe.

**Sans calibrage (humain ou auto), aucun manifest n'est publiable.** Pour le lingala : `configs/calibration_lin.md` (protocoles auto + humain).

---

## 3. Fournir les modèles (étapes marquées `*`)

Ces étapes existent dans le code mais sont **sautées** tant que le modèle n'est pas fourni.

| Étape | Modèle | Clé de config | Comportement actuel |
|---|---|---|---|
| **A7** qualité perceptuelle | `dnsmos.onnx` | `audio.A7_dnsmos.model_path` | sauté, journalisé |
| **A9** cohérence texte↔audio | M3 (XLS-R + CTC) — MMS exclu (D6) | `audio.A9_asr_wer.model_path` | sauté, journalisé |
| **T6** identification de langue | `fasttext lid.176` (**couverture `lin` à vérifier** → repli cld3/classifieur maison) | `text.T6_langid` | repli, journalisé |
| **T9** qualité de parallélisme | SONAR / LaBSE | `text.T9_parallel` | sauté, journalisé |

Ces seuils (3,0 · 30 % · 0,75 · 0,55) sont des **hypothèses de la littérature**, pas des valeurs de nos données (§3.4).

---

## 4. Passer des replis CPU aux cibles de production

Ces replis ont permis de faire tourner la pipeline **sans GPU ni modèles** ; en production il faut les remplacer.

| Étape | Repli actuel (CPU, testé) | Cible production |
|---|---|---|
| **A4** VAD | énergie maison | `silero-vad` |
| **A12** mel | scipy (filtres triangulaires) | `torchaudio` (80 bandes) |
| **A3** loudness | clipping seul testé | `pyloudnorm` (−23 LUFS ± 1) |
| **A8** SNR | estimateur simple | `WADA-SNR` |

> Note de fond : les replis ne sont **pas bit-identiques** à la prod → ne jamais publier un manifest issu d'un repli (c'est signalé dans `run_notes.json`).

---

## 5. Données manquantes

| Donnée | Usage | État |
|---|---|---|
| **Référentiel anti-fuite** FLORES-200 devtest | T10 / A10 | `data/flores/devtest/` **vide** → non vérifié |
| **Corpus parallèle FR↔lingala** | chaîne NMT | absent → NMT validé sur échantillon temporaire seulement |
| **Lexique tonal lingala** (D8) | chaîne G2P | à construire (grammaires lingala) |
| **Licence d'export An ka taa / Corbama** | G2P bambara (D14) | **audité 2026-10-18 → bloqué** (voir ci-dessous) |
| **Corpus courant FR↔lingala** (D-e) | registre de rejets → NMT | **audité 2026-10-18 → refusé** (licence inconnue) |

### Conclusions d'audit licences (2026-10-18)

Registre : `ml/corpus/configs/sources.csv` → `data/corpus/audit.json` (`python -m ml.corpus.run audit`).

- **Bamadaba / Corpus Bambara de Référence** (Vydrin & al.) : **CC BY-NC-SA 3.0 FR** → **non commercial → EXCLU** (D6). Bloque le lexique tonal bambara (D14).
- **An ka taa** (Donaldson & Fenayon) : **aucune licence ouverte affichée** → non utilisable tel quel ; contact auteurs requis.
- **`michsethowusu/french-lingala_sentence-pairs`** (~692k) : dérivé de **NLLB-v1 / OPUS**, **aucune licence explicite** et registre majoritairement religieux → **REFUSÉ** (D6).
- **`Svngoku/central-africa-multilingual-translation`** (~7,05M) : agrégation (michsethowusu + `google/smol`), **licence inconnue** → **REFUSÉ** (D6).
- **OPUS** générique : refusé en bloc ; rouvrir **sous-corpus par sous-corpus** (JW300 CC-BY-NC et clauses NC/ND exclus).

> Conséquence : les deux pistes « corpus courant » de D-e sont **écartées** ; il faut sourcer un corpus FR↔lin **explicitement sous licence permissive** (ou obtenir une autorisation écrite). G2P bambara reste bloquée sans autorisation des ayants droit.

---

## 6. Décisions produit — TRANCHÉES le 2026-10-18 (§11)

Figées dans `ml/preprocess/configs/decisions.yaml` et câblées dans `configs/preprocess.yaml`.

| # | Décision | Tranché | Porteur |
|---|---|---|---|
| D-a | Politique code-switching (T7) | **hybride** : `strict` TTS / `tolerant` NMT (+ marquage `domain`) | produit |
| D-b | Mode des filtres T4 / A5 / A6 | **`bucket`** | ML |
| D-c | Ton du wolof (§6) | **`none`** (revue `pitch_accent` ultérieure) | ML + linguiste |
| D-d | Registre TTS à couvrir | **`[religious, courant]`** (source courante à trouver) | produit |
| D-e | Élargir le corpus courant | **audit licences maintenant**, téléchargement différé (`audit_pending`) | produit + juridique |
| D-f | Validation sans relecteur | **auto** : percentiles + hypothèses whitelistées (T8, A3) + gates auto | ML |

> D-c, D-d sont posées en valeurs par défaut à remplacer dès qu'une source/revue est disponible.
> D-f autorise `auto_*` et `hypothese_*` (blocs whitelistés) à débloquer la publication, sous réserve
> des gates (`gates.py`) ; ces seuils restent marqués `auto_unvalidated`.

---

## 7. Supervision ClearML (§8, D12)

- Installer l'agent, lancer avec `--clearml`.
- Un **task par étape** → comparer taux de rejet et rétentions entre versions de config.
- **Scores GPU en cache** (DNSMOS, ASR) versionnés comme artefacts (rejouabilité).
- Manifests publiés comme **ClearML Datasets** ; un entraînement référence un `dataset_id`.
- Hébergement non tranché : `app.clearml.com` (gratuit) vs local (D12).

---

## 8. Synthèse et ordre d'exécution

| # | Action | Bloquant ? | Livrable |
|---|---|---|---|
| 1 | Smoke test `sm_120` (sur la 5090) | **oui** | Go / No-Go audio |
| 2 | ~~Trancher D-a à D-d~~ **+ D-e** ✅ 2026-10-18 | fait | `configs/decisions.yaml` |
| 3 | Fournir les modèles A7 / A9 / T6 / T9 | oui (pour la prod) | `model_path` renseignés |
| 4 | Calibrage : `calibrate auto` (D-f) et/ou 300 lignes + 100 clips/lang | **oui** | seuils sourcés + preuves + `calibration_*.md` |
| 5 | Remplacer les replis CPU par les cibles (§3) | oui (prod) | étapes natives |
| 6 | Ingérer le référentiel FLORES + corpus FR↔lin | oui (T10 / NMT) | anti-fuite actif, NMT réel |
| 7 | Brancher ClearML + datasets | non | suivi distant |
| 8 | Débloquer la licence G2P → `text_g2p.py` | non (G2P) | manifest G2P v1 |

### Définition de « terminé » (manifest publiable)

Un manifest est publiable quand **toutes** ces conditions sont réunies :

1. `blocked_blocks()` est vide (mode `human` : `calibrage_*` ; mode `auto` : `auto_*`/`hypothese_*` admis) ;
2. les gates automatiques passent (`gates.ok`) → `report.json` porte `publishable: true` ;
3. les étapes model-backed tournent (pas de `*_saute` dans `run_notes.json`) ;
4. les replis CPU sont remplacés par les cibles de production ;
5. les contrôles §7 passent : rétention par locuteur/source, échantillon de rejets examiné, **règle des 50 %** respectée.

---

*Fin — document d'état « reste à faire ». Toute modification des seuils, filtres ou politiques
(D-a à D-f) donne lieu à une nouvelle version du document et des manifests.*

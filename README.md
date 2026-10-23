# Pipeline de traitement des données — FR ↔ Lingala

Chaîne de préparation des données d'entraînement (NMT texte + TTS audio) pour
l'application d'apprentissage des langues africaines. Elle transforme des sources
brutes hétérogènes en **manifests JSONL traçables, filtrés, dédoublonnés et
découpés**, prêts pour l'entraînement.

Deux paquets :

| Paquet | Rôle |
|---|---|
| `ml.corpus` | Construit le corpus parallèle français ↔ lingala (USFM, BibleTTS, HF) |
| `ml.preprocess` | Filtre / normalise / découpe le texte (NMT) et l'audio (TTS) |

> Toutes les commandes se lancent **depuis le parent du paquet** (`/home/nael/Languages`),
> afin que les imports `ml.*` et les chemins `data/` soient résolus.

---

## Sommaire

- [Vue d'ensemble](#vue-densemble)
- [Installation](#installation)
- [Démarrage rapide](#démarrage-rapide)
- [Chaîne corpus](#chaîne-corpus)
- [Chaîne prétraitement](#chaîne-prétraitement)
- [Configuration et calibrage](#configuration-et-calibrage)
- [Sorties et schémas](#sorties-et-schémas)
- [Tests](#tests)
- [État du projet et limites](#état-du-projet-et-limites)

---

## Vue d'ensemble

```
data/corpus/raw/ebible/{fraLSG,lin}/*.usfm
              │
              ▼  ml.corpus.run audit   (inventaire + licences)
              │
              ▼  ml.corpus.run align   (appariement exact verset ↔ verset)
data/corpus/aligned/lin_fr.jsonl
              │
              ▼  ml.corpus.run build   (normalise, filtre, dédoublonne, split)
data/corpus/<run_id>/manifest_corpus.jsonl
data/corpus/<run_id>/{splits/*.jsonl, quarantine.jsonl, rejects.jsonl, report.json}
              │
              ▼  (export automatique)
data/parallel/lin_fr.jsonl
              │
              ▼  ml.preprocess.run nmt   (T1..T11)      → manifest_nmt.jsonl
              │
              └─ ml.preprocess.run audio (A1..A12)      → manifest_tts.jsonl + mel/
                 sources : BibleTTS, WAXAL
```

Principes transverses, appliqués aux deux chaînes :

1. **Aucun seuil en dur** — toute valeur chiffrée vit dans un YAML, avec une
   `provenance`. Un seuil sans `provenance: calibrage_<lang>_<date>` rend le
   manifest **non publiable** et bloque le run (code de sortie `2`) sauf
   `--allow-uncalibrated` (mode brouillon).
2. **Rien n'est silencieux** — chaque ligne écartée est journalisée
   (`rejects.jsonl`), chaque étape sautée faute de modèle est notée
   (`run_notes.json`), y compris l'usage d'un repli CPU.
3. **Quarantaine plutôt que perte sèche** — une paire douteuse (bande grise
   `warn_*`) part dans `quarantine.jsonl` pour validation humaine ultérieure.
4. **Licence d'abord (D6)** — seules les licences permissives entrent en
   production ; les sources NC/ND/inconnues sont refusées par l'audit.
5. **Anti-fuite** — le découpage est stable et, pour la Bible, fait **par livre**
   (`book_aware`) afin qu'un même livre ne soit jamais à cheval train/test.

---

## Installation

Python **3.10+**.

Dépendances cœur (texte + corpus + audio de base) :

```bash
pip install pyyaml numpy scipy soundfile pyarrow datasketch pytest
```

Dépendances optionnelles (activées si le modèle/la clé de config est fourni) :

| Usage | Paquet |
|---|---|
| Résample/mel de production | `torch`, `torchaudio` |
| VAD de production | `silero-vad` |
| Loudness | `pyloudnorm` |
| Identification de langue (T6) | `fasttext` |
| Parallélisme (T9) | `sentence-transformers` |
| DNSMOS (A7) | `onnxruntime` |
| ASR / WER (A9) | `transformers` |
| Suivi distant | `clearml` |

Aucune de ces dépendances n'est obligatoire : sans elles, l'étape concernée est
**sautée et journalisée**, jamais exécutée implicitement.

### Données attendues

```
data/corpus/raw/ebible/fraLSG/*.usfm     # Louis Segond 1910 (domaine public)
data/corpus/raw/ebible/lin/*.usfm        # Open Lingala Contemporary Bible
data/bibletts/extracted/lingala/dev/...  # .flac + .txt (48 kHz)
data/waxal/asr/lin/train/*.parquet       # audio + transcription (16 kHz)
data/flores/devtest/                     # référentiel anti-fuite (actuellement vide)
```

---

## Démarrage rapide

```bash
# 0) depuis /home/nael/Languages
python -m pytest ml/preprocess/tests ml/corpus/tests -q

# 1) inventaire et licences des sources
python -m ml.corpus.run audit

# 2) alignement USFM FR ↔ lin
python -m ml.corpus.run align

# 3) filtrage / dédoublonnage / split
#    (bloqué sans seuils calibrés ; --allow-uncalibrated = brouillon)
python -m ml.corpus.run build --run-id lin_fr_v2 --allow-uncalibrated

# 4) statistiques du corpus aligné
python -m ml.corpus.run stats

# 5) prétraitement NMT
python -m ml.preprocess.run nmt \
    --input data/parallel/lin_fr.jsonl --allow-uncalibrated

# 6) prétraitement audio (échantillon de 400 clips)
python -m ml.preprocess.run audio --limit 400 --sources bibletts,waxal \
    --allow-uncalibrated
```

---

## Chaîne corpus

Entrée : sources déclarées dans `ml/corpus/configs/sources.csv`, réglages dans
`ml/corpus/configs/corpus.yaml`.

| Étape | Commande | Effet |
|---|---|---|
| `audit` | `python -m ml.corpus.run audit` | Vérifie présence/taille/empreinte SHA-256 et **admission de licence**. Écrit `data/corpus/audit.json`. |
| `align` | `python -m ml.corpus.run align` | Parse les USFM (`\c`, `\v`, notes/Strong retirés) et apparie **exactement** sur `(livre, chapitre, verset)`. Écrit `data/corpus/aligned/lin_fr.jsonl` + `align_report.json` (versets orphelins de chaque côté). |
| `build` | `python -m ml.corpus.run build [--limit N] [--run-id ID]` | Normalise, filtre (C1, C2, C4, C5, C7, C8), met en quarantaine, découpe train/dev/test et exporte vers `data/parallel/lin_fr.jsonl`. |
| `stats` | `python -m ml.corpus.run stats [--input FILE]` | Compte les paires par domaine et par livre. |

Filtres appliqués par `build` :

| Code | Contrôle | Sort |
|---|---|---|
| C1 | Champs requis (`src`, `tgt`, `lang_src`, `lang_tgt`) | rejet |
| C2 | Doublon exact (`src`+`tgt`) | rejet |
| C4 | Longueur cible en mots (`min`/`max` durs, `warn_*` gris) | rejet / quarantaine |
| C5 | Ratio de longueur `tgt/src` en caractères | rejet / quarantaine |
| C7 | Part de lettres dans l'alphabet lingala | rejet / quarantaine |
| C8 | Quasi-doublon (MinHash LSH, n-grammes) | rejet |

`build` produit aussi `splits/{train,dev,test}.jsonl`. Le split est **déterministe**
(hash stable) et, en mode `book_aware`, calculé par **livre** pour éviter la fuite
train/test.

---

## Chaîne prétraitement

Réglages : `ml/preprocess/configs/preprocess.yaml` (un seul fichier, hashé comme
version du traitement). Sorties : `data/processed/<lang>/<run_id>/<stage>/`.

### Texte — NMT (`T1..T11`)

```bash
python -m ml.preprocess.run nmt --input data/parallel/lin_fr.jsonl
```

| Étape | Contrôle | Sans outil |
|---|---|---|
| T1 | Schéma d'entrée | rejet dur |
| T2 | Unicité exacte | rejet dur |
| T3 | Normalisation Unicode (NFC) + numéraux dans la langue (`numerals_lin.yaml`) | — |
| T4 | Longueur en mots (`bucket` par défaut) | — |
| T5 | Ratio de longueur | rejet dur |
| T6 | Identification de langue (fastText `lid.176`) | sauté, journalisé |
| T7 | Alphabet cible + politique code-switching (`tolerant` → `domain: code_switch`) | — |
| T8 | Quasi-doublons MinHash | — |
| T9 | Parallélisme sémantique (SONAR/LaBSE, cosinus) | sauté, journalisé |
| T10 | Anti-fuite vs FLORES-200 devtest | non vérifié, journalisé |
| T11 | Split stable train/dev/test | — |

### Audio — TTS (`A1..A12`)

```bash
python -m ml.preprocess.run audio --sources bibletts,waxal --limit 400
```

Ordre réel v1.1 : **A1 A2 A4 A5 A6 A7 A8 A9 A3 A10 A11 A12** — la qualité
(A7 DNSMOS, A8 SNR) est mesurée **avant** la normalisation de niveau (A3), sinon
le gain amplifierait le bruit avant qu'il ne soit mesuré.

| Étape | Rôle |
|---|---|
| A1 / A2 | Chargement mono, rééchantillonnage vers `target_sr` (24 kHz) |
| A4 | VAD (coupe des silences de bord) puis découpe en segments ≤ `max_s` |
| A5 / A6 | Durée et débit (mots/s) → `bucket` plutôt que rejet en bas ressource |
| A7 / A8 | Qualité perceptuelle (DNSMOS) et SNR, sur audio **non normalisé** |
| A9 | Cohérence texte↔audio (WER via MMS-ASR) |
| A3 | Loudness (−23 LUFS si `pyloudnorm`) + rejet du clipping (crête > −1 dBFS) |
| A10 | Anti-fuite |
| A11 | Métadonnées obligatoires (`speaker`, `lang`, `duration`, `sr`, `source`, `domain`) |
| A12 | Log-mel 80 bandes en cache (`mel/*.npy`) |

Le champ `source` (`bibletts` 48 kHz vs `waxal` 16 kHz) est **conservé** : il
empêche le modèle d'apprendre la source comme variable cachée.

### G2P — bloqué

`python -m ml.preprocess.run g2p` sort en code `3` : la licence du lexique tonal
bambara n'est pas confirmée (D14). Le G2P lingala reste à construire.

---

## Configuration et calibrage

### Principe bloquant

| Chaîne | Seuils « calibrables » | Fichier |
|---|---|---|
| Corpus | `C4_length`, `C5_ratio`, `C7_alphabet`, `C8_dedup` | `ml/corpus/configs/corpus.yaml` |
| Prétraitement | `T4`, `T5`, `T6`, `T7`, `T8`, `T9`, `A5`, `A6`, `A7`, `A8`, `A9`, `A3` | `ml/preprocess/configs/preprocess.yaml` |

Tant qu'un seul de ces blocs n'a pas `provenance: calibrage_<lang>_<date>` :

- le run refuse de produire un manifest publiable (code `2`), sauf
  `--allow-uncalibrated` ;
- `report.json` porte `publishable: false` et la liste `uncalibrated`.

### Outillage de calibrage

L'étape 0 est outillée par `ml.preprocess.calibrate` :

```bash
# 1) tirer les échantillons à annoter (300 lignes texte, 200 paires, 100 clips/source)
python -m ml.preprocess.calibrate sample --lang lin

# 2) remplir les labels (lang_id_ok, pair_ok, in_alphabet, quality_ok, text_match_ok)
#    puis calculer les seuils (≥ 95 % de précision sur les rejets)
python -m ml.preprocess.calibrate solve --lang lin

# 3) reporter les seuils dans le YAML avec provenance calibrage_lin_<date>
python -m ml.preprocess.calibrate apply --lang lin
```

Sans annotation, `solve` ne calcule rien et le signale : les seuils restent
`null` et les manifests restent non publiables. Le protocole détaillé et le
tableau de résultats à remplir sont dans `ml/preprocess/configs/calibration_lin.md`.

Les décisions produit (D-a → D-e) sont versionnées dans
`ml/preprocess/configs/decisions.yaml`.

---

## Sorties et schémas

### Corpus

```jsonc
// manifest_corpus.jsonl (accepté)
{"row_id":"GEN.1.1","src":"Au commencement…","tgt":"Na ebandeli…",
 "lang_src":"fra","lang_tgt":"lin","domain":"bible","source":"ebible",
 "license":"CC-BY-SA-4.0 + domaine public","ref":"Genèse 1:1","book":"GEN",
 "split":"train"}

// quarantine.jsonl (bande grise, à revoir)
{"..." : "...", "review": true, "review_reasons": ["C5_ratio"]}
```

Autres sorties d'un run `build` : `splits/{train,dev,test}.jsonl`,
`rejects.jsonl` (`row_id`, `etape`, `raison`, `valeur_observee`, `langue`,
`source`, `locuteur`), `report.json` (comptes, rejets, rétentions par
vocabulaire/tokens/locuteur/source/domaine).

### Prétraitement NMT

`manifest_nmt.jsonl` : `src`, `tgt`, `lang_src`, `lang_tgt`, `domain`,
`score`, `source`, `bucket`, `split`.

### Prétraitement TTS

`manifest_tts.jsonl` : `audio` (chemin mel ou `row_id`), `text`, `lang`,
`speaker`, `duration`, `sr`, `source`, `domain`, `bucket`.

Chaque run écrit aussi `report.json`, `config_snapshot.yaml`, `rejects.jsonl`
et, pour le NMT/TTS, `run_notes.json` (étapes sautées, replis utilisés).
`--clearml` ajoute le suivi distant (un task par étape, défensif si l'agent est
absent).

---

## Tests

```bash
python -m pytest ml/preprocess/tests ml/corpus/tests -q
```

31 tests golden couvrent : normalisation Unicode et numéraux, journal et
rétentions, dédoublonnage exact/MinHash, garde-fou de calibrage, parsing USFM,
alignement, split déterministe, filtres corpus, sélection de seuils, DSP audio
(rééchantillonnage, VAD, découpe, SNR, WER, clipping) et orchestration TTS.

---

## État du projet et limites

| Élément | État |
|---|---|
| Chaîne corpus FR↔lin | ✅ exécutable (Bible eBible) |
| Filtres NMT T1→T11 | ✅ (T6/T9 sautés sans modèle) |
| Chaîne audio A1→A12 | ✅ (A7/A9 sautés sans modèle) |
| G2P | ⛔ bloqué (licence, D14) |
| Calibrage des seuils | ❌ non fait → tous les manifests sont `publishable: false` |
| Référentiel anti-fuite FLORES | ❌ `data/flores/devtest/` vide |
| Modèles A7/A9/T6/T9 | ❌ à fournir (`model_path`) |
| Replis CPU → cibles prod | ❌ à remplacer (VAD silero, mel torchaudio, loudness pyloudnorm, SNR WADA) |

Un manifest n'est publiable que si `uncalibrated()` est vide, que les étapes
model-backed tournent réellement et qu'aucun repli CPU n'a servi. Tant que ce
n'est pas le cas, les sorties sont des **brouillons de travail** — utilisables
pour itérer, pas pour publier.

Sources refusées à l'audit (licence) et pistes de corpus courant :
`ml/corpus/configs/sources.csv` et `Reste_A_Faire_Pretraitement.md`.
# african-langs-data-prep

# Architecture data et entraînement

Pour quelqu'un qui rejoint le projet : comment les données sont traitées, comment les modèles sont entraînés, et comment est organisé le repo de pré-traitement.

> La structure du repo décrite en section 4 est une **proposition de départ**. Adapter les noms de dossiers et de scripts à ce qui existe réellement.

---

## 1. Le projet en une phrase

Prendre une phrase en français, la traduire en lingala / wolof / bambara, la transformer en audio, et renvoyer audio + texte.

```
phrase FR → [Traduction] → texte cible → [TTS] → audio → MP3 + texte
```

Deux modèles à entraîner, donc deux chaînes de données :

| Modèle | Rôle | Données d'entrée |
|---|---|---|
| Traduction (NLLB ou MADLAD-400, fine-tuné) | FR → langue cible | Paires de phrases FR ↔ langue |
| TTS (VITS) | Texte → voix | Audio + transcription |

---

## 2. Architecture du traitement de la data

Le principe : **les données brutes ne sont jamais modifiées**. Chaque étape lit un dossier et en écrit un autre.

```
data/raw/            Sources telles que téléchargées (lecture seule)
   │
   ▼
data/interim/        Nettoyage et normalisation
   │
   ▼
data/processed/      Jeux finaux prêts pour l'entraînement (train / val / test)
```

### 2.1 Chaîne texte (traduction)

1. **Collecte** : corpus FR ↔ langue, notés avec leur source et leur licence.
2. **Normalisation** : Unicode NFC, caractères spéciaux cohérents (ɛ, ɔ, ŋ, ɲ), espaces et ponctuation uniformes.
3. **Filtrage** : suppression des paires vides, trop courtes ou trop longues, des rapports de longueur aberrants et des mauvais alignements.
4. **Déduplication** : doublons exacts, puis quasi-doublons.
5. **Découpage** : train / validation / test, **sans fuite** (une même phrase, ou une même source proche, ne doit pas être dans deux ensembles).
6. **Export** : fichiers `train.jsonl`, `val.jsonl`, `test.jsonl`, avec les champs `src`, `tgt`, `src_lang`, `tgt_lang`, `source`.

### 2.2 Chaîne audio (TTS)

1. **Collecte** : BibleTTS (OpenSLR SLR129), WAXAL (google/WaxalNLP, à vérifier pour le lingala), enregistrements maison.
2. **Audio** : mono, rééchantillonnage à 22 050 Hz, normalisation du volume.
3. **Segmentation** : segments de 2 à 10 s, suppression des longs silences, du bruit et de la musique.
4. **Texte** : normalisation (NFC, chiffres en lettres, abréviations développées, ponctuation cohérente).
5. **Alignement** : vérifier que chaque audio correspond à sa transcription (contrôle par échantillon et par ASR si possible).
6. **Découpage** : train / val / test, séparés par livre ou par source pour éviter les fuites.
7. **Export** : fichiers `train.txt` / `val.txt` au format `chemin_audio|texte`, plus l'alphabet (liste des caractères).

### 2.3 Contrôles qualité (à chaque chaîne)

- Rapport d'audit : nombre d'exemples, heures d'audio, caractères présents et leur fréquence, variantes suspectes (e/ɛ, o/ɔ).
- Aucune ligne perdue sans trace : chaque étape écrit le nombre d'exemples avant et après.
- Licence et source enregistrées pour chaque corpus (fichier `data/LICENSES.md`).

---

## 3. Architecture de l'entraînement

```
data/processed/ ──► Traduction ──► checkpoints/translation/ ──► évaluation
data/processed/ ──► TTS (VITS) ──► checkpoints/tts/         ──► évaluation
```

### 3.1 Traduction

- **Modèle** : NLLB-200 (usage non commercial) ou MADLAD-400 3B (Apache 2.0, usage commercial).
- **Méthode** : un seul modèle multilingue avec tag de langue cible. Fine-tuning par LoRA, ou QLoRA pour MADLAD.
- **Équilibrage** : échantillonnage par température pour ne pas écraser la langue la plus petite.
- **Évaluation** : chrF++ par langue sur le jeu de test et FLORES-200 `devtest`, comparé à la baseline sans fine-tuning. Relecture par des locuteurs natifs.

### 3.2 TTS

- **Modèle** : VITS (code MIT). Entrée : caractères (pas de G2P au départ). Un modèle par langue au départ.
- **Départ** : checkpoint à licence claire, ou depuis zéro.
- **Évaluation** : écoute à chaque checkpoint sur des phrases fixes, WER via un ASR lingala, MOS par locuteurs natifs.

### 3.3 Règle de reproductibilité

Chaque entraînement est décrit par un **fichier de config** versionné (hyperparamètres, chemins de données, graine). Pas de valeur codée en dur dans les scripts.

---

## 4. Le repo de pré-traitement (proposition)

```
preprocessing/
├── README.md                 Point d'entrée : installation et commandes
├── configs/
│   ├── text_lin.yaml         Paramètres de la chaîne texte (par langue)
│   ├── text_wol.yaml
│   ├── text_bam.yaml
│   └── audio_lin.yaml        Paramètres de la chaîne audio
├── data/
│   ├── raw/                  Données brutes (non versionnées, voir .gitignore)
│   ├── interim/              Sorties intermédiaires
│   ├── processed/            Jeux finaux
│   └── LICENSES.md           Source, licence et conditions de chaque corpus
├── src/
│   ├── text/
│   │   ├── normalize.py      Unicode NFC, caractères spéciaux, ponctuation
│   │   ├── filter.py         Filtrage des paires (longueur, alignement)
│   │   ├── dedup.py          Déduplication
│   │   └── split.py          Découpage train / val / test sans fuite
│   ├── audio/
│   │   ├── resample.py       Rééchantillonnage, conversion mono
│   │   ├── segment.py        Découpage, retrait des silences
│   │   └── validate.py       Contrôle des durées et de l'alignement
│   ├── audit/
│   │   └── report.py         Inventaire des caractères, heures, variantes suspectes
│   └── utils/
│       └── io.py             Lecture / écriture des fichiers
├── scripts/
│   ├── run_text.sh           Lance la chaîne texte pour une langue
│   └── run_audio.sh          Lance la chaîne audio pour une langue
├── tests/                    Tests de la normalisation et du découpage
├── requirements.txt
└── .gitignore                Exclut data/ (sauf LICENSES.md)
```

### Rôle des dossiers

- **`configs/`** : tout ce qui change d'une langue ou d'un corpus à l'autre (chemins, seuils de filtrage, fréquence d'échantillonnage). On modifie la config, pas le code.
- **`data/`** : jamais versionné, sauf `LICENSES.md`. Les données brutes ne sont jamais modifiées.
- **`src/`** : le code, découpé comme les chaînes (texte, audio, audit).
- **`scripts/`** : enchaînent les étapes dans le bon ordre.
- **`tests/`** : protègent surtout la normalisation et le découpage, les deux endroits où une erreur passe inaperçue (fuite de données, caractères mal normalisés).

### Utilisation type (à adapter)

```bash
# 1. Placer les données brutes dans data/raw/<corpus>/
# 2. Auditer avant de traiter
python -m src.audit.report --config configs/text_lin.yaml

# 3. Lancer la chaîne texte puis audio
bash scripts/run_text.sh lin
bash scripts/run_audio.sh lin

# 4. Les jeux finaux sont dans data/processed/<langue>/
```

---

## 5. Règles du projet

1. Ne jamais modifier `data/raw/`.
2. Chaque corpus a sa licence notée dans `data/LICENSES.md` avant d'être utilisé.
3. Auditer les transcriptions avant d'entraîner (caractères, variantes e/ɛ, o/ɔ, accents).
4. Séparer train / val / test avant tout entraînement, et le vérifier (pas de fuite).
5. Une config versionnée par entraînement.
6. Toute évaluation compare à une baseline.
7. Avant un usage commercial : valider les licences des données, des poids et des enregistrements (accord écrit des locuteurs).

---

## 6. Points ouverts

- Le TTS lingala de WAXAL : présence, heures et licence à confirmer sur la fiche Hugging Face.
- Sources de données wolof et bambara pour le TTS : à trouver ou à enregistrer.
- Usage commercial ou non : décide NLLB ou MADLAD, MMS-TTS ou VITS.
- G2P : non prévu au départ, à réévaluer après écoute par des locuteurs natifs.

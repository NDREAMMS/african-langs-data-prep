# NOTE TECHNIQUE — v1.2

## Prétraitement des données

Application d'apprentissage des langues africaines — Wolof · Lingala · Bambara

---

**STATUT du DOCUMENT**

Révision après mise en service de la **chaîne corpus** (étage amont du NMT). Complète le registre des décisions techniques **v1.1, décision D11** (+ D6 licences, D10 schéma).

**Changements v1.1 → v1.2**

| # | Ajout relevé | Traitement |
|---|---|---|
| 1 | La chaîne texte (§4) présupposait un corpus parallèle **déjà propre** ; rien ne le construisait | Nouvelle **chaîne corpus** (§4.A) : audit des sources, alignement verset par verset, filtrage, découpage → alimente le stage `nmt` |
| 2 | Sources FR↔LN dispersées, licences non vérifiées, risque d'usage non commercial | **Registre des sources** `sources.csv` portant la licence ; entrée conditionnée par la politique **D6** (permissif uniquement) |
| 3 | Alignement FR↔LN potentiellement bruité | **Alignement exact verset par verset** (clé *livre, chapitre, verset*), sans traduction automatique ; écarts de versification listés |
| 4 | Corpus biblique : fuite entre train et test à craindre | Découpage **par livre** (un livre entier dans un seul split), jamais par verset |
| 5 | Seuils de filtrage corpus non distingués des seuils NMT | Blocs **C1–C8** dans `corpus.yaml`, soumis au même garde-fou de calibrage (§2.2) |
| 6 | Sans annotation humaine, une binaire accepter/rejeter jette des données valides | **Trois catégories** : accepté / **quarantaine** (`quarantine.jsonl`, bande grise `warn_*`) / rejeté — revue humaine reportée (§4.A) |

**Changements v1.0 → v1.1**

| # | Point relevé en revue | Traitement |
|---|---|---|
| 1 | Seuils empruntés à des hypothèses haute ressource (lid.176, WER A9, cosine T9) | Nouvelle **étape 0 — calibrage** (§3) ; tous les seuils marqués *hypothèses* jusqu'à calibration |
| 2 | Seuils durs = perte de données non seconde-pensable en bas ressource | Filtres *down-weight/bucket* optionnels (T4, A5, A6) ; rapports de rétention **vocabulaire unique et locuteurs**, pas seulement de lignes (§7) |
| 3 | −23 LUFS = convention broadcast ; normaliser avant A7/A8 amplifie le bruit | **Ordre corrigé** : A7/A8 sur audio non normalisé, A3 après (§5) ; contrôle de crête/clipping ajouté |
| 4 | Résample 48→24 kHz vs 16→24 kHz : bande haute vide, source = variable cachée | Champ **`source` obligatoire** (A11), conditionnement explicite + sous-ensemble « haute qualité » pour la dernière étape d'entraînement |
| 5 | Registre biblique étroit (v1 : `domain` optionnel) | **`domain` obligatoire** sur les manifests NMT et TTS, distribution publiée dans `report.json` (§7) |
| 6 | Normalisation des chiffres non spécifiée pour les langues cibles | T3 étendu : tables de numéraux par langue, **synchronisées côté audio** pour ne pas fausser A9 (§4) |
| 7 | T7 (90 %) rejette le code-switching, très présent dans les 3 langues | **Décision produit explicite** à prendre, politique paramétrable par langue (§4, §2) |
| 8 | Ton wolof toujours « à clarifier » | `tone_model` par langue dans la config ; wolof = `none` par défaut tant que non tranché (§6) |
| 9 | `sm_120` peut invalider le plan audio | **Étape 0 technique** (smoke test GPU) placée avant toute écriture de code (§9) |
| — | Déterminisme GPU irréprochable | Reformulé : reproductibilité **dans un environnement épinglé** ; scores DNSMOS/ASR mis en cache traités comme entrées (§2, §8) |
| — | On ne contrôle que les lignes gardées | **Échantillonnage manuel des rejets** ajouté (§7) |
| — | Un filtre peut effacer un locuteur entier | Rétention **par locuteur et par source** journalisée (§7) |

**Sources** : Cahier des charges design · Règles métier v2 · Registre v1.1 (D6, D8, D10, D11, D12) · Caractéristiques vérifiées des sources (WAXAL arXiv:2602.02734, BibleTTS OpenSLR SLR129, An ka taa, LanguageNet) · eBible.org / Open.Bible (*Open Lingala Contemporary Bible*, Biblica 2020, CC BY-SA 4.0 ; *Louis Segond 1910*, domaine public) · Revue de spécification du 10 octobre 2026.

16 octobre 2026 — document de conception, usage interne projet

---

## 1. Chaînes couvertes

Le prétraitement couvre **quatre chaînes**. La chaîne *corpus* est l'étage amont : elle produit le parallèle FR↔LN que consomme la chaîne texte.

| Chaîne | Rôle | Sortie |
|---|---|---|
| **Corpus (FR ↔ LN)** *(v1.2)* | Collecter, auditer, aligner et filtrer les sources parallèles | `data/parallel/lin_fr.jsonl` + `data/corpus/<run_id>/splits/*.jsonl` |
| **Texte (NMT)** | Filtrer le parallèle et le découper en manifest entraînable | `manifest_nmt.jsonl` |
| **Audio (TTS)** | Nettoyer les corpus vocaux (BibleTTS, WAXAL) et pré-calculer les mel | `manifest_tts.jsonl` + mel |
| **G2P** | Lexique de graphème→phonème/tons (D8) | `manifest_g2p.jsonl` |

Chaque chaîne a ses propres filtres mais partage le socle `common/` (config, unicode, journal des rejets, dédoublonnage).

**Sources prises en charge** : WAXAL (ASR, CC BY 4.0), BibleTTS / Open.Bible (TTS, CC BY-SA 4.0), **eBible.org** (alignement parallèle FR↔LN), An ka taa (G2P, licence à confirmer, D14). Toute source hors liste est refusée par l'audit de licences (D6).

**Pourquoi ce document existe.** Le prétraitement décide du plafond de qualité : une donnée mal alignée ou mal filtrée se paie en dégradation diffuse, non localisable. Cette révision ajoute l'étage qui manquait — la construction du corpus — pour que la chaîne texte ne dépende plus d'un parallèle « déjà propre » qu'aucun outil ne produisait.

---

## 2. Principes transverses

1. **Configuration unique, aucun seuil en dur.** Chaque chaîne lit son fichier de config (`preprocess.yaml`, `corpus.yaml`) ; le hash de la config est l'identifiant de version du traitement. Une modification de seuil = nouvelle version de manifest.
2. **Un seuil n'existe qu'après calibrage.** Chaque valeur numériquement listée dans ce document est une **hypothèse de départ**, à être posée sur un échantillon étiqueté par langue (§3). Un seuil non calibré est signalé `provenance: null` dans la config et **bloque** la production du manifest (code de sortie 2), sauf mode brouillon explicite `--allow-uncalibrated`.
3. **Traçabilité des rejets.** Chaque ligne écartée est journalisée `row_id, etape, raison, valeur_observee, langue, source, locuteur` (les trois derniers permettent de voir qu'un filtre vide locuteurs ou sources entiers).
4. **Déterminisme dans un environnement épinglé.** Graine fixe, tri stable, dépendances verrouillées (`uv.lock`/image Docker) : même config + même versions = manifests bit-à-bit identiques. Les sorties GPU (DNSMOS, ASR) ne sont pas garanties reproductibles entre matériel/bibliothèques : **leurs scores sont mis en cache et réutilisés comme entrées**, jamais recalculés silencieusement.
5. **Double normalisation Unicode.** Stockage en **NFC**, analyse en **NFD** : en NFD, les marques de ton (grave, aigu, circonflexe, caron) se séparent des voyelles — condition indispensable au lexique tonal (D8).
6. **Filtres du moins cher au plus cher** (hash/règles CPU avant embeddings et GPU).
7. **Préférer déclasser à jeter quand c'est défendable.** Les filtres T4, A5 et A6 peuvent passer en mode *down-weight* (ligne conservée, poids réduit) ou *bucket* (lot séparé) plutôt qu'en rejet, dans les langues où le volume fait défaut — décision prise au calibrage, pas au fil de l'eau.
8. **Les compteurs partent dans ClearML** (D12) : taux de rejet par filtre = première métrique regardée après chaque exécution.
9. **Le brut est archivé** (`raw/`, lecture seule) : toute règle révisée se rejoue sans re-téléchargement.

---

## 3. Étape 0 — Calibrage des seuils

Aucune chaîne ne démarre avant cette étape. Elle produit les seuils de `preprocess.yaml` et de `corpus.yaml`.

**Protocole, par langue (wo, lin, bam) :**

1. **Échantillon texte** : 300 lignes tirées au sort et annotées `langue correcte ?`, `alphabet correct ?`, `phrases mélangées ?`.
2. **Échantillon corpus** : 200 paires FR↔LN tirées au sort — juger l'alignement et la qualité de la cible (sert à calibrer C4, C5, C7).
3. **Échantillon audio** : 100 clips annotés `qualité correcte ?`, `contenu autorisé ?`.
4. **Pose des seuils** : filtrer du moins cher au plus cher, ajuster chaque valeur jusqu'à ≤ 5 % de gardés manifestement mauvais et ≤ 5 % de rejets manifestement bons. Consigner chaque seuil avec `provenance: calibrage_<lang>_<date>`.
5. **Rapport de calibrage** : matrice de confusion par filtre, taux de rejet, exemples.

---

## 4. Chaîne texte : du corpus parallèle au manifest NMT

La chaîne texte a **deux étages** : (A) la **chaîne corpus** collecte et aligne les sources FR↔LN en un parallèle propre ; (B) les **filtres NMT (T1–T11)** transforment ce parallèle en `manifest_nmt.jsonl`.

### 4.A Chaîne corpus (FR ↔ lingala) *(nouveau en v1.2)*

**Entrée** : sources parallèles hétérogènes (alignement biblique USFM ; jeux HuggingFace/OPUS à venir).
**Sortie** : `data/parallel/lin_fr.jsonl` — le JSONL `{src, tgt, lang_src, lang_tgt, domain}` attendu par le stage `nmt`.

| Stage | Rôle | Sortie |
|---|---|---|
| `audit` | Inventaire des sources : présence, empreinte SHA-256, **licence admise ou non** (D6) | `data/corpus/audit.json` |
| `align` | Alignement **verset par verset** (clé *livre, chapitre, verset*), sans traduction automatique | `data/corpus/aligned/lin_fr.jsonl` + `align_report.json` |
| `build` | Normalisation, filtres C1–C8, dédoublonnage, découpage **par livre** | `data/corpus/<run_id>/{manifest_corpus.jsonl, rejects.jsonl, report.json, splits/*.jsonl}` |
| `stats` | Statistiques du manifest | console |

**Filtres corpus** (hypothèses, à calibrer — mêmes principes que §2) :

| # | Règle | Seuil (hyp.) |
|---|---|---|
| C1 | Validation de schéma | `src`, `tgt`, `lang_src`, `lang_tgt` non vides |
| C2 | Unicité exacte | `sha1(src+tgt)` — zéro doublon |
| C4 | Longueur (mots cible) | 1–200 |
| C5 | Ratio de longueur `len(tgt)/len(src)` | 0,4–3,6 |
| C7 | Alphabet de la langue cible | ≥ 0,80 **à calibrer** |
| C8 | Dédoublonnage approx. | MinHash LSH, similarité ≥ 0,85 |

**Trois catégories, pas deux.** Sans annotation humaine, accepter/rejeter serait une dichotomie trompeuse : un score élevé ne garantit pas une traduction correcte (les détecteurs de langue connaissent mal le lingala, et deux phrases sur le même sujet peuvent sembler « similaires » sans être traduites l'une par l'autre). Le build produit donc **trois sorties** :

| Catégorie | Destination | Critère |
|---|---|---|
| **Accepté** | `manifest_corpus.jsonl` → stage `nmt` | passe les bornes dures et reste hors bande grise |
| **Quarantaine** | `quarantine.jsonl` (validation humaine ultérieure) | signal suspect **mais pas de preuve** : longueur, ratio ou alphabet dans la bande grise (`warn_*`) |
| **Rejeté** | `rejects.jsonl` | erreur certaine : schéma, doublon exact/approximatif, ou hors **bornes dures** |

Chaque ligne de quarantaine porte `review: true` et `review_reasons` (quels signaux ont alerté), afin que la revue ultérieure cible les cas ambigus plutôt que de relire tout le corpus. Les seuils restent **provisoires** tant qu'ils ne sont pas calibrés (§3).

**Alignement biblique = clé exacte, pas de traduction automatique.** L'*Open Lingala Contemporary Bible* (Biblica 2020, CC BY-SA 4.0) et *Louis Segond 1910* (domaine public) partagent la versification standard : on apparie `(livre, chapitre, verset)`. Le balisage USFM (notes `\\f…\\f*`, références `\\x…\\x*`, mots Strong `\\w…|strong="H…"\\w*`) est retiré. Les versets présents d'un seul côté ne sont **pas perdus** : ils sont listés dans `align_report.json` (première extraction : ≈31 059 versets alignés sur 66 livres, 221 écarts de versification identifiés ; après filtres, ≈30 330 paires acceptées, 102 en quarantaine, 627 rejetées).

**Découpage par livre.** Sur un corpus biblique, un découpage par verset laisserait un même livre des deux côtés de la frontière train/test : le test mesurerait la mémorisation du livre. Le hash de découpage porte donc sur le **livre**, pas sur le verset.

**Licences (D6).** Le registre `sources.csv` porte la licence de chaque source ; l'audit refuse toute source non permissive (NC/ND/inconnue). C'est ce qui garantit qu'un corpus, une fois filtré, reste réutilisable en production.

### 4.B Filtres NMT (T1–T11)

Filtres dans l'ordre d'exécution. **Valeurs = hypothèses, à calibrer (§3).**

| # | Règle | Outil | Seuil (hyp.) | Défaut évité sans elle |
|---|---|---|---|---|
| T1 | Validation de schéma | `pydantic` | `src`, `tgt`, `lang_src`, `lang_tgt` non vides ; **`domain` obligatoire** (cf. §7) | lignes malformées |
| T2 | Unicité exacte | `sha1(src+tgt)` | zéro doublon | mémorisation au lieu d'apprentissage |
| T3 | Normalisation Unicode + texte | NFC, espaces, entités HTML, **numéraux → mots** | — | variantes d'un même « mot » |
| T4 | Longueur | — | 1–50 mots · **mode `down-weight` possible au-delà** | séquences tronquées |
| T5 | Ratio de longueur | `len(tgt)/len(src)` | 0,5–2,0 | alignements catastrophiques |
| T6 | Identification de langue | `fasttext lid.176` (couverture wo/lin/bm **à vérifier**) | conf ≥ 0,75 **à calibrer** ; repli cld3/classifieur maison | texte hors langue |
| T7 | Alphabet de la langue | lettres autorisées par langue | ≥ 90 % **à calibrer** + **politique code-switching explicite** (voir ci-dessous) | phrases hors langue |
| T8 | Dédoublonnage approx. | MinHash LSH (`datasketch`), n-grammes 5 | similarité ≥ 0,85 | doublons de pages |
| T9 | Qualité de parallélisme | `SONAR`/`LaBSE`, fenêtre glissante | cosine ≥ 0,55 **à calibrer par paire de langues** | paires mal alignées |
| T10 | Fuite vers le test | n-grammes vs **FLORES-200 devtest** | **0** chevauchement | BLEU faussement élevé |
| T11 | Découpage | hash stable du texte | proportions fixes | reproductibilité |

**T3 — numéraux.** La conversion chiffres→mots n'est spécifiée que pour le français ; les langues cibles ont leurs propres formes (wolof `fukk ak ñaar`, etc.). La table de numéraux doit être **la même côté texte et côté audio** : sinon A9 mesure un WER artificiel sur les phrases contenant des nombres. Chaque langue porte sa table dans `configs/numerals_<lang>.yaml`, appliquée aussi à la normalisation des textes TTS.

**T7 — code-switching (décision produit requise).** Le code-switching français est fréquent et normal dans les 3 langues ; un filtre à 90 % le rejette en masse. Deux politiques possibles, **à trancher avant le calibrage** :
- *strict* : orthographe cible pure — utile pour l'audio de base du TTS (texte toujours lu) ;
- *tolérant* : garder les phrases mixtes, marquées `domain: code_switch` — utile si l'app doit reconnaître/afficher du français emprunté.
La politique peut différer par chaîne (strict pour TTS, tolerant pour NMT) ; elle est un paramètre de config, pas un constat.

---

## 5. Chaîne audio (TTS)

**Ordre d'exécution modifié en v1.1.** A7 et A8 sont calculés **avant** A3 (normalisation de loudness).

**Ordre v1.1 (rappel) :** A1 → A2 → A4 → A5 → A6 → A7 → A8 → A9 → **A3** → A10 → A11 → A12.

| # | Étape | Rôle / outil | Seuil (hyp.) |
|---|---|---|---|
| A1 | Inventaire + lecture | décodage, mono (`soundfile`) | — |
| A2 | Résample | tout en 24 kHz (`torchaudio`) | `target_sr` |
| A4 | Détection d'activité vocale | VAD + découpe (`silero-vad`) | silences de bord > 0,5 s |
| A5 | Durée | rejeter clips trop courts/longs | 1,5–10 s · **mode `bucket` au-delà** |
| A6 | Débit | mots/durée | ≤ 4 mots/s **à calibrer** |
| A7 | Qualité perceptuelle | DNSMOS (ONNX, GPU) — **audio non normalisé** | ≥ 3,0 **à calibrer** |
| A8 | SNR | WADA-SNR — **audio non normalisé** | ≥ 15 dB **à calibrer** |
| A9 | Contrôle texte ↔ audio | MMS-ASR → re-G2P → WER | ≤ 30 % **à calibrer** |
| A3 | Loudness + crête | `pyloudnorm` | −23 LUFS ± 1 ; crête > −1 dBFS → **rejet** |
| A10 | Anti-fuite | hash du texte vs splits | 0 croisement |
| A11 | Métadonnées | `speaker`, `lang`, `duration`, `sr`, **`source`**, **`domain`** (obligatoires) | — |
| A12 | Pré-calcul caractéristiques | mel 80 bandes, cache Arrow | une fois |

**Pourquoi cet ordre.** Normaliser le loudness avant de mesurer DNSMOS/SNR modifie ce qu'on mesure (le gain change SNR et parfois la qualité perçue) : on mesure donc la qualité sur le signal brut, puis on normalise.

**Partition 48 kHz / 16 kHz.** Le rééchantillonnage laisse une bande vide (16→24 kHz n'apporte rien au-dessus de 8 kHz d'origine). Mélanger les deux sans marquer la source revient à apprendre l'origine comme variable cachée de la qualité : d'où `source` obligatoire et un sous-ensemble haute qualité (BibleTTS) réservé aux dernières époques.

**Détail A9** : le seul filtre qui teste la cohérence *sémantique* de la paire. Un fichier dont le texte ne correspond pas à l'audio passe A1–A8 sans difficulté et est toxique pour l'entraînement.

**Partition GPU** : A7, A8, A9 (les seules étapes coûteuses), après smoke test `sm_120` (§9).

---

## 6. Chaîne G2P (lexique tonal)

À lancer dès que la licence d'export du lexique bambara est confirmée.

**Config par langue (v1.1) : `tone_model: lexical | none | pitch_accent`**

| Langue | `tone_model` | Justification |
|---|---|---|
| Lingala | `lexical` | 2 tons (bas non marqué / aigu) + descendant, tons portés par les morphèmes verbaux |
| Bambara | `lexical` | 2 tons + modulé, sandhi de liaison en contexte phrase |
| **Wolof** | **`none` par défaut** | **Le wolof n'est pas tonal** au sens du lingala ; revue linguistique requise avant tout `pitch_accent` |

| # | Étape | Rôle / seuil |
|---|---|---|
| G1 | Alignement graphème ↔ phonème | table issue du lexique source |
| G2 | Ton | `tone_model` par langue (voir ci-dessus) |
| G3 | Validation | alphabet (§4.B T7) |
| G4 | Filtrage | mêmes principes que §2 |
| G5 | Clé d'entrée | `grapheme` (NFC) / clé tonale (NFD sans tons) |
| G6 | Export | `{"graphemes","phonemes","tones","syllables","lang"}` (D10) — `tones` vide si `tone_model: none` |
| G7 | Découpage d'évaluation | 90/10 **par type**, jamais par token |

---

## 7. Sorties et rapports

```
data/corpus/                              # chaîne corpus (v1.2)
├── audit.json
├── aligned/lin_fr.jsonl  + align_report.json
└── <run_id>/{manifest_corpus.jsonl, quarantine.jsonl, rejects.jsonl, report.json, splits/{train,dev,test}.jsonl}
data/parallel/lin_fr.jsonl                # export consommé par le stage nmt

data/processed/<lang>/<run_id>/           # prétraitement
├── manifest_nmt.jsonl | manifest_tts.jsonl | manifest_g2p.jsonl
├── report.json
├── rejects.jsonl          # row_id, etape, raison, valeur, langue, source, locuteur
└── run_notes.json         # étapes sautées (modèles absents) — jamais en silence
```

**`report.json`** contient `read`, `kept`, `drops` (par étape) et un bloc `retention` : vocabulaire unique, tokens, locuteurs (avec liste des locuteurs **effacés** par un filtre), et rétention **par source et par domaine** — pour qu'un filtre qui vide une source entière soit visible immédiatement.

**Règle des 50 %.** Si un filtre rejette plus de 50 % du volume restant, on revoit la règle (et son calibrage) avant de continuer.

**Rejets.** Ne pas se fier aux seuls gardés : échantillonner les rejets (≈100 par étape) pour détecter un filtre trop dur — c'est la perte la plus coûteuse en bas ressource.

---

## 8. Instrumentation ClearML (D12)

```python
task = Task.init(project_name="langues", task_name=f"prep_{stage}_{cfg_hash}")
task.connect(cfg)                                    # seuils = hyperparams, y compris leur provenance
for name, n_drop in stats.items():
    task.get_logger().report_scalar(f"drop/{stage}", name, n_drop, iteration=0)
for metric, value in report["retention"].items():
    if isinstance(value, float):
        task.get_logger().report_scalar(f"retention/{stage}", metric, value, iteration=0)
task.upload_artifact("report", artifact_object="report.json")
task.upload_artifact("rejects_sample", artifact_object=sample_path)   # échantillon de rejets
ClearML Dataset.create(project="langues", name=f"manifest_{lang}").add_files(manifest_path)
```

- Un **task par étape** → comparaison des taux de rejet et des rétentions entre versions de config.
- **Scores GPU en cache** (DNSMOS, ASR) versionnés comme artefacts : ils entrent dans le traitement comme des entrées, ce qui rend le run rejouable même si l'ONNX change (cf. §2, point 4).
- Manifests versionnés comme **ClearML Datasets** (D10) : un entraînement référence toujours un `dataset_id`.

---

## 9. Mise en œuvre

**Structure**

```
ml/
├── corpus/                       # chaîne corpus (v1.2)
│   ├── configs/{corpus.yaml, sources.csv}
│   ├── usfm.py                   # lecture USFM → versets (livre, chapitre, verset)
│   ├── align.py                  # alignement verset par verset
│   ├── sources.py                # registre + audit licences
│   ├── filter_pairs.py           # filtres C1–C8, dédoublonnage, découpage
│   ├── config.py                 # seuils + garde-fou de calibrage
│   ├── run.py                    # CLI : audit | align | build | stats
│   └── tests/golden/
└── preprocess/
    ├── configs/
    │   ├── preprocess.yaml           # seuils + provenance (calibrage_<lang>_<date>)
    │   ├── calibration_<lang>.md     # courbes et décisions (étape 0)
    │   └── numerals_<lang>.yaml      # tables chiffres→mots, partagées texte/audio
    ├── common/                       # unicode, langid, dedup, filtres, journal
    ├── text_nmt.py
    ├── text_g2p.py
    ├── audio_tts.py
    ├── report.py                     # report.json + remontée ClearML
    └── tests/golden/
```

**Ordre de développement**

| # | Étape | Livrable | État |
|---|---|---|---|
| 0 | **Smoke test GPU (`sm_120`)** : ONNX DNSMOS, MMS-ASR, `torchaudio` résample + mel sur la 5090 | *Passé* → le plan audio tient · *Échoué* → on ajuste D7/D13 | à faire |
| 0′ | **Calibrage** (§3) : échantillons étiquetés par langue, seuils posés, couverture des outils vérifiée | `preprocess.yaml` + `corpus.yaml` sourcés | à faire |
| 1 | Socle : config, unicode, journal des rejets, golden tests | `common/` + tests verts | **fait** (20 tests) |
| 2 | **Chaîne corpus** : audit, alignement USFM, filtres, découpage | `ml/corpus/` opérationnelle | **fait** (6 tests) |
| 3 | `text_nmt.py` sur le corpus | rapport de rejets et de rétentions lu | **fait** (validé sur échantillon) |
| 4 | `audio_tts.py` (ordre §5) | manifest TTS v1 avec `source` + `domain` | **fait** (étapes modèle-backed sautées et journalisées) |
| 5 | `text_g2p.py` (bloqué sur licence) | manifest G2P v1 → alimente D8 | en attente (D14) |
| 6 | Instrumentation ClearML + versionnement des datasets | suivi distant opérationnel | à brancher |

**Dépendances** : `PyYAML`, `datasketch`, `pydantic` (socle) ; `datasets`, `fasttext` (+ `lid.176.bin`), `SONAR`/`sentence-transformers`, `torchaudio`, `silero-vad`, `pyloudnorm`, `soundfile`, `onnxruntime` (DNSMOS), `clearml`.

---

## 10. Risques

| Risque | Impact | Mitigation |
|---|---|---|
| **Alignement FR↔LN bruité** (aligneur automatique) | Paires fausses → le modèle apprend du bruit | Alignement **verset par verset** (clé exacte) ; `align_report.json` des écarts |
| **Source de licence non vérifiée intégrée au corpus** | Corpus inutilisable en production, risque juridique | Registre `sources.csv` + audit bloquant (D6) |
| **Un même livre à cheval train/test** | Le test mesure la mémorisation, pas la généralisation | Découpage **par livre** (§4.A) |
| **Filtre corpus trop dur** | Perte de volume en bas ressource | Rejets journalisés + règle des 50 % (§7) |
| Seuil non calibré appliqué tel quel | Rejet de données valides, exactement ce qu'on peut le moins se permettre en bas ressource | Étape 0 bloquante (§3) ; seuil sans `source: calibrage_*` = manifest non publiable |
| Filtre trop dur non détecté | Perte silencieuse de couverture | Échantillon de **rejets** + rétentions vocabulaire/locuteurs (§7) |
| `lid.176` / MMS-ASR / SONAR / DNSMOS mal adaptés à wo/lin/bam | Filtres faux (trop durs ou trop laxistes) | Vérification de couverture au §3 avec plan de repli (cld3, classifieur maison, seuils recalculés) |
| `sm_120` incompatible ONNX/ASR | Chaîne audio bloquante | Smoke test en **étape 0** avant toute écriture (§9) |
| Licence d'export An ka taa / Corbama | Chaîne G2P bloquée | Vérifier avant développement (D14) |
| Registre biblique dominant | Vocabulaire quotidien sous-représenté en sortie TTS | `domain` obligatoire + `by_domain` publié (§7) ; décision D-e |
| Mélange 48 kHz / 16 kHz non conditionné | Voix « étroite », source apprise comme variable cachée | Champ `source` obligatoire + sous-ensemble haute qualité pour la dernière étape (§5) |
| Traitements non rejouables | Impossibilité de corriger une règle | Principes 3 et 9 (journal + `raw/` archivé) + scores GPU en cache (§2) |

---

## 11. Décisions à prendre

| # | Décision | Options | Porteur |
|---|---|---|---|
| D-a | Politique code-switching (T7) | strict par chaîne / tolérant + marquage `domain` | produit |
| D-b | Mode des filtres en bas ressource (T4, A5, A6) | rejet / down-weight / bucket | ML |
| D-c | Ton du wolof (§6) | `none` (défaut) / `pitch_accent` après revue | ML + linguiste |
| D-d | Registre TTS à couvrir | biblique seul / biblique + courant | produit |
| D-e | **Élargir le corpus au-delà de la Bible** | intégrer HF/OPUS de registre courant, licence auditée (D6) | ML + juridique |

---

## 12. Prochaines étapes

| # | Étape | État |
|---|---|---|
| 1 | **Chaîne corpus opérationnelle** (audit, alignement, filtres, découpage) | **fait** — v1.2 |
| 2 | Smoke test `sm_120` (étape 0 technique, §9) | à faire |
| 3 | Calibrage : 300 lignes + 200 paires + 100 clips par langue (§3) | à faire |
| 4 | Trancher D-a à D-e | à faire |
| 5 | Auditer et intégrer une source parallèle de registre courant (licence permissive) | à faire |
| 6 | `text_nmt.py` puis `audio_tts.py` sur données calibrées | en cours |
| 7 | Débloquer la licence G2P bambara → `text_g2p.py` (alimente D8) | à faire (D14) |
| 8 | Branchement ClearML (tasks, datasets versionnés, scores GPU en cache) | à faire |

---

*Fin du document — Prétraitement des données v1.2. Toute modification des seuils, des filtres, des sources de corpus ou des politiques (D-a à D-e) donne lieu à une nouvelle version du document et des manifests.*

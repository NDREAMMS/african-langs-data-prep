# Architecture : pipeline spécialisé vs modèle multimodal

Document de décision — traduction FR → lingala + synthèse vocale.

Statut : **proposition à valider en revue** (révision 2026-11-02 : trois modèles indépendants et évaluation de prononciation déterministe, §10). Les scores et estimations chiffrées sont indicatifs et doivent être confirmés par l'équipe avant d'être considérés comme des seuils (cf. principe de provenance du repo).

---

## 0. Résumé exécutif

Le produit doit rendre **du texte lingala et de l'audio lingala** à partir d'une phrase française. Deux familles d'architectures existent :

- **A. Cascade spécialisée** : NMT (MADLAD-400 3B + LoRA) puis TTS (VITS).
- **B. Modèle multimodal bout-en-bout** : un modèle audio-texte qui traduit et parle directement.

**Recommandation : garder la cascade comme colonne vertébrale, et intégrer des briques multimodales de façon ciblée** (évaluation, prosodie, feedback pédagogique). Le multimodal ne devient pas l'architecture centrale, pour quatre raisons : aucun modèle ouvert ne produit du lingala parlé, les modèles parole→parole permissifs n'existent pas, le coût compute est 20 à 200× supérieur, et la traçabilité du repo (manifests, rejets, provenance) serait perdue.

**Révision 2026-11-02 (§10)** : l'évaluation de prononciation est un pipeline **déterministe** (alignement forcé + GOP segmental), **sans LLM** ; la cascade se décline en **trois modèles indépendants** (texte, génération audio, évaluation audio) qui ne partagent que le noyau symbolique **G2P segmental** (le ton est hors périmètre, décision « sans relecteur natif »).

---

## 1. Le besoin et les contraintes

| Contrainte | Valeur |
|---|---|
| Entrée | texte français |
| Sorties | texte lingala **et** audio lingala |
| Données disponibles | Bible FR↔lin ; BibleTTS 71,6 h mono-locuteur 48 kHz ; WAXAL ASR lin 16 kHz |
| Matériel | RTX 5090, 32 Go VRAM, `sm_120` |
| Licences | permissives uniquement ; NC / ND refusés à l'audit |
| Langue | lingala **tonal**, orthographe non standardisée |
| Exigences repo | manifests traçables, rejets journalisés, seuils avec provenance |

Deux conséquences structurantes :

1. Le **texte** est un artefact produit, pas un intermédiaire jetable : l'audio est une modalité d'accessibilité.
2. La **donnée** est le facteur limitant, pas la taille des modèles.

---

## 2. Les trois architectures candidates

### A. Cascade spécialisée

```
phrase FR
   │
   ▼
NMT  (MADLAD-400 3B + LoRA)
   │
   ├──────────────► texte lin  ──────────────► (produit)
   │
   ▼
TTS  (VITS, entrée caractères)
   │
   ▼
audio lin  ──────────────────────────────────► (produit)
```

### B. Modèle multimodal bout-en-bout

```
phrase FR (+ option audio)
   │
   ▼
Modèle omni / parole→parole
   │
   ├──────────────► texte lin (si le modèle en émet)
   └──────────────► audio lin
```

### C. Hybride (cascade + briques multimodales ciblées)

```
phrase FR
   │
   ▼
NMT ─► texte lin ─┬─► VITS ─► audio ─┐
                  │                  ├─► Évaluation prononciation
                  └─► lexique tonal ─┘   (ASR + alignement + GOP + F0)
                                          │
audio de référence (BibleTTS) ────────────┘
                                          │
                                          ▼
                              Feedback pédagogique (audio-LLM, non-gate)

encodeur de parole ─► features prosodie/ton ─► conditionnement VITS
```

---

## 3. Critères de décision

| Critère | Poids | Pourquoi |
|---|---|---|
| Licence / usage commercial | 25 % | contrainte éliminatoire, pas un arbitrage |
| Couverture du lingala | 20 % | aucune valeur si la langue n'est pas couverte |
| Qualité texte (NMT) | 15 % | le texte est un livrable |
| Qualité audio / prosodie | 15 % | cœur de la perception utilisateur |
| Compute / VRAM | 10 % | 32 Go, un seul GPU |
| Traçabilité / évaluation | 10 % | principe du repo |
| Latence / coût de production | 5 % | secondaire à ce stade |

### Matrice indicative (1 = mauvais, 5 = excellent)

| Critère | A. Cascade | B. Multimodal | C. Hybride |
|---|---|---|---|
| Licence | 5 | 2 | 4 |
| Couverture lingala | 4 | 2 | 5 |
| Qualité texte | 4 | 4 | 4 |
| Qualité audio / prosodie | 3 | 3 | 4 |
| Compute / VRAM | 5 | 1 | 3 |
| Traçabilité | 5 | 2 | 4 |
| Latence / coût prod | 5 | 3 | 4 |
| **Score pondéré** | **4,35** | **2,40** | **3,90** |

Lecture : la cascade gagne sur les critères éliminatoires et le coût ; l'hybride gagne sur la couverture et la prosodie mais paie en complexité. Le multimodal pur ne gagne sur aucun critère décisif.

---

## 4. Analyse détaillée

### 4.1 Licences (critère éliminatoire)

| Modèle | Type | Licence | Utilisable en production |
|---|---|---|---|
| MADLAD-400 3B | NMT texte | Apache 2.0 | ✅ |
| NLLB-200 | NMT texte | CC-BY-NC 4.0 | ❌ POC seulement |
| VITS (code original) | TTS | MIT | ✅ |
| Coqui TTS (implémentation) | framework TTS | MPL 2.0 | ✅ (copyleft faible, à valider) |
| Chatterbox Multilingual 0,5 B | TTS Transformer | MIT | ✅ (mais pas de lingala) |
| Parler-TTS | TTS Transformer | Apache 2.0 | ✅ (base anglophone) |
| XTTS v2 | TTS | CPML | ❌ non-commercial |
| SeamlessM4T v2 | parole→parole | CC-BY-NC 4.0 | ❌ |
| MMS-TTS (toutes langues) | TTS VITS | CC-BY-NC 4.0 | ❌ |
| BibleTTS (données) | audio+texte | CC-BY-SA 4.0 | ⚠️ commercial sous conditions |
| WAXAL (données) | audio+texte | CC-BY-SA 4.0 | ⚠️ commercial sous conditions |

Deux règles à conserver dans l'audit :

1. **Le NC est contagieux** : un fine-tune de MMS-TTS reste NC.
2. **Un dérivé ne peut pas changer de licence** : une carte modèle qui affiche Apache/MIT sur une base NC est juridiquement fausse.

Les modèles omni ouverts (Qwen-Omni, Moshi, etc.) sont à vérifier au registre : leurs licences sont hétérogènes et leur couverture vocale du lingala n'est pas documentée.

### 4.2 Couverture du lingala

| Étage | Couvert par un modèle ouvert ? |
|---|---|
| Texte lin (entrée/sortie) | Oui — MADLAD-400 inclut `lin_Latn` |
| Audio lin (sortie) | **Non** — aucun modèle ouvert listé |
| Parole→parole FR→lin | **Non** |

C'est le point décisif : un modèle multimodal devrait **quand même être fine-tuné** sur les 71,6 h de lingala. On paierait donc la taille d'un modèle omni pour la même donnée.

### 4.3 Compute (estimations, à confirmer)

| Scénario | Params entraînables | VRAM | Durée estimée (5090) |
|---|---|---|---|
| NMT MADLAD-3B LoRA (r=16) | ~37 M (1,2 %) | 20–26 Go | 20–40 min (25–30 k paires) |
| TTS VITS 30 M full fine-tune | 30 M | 12–20 Go | 2–4 jours (300–500 k steps) |
| TTS VITS scalé ~80 M | 80 M | 18–26 Go | 3–6 jours |
| TTS Chatterbox 0,5 B LoRA | ~10–30 M | 16–24 Go | plusieurs jours |
| Omni 7 B LoRA bf16 | ~50–100 M | > 32 Go (4-bit ou sharding requis) | plusieurs semaines-équivalent |

Le TTS est la partie la moins coûteuse du plan. Le multimodal est la plus coûteuse, pour un gain non démontré sur le lingala.

### 4.4 Traçabilité et évaluation

Le repo est bâti sur des manifests, `rejects.jsonl`, `run_notes.json` et des seuils avec provenance. Une cascade permet :

- d'attribuer une erreur à un étage (traduction vs prononciation vs audio) ;
- de réentraîner le TTS sans retoucher la traduction ;
- de mesurer séparément chrF++ (texte) et MOS/WER (audio) ;
- de conserver le texte comme livrable.

Un modèle bout-en-bout rend l'erreur opaque et impose une métrique unique, difficile à calibrer.

---

## 5. Le mythe « multimodal = meilleure prosodie »

La prosodie ne vient pas de l'architecture, elle vient de la donnée.

- BibleTTS = **un seul locuteur, lecture biblique, prosodie régulière**. Un modèle 100× plus gros entraîné dessus produira la même voix plate.
- Le lingala est **tonal** : sans ton explicite (G2P/lexique), les homographes sont prononcés au hasard. C'est le premier signal d'artificialité, et aucun modèle plus gros ne le corrige.
- Le zero-shot cloning (Chatterbox) peut emprunter une voix expressive, mais pas inventer la prosodie lingala.

Conséquence : investir dans le **lexique tonal** et dans un **conditionnement prosodique** rapporte plus que changer de famille de modèles.

---

## 6. Évaluation de la prononciation

### 6.1 Évaluer le TTS (contrôle qualité interne — ce n'est pas l'apprenant)

BibleTTS fournit l'**audio de référence du même verset** : l'évaluation peut être reference-based.

| Axe | Méthode | Rôle du multimodal |
|---|---|---|
| Intelligibilité | ASR (MMS) → CER/WER | aucune (ASR classique) |
| Prononciation | alignement forcé → GOP | encodeur de parole utile comme features |
| **Ton** | contour F0 + DTW vs référence | aucune |
| Naturel | UTMOS / DNSMOS | aucune |
| Proximité locuteur | embeddings (SECS) | oui, encodeur de parole |

Un audio-LLM peut produire un **diagnostic en langage naturel**, mais il est mal calibré, non reproductible et biaisé : il ne peut pas servir de **gate**. Il intervient après les métriques, jamais à leur place.

### 6.2 Évaluer l'apprenant (cible produit — détail en §10)

La détection d'erreur de prononciation (MDD) exige :

1. un modèle acoustique + alignement forcé ;
2. un **lexique phonétique de référence** (G2P) ;
3. des scores GOP par phonème, **plus le ton**.

Le blocage actuel n'est pas le modèle mais le **G2P lingala et l'inventaire tonal**. Un audio-LLM dira « ça sonne approximatif », pas « le ton haut est tombé sur la mauvaise syllabe ».

---

## 7. Décision recommandée

### 7.1 Architecture retenue

**Cascade spécialisée (A) comme socle, briques multimodales ciblées (C) comme trajectoire.**

| Étage | Choix | Licence |
|---|---|---|
| NMT | MADLAD-400 3B + LoRA (r=16, α=32) | Apache 2.0 |
| TTS | VITS from scratch, 22,05 kHz, ~30–80 M | MIT / MPL 2.0 |
| Évaluation | ASR + alignement + GOP + F0 + UTMOS | permissif |
| Feedback | audio-LLM en restitution, hors gate | à vérifier |

### 7.2 Chemins d'amélioration, dans l'ordre

1. **VITS baseline** sur 20–30 h → gate d'écoute (M3).
2. **Ablation ton** : texte avec tons vs sans → isoler la cause de l'artificialité.
3. **VITS scalé** (~80 M) + conditionnement prosodique (F0/durée).
4. **Chatterbox 0,5 B + LoRA** (MIT) si les étapes précédentes plafonnent — accepter le watermark PerTh et l'absence de lingala natif.

### 7.3 Conditions de réexamen du multimodal

Repasser l'arbitrage si l'une de ces conditions est remplie :

- un modèle omni ouvert **permissif** liste le lingala en **sortie vocale** ;
- le volume audio dépasse ~500 h multi-locuteurs ;
- l'expressivité devient une exigence produit de premier rang ;
- la traduction parole→parole temps réel devient un besoin commercial.

**Extension (révision 2026-11-02)** : l'architecture retenue est déclinée en **trois modèles indépendants** et l'évaluation de prononciation est précisée en **§10** (alignement forcé + GOP segmental, sans LLM ; le ton est retiré par décision « sans relecteur natif »).

---

## 8. Risques et parades

| Risque | Impact | Parade |
|---|---|---|
| Contamination NC (MMS, Seamless) | juridique | audit de licence par poids, pas par carte modèle |
| Domaine biblique unique | qualité hors domaine | tests hors domaine, compléter par WAXAL |
| Ton lingala non modélisé | prononciation fausse | G2P/lexique tonal avant scale-up |
| 24 kHz vs 22,05 kHz | réentraînement | trancher avant le premier run |
| Surapprentissage NMT | chrF biblique trompeur | éval sur FLORES + hors domaine |
| Watermark Chatterbox | traçabilité des sorties | accepter explicitement ou éviter |
| Catastrophic forgetting (omni) | perte de qualité | LoRA, faible LR, éval par langue |

---

## 9. Plan d'action

| Phase | Contenu | Sortie |
|---|---|---|
| 0 | Calibrer les seuils, remplir FLORES, débloquer le G2P tonal | manifests `publishable: true` |
| 1 | NMT LoRA + VITS baseline | gate M3 (écoute native) |
| 2 | Harnais d'évaluation prononciation reference-based | rapport par axe |
| 3 | VITS scalé + prosodie | comparaison MOS |
| 4 (conditionnel) | Chatterbox LoRA | décision go/no-go |

---

## 10. Révision — architecture à trois modèles et évaluation de prononciation (sans LLM)

Statut : **révision proposée le 2026-11-02**. Complète §6.2 et §7.1 ; ne les remplace pas. Les scores et seuils cités restent indicatifs tant qu'ils ne sont pas calibrés.

### 10.1 Décision

L'application passe de « cascade + brique multimodale de feedback » à **trois modèles indépendants, sans poids partagés** :

| Modèle | Rôle | Choix | Licence |
|---|---|---|---|
| **M1 — Texte** | FR → lingala | MADLAD-400 3B + LoRA | Apache-2.0 |
| **M2 — Génération audio** | texte lingala → audio | VITS (BibleTTS) | MIT / MPL-2.0 |
| **M3 — Évaluation audio** | audio apprenant → score par mot | encodeur SSL + alignement forcé + GOP | Apache-2.0 (encodeur) |

Le seul partage est **symbolique** : le noyau **G2P segmental** (phonèmes), consommé par M3 (cible d'alignement). Le **lexique tonal n'est pas développé** (décision « sans relecteur natif », ci-dessous) ; M2 n'est pas conditionné. **Aucun poids n'est partagé.**

Justification (reprend §4.4) :
- **M2 = BibleTTS uniquement** : WAXAL ne fournit **pas** de sous-corpus TTS lingala (`lin_tts` absent) ; WAXAL est réservé à M3 (ASR/évaluation) ;
- données disjointes : BibleTTS = 1 locuteur (M2), WAXAL = multi-locuteurs (M3) ;
- licences auditables par modèle ;
- erreur attribuable par étage ;
- pas de transfert négatif entre génération et discrimination.

**Objet de l'évaluation : l'apprenant uniquement.** L'évaluation du TTS (§6.1) est un contrôle qualité interne, un autre objet ; elle n'est ni la cible ni la référence de M3.

**Le feedback audio-LLM est retiré.** M3 ne produit pas de diagnostic en langage naturel : il produit un **rapport structuré** et un **surlignage au niveau du mot** — **vert = bien prononcé, neutre = à réessayer** (rouge réservé aux erreurs nettes, optionnel), avec icône pour l'accessibilité. C'est déterministe, reproductible et testable.

**Décision complémentaire — sans relecteur natif (2026-11-02).** Aucun locuteur natif, linguiste ni annotateur n'étant disponible, la révision est restreinte au **segmental** : le ton (F0, lexique tonal, gold set §8 du pilot, MOS natif, gate humain L7) est **retiré du périmètre**. Les gates deviennent **automatiques** : back-translation + chrF/COMET pour M1, UTMOS/DNSMOS + WER pour M2, calibration natif vs corrompu pour M3. La variété Kinshasa reste une **hypothèse non vérifiée**.

### 10.2 Pipeline M3 (alignement forcé + GOP)

**Deux modes d'entrée, le même M3 :**

- **Mode A — mot / phrase à apprendre** : M1 traduit, M2 génère l'audio de référence ; l'orthographe et la prononciation sont affichées, l'apprenant répète, puis M3 évalue.
- **Mode B — phrase écrite dans la langue cible** : l'apprenant lit la phrase affichée ; M3 évalue directement (sans M1 ni M2).

```
phrase lingala affichée ─► G2P segmental ─► phonèmes attendus
                                              │
audio apprenant ─► encodeur acoustique ─► alignement forcé (Viterbi contraint)
                                              │
                                              ├─► GOP par phonème
                                              └─► (non déployé) F0 par syllabe → score de ton
                                              │
                                              ▼
                                 agrégation mot / syllabe
                                              ▼
                          rapport structuré (JSON) → couleur + icône
```

- **Alignement forcé** : la phrase cible est connue → pas de reconnaissance libre ; on place les frontières des phonèmes attendus.
- **GOP** : `log P(phonème attendu | segment) − log max_q P(q | segment)`. Proche de 0 = bon ; très négatif = erreur.
- **Ton** : **non déployé** (pas de lexique tonal). Le GOP reste segmental ; `mutu`/`mutú` ne sont pas distingués automatiquement.
- **Référence** : **parole native** (WAXAL/FLEURS), sans validation humaine. **M2 n'est jamais la référence de score** (circularité).

### 10.3 Contrat de données

Quatre manifestes reliés par `core_id` ; aucun mélange de fichiers audio.

```jsonc
// core_phonemes.jsonl — noyau partagé
{"core_id":"...", "text":"...", "phonemes":["m","u","t","u"],
 "syllables":[...], "lang":"lin", "variety":"kin"}

// manifest_tts.jsonl
{"core_id":"...", "audio":"...", "sr":48000, "speaker":"bibletts_EZR",
 "domain":"bible", "source":"bibletts", "license":"CC-BY-SA-4.0"}

// manifest_mdd.jsonl
{"core_id":"...", "learner_audio":"...", "reference_id":"...",
 "labels":{"phonemes":[...], "scores":[...]},
 "speaker":"...", "l1":"fra", "source":"...", "license":"..."}

// pronunciation_report.jsonl — sortie M3
{"utterance_id":"...", "words":[{"text":"mutu","gop":0.81,"color":"green"}]}
// champ "tone" réservé mais non produit (pas de lexique tonal)
```

Règles :
- `core_id` = clé de jointure (phonèmes) ;
- l'audio de référence vient d'un **natif** (WAXAL/FLEURS), jamais de M2 ;
- les seuils de couleur sont calibrés sur **natif vs corrompu** et leur provenance est journalisée.

### 10.4 Licences vérifiées au registre (2026-11-02)

| Modèle | Licence | Verdict |
|---|---|---|
| `facebook/wav2vec2-base-960h` | Apache-2.0 | ✅ |
| `facebook/wav2vec2-large-xlsr-53` | Apache-2.0 | ✅ (lingala probablement absent) |
| `facebook/wav2vec2-xls-r-300m` | Apache-2.0 | ✅ base recommandée |
| `facebook/wav2vec2-xls-r-1b` | Apache-2.0 | ✅ |
| MMS (`mms-1b-all`, `mms-300m`, …) | CC-BY-NC | ❌ D6 |
| Fine-tunes lingala HF (licence inconnue / base MMS) | None / NC | ❌ tant que non confirmés |
| `torchaudio` | BSD-2-Clause | ✅ |
| `transformers` | Apache-2.0 | ✅ |

Conséquence : **aucun checkpoint CTC lingala admissible** n'existe. M3 se construit en fine-tunant **XLS-R-300m** sur WAXAL.

### 10.5 POC et jalon go/no-go

- **POC-0 (plomberie)** : `torchaudio.functional.forced_align` + `merge_tokens` sur un clip WAXAL, cible = greedy d'un modèle Apache (mécanique seulement, qualité non jugée).
- **POC-1 (le vrai)** : fine-tune XLS-R-300m + tête CTC caractères sur 1–3 h de WAXAL ; aligner la **transcription réelle** ; calculer un GOP par token ; **test de sanité** sur audio corrompu (les GOP doivent chuter).
- **Critère go/no-go** : le GOP sépare nettement correct vs corrompu. Sinon, on arrête M3.
- **Prérequis bloquants** : G2P **segmental** lingala et calibration **natif vs corrompu** (pas de lexique tonal ni de corpus annoté).

### 10.6 Risques et parades

| Risque | Impact | Parade |
|---|---|---|
| Circularité (TTS comme référence) | apprend de fausses prononciations | référence native uniquement |
| Ton absent du GOP | `mutu`/`mutú` notés verts | **hors périmètre** : pas de score tonal (décision sans relecteur) |
| Seuils non calibrés | faux négatifs | calibration natif vs corrompu, seuils pré-enregistrés |
| Pas de données L2 lingala | MDD non validé | GOP non supervisé + calibration natif vs corrompu |
| Aucun relecteur natif | gates humains impossibles | décision sans relecteur : gates automatiques, ton abandonné |
| Mots courts mal alignés | faux négatifs | prudence / seuils distincts |
| Locuteur / micro | faux négatifs | normalisation, tests multi-locuteurs |
| Licence des poids | juridique | audit par modèle ; éviter MMS |
| Audio apprenant (vie privée) | RGPD | consentement, non-conservation par défaut |

### 10.7 Décisions à ratifier

1. Trois modèles, aucun poids partagé ; noyau **segmental** partagé.
2. Suppression du feedback audio-LLM ; sortie = rapport structuré + couleur.
3. M3 = alignement forcé + GOP, référence native (sans F0).
4. Encodeur = XLS-R-300m (Apache-2.0), MMS exclu.
5. Contrat de données à quatre manifestes, joint par `core_id`.
6. POC-1 comme gate avant tout développement produit.
7. Prérequis bloquants : G2P segmental + calibration natif vs corrompu.
8. Décision « sans relecteur natif » : ton, gold set et MOS humain hors périmètre.

---

## 11. Données vérifiées (état sur disque, 2026-11-02)

| Source | Usage | État réel | Volume | Licence |
|---|---|---|---|---|
| **eBible FR↔lin** (`data/corpus/lin_fr_v2/`) | M1 | 30 330 paires gardées ; 102 quarantaine ; 627 rejets | ~31 k paires | CC BY-SA 4.0 + domaine public |
| **BibleTTS `lin`** (`data/bibletts/`) | M2 | `.tgz` 13 Go ; **seul `dev/EZR` extrait** (202 flac) | 0,97 h extraites / **71,6 h** attendues | CC BY-SA 4.0 |
| **WAXAL `lin` ASR** (`data/waxal/asr/lin/`) | M3 | train 14 400 clips ; val 1 844 ; test 1 866 | **71,9 h** train | **CC BY-SA 4.0** (Digital Umuganda) |
| **FLEURS `lin`** (à télécharger) | références / éval / voix moderne | absent | ~10 h | **CC BY 4.0** |
| **FLORES-200 devtest** (`data/flores/`) | éval M1 + anti-fuite | parquet présent ; `data/flores/devtest/` **vide** | petit | CC BY-SA 4.0 |

Corrections à reporter au registre :

1. **WAXAL `lin` = CC-BY-SA-4.0**, pas CC BY 4.0 (`Pilot_Lingala_v1.1.md:54` est à corriger).
2. **WAXAL audio = 48 kHz** (quelques clips à 44,1 kHz), alors que `ml/README.md:107` et `audio_sources.py` annoncent 16 kHz.
3. **BibleTTS** n'est extrait que pour `dev/EZR` ; `audio_tts.py` ne lit que `splits=("dev",)`.
4. **Common Voice 17 ne propose pas le lingala** (`ln` absent de la liste des langues).
5. Les jeux HF communautaires (`KasuleTrevor/Lingala_100hrs`, `AfriVoice-lin`, `AMMI/LRSC`) affichent une **licence inconnue** → refusés tant que non confirmés (D6).

---

## 12. Prérequis communs

### 12.1 Environnement

- PyTorch **2.14.1+cu130** déjà installé ; **`torchaudio` absent** → installer la version appariée.
- `transformers`, `soundfile`, `pyarrow` ; `librosa`/`crepe` **non requis** (F0 hors périmètre, §3.4).
- Respecter D13 (`sm_120`, CUDA 12.8+/cu130).

### 12.2 Préparation des données

1. Extraire **BibleTTS complet** depuis `data/bibletts/lingala.tgz`.
2. Passer M2 sur `sources=["bibletts"]` uniquement (le défaut actuel mélange `bibletts` et `waxal` dans `_gather_stream`).
3. Remplir `data/flores/devtest/`.
4. Construire les **splits** : book-aware pour la Bible (M1/M2), **speaker-disjoint** pour WAXAL (M3).
5. Définir le **vocabulaire** : caractères lingala (M3, issu des transcriptions WAXAL) et phonèmes+tons (noyau, une fois le G2P construit).

### 12.3 Versionnement

- Manifests et splits versionnés comme **ClearML Datasets** (D10) ; un entraînement référence un `dataset_id`.
- Chaque run journalise : seed, hash de config, hash de manifest, version des poids de base, licence.

### 12.4 Décision : sans relecteur natif (2026-11-02)

**Contexte** : aucun locuteur natif, linguiste ni annotateur n'est disponible pour le projet.

| Élément initialement prévu | Statut |
|---|---|
| Lexique tonal + score de ton (F0) | **non développé** ; M2 et M3 restent segmentaux |
| Gold set tonal annoté (pilot §8) | **supprimé** ; remplacé par des contrôles automatiques |
| Gate humain L7 sur le core NMT | **remplacé** par back-translation + chrF/COMET + couverture lexicale |
| MOS natif de M2 | **remplacé** par UTMOS/DNSMOS + WER via M3 |
| Calibration des seuils sur set annoté | **remplacée** par calibration natif vs audio corrompu |
| Vérification de la variété (pilot L1) | **hypothèse non vérifiée** : Kinshasa assumé par défaut, documenté comme tel |

**Ce qui reste possible sans relecteur** : G2P segmental (règles), alignement forcé, GOP, CER/WER, UTMOS, back-translation. **Ce qui est abandonné** : toute décision exigeant un jugement natif (validation tonale, MOS, arbitrage de variété, gold set).

---

## 13. M1 — NMT FR → lingala

### 13.1 Données

- `data/corpus/lin_fr_v2/manifest_corpus.jsonl` + `splits/{train,dev,test}.jsonl`.
- **Exclure FLORES** de l'entraînement (réservé à l'éval et à l'anti-fuite).
- Le corpus est **majoritairement biblique** : risque d'effondrement de domaine. Le NMT reste un **brouillon** ; sans relecteur, le vocabulaire core passe par des **contrôles automatiques** (§13.4).

### 13.2 Architecture

- Base `google/madlad-400-3b` (Apache-2.0), tokenizer SentencePiece, préfixes de langue `fra`→`lin_Latn`.
- **LoRA** : rang r=16, α=32, sur `q/k/v/o` et `gate/up/down` ; ≈37 M paramètres entraînables.
- **Learning rate schedule** : cosine decay avec warmup de 10 % des steps, LR initiale 2e-4, min LR 2e-5.

### 13.3 Recette

| Paramètre | Valeur |
|---|---|
| Perte | cross-entropy + label smoothing 0,1 |
| LR | 1e-4 à 2e-4 (LoRA) → **cosine decay + warmup 10 %** |
| Batch effectif | 32 (accumulation de gradient) |
| Longueur max | 256 tokens |
| Époques | 3 à 5 |
| Précision | bf16 + gradient checkpointing |
| VRAM | 20–26 Go |
| Durée (5090) | ~20–40 min pour 25–30 k paires |
| **Schedule** | cosine decay, min LR 2e-5 |

### 13.4 Évaluation / gate

- **chrF++**, BLEU, COMET sur FLORES `lin_Latn` **et** sur un dev biblique tenu à l'écart.
- Test hors domaine obligatoire (le chrF biblique est trompeur).
- **Contrôles automatiques du core** (remplacent le gate humain L7) :
  - **back-translation** lin→FR (MADLAD) puis **chrF/COMET** contre la phrase source ;
  - **couverture lexicale** : le mot core doit être attesté dans le corpus, pas une hallucination ;
  - **filtre de confiance** : une entrée sous le seuil de back-translation n'est pas exposée comme vérité, seulement comme suggestion.
- **Limite assumée** : sans relecteur natif, ces contrôles détectent les dérives grossières, pas les nuances sémantiques.

### 13.5 Artefacts

- Adaptateur LoRA + config fusionnée ; carte modèle avec licence Apache-2.0 et provenance des données.
- Rapport d'éval (FLORES + dev biblique) attaché au run.

---

## 14. M2 — TTS VITS

### 14.1 Données

- **BibleTTS `lin` uniquement** : 71,6 h alignées (+151,7 h non alignées en bonus), 48 kHz, **1 locuteur studio**.
- **WAXAL n'entre pas dans M2** (pas de `lin_tts`, multi-locuteurs, conditions variables). WAXAL est réservé à M3.
- Chaîne de préparation : `ml/preprocess` (A1–A12) → `manifest_tts.jsonl` + mel. Changer le défaut de sources pour `["bibletts"]`.

### 14.2 Architecture

- **VITS from scratch**, ~30–80 M paramètres.
- Fréquence cible : **24 kHz** (D7/D10) — VITS historiquement à 22,05 kHz : **trancher avant le premier run** (risque §8 du doc architecture).
- Entrée texte **segmentale** uniquement (régime A) ; le conditionnement **tonal** (régime B) est **retiré** par la décision « sans relecteur » (§12.4).
- **Learning rate schedule** : cosine annealing avec warmup de 5 % des steps, LR initiale 2e-4, min LR 2e-5.

### 14.3 Recette

| Paramètre | Valeur |
|---|---|
| Steps | 300 000 à 500 000 |
| Batch | 16 à 32 |
| Optimiseur | AdamW |
| **LR schedule** | **cosine annealing + warmup 5 %** |
| Précision | bf16 |
| Discriminateur | HiFi-GAN (inclus) |
| VRAM | 12–26 Go selon la taille |
| Durée (5090) | 2 à 4 jours |

### 14.4 Évaluation / gate

- **Pas de MOS natif** (décision §12.4) ; évaluation automatique à chaque checkpoint sur phrases fixes :
  - **UTMOS / DNSMOS** pour la naturalité ;
  - **WER via ASR** — réutiliser M3, pas MMS ;
  - **test de sanité** : audio généré vs silence/bruit, le WER doit se dégrader nettement.
- **Pas de régime B** : le conditionnement tonal est hors périmètre sans relecteur ; M2 est segmental uniquement.

### 14.5 Artefacts

- Générateur + config + hash des données ; échantillons audio de référence par checkpoint.
- Mention explicite de la licence des données (CC BY-SA 4.0, copyleft — réserve L8) et de la voix unique.

---

## 15. M3 — Modèle acoustique d'évaluation

### 15.1 Données

- **WAXAL `lin`** : train 14 400 clips (71,9 h), val 1 844, test 1 866 ; audio **48 kHz** → resampler **16 kHz**.
- Splits **speaker-disjoint** obligatoires.
- **FLEURS `lin`** (CC BY 4.0, ~10 h) peut servir de références modernes / jeu de validation externe, pas d'entraînement principal.

### 15.2 Vocabulaire

- Démarrer **au caractère** : alphabet lingala extrait des transcriptions WAXAL.
- Conséquence : **pas besoin du G2P** pour le coloriage segmental. Le G2P segmental ne sert qu'à un diagnostic phonétique plus fin ; le lexique tonal, lui, n'est pas développé (§12.4).

### 15.3 Architecture

- `facebook/wav2vec2-xls-r-300m` (Apache-2.0) + tête CTC.
- Geler le feature extractor au début, puis dégeler (ou LoRA).
- **Learning rate schedule** : cosine annealing avec warmup de 10 % des steps, LR tête 1e-4 → 1e-5, encodeur 3e-5 → 1e-6.

### 15.4 Recette

| Paramètre | Valeur |
|---|---|
| Perte | CTC |
| LR | 1e-4 (tête) / 3e-5 (encodeur) |
| Warmup | 10 % des steps |
| Batch | 8 à 16 + accumulation |
| Précision | bf16 |
| Époques | 10 à 30 |
| Augmentation | SpecAugment + speed perturbation (×0,9 / ×1,1) |
| VRAM | 16–24 Go |
| Durée (5090) | 1 à 2 jours pour 72 h |

### 15.5 Évaluation / gate

1. **CER/WER** sur WAXAL test.
2. **Test de sanité GOP** : comparer audio correct vs audio corrompu (autre locuteur / inversé / décalé). Les scores doivent chuter nettement.
3. **Calibration sans annotation** : les seuils vert/neutre sont calibrés sur la distribution **natif vs corrompu** (et sur des paires de mots courts/longs), pas sur un set annoté humain.
4. **Go/no-go** : si le GOP ne sépare pas correct vs corrompu, on arrête M3. Le ton n'est plus un critère (hors périmètre).

### 15.6 Pipeline d'évaluation (déterministe, hors entraînement)

```
phrase lingala affichée
   │
   ├─► (optionnel) G2P segmental ─► phonèmes attendus
   │
audio apprenant ─► M3 (posteriors) ─► alignement forcé (Viterbi contraint)
                                           │
                                           ├─► GOP par caractère/phonème
                                           └─► (non déployé) F0 par syllabe → score de ton
                                           │
                                           ▼
                              agrégation mot / syllabe → seuils
                                           ▼
                      rapport structuré → surlignage vert / neutre
```

- **Alignement forcé** : `torchaudio.functional.forced_align` sur la séquence **connue** (la phrase est affichée).
- **GOP** : `log P(unité attendue | segment) − log max_q P(q | segment)`.
- **Ton** : **non déployé** (pas de lexique tonal) ; le GOP reste segmental.
- **Référence** : **parole native** (WAXAL/FLEURS), sans validation humaine ; **jamais l'audio de M2** (circularité).
- **Seuils** : calibrés sur **natif vs corrompu** (pas de set annoté), pré-enregistrés ; viser un faible taux de faux négatifs.

### 15.7 Sortie

```jsonc
// pronunciation_report.jsonl
{"utterance_id":"...", "words":[
  {"text":"mutu",  "gop":0.81, "color":"green"},
  {"text":"akoki", "gop":0.42, "color":"none"}
]}
```

Le champ `tone` est **réservé mais non produit** (pas de lexique tonal, §12.4) ; les consommateurs doivent tolérer son absence.

Coloriage : **vert = bien prononcé**, **neutre = à réessayer**. Rouge optionnel pour les erreurs nettes. Icône + soulignement pour l'accessibilité (ne pas coder l'information par la couleur seule).

### 15.8 Deux modes d'entrée, le même M3

- **Mode A — mot/phrase à apprendre** : M1 traduit, M2 génère l'audio de référence, orthographe et prononciation affichées ; l'apprenant répète, M3 évalue.
- **Mode B — phrase écrite en lingala** : l'apprenant lit ; M3 évalue directement (sans M1 ni M2).

---

## 16. Ordre d'exécution et planning

| Étape | Contenu | Sortie | Durée indicative |
|---|---|---|---|
| 0 | Env + data prep (extraction BibleTTS, splits, FLEURS, FLORES) | manifests versionnés | 1–2 j |
| 1 | **M3 POC** sur 5–10 h WAXAL | décision go/no-go | 2–4 j |
| 2 | **M3 complet** (72 h) | modèle CTC + rapport GOP | 2–4 j |
| 3 | **M1 LoRA** | adaptateur + éval FLORES | < 1 j |
| 4 | **M2 VITS** (BibleTTS complet) | générateur + UTMOS/WER | 3–5 j |
| 5 | Calibration seuils + UI couleur | rapport + surlignage | 3–5 j |

Justification de l'ordre : M3 est le **risque nouveau** (fonctionnalité demandée) → le dé-risquer en premier ; M1 est rapide et débloque le mode A ; M2 est long mais non bloquant pour l'évaluation.

### Récapitulatif compute

| Modèle | VRAM | Durée (5090) |
|---|---|---|
| M1 LoRA | 20–26 Go | 20–40 min |
| M2 VITS | 12–26 Go | 2–4 jours |
| M3 XLS-R CTC | 16–24 Go | 1–2 jours |

---

## 17. Ce qui n'est **pas** un modèle entraîné

| Brique | Nature |
|---|---|
| G2P segmental | règles (orthographe → phonèmes) ; **lexique tonal non développé** |
| Alignement forcé | algorithme (`torchaudio`) |
| GOP | calcul sur postérieurs |
| Seuils vert/neutre | calibration statistique |
| Surlignage / rapport | logique applicative |

---

## 18. Reproductibilité et registres

- Chaque modèle publie : config, seed, hash de manifest, `dataset_id` ClearML, version des poids de base.
- Les rejets et les seuils non calibrés restent journalisés (`rejects.jsonl`, `run_notes.json`) — la règle « seuil sans provenance = non publiable » s'applique.
- Registre des modèles à tenir : `id`, rôle, base, licence des poids, licence des données, statut (POC / prod), usage.

---

## 19. Risques et parades

| Risque | Modèle | Parade |
|---|---|---|
| Effondrement de domaine (tout biblique) | M1 | test FLORES + hors domaine, contrôles automatiques (back-translation, chrF/COMET) |
| Voix unique + prosodie biblique | M2 | accepter en v1 ; FLEURS/WAXAL pour une v2 moderne |
| CC BY-SA (copyleft) | M2 / M3 | revue juridique L8 ; FLEURS (CC BY) pour les références |
| Pas de `lin_tts` WAXAL | M2 | exclure WAXAL de M2 ; l'utiliser pour M3 |
| Pas de données L2 lingala | M3 | GOP non supervisé + calibration natif vs corrompu |
| Ton absent du GOP | M3 | **hors périmètre** : pas de score tonal (décision sans relecteur) |
| Seuils non calibrés | M3 | calibration natif vs corrompu, seuils pré-enregistrés |
| Aucun relecteur natif | tous | décision §12.4 : gates automatiques, ton abandonné, hypothèses documentées |
| Fuite train/test | M1/M2/M3 | splits book-aware / speaker-disjoint |
| Licence des poids | tous | éviter MMS (NC) ; vérifier chaque base |
| Vie privée de l'audio apprenant | M3 | consentement, non-conservation par défaut, RGPD |

---

## 20. Décisions ouvertes

1. Fréquence TTS : 22,05 kHz (naturel VITS) vs 24 kHz (D7/D10) — à trancher avant le premier run.
2. Régime tonal M2 : **tranché — A (sans ton)** ; B hors périmètre (§12.4).
3. Taille M2 : 30 M vs 80 M.
4. Calibration des seuils : **tranché — natif vs corrompu**, sans corpus L2 annoté (§12.4).
5. FLEURS `lin` : entraînement M3 ou seulement références/éval.
6. WAXAL : v2 TTS multi-locuteurs — oui/non, et avec quels splits.
7. Statut juridique des dérivés CC BY-SA (voix, éventuel lexique) — L8.

---

## Annexe A — Arborescence cible

```
ml/
  train/
    common.py          # seeds, config, logging, ClearML
    nmt.py             # M1 — MADLAD + LoRA
    tts.py             # M2 — VITS (BibleTTS)
    mdd.py             # M3 — XLS-R + CTC (WAXAL)
  eval/
    nmt_eval.py        # chrF++/BLEU/COMET (FLORES)
    tts_eval.py        # UTMOS/WER (pas de MOS natif)
    pron_eval.py       # forced_align + GOP + rapport
models/
  nmt/  tts/  mdd/     # checkpoints + config + cartes modèle
data/
  processed/lin/...    # manifests versionnés (ClearML)
```

## Annexe B — Hyperparamètres (résumé)

| | M1 | M2 | M3 |
|---|---|---|---|
| Base | MADLAD-400 3B | VITS 30–80 M | XLS-R-300m |
| Adaptation | LoRA r=16 α=32 | from scratch | full / LoRA |
| **LR schedule** | **cosine decay + warmup 10 %** | **cosine annealing + warmup 5 %** | **cosine annealing + warmup 10 %** |
| LR initiale | 2e-4 | 2e-4 | tête: 1e-4, encodeur: 3e-5 |
| Min LR | 2e-5 | 2e-5 | tête: 1e-5, encodeur: 1e-6 |
| Précision | bf16 | bf16 | bf16 |
| Steps/époques | 3–5 époques | 300–500 k steps | 10–30 époques |
| Sortie | adaptateur LoRA | générateur VITS | tête CTC |

---

## Annexe — glossaire

| Terme | Définition |
|---|---|
| S2ST | Speech-to-Speech Translation |
| NMT | Neural Machine Translation |
| TTS | Text-to-Speech |
| VITS | Variational Inference with adversarial learning for end-to-end TTS |
| LoRA | Low-Rank Adaptation (adaptateur de rang faible) |
| GOP | Goodness of Pronunciation |
| MDD | Mispronunciation Detection and Diagnosis |
| F0 | Fréquence fondamentale (porteur du ton) |
| CER / WER | Character / Word Error Rate |
| UTMOS | Métrique de naturalité audio prédite |
| SECS | Speaker Embedding Cosine Similarity |
| NC / ND / SA | NonCommercial / NoDerivatives / ShareAlike |

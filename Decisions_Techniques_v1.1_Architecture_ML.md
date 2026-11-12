# NOTE TECHNIQUE — MISE À JOUR v1.1

## Registre des décisions techniques — Architecture ML & pipeline de prononciation

Application d'apprentissage des langues africaines — Wolof · Lingala · Bambara

---

**STATUT DU DOCUMENT**

Complément au registre v1.0 (24 août 2026). Ajoute les décisions **D6 à D14** (périmètre ML) et amende la ligne « Inférence TTS » de **D4**. Les décisions **D1 à D3 et D5** restent inchangées.

**Décisions validées en session** : D8, D9, D10, D11, D13.
**Décisions soumises à arbitrage** : D6, D7 (choix permissif vs non commercial), D12 (hébergement ClearML), D14.

8 octobre 2026 — document de conception, usage interne projet
Sources : Cahier des charges design · Règles métier v2 · Registre v1.0 · Recherche licences/datasets (WAXAL, BibleTTS, MADLAD-400, An ka taa, LanguageNet) · Tests `africa-g2p` 0.3.2 et `uiuc-sst/g2ps`

---

## 1. Ce que cette mise à jour modifie

| Décision v1.0 | Impact de la v1.1 |
|---|---|
| D4 — Cache audio déterministe | Mécanique inchangée (`sha256(langue\|texte\|voix)`). **Le modèle derrière change** : XTTS-v2 (CPML NC) → modèle permissif, cf. D7. |
| Table section 3 : « Inférence TTS = Replicate (XTTS-v2 fine-tuné) » | **Remplacée** par la décision D7. |
| Phase 1 — fine-tuning XTTS-v2 (document dédié) | **Restreinte au POC interne** (usage non commercial uniquement), cf. D7. |
| D1, D2, D3, D5 | Inchangées. |
| Hors périmètre v1.0 : « pipeline de fine-tuning TTS » | **Ramené dans le périmètre** du registre : chaîne NMT, G2P, couche tonale, TTS, supervision. |

**Principe transversal (non numéroté) — Politique de licences.** L'app vise un premium à 3-4 $/mois : **tout composant déployé en production doit être sous licence permissive** (Apache-2.0, MIT, CC-BY, CC-BY-SA). Les licences non commerciales (CC-BY-NC, CPML) sont tolérées **uniquement** en POC interne, jamais exposées à l'appel utilisateur ni à des poids téléchargés.

---

## 2. Architecture ML cible

```
        ENTRAÎNEMENT / SUPERVISION (poste RTX 5090, hors parc VPS)
        ┌──────────────────────────────────────────────────────────────────┐
        │  ClearML agent → tracking expériences · datasets · métriques     │
        └──────────────────────────────────────────────────────────────────┘

        PIPELINE DE PRONONCIATION (batch, à l'ingestion)
[Texte FR] ─► [D6 NMT] ─► [Texte cible] ─┬─► [D9 G2P segmental] ─► [D8 COUCHE TONALE] ─► phonèmes + tons ─┐
                                          │        africa-g2p            lexique + règles                  │
                                          │                                            │                      ▼
                                          │        [affichage : prononciation        │            [Modèle acoustique
                                          │         écrite « dǎn.ki.li »] ◄───────────┘             → mel-spectrogramme]
                                          │                                                                     │
                                          │                                                                     ▼
                                          └────────────────► [cache D4] ◄──────────────── [D7 vocoder HiFi-GAN] ─► MP3
```

Deux branches se rejoignent au **mel-spectrogramme** : le **transformer** (NMT, tokens texte) et le **CNN** (vocoder HiFi-GAN, signal). La couche tonale D8 est le seul endroit où l'information de hauteur entre dans la chaîne.

---

## 3. Décisions

### D6 — Chaîne NMT : MADLAD-400 par défaut, NLLB-200 réservé au POC — PROPOSÉ

**Contexte**
La session de design a retenu le fine-tuning de NLLB-200. La vérification de licence montre que **NLLB-200 est CC-BY-NC-4.0** : inutilisable derrière un premium. Le projet WAXAL ne contient **aucune donnée parallèle** pour les 3 langues → impossible de partir de zéro à court terme.

**Décision**
MADLAD-400 (3B, **Apache-2.0**, 400+ langues, couvre `lin_Latn`, `wol_Latn`, `bam_Latn`) est le candidat par défaut pour le fine-tuning FR → cible. NLLB-200 reste utilisable en **POC interne** uniquement (bench qualité), sans appel exposé et sans redistribution de poids. Évaluation systématique sur **FLORES-200 devtest** (déjà retenu dans les specs), métrique BLEU/chrF + COMET lié aux scores du manifest.

**Alternatives écartées**
NLLB-200 (CC-BY-NC : bloquant pour le premium) · Opus-MT (CC-BY : licence correcte, couverture des 3 langues à vérifier, retenu comme filet de sécurité) · mBART-50 (permissif mais couverture faible sur ces langues).

**Conséquences**
Une passe de benchmark MADLAD vs Opus-MT sur FLORES devtest avant tout entraînement ; si la couverture ou la qualité est insuffisante, bascule Opus-MT sans changement d'architecture (le manifest et l'éval ne changent pas).

---

### D7 — Chaîne TTS : modèle permissif auto-hébergé, XTTS-v2 en POC — PROPOSÉ

**Contexte**
Phase 1 de la v1.0 = fine-tuning XTTS-v2. Or **XTTS-v2 est sous CPML (non commercial)** ; les checkpoints F5-TTS sont CC-BY-NC-4.0 (le code est MIT, un re-entraînement from scratch est commercialement libre) ; `galsenai/xTTS-v2-wolof` hérite des mêmes restrictions ; MMS-TTS et Spark-TTS sont également NC. BibleTTS est **CC BY-SA 4.0** (commercial-compatible, sans affichage de versets) et WAXAL TTS fournit ~235 h mono-locuteur **16 kHz** mais **sans `lin_tts`, `wol_tts`, `bam_tts`**.

**Décision**
1. **POC interne** : fine-tuning XTTS-v2 maintenu, uniquement pour valider le pipeline et la qualité, jamais exposé en production.
2. **Cible production** : modèle **permissif** auto-hébergé sur la RTX 5090 — **Parler-TTS (Apache-2.0)** ou **VITS from scratch (~30 M paramètres, ~20-40 h/langue, MIT)** — entraîné sur BibleTTS (résamplé 24 kHz) + WAXAL TTS 16 kHz résamplé. Le proxy API et le cache D4 restent identiques : seul le fournisseur d'inférence change (Replicate maintenu en secours, modèle permissif).
3. Sortie standardisée **24 kHz**, conforme au manifest TTS (D10).

**Alternatives écartées**
XTTS-v2 / `xTTS-v2-wolof` en production (CPML NC) · F5-TTS checkpoints (CC-BY-NC, l'option « from scratch » est reportée car plus longue à mettre en œuvre) · Piper (MIT mais qualité jugée insuffisante pour un MOS cible ≥ 3,5).

**Conséquences**
Budget GPU maison (pas de coût Replicate en régime permanent) ; charge d'exploitation (patchs, VRAM) à notre charge ; validation native obligatoire des 20 échantillons/variante prévue aux specs avant toute mise en production.

---

### D8 — Couche tonale : composant obligatoire entre G2P et modèle acoustique — VALIDÉ (principe)

**Contexte**
Les 3 langues sont **tonales** (lingala et bambara : tons haut/bas ; bambara : ton montant composé ; wolof : hauteur — statut exact à confirmer, WALS le classe non tonal). L'orthographe courante **ne porte pas le ton**. Les 3 modèles SOTA testés en 2026 sur une langue tonale (arXiv:2607.04515, Efik) produisent un accent étranger ou des erreurs de ton malgré 3 h de données — seule la combinaison « +données +modélisation tonale » améliore le MOS. Les G2P existants **suppriment** le ton (africa-g2p retire les accents en IPA ; les FST LanguageNet n'en émettent aucun).

**Décision**
Composant logique **D8**, obligatoire dans le pipeline, qui prolonge le G2P segmental :

- **Entrée** : texte cible.
- **Sortie** : `{"graphemes", "phonemes", "tones", "syllables", "lang"}` (voir D10).
- **Deux consommateurs** : (a) **modèle acoustique** — les tons conditionnent la mélodie du TTS ; (b) **affichage app** — la prononciation écrite de l'app porte les marques tonales (`dǎn.ki.li`), pédagogiquement attendu.
- **Approche hybride** : lexique toné → règles morpho-tonales → petit modèle neural (char → phonèmes+tons) pour les OOV.
- **Sandhi tonal** (liaison bambara, tons verbaux lingala) : géré **au niveau phrase**, en entrée du modèle acoustique, pas dans le lexique mot-à-mot.
- **Sources d'amorçage** : Bambara = **An ka taa** (dictionnaire 100 % toné) + corpus `corbama-net-tonal` ; Lingala = règles issues des grammaires (2 tons + descendant, tons des morphèmes verbaux, paires minimales `mutu/mutú`, `kokoma/kokóma`) ; Wolof = liste UCLA 1981 (tons + IPA).
- **Statut MVP** : sans cette couche l'app fonctionne (audio plat, prononciation sans tons) ; **avec** elle seule l'objectif MOS ≥ 3,5 est atteignable. Insertion prévue en **Phase 1.5**, pas au MVP.

**Alternatives écartées**
Tons appris implicitement par le seul TTS (écarté : c'est précisément ce qui échoue en bas ressources selon l'état de l'art) · TTS alimenté directement en texte brut sans G2P (écarté : perd l'affichage de prononciation et rend l'audio non corrigeable).

**Conséquences**
Un lexique toné à construire par langue (effort linguistique, pas GPU) ; métrique d'éval dédiée (accuracy tonale, cf. D12) ; dépendance entre la qualité du TTS et la qualité de ce lexique.

---

### D9 — G2P segmental : africa-g2p, FST LanguageNet en baseline — VALIDÉ

**Contexte**
Test effectué le 08/10/2026 sur les 3 langues.

**Décision**
`africa-g2p` (0.3.2, **MIT**, pip, sans dépendance) est le G2P segmental de référence : multigraphes (`ny`, `mb`, `kp`) conservés comme unités, ce qui convient au TTS. Les FST Phonetisaurus LanguageNet (`wolof`, `bambara`, **pas de lingala**) sont conservés **uniquement comme baseline de référence** — modèles de 2,7/4,9 Ko, sorties sans ton, `cogona → o ɡ o n a` en bambara. `espeak-ng` est **exclu** (aucune voix lingala/wolof/bambara).

**Alternatives écartées**
espeak-ng (pas de couverture) · FST LanguageNet comme composant de production (pas de lingala, aucun ton, qualité bambara insuffisante).

**Conséquences**
Le champ `tones` des fiches `languages/*.json` d'africa-g2p (393 langues sur 750, dont lingala) sert de **documentation des conventions d'écriture du ton**, consommée par D8 — ce n'est pas un prédicteur.

---

### D10 — Formats de données : trois manifests JSONL — VALIDÉ

**Contexte**
Trois briques entraînées séparément, une éval commune.

**Décision**

| Jeu | Schéma |
|---|---|
| NMT | `{"src", "tgt", "lang_src", "lang_tgt", "domain", "score"}` |
| TTS | `{"audio", "text", "lang", "speaker", "duration", "sr": 24000}` |
| G2P (sortie D8) | `{"graphemes", "phonemes", "tones", "syllables", "lang"}` |

Test NMT : **FLORES-200 devtest** (`lin_Latn`, `wol_Latn`, `bam_Latn`). Les 3 jeux sont versionnés comme **ClearML Datasets** (D12).

**Conséquences**
Contrat stable entre l'entraînement et l'app ; toute extension de schéma (ex. `region`, cf. D14) exige une nouvelle version du manifest.

---

### D11 — Prétraitement obligatoire en amont des entraînements — VALIDÉ

**Contexte**
WAXAL est brut (16 kHz, variations de niveau, bruit) et les jeux NT sont hétérogènes.

**Décision**
Chaîne de préparation bloquante avant tout entraînement :
- **Texte** : normalisation NFC · chiffres et ponctuation · identification de langue · dédoublonnage MinHash · filtre de parallélisme (ratio de longueur + embeddings) · détection de domaine.
- **Audio** : résample 24 kHz · normalisation LUFS · VAD · filtre DNSMOS > 3,0 · rejet des durées < 1,5 s et > 10 s · rejet des débits > 4 mots/s · vérification ASR.
- **Performances** : cache Arrow, bucketing par longueur, pré-calcul des mel-spectrogrammes, bf16, accumulation de gradients.

**Conséquences**
Aucun entraînement ne part d'un jeu brut ; le filtre de qualité audio sert aussi de filet sur les données BibleTTS/WAXAL ; temps de préparation ajouté à la Phase 1.

---

### D12 — Supervision ClearML — VALIDÉ (hébergement à confirmer)

**Contexte**
Entraînements menés sur la RTX 5090 du poste de l'école, suivis à distance.

**Décision**
Agent ClearML installé sur la machine d'entraînement ; dans chaque script : `Task.init()`, `Task.connect(cfg)`, `logger.report_scalar()`. Jeux de données (D10) publiés via **ClearML Dataset**. Métriques suivies : loss NMT, BLEU/chrF/COMET (FLORES), MOS estimé et DNSMOS (TTS), **accuracy tonale et PER (D8)**. Chaîne de préparation modélisée en **Pipeline ClearML** (`préparation → entraînement → évaluation`).
Hébergement : **`app.clearml.com` (gratuit) recommandé**, bascule locale possible en changeant l'URL de `~/clearml.conf` — **choix de l'utilisateur non encore rendu**. Sortante HTTPS 443 uniquement (compatible firewalls).

**Conséquences**
Historique d'expériences exploitable pour comparer modèles et lexiques ; une seule dépendance réseau sortante ; coût zéro tant que l'offre gratuite suffit.

---

### D13 — Environnement d'entraînement : Blackwell `sm_120` — VALIDÉ

**Contexte**
La RTX 5090 est une Blackwell : support matériel `sm_120`.

**Décision**
PyTorch **≥ 2.7 (wheels cu128)** / **CUDA 12.8+** obligatoire. Validation en tête de Phase 1 : compilation des opérateurs audio (torchaudio, mel-spectrogramme) et chargement du modèle TTS de POC. Aucun environnement CUDA ancien ne doit être provisionné.

**Conséquences**
Bloquant potentiel sur les dépendances audio legacy (résolution = repli sur une version compatible ou rebuild from scratch, cf. D7) ; à figer dans le `pyproject.toml` + image Docker d'entraînement.

---

### D14 — Dimension régionale et culturelle : donnée à collecter — PROPOSÉ

**Contexte**
Les specs prévoient des contenus régionaux (Dakar, Kinshasa, Bamako) et l'app s'appuie sur des variantes. Or **aucune source existante ne porte l'information de région** : WAXAL collecte âge, genre, langue, environnement, locuteur — pas la région (et sa limitation §5.1 note l'absence de variation dialectale) ; BibleTTS = 1 seul narrateur par langue ; WAXAL ne fournit aucun `wol_tts` exploitable.

**Décision**
Les contenus régionaux passent par une **annotation/collection propre** : marquage `region` ajouté au manifest TTS (D10) pour toute donnée maison, et campagne de collecte dédiée (les specs prévoient déjà « 500 mots en enregistrements humains natifs »). Contact disponible : `waxal-dataset-support@google.com` pour lever le doute sur la région des locuteurs WAXAL.

**Conséquences**
Délai et coût de collecte à intégrer au planning ; tant que la collecte n'est pas faite, l'app reste en variante neutre (pas de promesse de « voix de Dakar »).

---

## 4. Risques introduits ou confirmés

| Risque | Impact | Mitigation |
|---|---|---|
| MADLAD-400 mal couvert sur `lin`/`wol`/`bam` | Traductions médiocres | Bench FLORES devtest MADLAD vs Opus-MT avant entraînement (D6) |
| Ton erroné produit un sens inversé | Audio faux, confiance cassée | Accuracy tonale suivie en ClearML (D12) + 20 échantillons natifs/variante (specs) |
| Statut tonal du wolof incertain (WALS : non tonal) | Effort D8 surévalué | Trancher avec une source linguistique avant de construire le lexique wolof |
| An ka taa / Corbama sans licence ML explicite | Blocage du lexique bambara | Vérifier licence et export bulk **avant** tout scraping ; sinon contact des auteurs (Donaldson & Fenayon) |
| Modèle permissif TTS moins bon qu'XTTS | MOS < 3,5 | Validation native avant intégration ; garde-fou humain sur le vocabulaire core (déjà en v1.0) |
| Environnement `sm_120` incompatible torchaudio | Phase 1 bloquée | Validation CUDA/PyTorch en tout premier (D13) |

---

## 5. Prochaines étapes

| # | Étape | Livrable |
|---|---|---|
| 1 | Arbitrer D6 et D7 (permissif par défaut vs garder NLLB/XTTS en POC) | Décisions passées à VALIDÉ |
| 2 | Vérifier licence + export bulk d'An ka taa et du corpus tonal bambara ; clarifier le statut tonal du wolof | Lexique bambara amorcé / décision écrite |
| 3 | Initialiser le dépôt ML (`ml/`) : 3 manifests v1 (D10), pipeline africa-g2p + squelette D8 | Repo + 1 manifest généré |
| 4 | Installer l'agent ClearML, publier une métrique test | Suivi distant opérationnel (D12) |
| 5 | Valider l'environnement `sm_120` (PyTorch ≥ 2.7 / CUDA 12.8) | Environnement d'entraînement figé (D13) |

---

*Fin de la mise à jour v1.1. Toute modification des décisions D1 à D13 ou des principes d'API doit donner lieu à une nouvelle version des registres (v1.0 + v1.1).*

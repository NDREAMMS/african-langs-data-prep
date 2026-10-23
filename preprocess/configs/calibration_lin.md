# Calibration — Lingala (lin) — étape 0 (§3)

> **STATUT : NON FAIT.** Ce fichier est un gabarit. Tant qu'il n'est pas rempli et que les
> seuils de `preprocess.yaml` ne portent pas `provenance: calibrage_lin_<date>`, tout manifest
> `lin` est marqué `publishable: false` (principe §2.2).

## Protocole

1. **Échantillon texte** : 300 lignes tirées au hasard dans les sources parallèles, annotées :
   `lang_id_ok`, `pair_ok`, `in_alphabet`.
2. **Échantillon audio** : 100 clips/source annotés : `quality_ok`, `text_match_ok`.
   Sources `lin` : `bibletts` (EZR, 48 kHz studio), `waxal` (16 kHz).
3. **Choix des seuils** : viser ≥ 95 % de précision sur les rejets (sauf A9 : optimiser la
   détection des mauvais appariements).
4. **Vérification de couverture des outils** :
   - `fasttext lid.176` sur `lin` : présence/rappel réels (souvent absent → repli cld3/classifieur).
   - `MMS-ASR` : WER de référence `lin` sur l'échantillon A9.
   - `SONAR`/`LaBSE` : distribution des cosinus sur paires justes/fausses FR→lin.
   - `DNSMOS` : distribution sur les 100 clips `lin` (le 3,0 vient de la littérature, pas de nos données).
5. **Conservation** : chaque seuil écrit avec `source: calibrage_lin_<date>` ; aucun `default`.

## Résultats (à remplir)

| Filtre | Valeur retenue | Précision rejets | Source |
|---|---|---|---|
| T4_longueur | — | — | — |
| T5_ratio | — | — | — |
| T6_langid | — | — | — |
| T7_alphabet | — | — | — |
| T8_minhash | — | — | — |
| T9_cosine | — | — | — |
| A5_durée | — | — | — |
| A6_débit | — | — | — |
| A7_dnsmos | — | — | — |
| A8_snr | — | — | — |
| A9_wer | — | — | — |

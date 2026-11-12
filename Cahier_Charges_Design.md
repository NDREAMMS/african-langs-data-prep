# Cahier des charges design — Apprentissage des langues africaines

> Wolof · Lingala · Bambara — Maquette Figma

---

## 1. Charte graphique

### 1.1 Palette de couleurs

| Rôle | Nom | Hex | Usage |
|------|-----|-----|-------|
| **Primaire** | Terracotta | `#E76F51` | Boutons principaux, liens, accent fort |
| **Secondaire** | Vert savane | `#2D6A4F` | Barres de progression, validation, succès |
| **Accent** | Or | `#F4A261` | Badges, streak, XP, éléments gamifiés |
| **Arrière-plan** | Blanc cassé | `#FEFAE0` | Fond d'écran principal (clair) |
| **Texte principal** | Noir profond | `#1A1A2E` | Titres et corps de texte |
| **Texte secondaire** | Gris chaud | `#6B6B6B` | Sous-titres, labels, infos |
| **Erreur** | Rouge doux | `#E63946` | Erreurs, mauvaises réponses |

**Mode sombre** (à prévoir dès la maquette) :

| Rôle | Hex | Usage |
|------|-----|-------|
| Fond principal | `#1A1A2E` | Arrière-plan sombre |
| Surface/carte | `#2A2A3E` | Cartes et conteneurs |
| Texte principal | `#FEFAE0` | Texte sur fond sombre |
| Texte secondaire | `#A0A0B0` | Sous-titres sombre |

### 1.2 Typographie

| Style | Police | Graisse | Taille (mobile) | Usage |
|-------|--------|---------|-----------------|-------|
| **Titre h1** | Poppins | Bold | 28-32px | Titres d'écran |
| **Titre h2** | Poppins | Bold | 22-24px | Titres de section |
| **Titre h3** | Poppins | Semi-Bold | 18-20px | Titres de carte |
| **Corps** | Nunito | Regular | 16px | Texte courant |
| **Corps petit** | Nunito | Regular | 14px | Labels, infos |
| **Bouton** | Nunito | Bold | 16-18px | Boutons |
| **Badge/XP** | Nunito | Extra-Bold | 12-14px | Badges, compteurs |

**Multi-format :** Multiplier les tailles par 1.1 pour tablette (ex: h1 = 32-36px).

### 1.3 Arrondis & espacements

- **Arrondis cards** : 20-24px
- **Arrondis boutons** : 24px (pilules)
- **Arrondis inputs/champs** : 16px
- **Arrondis avatars/badges** : 50% (cercle parfait)
- **Gouttière (padding horizontal)** : 20px mobile, 32px tablette
- **Espacement vertical entre sections** : 24px
- **Espacement entre items** : 12-16px

### 1.4 Ombres (clair)

- **Ombre légère** : `0px 2px 8px rgba(26, 26, 46, 0.08)` — cartes
- **Ombre moyenne** : `0px 4px 16px rgba(26, 26, 46, 0.12)` — modales, boutons flottants

**Mode sombre** : ombres noires plus marquées : `0px 4px 16px rgba(0,0,0,0.4)`

### 1.5 Icônes

- **Librairie** : Phosphor Icons (MIT) — style "Duotone" ou "Regular"
- **Taille standard** : 24px dans les boutons, 28-32px dans la tab bar

---

## 2. Architecture de navigation

### 2.1 Structure

```
Tab Bar (bas)
├── 🏠 Accueil (Home) — Tableau de bord, streak, progression
├── 📚 Leçons (Lessons) — Arbre/chemin des leçons
├── 🏆 Classement (Leaderboard) — Optionnel, à confirmer
└── 👤 Profil (Profile) — Paramètres, stats, préférences

Stack (piles)
├── Onboarding → Test placement → Home
├── Carte leçon → Exercice (QCM / Traduction / Association)
└── Toute page peut être fermée par "←" ou "✕"
```

### 2.2 Écrans identifiés (MVP)

| # | Écran | Type | Priorité |
|---|-------|------|----------|
| 1 | **Onboarding** — sélection langue + niveau + objectif | Stack (entrée) | Haute |
| 2 | **Test de placement** — 5-20 questions | Stack | Haute |
| 3 | **Home / Tableau de bord** — streak, progression, XP | Tab | Haute |
| 4 | **Exercice QCM** — audio + 4 choix | Stack (leçon) | Haute |
| 5 | **Exercice Traduction libre** — input texte | Stack (leçon) | Haute |
| 6 | Chemin de leçons (arbre) | Tab | Moyenne |
| 7 | Profil | Tab | Basse |

---

## 3. Spécifications des écrans

### 3.1 Écran d'onboarding (flux en 3-4 étapes)

**Objectif :** Nouvel utilisateur → configuré et prêt à apprendre en < 1 min.

#### Étape 1 — Bienvenue + choix langue
```
┌─────────────────────────────┐
│                             │
│     [Illustration héros]    │  ← mascotte placeholder
│                             │
│   "Prêt à apprendre une     │
│    nouvelle langue ?"       │  ← Poppins Bold, h1
│                             │
│   [Sélection langue]        │  ← 3 cartes cliquables :
│   ┌──────┐ ┌──────┐ ┌──────┐│     Wolof / Lingala / Bambara
│   │ WOLOF│ │LINGALA│ │BAMBAR││     Carte sélectionnée = bordure
│   │      │ │       │ │      ││     Terracotta + fond légèrement teinté
│   └──────┘ └──────┘ └──────┘│
│                             │
│         [Continuer]         │  ← Bouton Terracotta, plein, arrondi 24px
│                             │
└─────────────────────────────┘
```

**Comportement :**
- Langue non sélectionnée → bouton grisé
- Après sélection → bouton s'active (animation de remplissage)
- Swipe ou bouton → étape suivante

#### Étape 2 — Auto-évaluation
```
┌─────────────────────────────┐
│                             │
│   "Quel est ton niveau      │
│    en [Langue] ?"           │  ← h1
│                             │
│   ○ Débutant complet        │  ← 3 options radio stylisées en cartes
│   ○ Quelques notions        │     Carte sélectionnée = fond Vert savane
│   ○ Bases solides           │     + icône coche
│                             │
│   [Petit libellé info]      │  ex: "Pas d'inquiétude, on commence par
│                             │      le test de placement !"
│                             │
│         [Continuer]         │
└─────────────────────────────┘
```

#### Étape 3 — Objectif quotidien
```
┌─────────────────────────────┐
│                             │
│   "Combien de minutes       │
│    par jour ?"              │  ← h1
│                             │
│   ┌───────────────────────┐ │
│   │   5 min  │  10 min  │15│ │  ← 3 boutons sélecteurs côte à côte
│   │   Débutant│Recommandé│Exp│ │     Mini 5 = sélectionné par défaut
│   └───────────────────────┘ │     10 = recommandé (badge "Recommandé")
│                             │
│         [Continuer]         │
└─────────────────────────────┘
```

#### Étape 4 — Prénom + lancement
```
┌─────────────────────────────┐
│                             │
│   "Pour finir, comment      │
│    t'appelles-tu ?"         │  ← h1
│                             │
│   ┌─────────────────────┐   │
│   │  [Prénom]            │   │  ← Input arrondi 16px, icône utilisateur
│   └─────────────────────┘   │
│                             │
│   ⚡ "XX personnes apprennent│  ← micro copy sociale
│      le [Langue]"           │
│                             │
│      [Commencer !]          │  ← Bouton Vert savane
│                             │      → Redirige vers test de placement
└─────────────────────────────┘
```

**Options de navigation :** Points en haut (1/4, 2/4, 3/4, 4/4) avec swipe horizontal possible.

---

### 3.2 Test de placement

**Objectif :** Évaluer le niveau réel → placement automatique dans le curriculum.

#### Écran de début
```
┌─────────────────────────────┐
│                             │
│   "Test de placement"       │  ← h1
│                             │
│   [Illustration type quiz]  │
│                             │
│   "5 à 20 questions selon   │
│    ton niveau déclaré.      │
│    Pas de stress !"         │
│                             │
│         [Commencer]         │
└─────────────────────────────┘
```

#### Question type (QCM)
```
┌─────────────────────────────┐
│  ← Quitter                   │  ← Top bar avec bouton retour
│                              │
│   ┌──────────────────────┐  │
│   │ ▶ Écouter             │  │  ← Bouton audio (Terracotta, cercle)
│   │                        │  │     Lit le mot/phrase en VO
│   └──────────────────────┘  │
│                              │
│   "Que signifie ce mot ?"   │  ← h2
│                              │
│   ┌──────────────────────┐  │
│   │ ○ Bonjour              │  │
│   ├──────────────────────┤  │
│   │ ○ Merci               │  │  4 cartes-options
│   ├──────────────────────┤  │     Arrondies 20px
│   │ ● Au revoir ← sélection│  │     Sélection = fond + bordure Terracotta
│   ├──────────────────────┤  │
│   │ ○ S'il vous plaît     │  │
│   └──────────────────────┘  │
│                              │
│   2 / 12             [Suivant]│
│                              │
└─────────────────────────────┘
```

**Règles :**
- 5 questions si "Débutant", 12 si "Quelques notions", 20 si "Bases solides"
- Questions adaptatives : bonne réponse → question plus dure
- Progression visible : "3 / 12" + barre fine en haut
- Après dernière question : écran de résultat avec niveau assigné

#### Écran de résultat
```
┌─────────────────────────────┐
│                             │
│   "Ton niveau :"            │
│                             │
│   ┌──────────────────────┐  │
│   │                      │  │
│   │   🌱 Débutant        │  │  ← Badge niveau (grand, centré)
│   │                      │  │     Couleur par niveau
│   └──────────────────────┘  │
│                             │
│   "Tu commences à l'unité   │
│    1 — Les salutations"     │
│                             │
│   [Barre de progression]    │  ← Vue globale du chemin
│   ●●○○○○○○○○                │     Points = unités
│                             │
│      [Commencer l'app]      │  → Redirige vers Home
└─────────────────────────────┘
```

---

### 3.3 Tableau de bord (Home)

**Objectif :** Donner envie d'apprendre tous les jours. Vue claire de la progression.

```
┌─────────────────────────────┐
│   👋 Salut, [Prénom]        │  ← Top bar
│                              │
│   🔥 7 jours     ⭐ 340 XP  │  ← Streak (flamme) + XP total
│                              │
│   [Barre progression]        │  ← Section "Aujourd'hui"
│   ●●●○○○○○○○○○               │     Barre de progression journalière
│   3 / 10 min aujourd'hui     │     (ex: si objectif 10 min)
│                              │
│   📚 À réviser : 12 items   │  ← Bouton CTA principal
│   ┌────────────────────────┐ │
│   │   [Continuer]          │ │  ← Vert savane, grand bouton
│   │   Reprends ta leçon    │ │
│   └────────────────────────┘ │
│                              │
│   ─── Prochains badges ───  │
│   ┌──┐ ┌──┐ ┌──┐           │
│   │🔒│ │🔒│ │🔥│           │  ← Badges à débloquer (3 miniatures)
│   │ 7j│ │30j│ │100j│        │     Verrouillé = grisé, débloqué = Or
│   └──┘ └──┘ └──┘           │
│                              │
│   [Tab Bar]                  │
│  🏠 📚 🏆 👤               │
└─────────────────────────────┘
```

**Éléments clés :**
- **CTA principal** "Continuer" : toujours visible, toujours le même emplacement
- **Section "À réviser"** : nombre d'items qui arrivent à échéance aujourd'hui
- **Badges** : 3 prochains badges à débloquer (streak 7j, 30j, 100j)
- **Ton général** : encourageant, jamais culpabilisant
- Si streak brisée : message doux "Pas grave, on recommence !" plutôt qu'un reproche

---

### 3.4 Exercice QCM (audio + 4 choix)

**Objectif :** Reconnaissance auditive et vocabulaire.

#### Écran de l'exercice
```
┌─────────────────────────────┐
│  ← ✕ Quitter                │  ← Top bar : retour = confirmer abandon
│   ──────────────────         │     Barre fine de progression dans la leçon
│                              │
│   Écoute et choisis         │  ← Instruction (Nunito, 16px, gris)
│                              │
│   ┌──────────────────────┐  │
│   │   ▶                  │  │  ← Gros bouton audio (cercle 64px, Terracotta)
│   │   Réécouter           │  │     Rougeoiement au clic
│   └──────────────────────┘  │
│                              │
│   ┌────────────────────────┐│
│   │   ○  [Option A]        ││  4 options, fond blanc cassé
│   ├────────────────────────┤│     Bordure 1px gris clair
│   │   ○  [Option B]        ││     Clic → bordure Terracotta + fond teinté
│   ├────────────────────────┤│     Arrondis 20px
│   │   ○  [Option C]        ││
│   ├────────────────────────┤│
│   │   ○  [Option D]        ││
│   └────────────────────────┘│
│                              │
│           [Valider]          │  ← Bouton désactivé tant qu'aucune sélection
│                              │
│   ● ● ○ ● ●   4 / 12        │  ← Progression : points pour les items de la leçon
└─────────────────────────────┘
```

#### Feedback bonne réponse
```
│                              │
│   ┌────────────────────────┐│
│   │ ✅ "Sawa !" ★ +10 XP  ││  ← Fond vert savane
│   │   Bonne réponse !      ││     Mot natif validant selon la langue
│   │   [Mot] = [Traduction] ││     Animation : coche + particules ✨
│   └────────────────────────┘│
│                              │
│           [Continuer]        │  ← Auto-avance après 1.5s ou clic
```

#### Feedback mauvaise réponse
```
│                              │
│   ┌────────────────────────┐│
│   │ ❌ "Presque !"         ││  ← Fond rouge doux
│   │   La bonne réponse :   ││     Montrer la bonne réponse
│   │   [Option correcte]    ││
│   └────────────────────────┘│
│                              │
│           [Continuer]        │
```

---

### 3.5 Exercice Traduction libre

**Objectif :** Production écrite avec tolérance aux fautes de frappe (Levenshtein).

#### Écran de l'exercice
```
┌─────────────────────────────┐
│  ← ✕ Quitter                │
│   ──────────────────         │
│                              │
│   Traduis cette phrase      │  ← Instruction
│                              │
│   ┌──────────────────────┐  │
│   │   ▶  "Bonjour"        │  │  ← Audio + phrase source en français
│   └──────────────────────┘  │
│                              │
│   ┌──────────────────────┐  │
│   │                       │  │  ← Input texte, arrondi 16px
│   │   [Écris ta réponse]  │  │     Placeholder centré
│   │                       │  │     Icône micro ? (pour Phase 2)
│   └──────────────────────┘  │
│                              │
│   ┌────────────────────────┐│
│   │   Astuce               ││  ← Bouton indice (optionnel)
│   └────────────────────────┘│     Révèle 1 lettre ou 1 mot
│                              │
│           [Valider]          │
│                              │
│   ● ● ○ ● ●   4 / 12        │
└─────────────────────────────┘
```

#### Feedback (score Levenshtein)
```
│                              │
│   ┌────────────────────────┐│
│   │ ✅ Exact ! ★ +10 XP   ││  Si distance < 10% de la longueur
│   │                        ││
│   │ ❌ "Presque !"         ││  Si distance 10-30%
│   │   Tu as écrit : [...]  ││     Montrer la différence
│   │   Attendu : [...]      ││
│   │                        ││
│   │ ❌ "Pas tout à fait"   ││  Si distance > 30%
│   │   [Bonne réponse]      ││
│   └────────────────────────┘│
│                              │
│           [Continuer]        │
```

---

## 4. Composants récurrents (Design System > Figma Components)

### 4.1 Tab Bar
```
┌─────────────────────────────────────────────┐
│  🏠          📚          🏆          👤     │
│  Accueil     Leçons     Classement    Profil │
│  [●]         ○          ○            ○      │  ← Onglet actif = Terracotta
│                                              │     Onglet inactif = Gris
└─────────────────────────────────────────────┘
```
- Hauteur : 64px
- Fond : Blanc (clair) / `#2A2A3E` (sombre)
- Top border : 1px gris clair

### 4.2 Bouton principal (CTA)
- Fond : Terracotta
- Texte : Blanc, Nunito Bold 18px
- Hauteur : 56px
- Arrondi : 28px (pilule)
- États : Normal / Pressé (assombrir 10%) / Désactivé (opacité 50%)
- Pleine largeur avec padding horizontal 20px

### 4.3 Carte d'option (QCM, sélection)
- Fond : Blanc cassé (clair) / `#2A2A3E` (sombre)
- Bordure : 1px `#E0E0E0` (clair) / `#3A3A4E` (sombre)
- Arrondi : 20px
- Padding : 16px
- États : Normal / Sélectionné (bordure Terracotta + fond teinté) / Correct (Vert savane) / Incorrect (Rouge doux)

### 4.4 Barre de progression
- Hauteur : 6px
- Arrondi : 3px
- Fond : Gris clair `#E0E0E0`
- Remplissage : Vert savane
- Animation : fluide (0.3s ease)

### 4.5 Badge/Compteur
- Arrondi : 50% (cercle) ou pilule
- Fond : Or `#F4A261` (pour XP), Vert savane (pour streak), Gris (pour verrouillé)
- Texte : Blanc, Nunito Extra-Bold, 12-14px

### 4.6 Feedback overlay (bonne/mauvaise réponse)
- Type : Banner slide-in depuis le bas
- Hauteur : ~80px
- Durée : 1.5s avant auto-avance
- Animation : slide up (0.3s) + slide down (0.3s)
- Couleurs : Vert savane (✔) / Rouge doux (✘)

### 4.7 Audio button
- Taille : 64px (grand, exercice) / 40px (petit, carte)
- Forme : Cercle
- Fond : Terracotta
- Icône : ▶ (play) / 🔄 (replay après 1er clic)
- Animation : pulse au clic + bague d'ondulation

---

## 5. Layout par format

### 5.1 Mobile portrait (375-430px width)
- Grille : 1 colonne
- Gouttière : 20px
- Contenu : centré, max-width 400px dans les conteneurs

### 5.2 Mobile paysage (optionnel pour MVP)
- Adapter : QCM sur 2 colonnes, barre d'outils compacte

### 5.3 Tablette (768-1024px)
- Grille : possibilité de split (ex: leçon à gauche, exercice à droite)
- Gouttière : 32px
- Tailles de police : ×1.1
- Composants : plus aérés, padding majoré de 20%

---

## 6. Animations & micro-interactions

| Élément | Animation | Durée | Easing |
|---------|-----------|-------|--------|
| Changement d'écran | Slide horizontal (stack), fade (tab) | 0.3s | ease-in-out |
| Réponse correcte | Coche + scale(1.05) + particules | 0.5s | spring |
| Réponse incorrecte | Shake horizontal + rouge flash | 0.4s | ease |
| Bouton audio | Pulse + ring expansion | 0.6s | ease-out |
| Barre progression | Fill horizontal | 0.6s | ease |
| Carte sélection | Border color transition | 0.2s | ease |
| Tab switch | Fade + scale badge | 0.2s | ease |
| Streak counter | Number increment + flame bounce | 0.3s | spring |

---

## 7. Écrans mode sombre (principes)

Pour chaque écran clair :
- `#FEFAE0` → `#1A1A2E`
- `#FFFFFF` (cartes) → `#2A2A3E`
- `#1A1A2E` (texte) → `#FEFAE0`
- `#6B6B6B` → `#A0A0B0`
- Ombre → plus marquée, teinte bleutée
- Terracotta, Vert savane, Or : conserver les mêmes hex (saturation suffisante)
- Illustrations : fond transparent, pas d'arrière-plan blanc

---

## 8. Placeholder mascotte

> 🐘 **Mascotte :** [À dessiner par le créateur]
>
> Emplacements réservés dans la maquette :
> - Écran d'onboarding (étape 1) — illustration héros, centré
> - Home — petit avatar dans la top bar (optionnel)
> - Écran de résultat / félicitations
> - Écran de streak brisée (message mascotte triste)
>
> Format : SVG ou PNG transparent, style flat design "Friendly African"

---

## 9. Hiérarchie de création Figma

1. **Page "Design System"** : couleurs, typos, composants (bouton, carte, tab bar, barre progression, audio button)
2. **Page "Onboarding"** : 4 écrans (frame iPhone + frame Android + frame tablette)
3. **Page "Test placement"** : écran début + question + résultat
4. **Page "Home"** : tableau de bord
5. **Page "Exercices"** : QCM + Traduction (avec états feedback)
6. **Page "Dark mode"** : doublon des pages précédentes en thème sombre

---

*Document généré le 13/07/2026 — à utiliser comme référence pour la maquette Figma.*

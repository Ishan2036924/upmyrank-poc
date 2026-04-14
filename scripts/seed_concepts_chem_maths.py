"""
Seed Chemistry (~80) and Maths (~80) concepts into the concepts table.

Covers all major JEE Class 11 + 12 chapters for both subjects.
Idempotent: ON CONFLICT DO NOTHING — safe to re-run.

ID format: {subject_short}.{class}.{snake_case_name}
  chemistry.11.atomic_structure
  maths.11.sets_basics

Subject values must match SUPPORTED_SUBJECTS in prompts.py:
  "Physics", "Chemistry", "Maths"

Usage:
  cd /path/to/upmyrank
  PYTHONPATH="" PYTHONHOME="" /opt/miniconda3/bin/python3.11 scripts/seed_concepts_chem_maths.py
"""
from __future__ import annotations

import os
import sys
import urllib.parse as _up

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
import psycopg2.extras

from app.config import settings

# ── DB connection ──────────────────────────────────────────────────────────────
dsn = settings.database_url
_parsed = _up.urlparse(dsn)
conn = psycopg2.connect(
    host=_parsed.hostname,
    port=_parsed.port or 5432,
    dbname=_parsed.path.lstrip("/"),
    user=_parsed.username,
    password=_up.unquote(_parsed.password or ""),
    sslmode="require",
)
conn.autocommit = False
cur = conn.cursor()

# ── Chemistry concepts ─────────────────────────────────────────────────────────
# (id, subject, topic, subtopic, description, prerequisite_ids)

CHEMISTRY_CONCEPTS = [
    # ── Class 11 ─────────────────────────────────────────────────────────────
    # Some Basic Concepts
    ("chemistry.11.mole_concept",       "Chemistry", "Some Basic Concepts of Chemistry",
     "Mole Concept and Molar Mass",
     "One mole = 6.022×10²³ particles (Avogadro's number). Molar mass = mass of one mole in grams.",
     []),
    ("chemistry.11.stoichiometry",      "Chemistry", "Some Basic Concepts of Chemistry",
     "Stoichiometry and Limiting Reagent",
     "Stoichiometry relates masses of reactants and products via balanced equations. Limiting reagent determines yield.",
     ["chemistry.11.mole_concept"]),
    ("chemistry.11.concentration",      "Chemistry", "Some Basic Concepts of Chemistry",
     "Concentration Terms (Molarity, Molality, Mole Fraction)",
     "Molarity (M) = moles of solute / litre of solution. Molality (m) = moles of solute / kg of solvent.",
     ["chemistry.11.mole_concept"]),

    # Atomic Structure
    ("chemistry.11.atomic_structure",   "Chemistry", "Atomic Structure",
     "Bohr's Model and Atomic Spectra",
     "Bohr postulated quantised electron orbits. Energy = -13.6/n² eV. Emission spectra arise from electron transitions.",
     []),
    ("chemistry.11.quantum_numbers",    "Chemistry", "Atomic Structure",
     "Quantum Numbers and Electron Configuration",
     "Four quantum numbers (n, l, m_l, m_s) fully describe an electron. Aufbau, Pauli, Hund rules govern filling.",
     ["chemistry.11.atomic_structure"]),
    ("chemistry.11.shapes_orbitals",    "Chemistry", "Atomic Structure",
     "Shapes of Atomic Orbitals (s, p, d, f)",
     "s orbitals are spherical; p orbitals have two lobes; d orbitals have four lobes or toroidal shapes.",
     ["chemistry.11.quantum_numbers"]),

    # Chemical Bonding
    ("chemistry.11.ionic_bonding",      "Chemistry", "Chemical Bonding and Molecular Structure",
     "Ionic Bonding and Lattice Energy",
     "Ionic bonds form via electron transfer. Lattice energy measures stability; Born-Haber cycle calculates it.",
     []),
    ("chemistry.11.covalent_bonding",   "Chemistry", "Chemical Bonding and Molecular Structure",
     "Covalent Bonding and Lewis Structures",
     "Covalent bonds form by electron sharing. Lewis dot structures show bonding and lone pairs.",
     []),
    ("chemistry.11.vsepr",              "Chemistry", "Chemical Bonding and Molecular Structure",
     "VSEPR Theory and Molecular Geometry",
     "VSEPR predicts geometry from electron pair repulsions: linear, trigonal planar, tetrahedral, etc.",
     ["chemistry.11.covalent_bonding"]),
    ("chemistry.11.hybridisation",      "Chemistry", "Chemical Bonding and Molecular Structure",
     "Hybridisation (sp, sp2, sp3, sp3d)",
     "Hybridisation mixes atomic orbitals to form equivalent hybrid orbitals explaining molecular geometry.",
     ["chemistry.11.covalent_bonding"]),
    ("chemistry.11.molecular_orbital",  "Chemistry", "Chemical Bonding and Molecular Structure",
     "Molecular Orbital Theory",
     "MO theory: atomic orbitals combine into bonding/antibonding MOs. Bond order = (bonding - antibonding) / 2.",
     ["chemistry.11.quantum_numbers"]),
    ("chemistry.11.hydrogen_bonding",   "Chemistry", "Chemical Bonding and Molecular Structure",
     "Intermolecular Forces and Hydrogen Bonding",
     "H-bonds form between H (bonded to F, O, N) and lone pairs on F, O, N. Strongest intermolecular force.",
     ["chemistry.11.covalent_bonding"]),

    # Thermodynamics (Chem 11)
    ("chemistry.11.enthalpy",           "Chemistry", "Thermodynamics",
     "Enthalpy and Hess's Law",
     "ΔH = enthalpy change. Hess's Law: ΔH is path-independent; sum of steps equals overall ΔH.",
     []),
    ("chemistry.11.entropy_gibbs",      "Chemistry", "Thermodynamics",
     "Entropy, Gibbs Free Energy, and Spontaneity",
     "ΔG = ΔH − TΔS. Spontaneous if ΔG < 0. Entropy measures disorder.",
     ["chemistry.11.enthalpy"]),
    ("chemistry.11.bond_enthalpies",    "Chemistry", "Thermodynamics",
     "Bond Enthalpies and Combustion",
     "Bond dissociation enthalpy = energy to break one mole of bond in gaseous state. ΔH_rxn = Σ(bonds broken) − Σ(bonds formed).",
     ["chemistry.11.enthalpy"]),

    # Equilibrium (Chem 11)
    ("chemistry.11.equilibrium_basics", "Chemistry", "Equilibrium",
     "Chemical Equilibrium and Equilibrium Constant (Kc, Kp)",
     "At equilibrium, forward rate = reverse rate. Kc = [products]^n / [reactants]^m. Kp = Kc(RT)^Δn.",
     []),
    ("chemistry.11.le_chatelier",       "Chemistry", "Equilibrium",
     "Le Chatelier's Principle",
     "A system at equilibrium shifts to counteract a stress (change in concentration, pressure, temperature).",
     ["chemistry.11.equilibrium_basics"]),
    ("chemistry.11.ionic_equilibrium",  "Chemistry", "Equilibrium",
     "Ionic Equilibrium, pH, and Buffer Solutions",
     "Ka and Kb are acid/base dissociation constants. pH = −log[H⁺]. Buffer resists pH change (Henderson-Hasselbalch).",
     ["chemistry.11.equilibrium_basics"]),
    ("chemistry.11.solubility_product", "Chemistry", "Equilibrium",
     "Solubility Product (Ksp) and Common Ion Effect",
     "Ksp = [A⁺]^m[B⁻]^n for A_mB_n. Common ion effect decreases solubility of a sparingly soluble salt.",
     ["chemistry.11.ionic_equilibrium"]),

    # Redox Reactions
    ("chemistry.11.redox",              "Chemistry", "Redox Reactions",
     "Oxidation States and Balancing Redox Equations",
     "Oxidation = increase in oxidation state (electron loss). Balancing by half-reaction method in acidic/basic media.",
     []),

    # States of Matter
    ("chemistry.11.gas_laws",           "Chemistry", "States of Matter",
     "Gas Laws (Boyle's, Charles's, Avogadro's, Ideal Gas)",
     "Ideal gas: PV = nRT. Boyle: P∝1/V at constant T. Charles: V∝T at constant P.",
     []),
    ("chemistry.11.real_gases",         "Chemistry", "States of Matter",
     "Real Gases and van der Waals Equation",
     "Van der Waals: (P + an²/V²)(V − nb) = nRT. 'a' corrects for intermolecular attraction; 'b' for volume.",
     ["chemistry.11.gas_laws"]),
    ("chemistry.11.kinetic_theory",     "Chemistry", "States of Matter",
     "Kinetic Theory and Maxwell-Boltzmann Distribution",
     "KMT: gas molecules in constant random motion; avg KE ∝ T. Maxwell-Boltzmann gives speed distribution.",
     ["chemistry.11.gas_laws"]),

    # Periodic Table
    ("chemistry.11.periodic_trends",    "Chemistry", "Classification of Elements and Periodicity",
     "Periodic Trends (Atomic Radius, IE, EA, Electronegativity)",
     "Atomic radius decreases across period, increases down group. IE increases across period. EA generally increases.",
     []),
    ("chemistry.11.s_block",            "Chemistry", "Classification of Elements and Periodicity",
     "s-Block Elements (Groups 1 and 2)",
     "Alkali (Group 1) and alkaline earth (Group 2) metals. Reactivity increases down group.",
     ["chemistry.11.periodic_trends"]),

    # ── Class 12 ─────────────────────────────────────────────────────────────
    # Solid State
    ("chemistry.12.solid_state",        "Chemistry", "Solid State",
     "Crystal Systems and Unit Cell",
     "Seven crystal systems. Unit cell: primitive, body-centred, face-centred. APF = (atoms × volume_atom) / unit_cell_volume.",
     []),
    ("chemistry.12.defects",            "Chemistry", "Solid State",
     "Crystal Defects (Schottky, Frenkel) and Properties",
     "Schottky: cation+anion vacancies (decreases density). Frenkel: cation in interstitial (no density change).",
     ["chemistry.12.solid_state"]),
    ("chemistry.12.electrical_props",   "Chemistry", "Solid State",
     "Electrical and Magnetic Properties of Solids",
     "Conductors, semiconductors, insulators based on band gap. n-type/p-type doping. Ferromagnetic, diamagnetic, paramagnetic.",
     ["chemistry.12.solid_state"]),

    # Solutions
    ("chemistry.12.colligative",        "Chemistry", "Solutions",
     "Colligative Properties (VP lowering, Boiling pt elevation, Freezing pt depression, Osmosis)",
     "Colligative properties depend on number of solute particles, not nature. ΔTb = Kb·m, ΔTf = Kf·m.",
     ["chemistry.11.concentration"]),
    ("chemistry.12.raoults_law",        "Chemistry", "Solutions",
     "Raoult's Law and Ideal/Non-Ideal Solutions",
     "Raoult's Law: p_A = x_A·p°_A. Ideal solutions obey Raoult's law. Deviations (+ve or −ve) for non-ideal.",
     ["chemistry.12.colligative"]),
    ("chemistry.12.osmosis",            "Chemistry", "Solutions",
     "Osmosis, Osmotic Pressure and van't Hoff Factor",
     "π = iCRT (van't Hoff). Osmotic pressure used for molar mass determination of macromolecules.",
     ["chemistry.12.colligative"]),

    # Electrochemistry
    ("chemistry.12.electrochemistry",   "Chemistry", "Electrochemistry",
     "Electrochemical Cells, EMF and Electrode Potential",
     "Galvanic cell converts chemical to electrical energy. E°cell = E°cathode − E°anode. SHE is reference (0V).",
     ["chemistry.11.redox"]),
    ("chemistry.12.nernst_equation",    "Chemistry", "Electrochemistry",
     "Nernst Equation and Cell Potential",
     "E = E° − (RT/nF)ln(Q). At equilibrium, E = 0 and ΔG = 0. ΔG° = −nFE°.",
     ["chemistry.12.electrochemistry"]),
    ("chemistry.12.electrolysis",       "Chemistry", "Electrochemistry",
     "Electrolysis and Faraday's Laws",
     "Faraday 1st law: m ∝ Q. Faraday 2nd law: m ∝ equivalent weight. 96485 C = 1 Faraday.",
     ["chemistry.12.electrochemistry"]),
    ("chemistry.12.conductance",        "Chemistry", "Electrochemistry",
     "Conductance, Kohlrausch's Law and Electrolytic Conductance",
     "Molar conductance Λm increases with dilution. Kohlrausch's law: Λ°m = Σλ°ions.",
     ["chemistry.12.electrochemistry"]),

    # Chemical Kinetics
    ("chemistry.12.rate_law",           "Chemistry", "Chemical Kinetics",
     "Rate Law, Rate Constant and Order of Reaction",
     "Rate = k[A]^m[B]^n. Order determined experimentally. Units of k depend on overall order.",
     []),
    ("chemistry.12.integrated_rate",    "Chemistry", "Chemical Kinetics",
     "Integrated Rate Equations (Zero, First, Second Order)",
     "1st order: [A] = [A]₀e^(−kt), t½ = 0.693/k. 2nd order: 1/[A] = 1/[A]₀ + kt.",
     ["chemistry.12.rate_law"]),
    ("chemistry.12.arrhenius",          "Chemistry", "Chemical Kinetics",
     "Arrhenius Equation and Activation Energy",
     "k = Ae^(−Ea/RT). ln(k₂/k₁) = (Ea/R)(1/T₁ − 1/T₂). Catalyst lowers Ea.",
     ["chemistry.12.rate_law"]),

    # Surface Chemistry
    ("chemistry.12.adsorption",         "Chemistry", "Surface Chemistry",
     "Adsorption Isotherms (Freundlich, Langmuir)",
     "Adsorption: accumulation of substance on surface. Freundlich: x/m = kp^(1/n). Langmuir: monolayer.",
     []),
    ("chemistry.12.catalysis",          "Chemistry", "Surface Chemistry",
     "Catalysis: Homogeneous, Heterogeneous and Enzyme Catalysis",
     "Catalyst increases rate without being consumed. Heterogeneous: solid catalyst, gas reactants. Enzyme: highly specific.",
     ["chemistry.12.adsorption"]),
    ("chemistry.12.colloids",           "Chemistry", "Surface Chemistry",
     "Colloids: Types, Preparation and Properties",
     "Colloids: particle size 1–1000 nm. Tyndall effect, Brownian motion, electrophoresis. Coagulation by electrolytes.",
     []),

    # p-Block Elements
    ("chemistry.12.p_block_15",         "Chemistry", "p-Block Elements",
     "Group 15 Elements (N, P, As) — Properties and Compounds",
     "N₂: inert due to triple bond. NH₃ pyramidal (sp³). HNO₃: strong oxidising acid. P₄O₁₀ is acidic oxide.",
     []),
    ("chemistry.12.p_block_16",         "Chemistry", "p-Block Elements",
     "Group 16 Elements (O, S, Se) — Properties and Oxoacids",
     "O₂ is paramagnetic (2 unpaired e⁻). SO₂ causes acid rain. H₂SO₄: dehydrating and oxidising agent.",
     []),
    ("chemistry.12.p_block_17",         "Chemistry", "p-Block Elements",
     "Group 17 Halogens — Reactivity and Interhalogen Compounds",
     "Reactivity F > Cl > Br > I. F₂ is strongest oxidiser. Interhalogen compounds: ClF₃, IF₇.",
     []),
    ("chemistry.12.p_block_18",         "Chemistry", "p-Block Elements",
     "Group 18 Noble Gases — Xenon Compounds",
     "Noble gases: stable ns²np⁶. Xe forms XeF₂, XeF₄, XeF₆, XeO₃ with F and O.",
     []),

    # d-Block / Coordination Chemistry
    ("chemistry.12.d_block",            "Chemistry", "d and f Block Elements",
     "d-Block Transition Elements — Properties and Trends",
     "Variable oxidation states, coloured compounds, catalytic activity, magnetic properties, alloy formation.",
     []),
    ("chemistry.12.coordination",       "Chemistry", "Coordination Compounds",
     "Coordination Compounds — Nomenclature, Isomerism, Bonding",
     "Central metal + ligands form coordination sphere. Werner's theory, VBT, CFT explain bonding and colour.",
     ["chemistry.12.d_block"]),
    ("chemistry.12.cft",                "Chemistry", "Coordination Compounds",
     "Crystal Field Theory (CFT) and d-Orbital Splitting",
     "Octahedral field splits d orbitals into t₂g (−0.4Δ₀) and eₘ (+0.6Δ₀). Δ₀ determines colour and magnetism.",
     ["chemistry.12.coordination"]),

    # Organic Chemistry
    ("chemistry.12.org_basics",         "Chemistry", "Organic Chemistry — Some Basic Principles",
     "IUPAC Nomenclature and Isomerism",
     "IUPAC: identify principal chain, number to give lowest locants, name substituents alphabetically.",
     []),
    ("chemistry.12.reaction_mechanisms","Chemistry", "Organic Chemistry — Some Basic Principles",
     "Reaction Mechanisms: Inductive, Resonance, Hyperconjugation",
     "Inductive effect: electron withdrawal/donation through σ bonds. Resonance: delocalisation through π system.",
     ["chemistry.12.org_basics"]),
    ("chemistry.12.alkenes_reactions",  "Chemistry", "Hydrocarbons",
     "Alkene and Alkyne Addition Reactions",
     "Electrophilic addition: Markovnikov's rule. Hydrohalogenation, hydration, ozonolysis, catalytic hydrogenation.",
     ["chemistry.12.reaction_mechanisms"]),
    ("chemistry.12.aromatic",           "Chemistry", "Hydrocarbons",
     "Benzene and Electrophilic Aromatic Substitution",
     "EAS: halogenation, nitration, sulfonation, Friedel-Crafts. Activating vs deactivating groups; ortho/para directors.",
     ["chemistry.12.reaction_mechanisms"]),
    ("chemistry.12.haloalkanes",        "Chemistry", "Haloalkanes and Haloarenes",
     "Nucleophilic Substitution (SN1, SN2) and Elimination",
     "SN2: concerted, inversion, 2nd order. SN1: carbocation intermediate, racemisation, 1st order. E2 competes.",
     ["chemistry.12.alkenes_reactions"]),
    ("chemistry.12.alcohols_ethers",    "Chemistry", "Alcohols, Phenols and Ethers",
     "Alcohols and Phenols — Preparation and Reactions",
     "Lucas test distinguishes 1°/2°/3°. Phenol is more acidic than alcohol. Ether synthesis: Williamson.",
     ["chemistry.12.haloalkanes"]),
    ("chemistry.12.carbonyl",          "Chemistry", "Aldehydes, Ketones and Carboxylic Acids",
     "Aldehydes and Ketones — Nucleophilic Addition",
     "Nucleophilic addition to C=O. Aldol condensation, Cannizzaro reaction, iodoform test.",
     ["chemistry.12.reaction_mechanisms"]),
    ("chemistry.12.carboxylic",        "Chemistry", "Aldehydes, Ketones and Carboxylic Acids",
     "Carboxylic Acids and Derivatives",
     "Acidity: RCOOH > H₂CO₃ > phenol > ROH. Esterification, Hell-Volhard-Zelinsky, decarboxylation.",
     ["chemistry.12.carbonyl"]),
    ("chemistry.12.amines",            "Chemistry", "Amines",
     "Amines — Basicity, Preparation and Reactions",
     "Basicity: aliphatic > NH₃ > aromatic. Diazonium salts: key synthetic intermediate. Carbylamine test for 1° amines.",
     ["chemistry.12.reaction_mechanisms"]),

    # Biomolecules
    ("chemistry.12.carbohydrates",     "Chemistry", "Biomolecules",
     "Carbohydrates — Monosaccharides, Disaccharides, Polysaccharides",
     "Glucose (C₆H₁₂O₆): open chain + Haworth projection. Reducing sugars give Fehling's test. Starch vs cellulose.",
     []),
    ("chemistry.12.proteins",         "Chemistry", "Biomolecules",
     "Amino Acids, Proteins and Enzymes",
     "Amino acids: amphoteric (zwitterion). Peptide bonds form polypeptides. Primary/secondary/tertiary/quaternary structure.",
     []),
    ("chemistry.12.nucleic_acids",    "Chemistry", "Biomolecules",
     "Nucleic Acids (DNA, RNA) and Genetic Code",
     "Nucleotide = base + sugar + phosphate. DNA double helix (Watson-Crick). A-T, G-C base pairs.",
     []),

    # Polymers
    ("chemistry.12.polymers",         "Chemistry", "Polymers",
     "Addition and Condensation Polymers",
     "Addition polymers: poly(ethene), PVC, PTFE — no byproduct. Condensation: nylon, polyester, Bakelite — loss of small molecule.",
     []),

    # Environmental Chemistry
    ("chemistry.12.env_chemistry",    "Chemistry", "Environmental Chemistry",
     "Air, Water and Soil Pollution",
     "Greenhouse gases, ozone depletion (CFCs), acid rain (SO₂, NOₓ). BOD measures water quality.",
     []),
]

# ── Maths concepts ─────────────────────────────────────────────────────────────

MATHS_CONCEPTS = [
    # ── Class 11 ─────────────────────────────────────────────────────────────
    # Sets
    ("maths.11.sets_basics",           "Maths", "Sets",
     "Sets, Subsets and Set Operations",
     "Set: well-defined collection of objects. Operations: union (∪), intersection (∩), complement, difference.",
     []),
    ("maths.11.venn_diagrams",         "Maths", "Sets",
     "Venn Diagrams and Counting Principles",
     "Venn diagrams visualise set operations. |A ∪ B| = |A| + |B| − |A ∩ B| (inclusion-exclusion).",
     ["maths.11.sets_basics"]),

    # Relations and Functions
    ("maths.11.relations",             "Maths", "Relations and Functions",
     "Relations: Domain, Range and Types",
     "Relation R ⊆ A×B. Reflexive, symmetric, transitive. Equivalence relation = all three.",
     ["maths.11.sets_basics"]),
    ("maths.11.functions_basics",      "Maths", "Relations and Functions",
     "Functions: Domain, Codomain, Range, Bijection",
     "Function maps each x in domain to exactly one y. Injective (1-1), surjective (onto), bijective.",
     ["maths.11.relations"]),
    ("maths.11.composition",           "Maths", "Relations and Functions",
     "Composition of Functions and Inverse Function",
     "(f∘g)(x) = f(g(x)). Inverse f⁻¹ exists iff f is bijective. (f∘f⁻¹)(x) = x.",
     ["maths.11.functions_basics"]),

    # Trigonometry
    ("maths.11.trig_ratios",           "Maths", "Trigonometric Functions",
     "Trigonometric Ratios and Allied Angles",
     "sin, cos, tan defined on unit circle. Allied angles: sin(90°−θ)=cosθ. ASTC rule for signs.",
     []),
    ("maths.11.trig_identities",       "Maths", "Trigonometric Functions",
     "Trigonometric Identities and Formulae",
     "sin²+cos²=1. Double-angle: sin2θ=2sinθcosθ. Sum-to-product: sinA+sinB=2sin((A+B)/2)cos((A-B)/2).",
     ["maths.11.trig_ratios"]),
    ("maths.11.trig_equations",        "Maths", "Trigonometric Functions",
     "Trigonometric Equations and General Solutions",
     "sinθ=a → θ = nπ±arcsin(a). cosθ=a → θ = 2nπ±arccos(a). General solution captures all solutions.",
     ["maths.11.trig_identities"]),
    ("maths.11.inverse_trig",          "Maths", "Inverse Trigonometric Functions",
     "Inverse Trigonometric Functions and Principal Value Branch",
     "arcsin: [−1,1]→[−π/2,π/2]. arccos: [−1,1]→[0,π]. Key identities: arcsin(x)+arccos(x)=π/2.",
     ["maths.11.trig_ratios"]),

    # Algebra
    ("maths.11.complex_numbers",       "Maths", "Complex Numbers and Quadratic Equations",
     "Complex Numbers: Modulus, Argument and Polar Form",
     "z = a + bi. |z| = √(a²+b²). arg(z) = arctan(b/a). Polar: z = r(cosθ + i sinθ). De Moivre's theorem.",
     []),
    ("maths.11.quadratic",             "Maths", "Complex Numbers and Quadratic Equations",
     "Quadratic Equations: Discriminant, Roots and Nature",
     "ax²+bx+c=0 has roots (−b±√Δ)/2a. Δ>0 real distinct; Δ=0 real equal; Δ<0 complex conjugate.",
     ["maths.11.complex_numbers"]),
    ("maths.11.sequences_ap",          "Maths", "Sequences and Series",
     "Arithmetic Progressions — nth Term and Sum",
     "AP: aₙ = a + (n−1)d. Sₙ = n/2 (2a + (n−1)d) = n/2(first + last).",
     []),
    ("maths.11.sequences_gp",          "Maths", "Sequences and Series",
     "Geometric Progressions — nth Term, Sum and Infinite GP",
     "GP: aₙ = arⁿ⁻¹. Sₙ = a(1−rⁿ)/(1−r). Infinite GP (|r|<1): S∞ = a/(1−r).",
     []),
    ("maths.11.sequences_hp",          "Maths", "Sequences and Series",
     "Harmonic Progressions and AM-GM-HM Inequality",
     "HP: reciprocals form AP. AM ≥ GM ≥ HM. Equality iff all terms equal.",
     ["maths.11.sequences_ap", "maths.11.sequences_gp"]),

    # Straight Lines & Conics
    ("maths.11.straight_lines",        "Maths", "Straight Lines",
     "Straight Lines: Slope, Forms of Equation, Distance",
     "slope m = tanθ = (y₂−y₁)/(x₂−x₁). Line forms: slope-intercept, point-slope, intercept, normal.",
     []),
    ("maths.11.circles",               "Maths", "Circles",
     "Circle: General Equation, Centre, Radius, Tangent",
     "x²+y²+2gx+2fy+c=0 has centre (−g,−f) radius √(g²+f²−c). Tangent: y=mx+c with c²=r²(1+m²).",
     ["maths.11.straight_lines"]),
    ("maths.11.parabola",              "Maths", "Conic Sections",
     "Parabola: Standard Forms, Focus, Directrix",
     "y²=4ax: focus (a,0), directrix x=−a, vertex (0,0). Parametric: (at², 2at).",
     ["maths.11.straight_lines"]),
    ("maths.11.ellipse",               "Maths", "Conic Sections",
     "Ellipse: Standard Form, Eccentricity, Foci",
     "x²/a²+y²/b²=1 (a>b). e=c/a<1, c²=a²−b². Sum of focal distances = 2a.",
     ["maths.11.parabola"]),
    ("maths.11.hyperbola",             "Maths", "Conic Sections",
     "Hyperbola: Standard Form, Asymptotes",
     "x²/a²−y²/b²=1. e>1, c²=a²+b². Asymptotes: y=±(b/a)x. Difference of focal distances = 2a.",
     ["maths.11.ellipse"]),

    # 3D Geometry (intro)
    ("maths.11.3d_coordinates",        "Maths", "Introduction to 3D Geometry",
     "3D Coordinate System, Distance and Section Formulae",
     "Distance = √((x₂−x₁)²+(y₂−y₁)²+(z₂−z₁)²). Section formula in 3D mirrors 2D version.",
     ["maths.11.straight_lines"]),

    # Statistics & Probability (11)
    ("maths.11.statistics",            "Maths", "Statistics",
     "Mean, Median, Mode, Variance and Standard Deviation",
     "Mean = Σx/n. Variance σ² = Σ(x−μ)²/n. SD = √variance. For grouped data use midpoints.",
     []),
    ("maths.11.probability_basics",    "Maths", "Probability",
     "Classical Probability, Events and Axioms",
     "P(A) = favourable/total for equally likely outcomes. 0≤P(A)≤1. P(A∪B) = P(A)+P(B)−P(A∩B).",
     ["maths.11.sets_basics"]),
    ("maths.11.conditional_prob",      "Maths", "Probability",
     "Conditional Probability and Multiplication Rule",
     "P(A|B) = P(A∩B)/P(B). Independent events: P(A∩B)=P(A)·P(B). Bayes' theorem: P(A|B)∝P(B|A)P(A).",
     ["maths.11.probability_basics"]),

    # Mathematical Reasoning
    ("maths.11.binomial_theorem",      "Maths", "Binomial Theorem",
     "Binomial Theorem: Expansion, General Term, Middle Term",
     "(a+b)ⁿ = Σ C(n,r) aⁿ⁻ʳ bʳ. General term: T_{r+1} = C(n,r) aⁿ⁻ʳ bʳ. Middle term for even/odd n.",
     []),
    ("maths.11.permutations",          "Maths", "Permutations and Combinations",
     "Permutations: nPr, Circular Permutations",
     "nPr = n!/(n−r)!. Circular: (n−1)!. With identical objects: n!/p!q!r!.",
     []),
    ("maths.11.combinations",          "Maths", "Permutations and Combinations",
     "Combinations: nCr and Applications",
     "nCr = n!/(r!(n−r)!). nCr = nC(n−r). Pascal's identity: C(n,r) = C(n−1,r−1)+C(n−1,r).",
     ["maths.11.permutations"]),

    # ── Class 12 ─────────────────────────────────────────────────────────────
    # Matrices & Determinants
    ("maths.12.matrices",              "Maths", "Matrices",
     "Matrix Operations: Addition, Multiplication, Transpose",
     "Matrix multiply AB: A(m×n)·B(n×p) = C(m×p). (AB)ᵀ = BᵀAᵀ. Identity matrix I: AI = IA = A.",
     []),
    ("maths.12.determinants",          "Maths", "Determinants",
     "Determinants: Cofactors, Expansion and Properties",
     "det(A) by expansion along any row/column. |AB|=|A||B|. det(kA) = kⁿ det(A) for n×n.",
     ["maths.12.matrices"]),
    ("maths.12.inverse_matrix",        "Maths", "Matrices",
     "Inverse Matrix and Cramer's Rule",
     "A⁻¹ = adj(A)/|A|. Exists iff |A|≠0. Cramer's rule: xᵢ = |Aᵢ|/|A| for system AX = B.",
     ["maths.12.determinants"]),

    # Limits and Continuity
    ("maths.12.limits",                "Maths", "Limits and Derivatives",
     "Limits: Definition, Standard Limits and L'Hôpital",
     "lim_{x→a} f(x) = L if f(x)→L as x→a from both sides. Standard: lim sinx/x=1 as x→0.",
     []),
    ("maths.12.continuity",            "Maths", "Continuity and Differentiability",
     "Continuity: Definition and Intermediate Value Theorem",
     "f is continuous at a if lim_{x→a} f(x)=f(a). IVT: continuous f takes all values between f(a) and f(b).",
     ["maths.12.limits"]),

    # Differentiation
    ("maths.12.differentiation",       "Maths", "Continuity and Differentiability",
     "Differentiation: Chain Rule, Product Rule, Quotient Rule",
     "Chain rule: (f∘g)'(x) = f'(g(x))·g'(x). Product: (uv)' = u'v + uv'. Quotient: (u/v)' = (u'v−uv')/v².",
     ["maths.12.continuity"]),
    ("maths.12.implicit_diff",         "Maths", "Continuity and Differentiability",
     "Implicit Differentiation and Parametric Differentiation",
     "Implicit: differentiate both sides w.r.t. x using chain rule for y terms. Parametric: dy/dx = (dy/dt)/(dx/dt).",
     ["maths.12.differentiation"]),
    ("maths.12.higher_derivatives",    "Maths", "Continuity and Differentiability",
     "Higher Order Derivatives and Leibniz Theorem",
     "d²y/dx² = d/dx(dy/dx). Leibniz: nth derivative of product uv = Σ C(n,k) u^(k) v^(n−k).",
     ["maths.12.differentiation"]),

    # Applications of Derivatives
    ("maths.12.maxima_minima",         "Maths", "Application of Derivatives",
     "Maxima, Minima and Monotonicity",
     "f'(x)=0 at critical points. f''(x)<0 → local max; f''(x)>0 → local min. First derivative test.",
     ["maths.12.differentiation"]),
    ("maths.12.tangent_normal",        "Maths", "Application of Derivatives",
     "Tangents, Normals and Angle Between Curves",
     "Slope of tangent = dy/dx at point. Normal ⊥ tangent: slope = −1/(dy/dx). Angle between curves via tan formula.",
     ["maths.12.differentiation"]),
    ("maths.12.mean_value_theorem",    "Maths", "Application of Derivatives",
     "Rolle's Theorem and Mean Value Theorem",
     "Rolle's: f(a)=f(b) → f'(c)=0 for some c∈(a,b). MVT: f'(c)=(f(b)−f(a))/(b−a).",
     ["maths.12.continuity"]),

    # Integration
    ("maths.12.basic_integration",     "Maths", "Integrals",
     "Basic Integration Formulae and Standard Integrals",
     "∫xⁿdx = xⁿ⁺¹/(n+1)+C. ∫eˣdx = eˣ+C. ∫sinxdx = −cosx+C. Integration = anti-differentiation.",
     ["maths.12.differentiation"]),
    ("maths.12.integration_methods",   "Maths", "Integrals",
     "Integration by Substitution, Parts and Partial Fractions",
     "Substitution: ∫f(g(x))g'(x)dx. Parts: ∫u dv = uv − ∫v du (ILATE). Partial fractions for rational functions.",
     ["maths.12.basic_integration"]),
    ("maths.12.definite_integrals",    "Maths", "Integrals",
     "Definite Integrals and Properties",
     "∫ₐᵇf(x)dx = F(b)−F(a). Key properties: ∫ₐᵇf=−∫ᵦₐf, ∫ₐᵃf=0, King's rule ∫ₐᵇf(x)=∫ₐᵇf(a+b−x).",
     ["maths.12.basic_integration"]),
    ("maths.12.area_under_curve",      "Maths", "Application of Integrals",
     "Area Under Curves and Between Curves",
     "Area = |∫ₐᵇf(x)dx|. Area between f and g: ∫ₐᵇ|f(x)−g(x)|dx. Find intersection points first.",
     ["maths.12.definite_integrals"]),

    # Differential Equations
    ("maths.12.diff_equations",        "Maths", "Differential Equations",
     "Differential Equations: Order, Degree, Formulation",
     "Order = highest derivative present. Degree = power of highest derivative (when polynomial in derivatives).",
     ["maths.12.differentiation"]),
    ("maths.12.separable_ode",         "Maths", "Differential Equations",
     "Variable Separable and Homogeneous Differential Equations",
     "Separable: dy/dx = f(x)g(y) → ∫dy/g(y) = ∫f(x)dx. Homogeneous: dy/dx = F(y/x), substitute y=vx.",
     ["maths.12.diff_equations"]),
    ("maths.12.linear_ode",            "Maths", "Differential Equations",
     "Linear First-Order ODE and Integrating Factor",
     "dy/dx + P(x)y = Q(x). IF = e^∫P dx. Solution: y·IF = ∫Q·IF dx + C.",
     ["maths.12.diff_equations"]),

    # Vectors
    ("maths.12.vectors_basics",        "Maths", "Vectors",
     "Vectors: Types, Addition, Scalar and Vector Products",
     "Position, unit, null vectors. Dot product: a·b = |a||b|cosθ. Cross product: |a×b| = |a||b|sinθ.",
     []),
    ("maths.12.vector_triple",         "Maths", "Vectors",
     "Triple Products and Collinearity/Coplanarity Conditions",
     "Scalar triple product [a,b,c] = a·(b×c) = volume of parallelepiped. Zero iff coplanar.",
     ["maths.12.vectors_basics"]),

    # 3D Geometry
    ("maths.12.lines_3d",              "Maths", "Three Dimensional Geometry",
     "Lines in 3D: Direction Cosines, Vector and Cartesian Forms",
     "Line through (x₁,y₁,z₁) with direction (a,b,c): (x−x₁)/a=(y−y₁)/b=(z−z₁)/c. l²+m²+n²=1.",
     ["maths.12.vectors_basics"]),
    ("maths.12.planes_3d",             "Maths", "Three Dimensional Geometry",
     "Planes in 3D: Equations, Normal, Distance from Point",
     "Plane: ax+by+cz=d, normal (a,b,c). Distance from (x₀,y₀,z₀): |ax₀+by₀+cz₀−d|/√(a²+b²+c²).",
     ["maths.12.lines_3d"]),
    ("maths.12.skew_lines",            "Maths", "Three Dimensional Geometry",
     "Angle Between Lines, Planes and Skew Lines",
     "Angle between lines: cosθ = |l₁l₂+m₁m₂+n₁n₂|. Skew lines: not parallel, not intersecting. Shortest distance formula.",
     ["maths.12.lines_3d"]),

    # Probability (12)
    ("maths.12.probability_dist",      "Maths", "Probability",
     "Random Variables, Probability Distributions and Mean/Variance",
     "Discrete RV X with P(X=xᵢ)=pᵢ. E(X)=Σxᵢpᵢ. Var(X)=E(X²)−[E(X)]². Binomial: P(X=r)=C(n,r)pʳqⁿ⁻ʳ.",
     ["maths.11.conditional_prob"]),
    ("maths.12.bayes_theorem",         "Maths", "Probability",
     "Bayes' Theorem and Total Probability",
     "P(A) = ΣP(A|Bᵢ)P(Bᵢ). Bayes: P(Bⱼ|A) = P(A|Bⱼ)P(Bⱼ)/ΣP(A|Bᵢ)P(Bᵢ). Used in medical/reliability problems.",
     ["maths.11.conditional_prob"]),
    ("maths.12.binomial_dist",         "Maths", "Probability",
     "Binomial and Poisson Distributions",
     "Binomial: n trials, p success. Mean = np, Var = npq. Poisson: rare events, P(X=k)=e^(−λ)λᵏ/k!.",
     ["maths.12.probability_dist"]),

    # Linear Programming
    ("maths.12.linear_programming",    "Maths", "Linear Programming",
     "Linear Programming: Feasible Region and Corner Point Method",
     "Maximise/minimise Z = ax+by subject to linear constraints. Feasible region is convex polygon. Optimal at corner.",
     []),
]


# ── Insert ─────────────────────────────────────────────────────────────────────

def insert_concepts(concepts: list[tuple]) -> int:
    inserted = 0
    for row in concepts:
        cid, subject, topic, subtopic, description, prereqs = row
        cur.execute(
            """
            INSERT INTO concepts (id, subject, topic, subtopic, description, prerequisite_ids)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (cid, subject, topic, subtopic, description, prereqs),
        )
        inserted += cur.rowcount
    return inserted


print("Inserting Chemistry concepts …")
chem_n = insert_concepts(CHEMISTRY_CONCEPTS)

print("Inserting Maths concepts …")
maths_n = insert_concepts(MATHS_CONCEPTS)

conn.commit()
cur.close()
conn.close()

print(f"\n✓ Done: {chem_n} Chemistry + {maths_n} Maths concepts inserted (skipped existing).")
print(f"  Total new rows: {chem_n + maths_n}")

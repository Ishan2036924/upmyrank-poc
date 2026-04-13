/**
 * Static JEE syllabus constant — Subject → Chapter → Topic hierarchy.
 *
 * Used as a fallback when /taxonomy returns 0 chapters for a subject
 * (e.g. Maths is sparse in the concepts table due to fewer ingested chunks).
 *
 * Source: NTA JEE Main + Advanced syllabus, NCERT Class 11 & 12.
 */

export interface SyllabusTopic {
  id: string    // slug, e.g. "rotational-dynamics__moment-of-inertia"
  name: string  // display name, e.g. "Moment of Inertia"
}

export interface SyllabusChapter {
  id: string
  name: string
  topics: SyllabusTopic[]
}

export interface SyllabusSubject {
  name: 'Physics' | 'Chemistry' | 'Maths'
  color: string       // Tailwind text color class
  bgColor: string     // Tailwind bg class for subject badge
  borderColor: string // Tailwind border class
  chapters: SyllabusChapter[]
}

function slug(subject: string, chapter: string, topic: string): string {
  const s = (v: string) => v.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
  return `${s(subject)}__${s(chapter)}__${s(topic)}`
}

function chapterSlug(subject: string, chapter: string): string {
  const s = (v: string) => v.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
  return `${s(subject)}__${s(chapter)}`
}

function makeChapter(subject: string, name: string, topics: string[]): SyllabusChapter {
  return {
    id: chapterSlug(subject, name),
    name,
    topics: topics.map((t) => ({ id: slug(subject, name, t), name: t })),
  }
}

// ── Physics ────────────────────────────────────────────────────────────────────

const PHYSICS_CHAPTERS: SyllabusChapter[] = [
  makeChapter('Physics', 'Units & Dimensions', [
    'Physical Quantities & Units', 'Dimensional Analysis', 'Significant Figures', 'Errors in Measurement',
  ]),
  makeChapter('Physics', 'Kinematics', [
    'Motion in a Straight Line', 'Projectile Motion', 'Relative Motion', 'Circular Motion Basics',
  ]),
  makeChapter('Physics', 'Laws of Motion', [
    "Newton's Laws", 'Free Body Diagrams', 'Friction', 'Connected Bodies & Pulleys',
  ]),
  makeChapter('Physics', 'Work, Energy & Power', [
    'Work Done by a Force', 'Kinetic & Potential Energy', 'Work-Energy Theorem',
    'Conservation of Energy', 'Power & Efficiency', 'Collisions',
  ]),
  makeChapter('Physics', 'Rotational Dynamics', [
    'Centre of Mass', 'Moment of Inertia', 'Torque & Angular Momentum',
    'Rolling Motion', 'Conservation of Angular Momentum',
  ]),
  makeChapter('Physics', 'Gravitation', [
    "Newton's Law of Gravitation", 'Gravitational Field & Potential',
    'Satellite Motion & Orbital Velocity', 'Escape Velocity', "Kepler's Laws",
  ]),
  makeChapter('Physics', 'Properties of Matter', [
    'Elasticity & Stress-Strain', 'Fluid Statics & Pressure',
    "Bernoulli's Equation", 'Viscosity & Surface Tension',
  ]),
  makeChapter('Physics', 'Thermodynamics', [
    'Temperature & Heat', 'First Law of Thermodynamics', 'Second Law & Entropy',
    'Carnot Engine', 'Heat Transfer',
  ]),
  makeChapter('Physics', 'Kinetic Theory of Gases', [
    'Ideal Gas Equation', 'Kinetic Energy & Temperature',
    'Degrees of Freedom', 'Mean Free Path',
  ]),
  makeChapter('Physics', 'Oscillations', [
    'Simple Harmonic Motion', 'Energy in SHM',
    'Damped & Forced Oscillations', 'Resonance',
  ]),
  makeChapter('Physics', 'Waves', [
    'Wave Motion & Speed', 'Superposition & Interference',
    'Standing Waves', 'Doppler Effect',
  ]),
  makeChapter('Physics', 'Electrostatics', [
    "Coulomb's Law", 'Electric Field & Potential', 'Gauss\'s Law',
    'Capacitors & Dielectrics', 'Energy of a Charge System',
  ]),
  makeChapter('Physics', 'Current Electricity', [
    "Ohm's Law & Resistance", 'Kirchhoff\'s Laws', 'Wheatstone Bridge',
    'RC & RL Circuits', 'Electrical Power',
  ]),
  makeChapter('Physics', 'Magnetic Effects of Current', [
    'Biot-Savart Law', 'Ampere\'s Law', 'Force on a Moving Charge',
    'Torque on a Current Loop', 'Cyclotron',
  ]),
  makeChapter('Physics', 'Electromagnetic Induction', [
    "Faraday's Law", 'Lenz\'s Law', 'Motional EMF',
    'Self & Mutual Inductance', 'AC Generator',
  ]),
  makeChapter('Physics', 'Alternating Current', [
    'AC Circuits & Phasors', 'LC & LCR Circuits',
    'Resonance in AC Circuits', 'Power in AC',
  ]),
  makeChapter('Physics', 'Ray Optics', [
    'Reflection & Mirrors', 'Refraction & Snell\'s Law',
    'Prism & Dispersion', 'Lenses & Lens Formula', 'Optical Instruments',
  ]),
  makeChapter('Physics', 'Wave Optics', [
    "Young's Double Slit", 'Diffraction', 'Polarisation',
  ]),
  makeChapter('Physics', 'Modern Physics', [
    'Photoelectric Effect', 'de Broglie Wavelength',
    'Bohr Model of Atom', 'Radioactivity', 'Nuclear Reactions',
  ]),
  makeChapter('Physics', 'Semiconductor Devices', [
    'P-N Junction Diode', 'Transistors', 'Logic Gates',
  ]),
]

// ── Chemistry ─────────────────────────────────────────────────────────────────

const CHEMISTRY_CHAPTERS: SyllabusChapter[] = [
  makeChapter('Chemistry', 'Basic Concepts of Chemistry', [
    'Mole Concept', 'Empirical & Molecular Formula',
    'Stoichiometry', 'Limiting Reagent & Yield',
  ]),
  makeChapter('Chemistry', 'Structure of Atom', [
    'Quantum Numbers', 'Orbital Shapes & Energies',
    'Electronic Configuration', 'Aufbau & Hund\'s Rule',
  ]),
  makeChapter('Chemistry', 'Periodic Table & Periodicity', [
    'Classification of Elements', 'Periodic Trends',
    'Ionisation Energy & Electron Affinity', 'Atomic & Ionic Radii',
  ]),
  makeChapter('Chemistry', 'Chemical Bonding', [
    'Ionic & Covalent Bonds', 'VSEPR Theory & Shapes',
    'Hybridisation', 'Molecular Orbital Theory', 'Hydrogen Bonding',
  ]),
  makeChapter('Chemistry', 'States of Matter', [
    'Ideal & Real Gases', 'van der Waals Equation',
    'Liquefaction of Gases', 'Liquid State Properties',
  ]),
  makeChapter('Chemistry', 'Chemical Thermodynamics', [
    'Internal Energy & Enthalpy', 'Hess\'s Law',
    'Entropy & Spontaneity', 'Gibbs Free Energy',
  ]),
  makeChapter('Chemistry', 'Equilibrium', [
    'Chemical Equilibrium & K', 'Le Chatelier\'s Principle',
    'Ionic Equilibrium', 'pH & Buffer Solutions', 'Solubility Product',
  ]),
  makeChapter('Chemistry', 'Redox Reactions & Electrochemistry', [
    'Oxidation & Reduction', 'Balancing Redox Equations',
    'Electrochemical Cells', 'Nernst Equation', 'Electrolysis',
  ]),
  makeChapter('Chemistry', 'Chemical Kinetics', [
    'Rate of Reaction', 'Rate Laws & Order',
    'Integrated Rate Equations', 'Activation Energy & Arrhenius',
  ]),
  makeChapter('Chemistry', 'Solutions', [
    'Types of Solutions', 'Colligative Properties',
    'Vapour Pressure & Raoult\'s Law', 'Osmosis & van\'t Hoff Factor',
  ]),
  makeChapter('Chemistry', 'Surface Chemistry', [
    'Adsorption', 'Colloids & Emulsions', 'Catalysis',
  ]),
  makeChapter('Chemistry', 'p-Block Elements', [
    'Group 13 Elements (Boron family)', 'Group 14 (Carbon family)',
    'Group 15 (Nitrogen family)', 'Group 16 (Oxygen family)',
    'Group 17 (Halogens)', 'Group 18 (Noble gases)',
  ]),
  makeChapter('Chemistry', 'd and f Block Elements', [
    'Transition Metals', 'Oxidation States',
    'Colour & Magnetic Properties', 'Lanthanides & Actinides',
  ]),
  makeChapter('Chemistry', 'Coordination Compounds', [
    'Nomenclature & Isomerism', 'Bonding Theories',
    'Crystal Field Theory', 'Stability of Complexes',
  ]),
  makeChapter('Chemistry', 'Organic Chemistry — Basics', [
    'IUPAC Nomenclature', 'Reaction Mechanisms',
    'Inductive & Resonance Effects', 'Isomerism',
  ]),
  makeChapter('Chemistry', 'Hydrocarbons', [
    'Alkanes', 'Alkenes & Dienes', 'Alkynes',
    'Aromatic Compounds & Aromaticity',
  ]),
  makeChapter('Chemistry', 'Haloalkanes & Haloarenes', [
    'Nucleophilic Substitution (SN1/SN2)', 'Elimination Reactions', 'Aromatic Halides',
  ]),
  makeChapter('Chemistry', 'Alcohols, Phenols & Ethers', [
    'Preparation & Properties of Alcohols', 'Phenols & Acidity',
    'Ethers & Williamson Synthesis',
  ]),
  makeChapter('Chemistry', 'Carbonyl Compounds', [
    'Aldehydes & Ketones', 'Nucleophilic Addition',
    'Carboxylic Acids & Derivatives', 'Named Reactions (Aldol, Cannizzaro)',
  ]),
  makeChapter('Chemistry', 'Nitrogen Compounds', [
    'Amines & Basicity', 'Diazonium Salts', 'Amino Acids & Proteins',
  ]),
  makeChapter('Chemistry', 'Biomolecules & Polymers', [
    'Carbohydrates', 'Lipids', 'Nucleic Acids',
    'Addition & Condensation Polymers',
  ]),
]

// ── Maths ─────────────────────────────────────────────────────────────────────

const MATHS_CHAPTERS: SyllabusChapter[] = [
  makeChapter('Maths', 'Sets, Relations & Functions', [
    'Types of Sets & Operations', 'Relations & Types',
    'Functions & Composition', 'Inverse Functions',
  ]),
  makeChapter('Maths', 'Trigonometry', [
    'Trigonometric Ratios & Identities', 'Compound & Multiple Angles',
    'Trigonometric Equations', 'Properties of Triangles',
  ]),
  makeChapter('Maths', 'Inverse Trigonometry', [
    'Domain & Range of Inverse Functions', 'Principal Values',
    'Properties & Identities',
  ]),
  makeChapter('Maths', 'Complex Numbers', [
    'Algebra of Complex Numbers', 'Argand Plane & Polar Form',
    'De Moivre\'s Theorem', 'Roots of Unity',
  ]),
  makeChapter('Maths', 'Quadratic Equations', [
    'Nature of Roots', 'Sum & Product of Roots',
    'Quadratic Inequalities', 'Common Roots',
  ]),
  makeChapter('Maths', 'Permutations & Combinations', [
    'Fundamental Counting Principle', 'Permutations',
    'Combinations', 'Circular Permutations',
  ]),
  makeChapter('Maths', 'Binomial Theorem', [
    'Binomial Expansion', 'General & Middle Term',
    'Properties of Binomial Coefficients',
  ]),
  makeChapter('Maths', 'Sequences & Series', [
    'AP — nth Term & Sum', 'GP — nth Term & Sum',
    'Special Series (Σn, Σn², Σn³)', 'Infinite GP',
  ]),
  makeChapter('Maths', 'Matrices & Determinants', [
    'Matrix Operations', 'Determinants & Properties',
    'Inverse of a Matrix', 'System of Linear Equations (Cramer\'s Rule)',
  ]),
  makeChapter('Maths', 'Straight Lines', [
    'Slope & Equations of a Line', 'Angle between Lines',
    'Distance from a Point', 'Locus Problems',
  ]),
  makeChapter('Maths', 'Circles', [
    'Equation of a Circle', 'Tangents & Normals',
    'Chord of Contact', 'Family of Circles',
  ]),
  makeChapter('Maths', 'Conic Sections', [
    'Parabola', 'Ellipse', 'Hyperbola',
    'Tangents & Normals to Conics',
  ]),
  makeChapter('Maths', 'Limits, Continuity & Differentiability', [
    'Limits & L\'Hôpital\'s Rule', 'Continuity',
    'Differentiability', 'Derivatives of Standard Functions',
  ]),
  makeChapter('Maths', 'Differentiation', [
    'Chain Rule & Product Rule', 'Implicit Differentiation',
    'Higher Order Derivatives', 'Logarithmic Differentiation',
  ]),
  makeChapter('Maths', 'Applications of Derivatives', [
    'Tangents & Normals', 'Increasing & Decreasing Functions',
    'Maxima & Minima', 'Rate of Change',
  ]),
  makeChapter('Maths', 'Integrals', [
    'Standard Integrals', 'Integration by Parts',
    'Integration by Partial Fractions', 'Definite Integrals & Properties',
  ]),
  makeChapter('Maths', 'Applications of Integrals', [
    'Area under a Curve', 'Area between Two Curves',
  ]),
  makeChapter('Maths', 'Differential Equations', [
    'Order & Degree', 'Variable Separable Method',
    'Homogeneous Equations', 'Linear Differential Equations',
  ]),
  makeChapter('Maths', 'Vectors', [
    'Vector Algebra & Types', 'Dot Product & Cross Product',
    'Scalar Triple Product', 'Vector Equations',
  ]),
  makeChapter('Maths', '3D Geometry', [
    'Direction Cosines & Ratios', 'Equation of a Line in 3D',
    'Equation of a Plane', 'Angle & Distance',
  ]),
  makeChapter('Maths', 'Probability', [
    'Classical & Conditional Probability', 'Bayes\' Theorem',
    'Binomial Distribution', 'Expected Value',
  ]),
]

// ── Full syllabus export ───────────────────────────────────────────────────────

export const STATIC_SYLLABUS: SyllabusSubject[] = [
  {
    name: 'Physics',
    color: 'text-blue-600',
    bgColor: 'bg-blue-50',
    borderColor: 'border-blue-200',
    chapters: PHYSICS_CHAPTERS,
  },
  {
    name: 'Chemistry',
    color: 'text-emerald-600',
    bgColor: 'bg-emerald-50',
    borderColor: 'border-emerald-200',
    chapters: CHEMISTRY_CHAPTERS,
  },
  {
    name: 'Maths',
    color: 'text-violet-600',
    bgColor: 'bg-violet-50',
    borderColor: 'border-violet-200',
    chapters: MATHS_CHAPTERS,
  },
]

/** Map from subject name → static syllabus entry */
export const SYLLABUS_MAP: Record<string, SyllabusSubject> = Object.fromEntries(
  STATIC_SYLLABUS.map((s) => [s.name, s]),
)

/** Mastery color from 0–1 float */
export function masteryColor(m: number): string {
  if (m <= 0.5) return '#EF4444'  // red  0–50%
  if (m <= 0.75) return '#F59E0B' // amber 51–75%
  return '#22C55E'                // green 76–100%
}

export function masteryBg(m: number): string {
  if (m <= 0.5) return 'bg-red-500'
  if (m <= 0.75) return 'bg-amber-500'
  return 'bg-emerald-500'
}

"""
Step 1 + 2: Clean existing data and seed Physics concept taxonomy.
Connects to Supabase via psycopg2 keyword-args (handles special chars in password).
"""
from __future__ import annotations
import os, sys, random, urllib.parse as _up
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
import psycopg2.extras
from app.config import settings

TEST_STUDENT_ID = "00e92458-39e8-41c9-beda-789b077dd6a2"

# ── Build psycopg2 keyword-arg connection (handles * and ! in password) ──────
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

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1: CLEAN ALL DATA (keep students)
# ═══════════════════════════════════════════════════════════════════════════════
print("=== STEP 1: Cleaning all data (keeping students) ===")
for table in ["session_events", "doubt_sessions", "concept_mastery",
              "problems", "knowledge_chunks", "concepts"]:
    cur.execute(f"DELETE FROM {table}")
    print(f"  Deleted from {table}: {cur.rowcount} rows")

conn.commit()

# Verify
cur.execute("SELECT count(*) FROM students")
(n,) = cur.fetchone()
print(f"\n  Students remaining: {n}")
assert n >= 1, "Test student missing!"
print("  ✅ Step 1 complete\n")

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2: INSERT PHYSICS CONCEPTS
# ═══════════════════════════════════════════════════════════════════════════════
print("=== STEP 2: Inserting Physics concept taxonomy ===")

# concept_id, topic, subtopic, prerequisites[]
CONCEPTS: list[tuple[str, str, str, list[str]]] = [
    # ── CLASS 11 ────────────────────────────────────────────────────────────────
    # Ch1 Physical World
    ("physics.11.physical_world",         "Physical World",          "Scope and Nature of Physics",          []),
    # Ch2 Units and Measurements
    ("physics.11.units_measurements",     "Units and Measurements",  "SI Units and Dimensional Analysis",    []),
    ("physics.11.dimensional_analysis",   "Units and Measurements",  "Dimensional Analysis and Applications",[  "physics.11.units_measurements"]),
    ("physics.11.significant_figures",    "Units and Measurements",  "Significant Figures and Error Analysis",[ "physics.11.units_measurements"]),
    # Ch3 Motion in a Straight Line
    ("physics.11.distance_displacement",  "Kinematics",              "Distance and Displacement",             []),
    ("physics.11.speed_velocity",         "Kinematics",              "Speed and Velocity",                    ["physics.11.distance_displacement"]),
    ("physics.11.acceleration",           "Kinematics",              "Acceleration and Equations of Motion",  ["physics.11.speed_velocity"]),
    ("physics.11.graphical_analysis",     "Kinematics",              "Graphical Analysis of Motion",          ["physics.11.acceleration"]),
    # Ch4 Motion in a Plane
    ("physics.11.vectors",                "Kinematics",              "Vectors and Vector Operations",         []),
    ("physics.11.projectile_motion",      "Kinematics",              "Projectile Motion",                     ["physics.11.vectors", "physics.11.acceleration"]),
    ("physics.11.circular_motion",        "Kinematics",              "Uniform Circular Motion",               ["physics.11.vectors", "physics.11.acceleration"]),
    # Ch5 Laws of Motion
    ("physics.11.newtons_first_law",      "Laws of Motion",          "Newton's First Law and Inertia",        []),
    ("physics.11.newtons_second_law",     "Laws of Motion",          "Newton's Second Law (F=ma)",            ["physics.11.newtons_first_law"]),
    ("physics.11.newtons_third_law",      "Laws of Motion",          "Newton's Third Law",                    ["physics.11.newtons_second_law"]),
    ("physics.11.friction",               "Laws of Motion",          "Friction (Static, Kinetic, Rolling)",   ["physics.11.newtons_second_law"]),
    ("physics.11.circular_motion_dynamics","Laws of Motion",         "Circular Motion Dynamics",              ["physics.11.newtons_second_law", "physics.11.circular_motion"]),
    # Ch6 Work Energy Power
    ("physics.11.work",                   "Work Energy Power",       "Work Done by a Force",                  ["physics.11.newtons_second_law"]),
    ("physics.11.kinetic_energy",         "Work Energy Power",       "Kinetic Energy and Work-Energy Theorem",["physics.11.work"]),
    ("physics.11.potential_energy",       "Work Energy Power",       "Potential Energy (Gravitational, Elastic)",["physics.11.work"]),
    ("physics.11.conservation_energy",    "Work Energy Power",       "Conservation of Energy",                ["physics.11.kinetic_energy", "physics.11.potential_energy"]),
    ("physics.11.power",                  "Work Energy Power",       "Power and Collisions",                  ["physics.11.kinetic_energy"]),
    # Ch7 Rotational Motion
    ("physics.11.centre_of_mass",         "Rotational Motion",       "Centre of Mass",                        ["physics.11.newtons_second_law"]),
    ("physics.11.moment_of_inertia",      "Rotational Motion",       "Moment of Inertia",                     ["physics.11.centre_of_mass"]),
    ("physics.11.torque",                 "Rotational Motion",       "Torque and Angular Momentum",           ["physics.11.moment_of_inertia"]),
    ("physics.11.rotational_dynamics",    "Rotational Motion",       "Rotational Dynamics and Rolling",       ["physics.11.torque"]),
    # Ch8 Gravitation
    ("physics.11.universal_gravitation",  "Gravitation",             "Universal Law of Gravitation",          ["physics.11.newtons_second_law"]),
    ("physics.11.gravitational_field",    "Gravitation",             "Gravitational Field and Potential",     ["physics.11.universal_gravitation"]),
    ("physics.11.orbital_motion",         "Gravitation",             "Orbital Motion and Satellites",         ["physics.11.gravitational_field"]),
    ("physics.11.escape_velocity",        "Gravitation",             "Escape Velocity and Kepler's Laws",     ["physics.11.orbital_motion"]),
    # Ch9 Properties of Solids
    ("physics.11.stress_strain",          "Properties of Solids",    "Stress, Strain, and Elastic Moduli",    []),
    ("physics.11.hookes_law",             "Properties of Solids",    "Hooke's Law and Elasticity",            ["physics.11.stress_strain"]),
    # Ch10 Properties of Fluids
    ("physics.11.pressure_fluids",        "Properties of Fluids",    "Pressure in Fluids and Pascal's Law",   []),
    ("physics.11.bernoulli",              "Properties of Fluids",    "Bernoulli's Principle and Viscosity",   ["physics.11.pressure_fluids"]),
    ("physics.11.surface_tension",        "Properties of Fluids",    "Surface Tension and Capillarity",       ["physics.11.pressure_fluids"]),
    # Ch11 Thermal Physics
    ("physics.11.temperature_heat",       "Thermal Physics",         "Temperature, Heat, and Thermal Expansion",[]),
    ("physics.11.calorimetry",            "Thermal Physics",         "Calorimetry and Change of State",       ["physics.11.temperature_heat"]),
    ("physics.11.heat_transfer",          "Thermal Physics",         "Heat Transfer (Conduction, Convection, Radiation)",["physics.11.temperature_heat"]),
    # Ch12 Thermodynamics
    ("physics.11.first_law_thermo",       "Thermodynamics",          "First Law of Thermodynamics",           ["physics.11.heat_transfer"]),
    ("physics.11.second_law_thermo",      "Thermodynamics",          "Second Law and Heat Engines",           ["physics.11.first_law_thermo"]),
    ("physics.11.carnot_cycle",           "Thermodynamics",          "Carnot Cycle and Entropy",              ["physics.11.second_law_thermo"]),
    # Ch13 Kinetic Theory
    ("physics.11.kinetic_theory_gases",   "Kinetic Theory",          "Kinetic Theory of Gases",               ["physics.11.temperature_heat"]),
    ("physics.11.gas_laws",               "Kinetic Theory",          "Gas Laws and Ideal Gas Equation",       ["physics.11.kinetic_theory_gases"]),
    # Ch14 Oscillations
    ("physics.11.shm",                    "Oscillations and Waves",  "Simple Harmonic Motion",                ["physics.11.newtons_second_law"]),
    ("physics.11.shm_energy",             "Oscillations and Waves",  "Energy in SHM and Damped Oscillations", ["physics.11.shm", "physics.11.conservation_energy"]),
    ("physics.11.pendulum",               "Oscillations and Waves",  "Simple Pendulum and Forced Oscillations",["physics.11.shm"]),
    # Ch15 Waves
    ("physics.11.wave_motion",            "Oscillations and Waves",  "Transverse and Longitudinal Waves",     ["physics.11.shm"]),
    ("physics.11.superposition",          "Oscillations and Waves",  "Superposition and Standing Waves",      ["physics.11.wave_motion"]),
    ("physics.11.doppler_effect",         "Oscillations and Waves",  "Doppler Effect and Sound",              ["physics.11.wave_motion"]),

    # ── CLASS 12 ────────────────────────────────────────────────────────────────
    # Ch1 Electric Charges and Fields
    ("physics.12.electric_charge",        "Electrostatics",          "Electric Charge and Coulomb's Law",     []),
    ("physics.12.electric_field",         "Electrostatics",          "Electric Field and Field Lines",        ["physics.12.electric_charge"]),
    ("physics.12.gauss_law",              "Electrostatics",          "Gauss's Law and Applications",          ["physics.12.electric_field"]),
    # Ch2 Electrostatic Potential
    ("physics.12.electric_potential",     "Electrostatics",          "Electric Potential and Potential Energy",["physics.12.electric_field"]),
    ("physics.12.capacitance",            "Electrostatics",          "Capacitors and Capacitance",            ["physics.12.electric_potential"]),
    ("physics.12.dielectrics",            "Electrostatics",          "Dielectrics and Energy Stored",         ["physics.12.capacitance"]),
    # Ch3 Current Electricity
    ("physics.12.ohms_law",               "Current Electricity",     "Ohm's Law and Resistance",              []),
    ("physics.12.kirchhoffs_laws",        "Current Electricity",     "Kirchhoff's Laws and Circuit Analysis", ["physics.12.ohms_law"]),
    ("physics.12.wheatstone_bridge",      "Current Electricity",     "Wheatstone Bridge and Potentiometer",   ["physics.12.kirchhoffs_laws"]),
    # Ch4 Moving Charges and Magnetism
    ("physics.12.magnetic_force",         "Magnetism",               "Magnetic Force on Moving Charges",      ["physics.12.electric_field"]),
    ("physics.12.biot_savart",            "Magnetism",               "Biot-Savart Law and Ampere's Law",      ["physics.12.magnetic_force"]),
    ("physics.12.solenoid_toroid",        "Magnetism",               "Solenoid, Toroid, and Force Between Conductors",["physics.12.biot_savart"]),
    # Ch5 Magnetism and Matter
    ("physics.12.magnetism_matter",       "Magnetism",               "Magnetic Properties of Materials",      ["physics.12.biot_savart"]),
    ("physics.12.earth_magnetism",        "Magnetism",               "Earth's Magnetism",                     ["physics.12.magnetism_matter"]),
    # Ch6 Electromagnetic Induction
    ("physics.12.faradays_law",           "EMI and AC",              "Faraday's Law and Lenz's Law",          ["physics.12.magnetic_force"]),
    ("physics.12.inductance",             "EMI and AC",              "Self and Mutual Inductance",            ["physics.12.faradays_law"]),
    ("physics.12.eddy_currents",          "EMI and AC",              "Eddy Currents and Applications",        ["physics.12.faradays_law"]),
    # Ch7 Alternating Current
    ("physics.12.ac_circuits",            "EMI and AC",              "AC Circuits (LCR, Resonance)",          ["physics.12.inductance"]),
    ("physics.12.transformers",           "EMI and AC",              "Transformers and Power Transmission",   ["physics.12.ac_circuits"]),
    # Ch8 Electromagnetic Waves
    ("physics.12.em_waves",               "EM Waves",                "Electromagnetic Spectrum and Properties",["physics.12.faradays_law"]),
    ("physics.12.em_wave_propagation",    "EM Waves",                "EM Wave Propagation and Applications",  ["physics.12.em_waves"]),
    # Ch9 Ray Optics
    ("physics.12.reflection_refraction",  "Optics",                  "Reflection and Refraction",             []),
    ("physics.12.lenses_mirrors",         "Optics",                  "Lenses, Mirrors, and Image Formation",  ["physics.12.reflection_refraction"]),
    ("physics.12.optical_instruments",    "Optics",                  "Optical Instruments (Microscope, Telescope)",["physics.12.lenses_mirrors"]),
    # Ch10 Wave Optics
    ("physics.12.interference",           "Optics",                  "Interference and Young's Double Slit",  ["physics.12.reflection_refraction"]),
    ("physics.12.diffraction",            "Optics",                  "Diffraction and Polarization",          ["physics.12.interference"]),
    # Ch11 Dual Nature
    ("physics.12.photoelectric",          "Modern Physics",          "Photoelectric Effect",                  ["physics.12.em_waves"]),
    ("physics.12.wave_particle_duality",  "Modern Physics",          "Wave-Particle Duality and de Broglie",  ["physics.12.photoelectric"]),
    # Ch12 Atoms
    ("physics.12.atomic_models",          "Modern Physics",          "Bohr Model and Hydrogen Spectrum",      ["physics.12.wave_particle_duality"]),
    ("physics.12.atomic_spectra",         "Modern Physics",          "Atomic Spectra and Energy Levels",      ["physics.12.atomic_models"]),
    # Ch13 Nuclei
    ("physics.12.nuclear_structure",      "Nuclear Physics",         "Nuclear Structure and Binding Energy",  ["physics.12.atomic_models"]),
    ("physics.12.radioactivity",          "Nuclear Physics",         "Radioactivity and Nuclear Reactions",   ["physics.12.nuclear_structure"]),
    ("physics.12.nuclear_fission_fusion", "Nuclear Physics",         "Nuclear Fission and Fusion",            ["physics.12.nuclear_structure"]),
    # Ch14 Semiconductor Electronics
    ("physics.12.semiconductors",         "Electronics",             "Semiconductors (Intrinsic, Extrinsic, p-n Junction)",[]),
    ("physics.12.diodes",                 "Electronics",             "Diodes, LED, Photodiode, Solar Cell",   ["physics.12.semiconductors"]),
    ("physics.12.transistors",            "Electronics",             "Transistors and Logic Gates",           ["physics.12.diodes"]),
]

print(f"  Inserting {len(CONCEPTS)} Physics concepts …")
cur.executemany(
    """
    INSERT INTO concepts (id, subject, topic, subtopic, prerequisite_ids)
    VALUES (%s, 'Physics', %s, %s, %s)
    ON CONFLICT (id) DO UPDATE SET
        subject = EXCLUDED.subject,
        topic = EXCLUDED.topic,
        subtopic = EXCLUDED.subtopic,
        prerequisite_ids = EXCLUDED.prerequisite_ids
    """,
    [(cid, topic, subtopic, prereqs) for cid, topic, subtopic, prereqs in CONCEPTS],
)
conn.commit()

cur.execute("SELECT count(*) FROM concepts")
(n,) = cur.fetchone()
print(f"  Total concepts in DB: {n}")

# ── Seed concept_mastery for test student ────────────────────────────────────
print(f"\n  Seeding concept_mastery for student {TEST_STUDENT_ID} …")
random.seed(42)
mastery_rows = [
    (TEST_STUDENT_ID, cid, round(random.uniform(0.2, 0.7), 3), 0, 0)
    for cid, _, _, _ in CONCEPTS
]
cur.executemany(
    """
    INSERT INTO concept_mastery
        (student_id, concept_id, mastery_score, error_count, attempt_count)
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (student_id, concept_id) DO UPDATE SET
        mastery_score = EXCLUDED.mastery_score
    """,
    mastery_rows,
)
conn.commit()

cur.execute("SELECT count(*) FROM concept_mastery")
(m,) = cur.fetchone()
print(f"  concept_mastery rows: {m}")
assert m == len(CONCEPTS), f"Expected {len(CONCEPTS)}, got {m}"

print("\n✅ Step 2 complete")
print(f"\nFinal table counts:")
for table in ["concepts", "concept_mastery", "knowledge_chunks", "problems", "doubt_sessions"]:
    cur.execute(f"SELECT count(*) FROM {table}")
    (cnt,) = cur.fetchone()
    print(f"  {table}: {cnt}")

cur.close()
conn.close()

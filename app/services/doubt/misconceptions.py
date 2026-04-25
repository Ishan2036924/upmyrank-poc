"""
Misconception detection library for JEE Physics, Chemistry, and Maths.

Entry points:
    check_for_misconception(student_response, topic, subject) → Misconception | None

No LLM call — pure keyword matching. Must stay fast (< 1ms).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Misconception:
    id: str                          # Unique slug, stored in doubt_blocks.misconception_id
    pattern_keywords: list[str]      # Lowercase phrases to match in student response
    pattern_description: str         # Human-readable description of the wrong model
    correction_prompt: str           # Socratic question targeting the specific wrong thinking
    concepts_affected: list[str]     # Topic strings to scope the check (case-insensitive substring match)
    hint_level_to_trigger: int       # Minimum hint level before this check fires (reserved for future use)
    subject: str = "Physics"         # Subject filter: "Physics" | "Chemistry" | "Maths"


# ── Library ───────────────────────────────────────────────────────────────────

MISCONCEPTION_LIBRARY: list[Misconception] = [

    # ── Circular Motion ───────────────────────────────────────────────────────

    Misconception(
        id="centripetal_outward_force",
        pattern_keywords=[
            "centrifugal", "centrifugal force", "outward force",
            "pushed outward", "pushes outward", "pulling outward",
            "pulling it outward", "pulling them outward",
            "outward pull", "outward push",
            "flying outward", "force outward",
            "moves outward because of force",
            "stays in because of centrifugal",
            "water stays in because",
        ],
        pattern_description="Student treats centrifugal / outward force as a real inertial force in a free body diagram.",
        correction_prompt=(
            "Before we continue — is centripetal force a new type of force acting outward, "
            "or is it a label we give to an existing force (tension, gravity, normal) that "
            "happens to point toward the centre? Try drawing the free body diagram with only real forces."
        ),
        concepts_affected=["circular motion", "centripetal", "uniform circular"],
        hint_level_to_trigger=1,
    ),

    Misconception(
        id="centripetal_accel_is_velocity",
        pattern_keywords=[
            "centripetal velocity", "v squared over r is velocity", "v²/r is the speed",
            "velocity toward center", "speed toward center", "centripetal speed",
        ],
        pattern_description="Student applies v²/r as a velocity rather than an acceleration magnitude.",
        correction_prompt=(
            "Quick check — v²/r gives you the *magnitude of centripetal acceleration*, not velocity. "
            "Velocity is always tangent to the circle. Can you re-state what v²/r represents "
            "and in which direction it acts?"
        ),
        concepts_affected=["circular motion", "centripetal", "uniform circular"],
        hint_level_to_trigger=1,
    ),

    Misconception(
        id="circular_constant_speed_no_accel",
        pattern_keywords=[
            "no acceleration", "constant speed means no acceleration",
            "uniform speed no force", "same speed no acceleration",
            "speed doesn't change so no", "speed is same so acceleration zero",
        ],
        pattern_description="Student concludes that constant speed implies zero acceleration, ignoring direction change.",
        correction_prompt=(
            "Acceleration is the rate of change of *velocity*, not speed. "
            "If an object moves in a circle at constant speed, is its velocity changing? "
            "What does that tell you about whether acceleration is zero?"
        ),
        concepts_affected=["circular motion", "centripetal", "uniform circular"],
        hint_level_to_trigger=1,
    ),

    # ── Newton's Laws ─────────────────────────────────────────────────────────

    Misconception(
        id="action_reaction_same_object",
        pattern_keywords=[
            "cancel each other", "cancel out", "action reaction cancel",
            "third law cancel", "equal and opposite so they cancel",
            "newton's third cancels", "forces cancel because third law",
        ],
        pattern_description="Student believes Newton's third law pairs cancel within the same free body diagram.",
        correction_prompt=(
            "Newton's third law pairs always act on *different* objects — they can never cancel "
            "in a single free body diagram. Can you identify which two objects form the "
            "action-reaction pair here, and draw a separate FBD for each?"
        ),
        concepts_affected=["newton", "laws of motion", "third law", "force"],
        hint_level_to_trigger=1,
    ),

    Misconception(
        id="normal_force_equals_mg",
        pattern_keywords=[
            "normal force is mg", "n equals mg", "normal equals weight",
            "normal force is equal to weight", "normal is always mg",
            "n = mg", "normal force mg always",
        ],
        pattern_description="Student assumes normal force always equals mg regardless of incline or acceleration.",
        correction_prompt=(
            "Normal force equals mg only on a flat, stationary surface with no other vertical forces. "
            "If the surface is inclined, or if the system is accelerating, what equation should you "
            "actually use to find N? (Hint: apply Newton's second law perpendicular to the surface.)"
        ),
        concepts_affected=["newton", "laws of motion", "normal force", "friction", "inclined"],
        hint_level_to_trigger=1,
    ),

    Misconception(
        id="friction_opposes_motion_direction",
        pattern_keywords=[
            "friction opposite to motion", "friction is backward",
            "friction opposes movement", "friction always opposes",
            "friction opposite direction of motion",
        ],
        pattern_description="Student believes friction always acts opposite to the direction of motion.",
        correction_prompt=(
            "Friction opposes *relative sliding* between surfaces — not necessarily the direction "
            "of motion of the object. Can you think of a case where friction acts in the "
            "direction of motion? (Hint: think about walking, or a car accelerating from rest.)"
        ),
        concepts_affected=["newton", "laws of motion", "friction", "force"],
        hint_level_to_trigger=1,
    ),

    # ── Work & Energy ─────────────────────────────────────────────────────────

    Misconception(
        id="work_by_normal_force_positive",
        pattern_keywords=[
            "normal force does work", "work done by normal", "work by normal is positive",
            "normal force does positive work", "work done by n",
        ],
        pattern_description="Student thinks normal force does positive work on a horizontally moving object.",
        correction_prompt=(
            "What is the angle between the normal force (perpendicular to the surface) and "
            "the displacement (along the surface)? How does that angle enter the work formula $W = Fd\\cos\\theta$?"
        ),
        concepts_affected=["work", "energy", "work energy", "power"],
        hint_level_to_trigger=1,
    ),

    Misconception(
        id="potential_energy_sign_confusion",
        pattern_keywords=[
            "potential energy negative", "mgh is negative", "pe is negative here",
            "losing height gains negative", "potential energy wrong sign",
            "potential energy decreases going up",
        ],
        pattern_description="Student applies incorrect sign to gravitational potential energy.",
        correction_prompt=(
            "Let's fix the reference point first — where have you placed the zero of potential energy? "
            "Gravitational PE increases as you move *against* gravity (upward). "
            "Can you re-state whether the object gains or loses PE in this step?"
        ),
        concepts_affected=["work", "energy", "potential energy", "conservation"],
        hint_level_to_trigger=1,
    ),

    Misconception(
        id="power_energy_confusion",
        pattern_keywords=[
            "power equals energy", "power same as energy",
            "power is the total energy", "more power means more energy stored",
            "power is energy", "power and energy are the same",
        ],
        pattern_description="Student uses power and energy interchangeably.",
        correction_prompt=(
            "Power is the *rate* of energy transfer — it's energy divided by time ($P = W/t$). "
            "Two engines can do the same total work (same energy) but one does it faster "
            "(higher power). Can you re-express what you said using the correct definition?"
        ),
        concepts_affected=["work", "energy", "power"],
        hint_level_to_trigger=1,
    ),

    # ── Rotational Dynamics ───────────────────────────────────────────────────

    Misconception(
        id="moment_of_inertia_is_mass",
        pattern_keywords=[
            "moment of inertia is mass", "rotational mass is the same",
            "i equals mass", "replace mass with i",
            "inertia is just mass", "i is just m",
        ],
        pattern_description="Student treats moment of inertia as a direct substitute for mass without accounting for distribution.",
        correction_prompt=(
            "Moment of inertia depends on both mass AND how that mass is distributed "
            "relative to the axis of rotation — $I = \\sum mr^2$. "
            "Two objects with equal mass can have very different moments of inertia. "
            "What is the mass distribution in this problem?"
        ),
        concepts_affected=["rotational", "rotation", "moment of inertia", "angular"],
        hint_level_to_trigger=1,
    ),

    Misconception(
        id="torque_direction_rhr_error",
        pattern_keywords=[
            "torque is upward", "torque is downward", "torque into page clockwise",
            "torque out of page anticlockwise wrong", "torque direction",
            "τ direction wrong", "torque direction is",
        ],
        pattern_description="Student makes right-hand rule errors when finding torque direction.",
        correction_prompt=(
            "For the right-hand rule on $\\vec{\\tau} = \\vec{r} \\times \\vec{F}$: "
            "point your fingers along $\\vec{r}$, curl them toward $\\vec{F}$ — "
            "your thumb gives the torque direction. Can you redo this "
            "for the specific $\\vec{r}$ and $\\vec{F}$ in this problem?"
        ),
        concepts_affected=["rotational", "rotation", "torque", "angular"],
        hint_level_to_trigger=1,
    ),

    Misconception(
        id="angular_momentum_always_conserved",
        pattern_keywords=[
            "angular momentum is always conserved", "angular momentum never changes",
            "l is always constant", "angular momentum conserved always",
            "conservation of angular momentum always applies",
        ],
        pattern_description="Student applies angular momentum conservation without checking for external torques.",
        correction_prompt=(
            "Angular momentum is conserved *only* when the net external torque on the system is zero. "
            "In this problem, are there any external torques acting? "
            "(Check: gravity, normal forces, friction — do any of them produce a torque about your chosen axis?)"
        ),
        concepts_affected=["rotational", "rotation", "angular momentum", "angular"],
        hint_level_to_trigger=1,
    ),

    # ── Electrostatics ────────────────────────────────────────────────────────

    Misconception(
        id="efield_direction_negative_charge",
        pattern_keywords=[
            "field points toward positive", "electric field toward positive charge source",
            "field direction is toward the charge", "field goes to negative",
            "field direction for negative is inward wrong", "field toward the source",
        ],
        pattern_description="Student reverses electric field direction for a negative source charge.",
        correction_prompt=(
            "Electric field is always defined as the force on a *positive* test charge divided by its magnitude. "
            "For a negative source charge, which direction would a positive test charge be pulled? "
            "Does the field point toward or away from the source?"
        ),
        concepts_affected=["electrostatics", "electric field", "coulomb", "charges"],
        hint_level_to_trigger=1,
    ),

    Misconception(
        id="superposition_cancels_completely",
        pattern_keywords=[
            "fields cancel completely", "charges cancel each other",
            "total field is zero", "superposition means they cancel",
            "the fields cancel", "net field zero because superposition",
        ],
        pattern_description="Student assumes superposition always results in cancellation rather than vector addition.",
        correction_prompt=(
            "Superposition means we *add* the field vectors from each charge — "
            "they cancel only if they point in exactly opposite directions with equal magnitude. "
            "Can you draw the field vector from each charge at the point of interest "
            "and then add them as vectors?"
        ),
        concepts_affected=["electrostatics", "electric field", "superposition", "charges"],
        hint_level_to_trigger=1,
    ),

    Misconception(
        id="electric_potential_equals_PE",
        pattern_keywords=[
            "potential is energy", "voltage is the energy",
            "electric potential is potential energy", "v equals pe",
            "potential same as potential energy", "potential is joules",
        ],
        pattern_description="Student confuses electric potential (V, in volts) with electric potential energy (PE, in joules).",
        correction_prompt=(
            "Electric potential $V$ and electric potential energy $PE$ are related by $PE = qV$ — "
            "they are not the same. Potential is a property of the field (independent of test charge); "
            "potential energy depends on the charge placed there. "
            "Which one are you being asked to find?"
        ),
        concepts_affected=["electrostatics", "electric potential", "potential energy", "charges"],
        hint_level_to_trigger=1,
    ),

    # ── Current Electricity ───────────────────────────────────────────────────

    Misconception(
        id="current_flows_with_electrons",
        pattern_keywords=[
            "current flows with electrons", "current flows from negative to positive",
            "current direction is electron direction", "conventional current wrong",
            "current in direction of electrons", "electrons flow so current flows same way",
        ],
        pattern_description="Student equates conventional current direction with electron flow direction.",
        correction_prompt=(
            "Conventional current (the $I$ in all circuit equations and Kirchhoff's laws) "
            "flows from the positive terminal to the negative terminal — *opposite* to electron flow. "
            "This is a historical convention, but every formula in the syllabus uses it. "
            "Does using conventional current direction change your analysis?"
        ),
        concepts_affected=["current electricity", "circuit", "current", "resistance"],
        hint_level_to_trigger=1,
    ),

    Misconception(
        id="internal_resistance_adds_voltage",
        pattern_keywords=[
            "terminal voltage higher than emf", "v equals emf plus ir",
            "internal resistance adds to voltage", "v = e + ir",
            "terminal voltage increases with current", "internal resistance adds",
        ],
        pattern_description="Student adds internal resistance voltage drop instead of subtracting it.",
        correction_prompt=(
            "For a cell delivering current, internal resistance *reduces* the terminal voltage: "
            "$V = \\varepsilon - Ir$. The internal resistance causes a voltage drop *inside* the cell. "
            "Which direction is current flowing through the internal resistance in your circuit?"
        ),
        concepts_affected=["current electricity", "circuit", "emf", "internal resistance"],
        hint_level_to_trigger=1,
    ),

    Misconception(
        id="kvl_sign_convention_error",
        pattern_keywords=[
            "all positive in the loop", "all voltages add up",
            "kvl signs wrong", "kirchhoff sign error",
            "loop equation signs", "voltage rises in loop",
        ],
        pattern_description="Student applies KVL without a consistent sign convention for voltage drops and rises.",
        correction_prompt=(
            "In KVL: first choose a traversal direction. Then — crossing a resistor *in* the direction "
            "of current is a drop ($-IR$); crossing a battery from $-$ to $+$ is a rise ($+\\varepsilon$). "
            "Can you redo the loop equation with these sign rules?"
        ),
        concepts_affected=["current electricity", "circuit", "kirchhoff", "kvl"],
        hint_level_to_trigger=1,
    ),

    # ── Waves ─────────────────────────────────────────────────────────────────

    Misconception(
        id="node_maximum_displacement",
        pattern_keywords=[
            "node maximum", "node vibrates most", "node has maximum amplitude",
            "node high amplitude", "node oscillates the most",
            "antinode zero displacement", "antinode no displacement",
        ],
        pattern_description="Student swaps the definitions of node and antinode in standing waves.",
        correction_prompt=(
            "Nodes are points of *zero* displacement — the string doesn't move there at all. "
            "Antinodes have *maximum* displacement — maximum oscillation. "
            "With this in mind, where are the nodes and antinodes in your standing wave setup?"
        ),
        concepts_affected=["waves", "standing wave", "node", "antinode"],
        hint_level_to_trigger=1,
    ),

    Misconception(
        id="standing_wave_phase_all_same",
        pattern_keywords=[
            "all points same phase", "standing wave all in phase",
            "phase difference standing wave is zero", "no phase difference standing",
            "standing wave same phase everywhere",
        ],
        pattern_description="Student thinks all points in a standing wave are in phase with each other.",
        correction_prompt=(
            "In a standing wave, all points *between* two adjacent nodes are in phase with each other, "
            "but they are out of phase (by 180°) with points on the other side of a node. "
            "How many nodes does your standing wave have, and which points are you comparing?"
        ),
        concepts_affected=["waves", "standing wave", "phase", "superposition"],
        hint_level_to_trigger=1,
    ),

    Misconception(
        id="path_difference_sign_error",
        pattern_keywords=[
            "path difference negative", "negative path difference constructive",
            "s1 minus s2 negative means destructive", "path difference sign matters",
            "negative path difference means",
        ],
        pattern_description="Student uses the signed path difference rather than its magnitude for interference conditions.",
        correction_prompt=(
            "Path difference for interference is $|S_1P - S_2P|$ — the absolute value. "
            "Constructive interference: $|\\Delta| = n\\lambda$; destructive: $|\\Delta| = (n+\\frac{1}{2})\\lambda$. "
            "The sign of the path difference alone doesn't determine constructive or destructive. "
            "Can you recalculate using the magnitude?"
        ),
        concepts_affected=["waves", "interference", "path difference", "young"],
        hint_level_to_trigger=1,
    ),

    # ── Thermodynamics ────────────────────────────────────────────────────────

    Misconception(
        id="isothermal_means_no_heat",
        pattern_keywords=[
            "isothermal no heat", "isothermal means no heat exchange",
            "isothermal q is zero", "isothermal adiabatic same",
            "isothermal heat zero",
        ],
        pattern_description="Student confuses isothermal (constant temperature) with adiabatic (no heat exchange).",
        correction_prompt=(
            "Isothermal means *constant temperature* — heat CAN flow in or out to maintain T. "
            "Adiabatic means *no heat exchange* — temperature can (and does) change. "
            "Which process is the one where $\\Delta T = 0$? Which is the one where $Q = 0$?"
        ),
        concepts_affected=["thermodynamics", "heat", "isothermal", "adiabatic"],
        hint_level_to_trigger=1,
    ),

    Misconception(
        id="entropy_always_increases_subsystem",
        pattern_keywords=[
            "entropy always increases", "entropy never decreases",
            "entropy must always increase", "impossible for entropy to decrease",
            "entropy can only go up",
        ],
        pattern_description="Student applies the entropy increase principle to a subsystem rather than the universe.",
        correction_prompt=(
            "The second law states that *total entropy of the universe* (system + surroundings) "
            "increases — but entropy of a *subsystem* can decrease if the surroundings gain more. "
            "A refrigerator reduces entropy inside the fridge. Is your system isolated, "
            "or is it exchanging energy with its surroundings?"
        ),
        concepts_affected=["thermodynamics", "entropy", "second law"],
        hint_level_to_trigger=1,
    ),

    Misconception(
        id="work_sign_by_vs_on_gas",
        pattern_keywords=[
            "work done on gas positive expansion", "expansion positive work on gas",
            "w positive when gas expands wrong", "work by gas negative expansion",
            "work sign convention gas wrong", "expansion work negative",
        ],
        pattern_description="Student mixes up the 'work done by gas' and 'work done on gas' sign conventions.",
        correction_prompt=(
            "Let's fix the convention first. Work done *by* the gas: $W = P\\Delta V$ — "
            "positive for expansion, negative for compression. "
            "The first law then reads $\\Delta U = Q - W_{\\text{by}}$. "
            "Are you consistently using the 'by' convention throughout your calculation?"
        ),
        concepts_affected=["thermodynamics", "work", "first law", "gas"],
        hint_level_to_trigger=1,
    ),

    # ── Additional entries to reach 30 ────────────────────────────────────────

    Misconception(
        id="gravity_zero_in_orbit",
        pattern_keywords=[
            "no gravity in space", "gravity is zero orbit", "weightless means no gravity",
            "astronaut zero gravity", "gravity absent in orbit", "zero gravity in satellite",
        ],
        pattern_description="Student believes gravity is zero in orbit or space, confusing weightlessness with zero gravity.",
        correction_prompt=(
            "Gravity doesn't vanish in orbit — it's actually providing the centripetal force "
            "that keeps the satellite moving in a circle. Weightlessness occurs because both "
            "the astronaut and the spacecraft are in free fall together. "
            "What is the gravitational force on the satellite at that orbital radius?"
        ),
        concepts_affected=["gravitation", "gravity", "satellite", "orbit"],
        hint_level_to_trigger=1,
    ),

    Misconception(
        id="heavier_objects_fall_faster",
        pattern_keywords=[
            "heavier falls faster", "more mass falls faster", "heavy object reaches first",
            "mass affects fall time", "heavier object hits ground first",
        ],
        pattern_description="Student believes heavier objects fall faster than lighter ones (ignoring air resistance).",
        correction_prompt=(
            "In free fall (ignoring air resistance), all objects have the same acceleration $g$ "
            "regardless of mass — this is what Galileo showed. In Newton's law: "
            "$F = mg$, $a = F/m = g$, the mass cancels. "
            "Does the problem specify air resistance? If not, how does this change your answer?"
        ),
        concepts_affected=["gravitation", "gravity", "free fall", "newton", "kinematics"],
        hint_level_to_trigger=1,
    ),

    Misconception(
        id="image_distance_always_positive",
        pattern_keywords=[
            "image distance positive always", "v is always positive",
            "distance cannot be negative", "image distance negative wrong",
            "v negative means error",
        ],
        pattern_description="Student assumes image distance is always positive, ignoring the sign convention for mirrors/lenses.",
        correction_prompt=(
            "In the standard sign convention (New Cartesian), distances are measured from the "
            "pole/optical centre. Distances in the direction of incident light are positive; "
            "against it are negative. A negative image distance tells you something physical — "
            "what does it indicate about where the image is formed?"
        ),
        concepts_affected=["optics", "ray optics", "mirror", "lens", "refraction"],
        hint_level_to_trigger=1,
    ),

    Misconception(
        id="current_same_everywhere_series",
        pattern_keywords=[
            "current splits in series", "different current each resistor series",
            "current divides series", "series current different",
            "current not same series",
        ],
        pattern_description="Student thinks current is different through each component in a series circuit.",
        correction_prompt=(
            "In a series circuit, there is only one path for current — so the *same* current "
            "flows through every component. Current only splits at a junction in a parallel circuit. "
            "Is your circuit series or parallel at the section you're analysing?"
        ),
        concepts_affected=["current electricity", "circuit", "series", "resistance"],
        hint_level_to_trigger=1,
    ),

    Misconception(
        id="voltage_same_everywhere_parallel",
        pattern_keywords=[
            "voltage different parallel", "voltage splits parallel",
            "different voltage across parallel", "parallel voltage unequal",
            "voltage divides in parallel",
        ],
        pattern_description="Student thinks voltage is different across parallel branches.",
        correction_prompt=(
            "Components in parallel share the *same* two nodes — so voltage across each is identical. "
            "It's the *current* that splits in parallel. "
            "Can you redraw the section of the circuit and label which nodes each component connects between?"
        ),
        concepts_affected=["current electricity", "circuit", "parallel", "resistance"],
        hint_level_to_trigger=1,
    ),

    Misconception(
        id="displacement_equals_distance",
        pattern_keywords=[
            "displacement equals distance", "displacement same as distance",
            "displacement is the total path", "distance and displacement same",
            "displacement is total distance travelled",
        ],
        pattern_description="Student treats displacement and distance as the same quantity, ignoring direction.",
        correction_prompt=(
            "Distance is the total length of the path taken (a scalar). "
            "Displacement is the straight-line vector from start to finish — "
            "it depends only on where you begin and end, not how you get there. "
            "Can you give an example where the distance is large but the displacement is zero?"
        ),
        concepts_affected=["kinematics", "motion", "displacement", "velocity"],
        hint_level_to_trigger=1,
        subject="Physics",
    ),

    # ── Chemistry Misconceptions ──────────────────────────────────────────────

    Misconception(
        id="le_chatelier_wrong_direction",
        pattern_keywords=["le chatelier", "equilibrium shift", "adds product shifts right",
                          "product added shifts forward", "adding product equilibrium right"],
        pattern_description="Confusing direction of Le Chatelier shift — adding a product shifts equilibrium LEFT, not right.",
        correction_prompt=(
            "When a product is added to an equilibrium mixture, the reaction shifts to the left "
            "(toward reactants) to re-establish equilibrium. Le Chatelier's principle: system opposes "
            "the change. If you add a product, which direction must the reaction shift to consume it?"
        ),
        concepts_affected=["chemical equilibrium", "le chatelier", "equilibrium"],
        hint_level_to_trigger=1,
        subject="Chemistry",
    ),

    Misconception(
        id="cell_emf_sign_error",
        pattern_keywords=["cell potential negative", "emf wrong sign", "anode cathode confused",
                          "cathode negative emf", "reduction at anode"],
        pattern_description="Sign error in cell EMF calculation — confusing cathode and anode.",
        correction_prompt=(
            "Cell EMF = E_cathode − E_anode. Reduction occurs at the cathode (higher reduction potential). "
            "A positive EMF means the reaction is spontaneous. Which electrode has the higher reduction "
            "potential in this cell, and are you subtracting in the correct order?"
        ),
        concepts_affected=["electrochemistry", "cell potential", "emf"],
        hint_level_to_trigger=1,
        subject="Chemistry",
    ),

    Misconception(
        id="molarity_molality_confusion",
        pattern_keywords=["molarity molality same", "molality per litre", "molarity per kg",
                          "molarity kilogram solvent", "molality per litre solution"],
        pattern_description="Confusing molarity (mol/L of solution) with molality (mol/kg of solvent).",
        correction_prompt=(
            "Molarity (M) = moles of solute / litres of SOLUTION. "
            "Molality (m) = moles of solute / kg of SOLVENT. "
            "They differ because solution volume changes with temperature, but solvent mass does not. "
            "Which one does this problem ask for?"
        ),
        concepts_affected=["solutions", "molarity", "molality", "mole concept"],
        hint_level_to_trigger=1,
        subject="Chemistry",
    ),

    Misconception(
        id="order_vs_molecularity",
        pattern_keywords=["order same as molecularity", "molecularity can be fractional",
                          "order always integer", "molecularity from rate law",
                          "order from mechanism directly"],
        pattern_description="Confusing order of reaction (experimental) with molecularity (theoretical, elementary step).",
        correction_prompt=(
            "Molecularity is the number of molecules in the rate-determining elementary step — always a "
            "positive integer. Order of reaction is determined experimentally from the rate law and can be "
            "fractional or zero. Can you identify which quantity the problem is asking you to find, and "
            "how each is determined?"
        ),
        concepts_affected=["chemical kinetics", "rate", "order", "molecularity"],
        hint_level_to_trigger=1,
        subject="Chemistry",
    ),

    Misconception(
        id="bohr_model_all_atoms",
        pattern_keywords=["bohr model all atoms", "orbit applies to carbon", "shell model all elements",
                          "fixed orbit multielectron", "circular orbit all atoms"],
        pattern_description="Applying Bohr model to multi-electron atoms where it is not valid.",
        correction_prompt=(
            "The Bohr model only works for hydrogen-like (single-electron) atoms. For multi-electron atoms, "
            "use quantum mechanical orbitals — electrons exist in probability clouds described by wavefunctions, "
            "not fixed circular orbits. Which type of atom does this problem involve?"
        ),
        concepts_affected=["atomic structure", "bohr model", "quantum", "orbit"],
        hint_level_to_trigger=1,
        subject="Chemistry",
    ),

    Misconception(
        id="negative_dh_always_spontaneous",
        pattern_keywords=["negative enthalpy spontaneous", "exothermic always spontaneous",
                          "negative delta h means spontaneous", "delta h negative so spontaneous"],
        pattern_description="Thinking a negative ΔH alone makes a reaction spontaneous.",
        correction_prompt=(
            "Spontaneity is determined by ΔG = ΔH − TΔS, not ΔH alone. A reaction with negative ΔH "
            "can be non-spontaneous if TΔS is more negative. What is the sign of ΔS for this reaction, "
            "and how does temperature affect the ΔG?"
        ),
        concepts_affected=["thermodynamics", "gibbs", "spontaneous", "entropy", "enthalpy"],
        hint_level_to_trigger=1,
        subject="Chemistry",
    ),

    Misconception(
        id="sn2_tertiary_carbon",
        pattern_keywords=["sn2 tertiary", "tertiary sn2 mechanism", "backside attack tertiary",
                          "sn2 works on tertiary", "tertiary carbon sn2"],
        pattern_description="Applying SN2 mechanism to tertiary carbons where backside attack is sterically blocked.",
        correction_prompt=(
            "SN2 (bimolecular nucleophilic substitution) requires backside attack — sterically impossible "
            "at tertiary carbons due to three bulky substituents. Tertiary substrates undergo SN1 via a "
            "carbocation intermediate. What is the substrate structure here, and which mechanism does it favour?"
        ),
        concepts_affected=["organic chemistry", "nucleophile", "sn1", "sn2", "substitution"],
        hint_level_to_trigger=1,
        subject="Chemistry",
    ),

    Misconception(
        id="high_electronegativity_always_ionic",
        pattern_keywords=["high electronegativity ionic always", "electronegativity difference ionic",
                          "large electronegativity ionic bond", "big difference always ionic"],
        pattern_description="Thinking high electronegativity difference always produces an ionic bond.",
        correction_prompt=(
            "Electronegativity difference > 1.7 suggests predominantly ionic character, but bonding is a "
            "spectrum. Even with high ΔEN, coordinate geometry and molecular properties must be considered. "
            "HF has high ΔEN but is a molecular compound. What other evidence — melting point, conductivity, "
            "solubility — supports the bond type here?"
        ),
        concepts_affected=["chemical bonding", "ionic", "covalent", "electronegativity"],
        hint_level_to_trigger=1,
        subject="Chemistry",
    ),

    Misconception(
        id="colligative_forget_vant_hoff",
        pattern_keywords=["colligative electrolyte", "freezing point nacl", "boiling point ionic",
                          "van't hoff forget", "colligative without i"],
        pattern_description="Forgetting van't Hoff factor i for electrolytes in colligative properties.",
        correction_prompt=(
            "For electrolytes that dissociate, the colligative property = i × (non-electrolyte value), "
            "where i = number of ions formed per formula unit. NaCl → 2 ions (i=2), so "
            "ΔTf = i × Kf × m = 2 × Kf × m. Have you included the van't Hoff factor for this solute?"
        ),
        concepts_affected=["solutions", "colligative", "freezing point", "boiling point", "osmotic"],
        hint_level_to_trigger=1,
        subject="Chemistry",
    ),

    Misconception(
        id="oxidation_reduction_reversed",
        pattern_keywords=["oxidation gain electrons", "reduction lose electrons",
                          "oxidation is gain", "reduction is loss", "oil rig wrong"],
        pattern_description="Confusing oxidation (loss of electrons) with reduction (gain of electrons).",
        correction_prompt=(
            "OIL RIG: Oxidation Is Loss (of electrons), Reduction Is Gain (of electrons). "
            "The oxidizing agent gets REDUCED (gains electrons); the reducing agent gets OXIDIZED "
            "(loses electrons). With this rule, which species is oxidized in this reaction?"
        ),
        concepts_affected=["redox", "oxidation", "reduction", "oxidation state"],
        hint_level_to_trigger=1,
        subject="Chemistry",
    ),

    Misconception(
        id="ideal_gas_always_valid",
        pattern_keywords=["ideal gas high pressure", "pv nrt high pressure",
                          "ideal gas law always", "pv nrt always applies"],
        pattern_description="Applying ideal gas law PV=nRT under conditions that require van der Waals corrections.",
        correction_prompt=(
            "PV=nRT is valid only at LOW pressure and HIGH temperature (conditions where intermolecular "
            "forces and molecular volume are negligible). At high pressure or low temperature, use van der "
            "Waals equation: (P + an²/V²)(V − nb) = nRT. What are the conditions in this problem?"
        ),
        concepts_affected=["gaseous state", "ideal gas", "pressure", "van der waals"],
        hint_level_to_trigger=1,
        subject="Chemistry",
    ),

    Misconception(
        id="coordination_number_vs_oxidation_state",
        pattern_keywords=["coordination number same as charge", "coordination number oxidation",
                          "oxidation state equals coordination", "cn equals charge"],
        pattern_description="Confusing coordination number with oxidation state of central metal.",
        correction_prompt=(
            "Coordination number = total number of ligand donor atoms bonded to the central metal. "
            "Oxidation state is the charge on the metal. In [Co(NH3)6]³⁺, Co has coordination number 6 "
            "and oxidation state +3 — they happen to be different numbers. "
            "Can you identify both separately for the complex in this problem?"
        ),
        concepts_affected=["coordination chemistry", "complex", "ligand", "coordination number"],
        hint_level_to_trigger=1,
        subject="Chemistry",
    ),

    Misconception(
        id="adsorption_absorption_confused",
        pattern_keywords=["adsorption bulk", "absorption surface", "adsorption throughout",
                          "absorption only surface", "charcoal absorbs"],
        pattern_description="Confusing adsorption (surface phenomenon) with absorption (bulk phenomenon).",
        correction_prompt=(
            "Adsorption occurs ON the surface — molecules stick to the surface of the adsorbent. "
            "Absorption occurs THROUGHOUT the bulk — molecules are taken into the absorbent material. "
            "Charcoal adsorbs gases; silica gel adsorbs water vapor. Which process does this problem describe?"
        ),
        concepts_affected=["surface chemistry", "adsorption", "absorption", "catalyst"],
        hint_level_to_trigger=1,
        subject="Chemistry",
    ),

    Misconception(
        id="faraday_current_vs_charge",
        pattern_keywords=["faraday current not time", "moles from current only",
                          "electrolysis current directly", "faraday law current moles"],
        pattern_description="Wrong application of Faraday's law — confusing charge with current.",
        correction_prompt=(
            "Faraday's first law uses CHARGE (Q = It, in coulombs), not just current. "
            "Moles deposited = Q / (n × F), where n = electrons transferred per ion, F = 96485 C/mol. "
            "Current alone tells you nothing without the time. Have you calculated Q = I × t first?"
        ),
        concepts_affected=["electrochemistry", "electrolysis", "faraday", "current"],
        hint_level_to_trigger=1,
        subject="Chemistry",
    ),

    Misconception(
        id="vsepr_ignore_lone_pairs",
        pattern_keywords=["lone pair no effect geometry", "lone pair ignored shape",
                          "nh3 trigonal planar", "h2o linear", "lone pair not counted"],
        pattern_description="Predicting wrong molecular geometry by ignoring lone pairs in VSEPR.",
        correction_prompt=(
            "In VSEPR theory, lone pairs count as electron domains and repel MORE strongly than bond pairs, "
            "compressing bond angles. NH3 has 3 bonds + 1 lone pair → trigonal pyramidal (not trigonal planar). "
            "H2O has 2 bonds + 2 lone pairs → bent/V-shaped (not linear). "
            "Can you count all electron domains — bonding AND lone pairs — for this molecule?"
        ),
        concepts_affected=["p-block", "hybridization", "vsepr", "lone pair", "shape", "geometry"],
        hint_level_to_trigger=1,
        subject="Chemistry",
    ),

    # ── Maths Misconceptions ─────────────────────────────────────────────────

    Misconception(
        id="integration_missing_constant",
        pattern_keywords=["integral no constant", "indefinite integral no c",
                          "antiderivative without c", "forgot constant of integration"],
        pattern_description="Forgetting the constant of integration C in indefinite integrals.",
        correction_prompt=(
            "Every indefinite integral must include +C (constant of integration) because differentiating "
            "any constant gives zero. ∫f(x)dx = F(x) + C. Only definite integrals (with limits) give a "
            "specific numerical value without C. Did you include +C in your answer?"
        ),
        concepts_affected=["integration", "integral", "antiderivative", "calculus"],
        hint_level_to_trigger=1,
        subject="Maths",
    ),

    Misconception(
        id="indeterminate_form_treated_as_value",
        pattern_keywords=["0/0 equals 0", "infinity over infinity equals 1",
                          "indeterminate is zero", "0/0 is undefined so skip",
                          "limit doesn't exist 0/0"],
        pattern_description="Treating 0/0 or ∞/∞ as having a definite value without applying L'Hôpital or factoring.",
        correction_prompt=(
            "0/0 and ∞/∞ are indeterminate forms — not actual values. They indicate you must do more work. "
            "Apply L'Hôpital's rule (differentiate numerator and denominator separately), or factor/"
            "rationalize the expression to resolve the form. Which technique applies to this limit?"
        ),
        concepts_affected=["limits", "limit", "infinity", "indeterminate", "lhopital"],
        hint_level_to_trigger=1,
        subject="Maths",
    ),

    Misconception(
        id="permutation_combination_confusion",
        pattern_keywords=["arrangement combination", "selection order matters",
                          "combination with order", "permutation selection only",
                          "ncr for arrangement", "npr for selection"],
        pattern_description="Confusing permutation (order matters) with combination (order doesn't matter).",
        correction_prompt=(
            "Use permutation nPr = n!/(n−r)! when arrangement ORDER matters (seating, ranking). "
            "Use combination nCr = n!/[r!(n−r)!] when only SELECTION matters, not order (choosing a committee). "
            "Ask: if I swap the positions of two selected items, do I get a different outcome? "
            "If yes → permutation. If no → combination."
        ),
        concepts_affected=["permutations", "combinations", "counting", "arrangements"],
        hint_level_to_trigger=1,
        subject="Maths",
    ),

    Misconception(
        id="chain_rule_forgotten",
        pattern_keywords=["chain rule forgot", "composite derivative wrong",
                          "sin x squared derivative cos x squared",
                          "derivative of f of g without inner derivative",
                          "forgot inner function derivative"],
        pattern_description="Forgetting to apply the chain rule when differentiating composite functions.",
        correction_prompt=(
            "For composite f(g(x)), the chain rule requires multiplying by the derivative of the inner "
            "function: d/dx[f(g(x))] = f'(g(x)) · g'(x). "
            "Example: d/dx[sin(x²)] = cos(x²) · 2x, not just cos(x²). "
            "What is the inner function g(x) in this expression, and what is g'(x)?"
        ),
        concepts_affected=["differentiation", "chain rule", "derivative", "composite"],
        hint_level_to_trigger=1,
        subject="Maths",
    ),

    Misconception(
        id="mutually_exclusive_independent",
        pattern_keywords=["mutually exclusive independent", "exclusive means independent",
                          "cannot occur together means independent",
                          "independent means cannot both happen"],
        pattern_description="Treating mutually exclusive events as independent events.",
        correction_prompt=(
            "Mutually exclusive events cannot happen simultaneously: P(A∩B)=0. "
            "Independent events do not affect each other: P(A∩B)=P(A)·P(B). "
            "Mutually exclusive events with P(A)>0 and P(B)>0 are actually DEPENDENT — knowing A occurred "
            "tells you B cannot. Can you identify which relationship applies here?"
        ),
        concepts_affected=["probability", "independent", "mutually exclusive", "events"],
        hint_level_to_trigger=1,
        subject="Maths",
    ),

    Misconception(
        id="matrix_multiplication_commutative",
        pattern_keywords=["ab equals ba matrix", "matrix multiplication commutative",
                          "ab same as ba matrices", "matrices commute always"],
        pattern_description="Assuming matrix multiplication is commutative: AB = BA.",
        correction_prompt=(
            "Matrix multiplication is NOT commutative in general: AB ≠ BA. Always maintain the order. "
            "(AB)ᵀ = BᵀAᵀ (order reverses on transpose). Only special cases like diagonal matrices "
            "or the identity matrix satisfy AB=BA. Can you try a 2×2 counterexample to verify?"
        ),
        concepts_affected=["matrices", "matrix", "multiplication", "product"],
        hint_level_to_trigger=1,
        subject="Maths",
    ),

    Misconception(
        id="inverse_trig_outside_principal_branch",
        pattern_keywords=["arcsin 200", "sin inverse 200", "inverse sin outside range",
                          "sin inverse greater than 90", "arcsin 150 degrees"],
        pattern_description="Taking inverse trig outside principal value branch — e.g. sin⁻¹(sin(200°)) = 200°.",
        correction_prompt=(
            "Inverse trig functions have restricted domains: sin⁻¹ range is [−π/2, π/2], cos⁻¹ range is [0,π], "
            "tan⁻¹ range is (−π/2, π/2). sin⁻¹(sin(200°)) ≠ 200°. First use the identity to bring the angle "
            "inside the principal range. What quadrant is 200° in, and how do you reduce it?"
        ),
        concepts_affected=["trigonometry", "inverse", "arcsin", "principal value"],
        hint_level_to_trigger=1,
        subject="Maths",
    ),

    Misconception(
        id="infinite_gp_no_convergence_check",
        pattern_keywords=["infinite gp sum any r", "gp sum formula always",
                          "infinite series sum without checking r",
                          "a over 1 minus r always valid"],
        pattern_description="Applying infinite GP sum formula S = a/(1−r) without checking |r| < 1.",
        correction_prompt=(
            "The infinite geometric series S∞ = a/(1−r) is only valid when |r| < 1 (series converges). "
            "If |r| ≥ 1, the series diverges and has no finite sum. "
            "What is the common ratio r in this series, and does |r| < 1 hold?"
        ),
        concepts_affected=["sequences", "series", "geometric", "infinite", "convergence"],
        hint_level_to_trigger=1,
        subject="Maths",
    ),

    Misconception(
        id="differential_equation_no_particular_solution",
        pattern_keywords=["general solution only", "forgot initial condition de",
                          "differential equation general answer", "no particular solution"],
        pattern_description="Stopping at the general solution without applying initial conditions.",
        correction_prompt=(
            "The general solution contains arbitrary constants (C₁, C₂, etc.). A particular solution "
            "requires substituting the given initial/boundary conditions to find specific constant values. "
            "Don't stop at the general solution when initial conditions are provided. "
            "Have you substituted the given values to find C?"
        ),
        concepts_affected=["differential equations", "particular solution", "initial condition"],
        hint_level_to_trigger=1,
        subject="Maths",
    ),

    Misconception(
        id="dot_product_cross_product_confusion",
        pattern_keywords=["dot product vector result", "cross product scalar",
                          "dot product perpendicular vector", "a dot b gives vector",
                          "cross product gives scalar"],
        pattern_description="Confusing dot product (scalar result) with cross product (vector result).",
        correction_prompt=(
            "Dot product a⃗·b⃗ = |a||b|cosθ gives a SCALAR — use it for projection or finding angles. "
            "Cross product a⃗×b⃗ = |a||b|sinθ n̂ gives a VECTOR perpendicular to both — use it for area or "
            "perpendicularity. Also note: a⃗×b⃗ = −b⃗×a⃗ (anti-commutative). "
            "Which operation does this problem require?"
        ),
        concepts_affected=["vectors", "cross product", "dot product", "scalar"],
        hint_level_to_trigger=1,
        subject="Maths",
    ),

    Misconception(
        id="binomial_rth_term_off_by_one",
        pattern_keywords=["rth term binomial formula r", "binomial r term uses r",
                          "third term r equals 3", "binomial term r not r minus 1"],
        pattern_description="Off-by-one error: using r in the general term formula instead of (r−1).",
        correction_prompt=(
            "In (a+b)ⁿ, the GENERAL term is T(r+1) = ⁿCᵣ · aⁿ⁻ʳ · bʳ, where r starts from 0. "
            "So T₁ uses r=0, T₂ uses r=1, etc. To find the rth term, set r+1 = target, so r = target−1. "
            "Which term are you finding, and what value of r should you substitute?"
        ),
        concepts_affected=["binomial theorem", "binomial", "expansion", "term"],
        hint_level_to_trigger=1,
        subject="Maths",
    ),

    Misconception(
        id="complex_modulus_real_part",
        pattern_keywords=["modulus equals real part", "modulus is a", "modulus re z",
                          "argument wrong quadrant", "argument always arctan b over a"],
        pattern_description="Confusing modulus |z| with the real part of z, or wrong argument quadrant.",
        correction_prompt=(
            "For z = a+bi: modulus |z| = √(a²+b²), NOT just a. "
            "Argument θ = tan⁻¹(b/a) but you MUST adjust for the quadrant. "
            "For z in Q2: θ = π − tan⁻¹(|b/a|). For z in Q3: θ = −(π − tan⁻¹(|b/a|)). "
            "Always draw the Argand diagram first. Which quadrant is your complex number in?"
        ),
        concepts_affected=["complex numbers", "complex", "modulus", "argument", "argand"],
        hint_level_to_trigger=1,
        subject="Maths",
    ),

    Misconception(
        id="ellipse_hyperbola_relation_mixed",
        pattern_keywords=["ellipse c squared a squared plus b squared",
                          "hyperbola c squared a squared minus b squared",
                          "ellipse relation hyperbola formula", "c squared wrong conic"],
        pattern_description="Using wrong c²=a²+b² vs c²=a²−b² relationship for ellipse vs hyperbola.",
        correction_prompt=(
            "For ellipse x²/a²+y²/b²=1 (a>b): c²=a²−b² and e=c/a<1. "
            "For hyperbola x²/a²−y²/b²=1: c²=a²+b² and e=c/a>1. "
            "Key: ellipse SUBTRACTS (c²=a²−b²), hyperbola ADDS (c²=a²+b²). "
            "Which conic is this problem about, and which formula applies?"
        ),
        concepts_affected=["conic sections", "ellipse", "hyperbola", "eccentricity"],
        hint_level_to_trigger=1,
        subject="Maths",
    ),

    Misconception(
        id="singular_matrix_has_inverse",
        pattern_keywords=["singular matrix inverse", "determinant zero inverse",
                          "det zero but find inverse", "zero determinant invert"],
        pattern_description="Thinking a matrix with zero determinant has an inverse.",
        correction_prompt=(
            "A matrix is invertible (non-singular) if and only if its determinant is NON-ZERO. "
            "If det(A)=0, the matrix is singular — it has no inverse, and the system Ax=b has "
            "either no solution or infinitely many solutions. "
            "What is the determinant of this matrix?"
        ),
        concepts_affected=["determinants", "matrices", "inverse", "singular"],
        hint_level_to_trigger=1,
        subject="Maths",
    ),

    Misconception(
        id="critical_point_extremum_no_second_derivative",
        pattern_keywords=["f prime zero means maxima", "f prime zero is minimum",
                          "critical point is always extremum", "f zero derivative extremum always"],
        pattern_description="Declaring a critical point (f'(x)=0) as maxima/minima without verifying via second derivative test.",
        correction_prompt=(
            "f'(c)=0 is necessary but not sufficient for a local extremum — it could be a point of inflection. "
            "Use the second derivative test: f''(c)<0 → local max, f''(c)>0 → local min, "
            "f''(c)=0 → inconclusive (use the first derivative sign change test instead). "
            "Have you applied the second derivative test at this critical point?"
        ),
        concepts_affected=["applications of derivatives", "maxima", "minima", "critical point"],
        hint_level_to_trigger=1,
        subject="Maths",
    ),
]

# ── Fast keyword checker ──────────────────────────────────────────────────────

def check_for_misconception(
    student_response: str,
    topic: str,
    subject: str = "Physics",
) -> Optional[Misconception]:
    """
    Check a student's response for known misconceptions relevant to the current topic and subject.

    - Pure keyword matching — no LLM call, runs in < 1 ms.
    - Subject filter applied first — Physics questions only match Physics misconceptions, etc.
    - Topic is matched case-insensitively against each misconception's concepts_affected.
    - Returns the first matched Misconception, or None.

    Args:
        student_response: The student's raw text response.
        topic: Topic string from problem analysis (e.g. "Circular Motion", "Electrostatics",
               "Chemical Equilibrium", "Integration").
        subject: Subject filter — "Physics", "Chemistry", or "Maths". Defaults to "Physics"
                 for backward compatibility. Pass the detected subject from analysis.

    Returns:
        Matched Misconception or None.
    """
    response_lower = student_response.lower()
    topic_lower = topic.lower()

    # First pass: topic + keyword match (strict — the original behaviour).
    for m in MISCONCEPTION_LIBRARY:
        if m.subject != subject:
            continue
        topic_match = any(
            ca.lower() in topic_lower or topic_lower in ca.lower()
            for ca in m.concepts_affected
        )
        if not topic_match:
            continue
        if any(kw in response_lower for kw in m.pattern_keywords):
            return m

    # v0.20.8 second pass: topic-agnostic fallback. The problem-analysis LLM
    # sometimes classifies a circular-motion misconception prompt under the
    # coarser "Laws of Motion" topic, or returns a generic subtopic that
    # doesn't overlap concepts_affected. When that happens, the first pass
    # misses even though the student's response has strong misconception
    # signal (multiple pattern_keywords present).
    #
    # Safe expansion: require ≥2 keyword hits (so a single incidental word
    # like "outward" won't false-trigger). Pattern keywords are specific
    # enough — "centrifugal", "outward force", "flying outward" — that two
    # co-occurring hits in one student turn is overwhelmingly a real
    # misconception.
    for m in MISCONCEPTION_LIBRARY:
        if m.subject != subject:
            continue
        hits = sum(1 for kw in m.pattern_keywords if kw in response_lower)
        if hits >= 2:
            return m

    return None

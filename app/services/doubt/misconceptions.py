"""
Misconception detection library for JEE Physics.

Entry points:
    check_for_misconception(student_response, topic) → Misconception | None

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


# ── Library ───────────────────────────────────────────────────────────────────

MISCONCEPTION_LIBRARY: list[Misconception] = [

    # ── Circular Motion ───────────────────────────────────────────────────────

    Misconception(
        id="centripetal_outward_force",
        pattern_keywords=[
            "centrifugal", "outward force", "pushed outward", "outward pull",
            "flying outward", "force outward", "outward push", "moves outward because of force",
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
    ),
]

# ── Fast keyword checker ──────────────────────────────────────────────────────

def check_for_misconception(
    student_response: str,
    topic: str,
) -> Optional[Misconception]:
    """
    Check a student's response for known misconceptions relevant to the current topic.

    - Pure keyword matching — no LLM call, runs in < 1 ms.
    - Topic is matched case-insensitively against each misconception's concepts_affected.
    - Returns the first matched Misconception, or None.

    Args:
        student_response: The student's raw text response.
        topic: Topic string from problem analysis (e.g. "Circular Motion", "Electrostatics").

    Returns:
        Matched Misconception or None.
    """
    response_lower = student_response.lower()
    topic_lower = topic.lower()

    for m in MISCONCEPTION_LIBRARY:
        # Topic scope filter: skip if no concept_affected overlaps with topic
        topic_match = any(
            ca.lower() in topic_lower or topic_lower in ca.lower()
            for ca in m.concepts_affected
        )
        if not topic_match:
            continue

        # Keyword match
        if any(kw in response_lower for kw in m.pattern_keywords):
            return m

    return None

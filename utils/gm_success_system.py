"""
Enhanced GM Success System for Star Wars RP Bot

This module implements a sophisticated action resolution system that:
- Evaluates player actions through multiple factors (not just RNG)
- Scales difficulty meaningfully
- Rewards clever planning and preparation
- Respects objective technical/physical limitations
- Provides structured outcomes for the AI to interpret
"""

from pydantic import BaseModel
from typing import Literal, Optional
import random


class ActionContext(BaseModel):
    """Context information about the action being attempted"""
    action_description: str
    difficulty_setting: str  # easy, medium, hard, extreme, impossible, realistic
    player_preparation: str  # What the player did to prepare/plan
    relevant_skills: list[str]  # Player's relevant skills/background
    equipment_advantages: list[str]  # Gear/tech that helps
    environmental_factors: list[str]  # Situational modifiers
    opposition_strength: str  # Strength of whatever opposes success


class SuccessFactors(BaseModel):
    """Breakdown of factors influencing success"""
    base_difficulty_dc: int  # 1-100 target number
    cleverness_bonus: int  # -30 to +30 bonus for smart/dumb plans
    technical_modifier: int  # -20 to +20 for objective advantages/disadvantages
    environmental_modifier: int  # -15 to +15 for circumstances
    final_target: int  # What needs to be rolled over
    dice_roll: int  # The random element (1-100)
    total_score: int  # dice_roll + all bonuses
    success: bool
    success_degree: Literal["critical_failure", "failure", "partial_success", "success", "critical_success"]


class OutcomeGuidance(BaseModel):
    """Guidance for the AI on how to narrate the outcome"""
    success_factors: SuccessFactors
    narration_guidance: str
    consequences: list[str]
    opportunities: list[str]  # What the player can do next


# Difficulty to base DC mapping
DIFFICULTY_DC = {
    "easy":       10,   # was 20 — trivial tasks still occasionally fail
    "medium":     20,   # was 40 — standard play feels achievable
    "hard":       35,   # was 60 — requires planning, not a coin flip
    "extreme":    40,   # was 80 — tough but not hopeless
    "impossible": 60,   # was 95 — actually possible with brilliance
    "realistic":  25,   # was 50 — slightly more forgiving baseline
}

def evaluate_cleverness(action_desc: str, preparation: str, equipment: list[str]) -> tuple[int, str]:
    """
    This would be called by the AI to score how clever/well-planned the action is.
    Returns bonus (-30 to +30) and reasoning.
    
    In practice, the AI would analyze the action and return a structured score.
    """
    # This is a placeholder - the actual implementation would have the AI evaluate this
    # For now, return neutral
    return 0, "Standard approach with no particular advantages or disadvantages."


def calculate_technical_modifier(action_desc: str, equipment: list[str], context: str) -> tuple[int, str]:
    """
    Evaluates objective technical advantages/disadvantages.
    Examples:
    - T-47 Airspeeder vs civilian speeder in a race = +20 bonus
    - Picking a lock with proper tools vs improvised tools = +10 vs -15
    - Imperial encryption vs rebel slicer = modifier based on tech disparity
    """
    # Placeholder - would be evaluated by AI in practice
    return 0, "No significant technical advantage or disadvantage."


def evaluate_action_success(context: ActionContext) -> OutcomeGuidance:
    """
    Main function that evaluates whether an action succeeds.
    
    This combines:
    1. Base difficulty (from scenario setting)
    2. How clever/well-planned the action is
    3. Objective technical factors
    4. Environmental circumstances
    5. Random chance (dice roll)
    """
    
    # 1. Get base difficulty
    base_dc = DIFFICULTY_DC.get(context.difficulty_setting.lower(), 50)
    
    # 2. Evaluate cleverness (AI would actually analyze this)
    cleverness_bonus, cleverness_reasoning = evaluate_cleverness(
        context.action_description,
        context.player_preparation,
        context.equipment_advantages
    )
    
    # 3. Technical advantages/disadvantages (objective reality)
    technical_mod, technical_reasoning = calculate_technical_modifier(
        context.action_description,
        context.equipment_advantages,
        context.opposition_strength
    )
    
    # 4. Environmental factors
    env_modifier = 0
    env_reasoning = "Neutral environmental conditions."
    # AI would evaluate environmental factors here
    
    # 5. Calculate final target
    final_target = max(1, min(99, base_dc - cleverness_bonus - technical_mod - env_modifier))
    
    # 6. Roll the dice (random element)
    dice_roll = random.randint(1, 100)
    
    # 7. Calculate total and determine success
    total_score = dice_roll + cleverness_bonus + technical_mod + env_modifier
    success = total_score >= base_dc
    
    # 8. Determine degree of success
    margin = total_score - base_dc
    
    if dice_roll <= 5 and not success:
        degree = "critical_failure"
    elif dice_roll >= 95 and success:
        degree = "critical_success"
    elif margin < -20:
        degree = "critical_failure"
    elif not success:
        degree = "failure"
    elif margin < 10:
        degree = "partial_success"
    elif margin < 30:
        degree = "success"
    else:
        degree = "critical_success"
    
    # Build narration guidance
    narration_parts = []
    
    if degree == "critical_failure":
        narration_parts.append("Not only does the action fail, but it creates a significant complication or danger.")
        consequences = [
            "Something breaks or is lost",
            "Attention is drawn to the player",
            "The situation becomes more dangerous",
            "A time-sensitive opportunity is lost"
        ]
        opportunities = ["Must deal with the consequences before proceeding"]
        
    elif degree == "failure":
        narration_parts.append("The action fails. The player's objective is not achieved.")
        consequences = [
            "The goal is not met",
            "Resources may be spent with no gain",
            "Opposition may react or adapt"
        ]
        opportunities = [
            "Try a different approach",
            "Retreat and regroup",
            "Accept the setback and move forward"
        ]
        
    elif degree == "partial_success":
        narration_parts.append("The action succeeds, but with complications or at a cost.")
        consequences = [
            "The goal is partially achieved",
            "Success comes with a drawback",
            "A choice must be made between competing priorities"
        ]
        opportunities = [
            "Follow through with the partial success",
            "Attempt to capitalize on what was gained",
            "Cut losses and change tactics"
        ]
        
    elif degree == "success":
        narration_parts.append("The action succeeds as intended.")
        consequences = [
            "The immediate objective is achieved",
            "The player is in a better position"
        ]
        opportunities = [
            "Build on this success",
            "Press the advantage",
            "Proceed to the next objective"
        ]
        
    else:  # critical_success
        narration_parts.append("The action succeeds exceptionally well, beyond expectations.")
        consequences = [
            "The objective is achieved with bonus benefits",
            "Additional opportunities arise",
            "The player gains significant advantage"
        ]
        opportunities = [
            "Exploit the exceptional outcome",
            "Gain information or resources not anticipated",
            "Put opposition at severe disadvantage"
        ]
    
    # Add reasoning about modifiers
    if cleverness_bonus != 0:
        narration_parts.append(f"Player planning: {cleverness_reasoning}")
    if technical_mod != 0:
        narration_parts.append(f"Technical factors: {technical_reasoning}")
    if env_modifier != 0:
        narration_parts.append(f"Environmental factors: {env_reasoning}")
    
    narration_guidance = " ".join(narration_parts)
    
    return OutcomeGuidance(
        success_factors=SuccessFactors(
            base_difficulty_dc=base_dc,
            cleverness_bonus=cleverness_bonus,
            technical_modifier=technical_mod,
            environmental_modifier=env_modifier,
            final_target=final_target,
            dice_roll=dice_roll,
            total_score=total_score,
            success=success,
            success_degree=degree
        ),
        narration_guidance=narration_guidance,
        consequences=consequences,
        opportunities=opportunities
    )


# Example difficulty scaling demonstrations
DIFFICULTY_EXAMPLES = {
    "easy": {
        "description": "Tasks that should succeed unless something goes very wrong",
        "examples": [
            "Shooting an unaware, stationary target at close range with a blaster",
            "Intimidating a frightened civilian",
            "Hot-wiring a civilian speeder with proper tools"
        ],
        "typical_dc": 20,
        "notes": "Even with no bonuses, 80% chance of success"
    },
    
    "medium": {
        "description": "Tasks that require competence and decent conditions",
        "examples": [
            "Hitting a moving target in combat",
            "Convincing a skeptical but reasonable person",
            "Picking a standard lock without perfect tools"
        ],
        "typical_dc": 40,
        "notes": "60% base chance; player decisions matter significantly"
    },
    
    "hard": {
        "description": "Tasks that require skill, preparation, or favorable circumstances",
        "examples": [
            "Defeating trained Stormtroopers in direct combat (they use cover, flanking, and call backup)",
            "Slicing into an Imperial security terminal",
            "Sneaking past alert guards"
        ],
        "typical_dc": 60,
        "notes": "40% base chance; good planning essential. Enemies fight smarter, not with better gear."
    },

    "extreme": {
        "description": "Tasks that should fail without excellent planning and execution",
        "examples": [
            "Taking on a coordinated squad of Death Troopers",
            "Infiltrating an ISB facility with active patrols and surveillance",
            "Convincing an Imperial officer to commit treason"
        ],
        "typical_dc": 80,
        "notes": "20% base chance; requires significant bonuses from clever planning. Enemies use superior numbers and tactics — not invented prototype equipment."
    },

    "impossible": {
        "description": "Tasks that should only succeed with perfect planning and exceptional luck",
        "examples": [
            "Stealing an Imperial Star Destroyer",
            "Single-handedly defeating a platoon",
            "Slicing the Imperial central database"
        ],
        "typical_dc": 95,
        "notes": "5% base chance; even with bonuses, should remain very difficult"
    },

    "realistic": {
        "description": "No artificial scaling; pure simulation of what would actually happen",
        "examples": [
            "Any action evaluated purely on its logical merits",
            "Used when the GM wants outcomes based on world physics, not game balance"
        ],
        "typical_dc": 50,
        "notes": "Baseline 50% chance, heavily modified by circumstances and logic"
    }
}


def get_difficulty_guidance(difficulty: str) -> dict:
    """Returns guidance on what a difficulty level means"""
    return DIFFICULTY_EXAMPLES.get(difficulty.lower(), DIFFICULTY_EXAMPLES["realistic"])


# Tool schema for AI to use
ACTION_EVALUATION_TOOL = {
    "type": "function",
    "function": {
        "name": "evaluate_player_action",
        "description": (
            "Evaluate whether a player action succeeds. This function considers difficulty setting, "
            "player preparation, technical factors, and random chance to determine realistic outcomes. "
            "Use this when players attempt actions with uncertain outcomes."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action_description": {
                    "type": "string",
                    "description": "What the player is attempting to do"
                },
                "player_preparation": {
                    "type": "string",
                    "description": "How the player prepared, planned, or approached this action. Include specific tactics, precautions, or clever ideas they mentioned."
                },
                "cleverness_score": {
                    "type": "integer",
                    "minimum": -30,
                    "maximum": 30,
                    "description": (
                        "Rate the quality of the player's approach:\n"
                        "+20 to +30: Exceptional planning, multiple contingencies, creative solution\n"
                        "+10 to +19: Good preparation, solid tactical thinking\n"
                        "0 to +9: Standard competent approach\n"
                        "-1 to -9: Hasty or suboptimal approach\n"
                        "-10 to -19: Poor planning, ignoring obvious risks\n"
                        "-20 to -30: Reckless, contradicts common sense"
                    )
                },
                "technical_modifier": {
                    "type": "integer",
                    "minimum": -20,
                    "maximum": 20,
                    "description": (
                        "Objective technical/physical advantages or disadvantages based ONLY on canonical, established gear and skills — never invent equipment:\n"
                        "+15 to +20: Overwhelming technical superiority (starfighter vs cargo ship, professional slicing rig vs no tools)\n"
                        "+8 to +14: Significant advantage (quality tools, better-suited equipment for the task)\n"
                        "0 to +7: Slight advantage\n"
                        "0 to -7: Slight disadvantage\n"
                        "-8 to -14: Significant disadvantage (improvised tools, inferior tech for the task)\n"
                        "-15 to -20: Overwhelming disadvantage (unarmed vs armed opponent, no equipment vs fully equipped)\n"
                        "IMPORTANT: If enemies have standard-issue gear and the player has standard-issue gear, this is near 0. Do NOT assign large negative values because you imagined the enemy has a special upgrade — only use what is established in the scene."
                    )
                },
                "environmental_modifier": {
                    "type": "integer",
                    "minimum": -15,
                    "maximum": 15,
                    "description": (
                        "Situational and environmental factors:\n"
                        "+10 to +15: Extremely favorable conditions (distracted guards, perfect timing)\n"
                        "+5 to +9: Favorable conditions (cover, surprise, distraction)\n"
                        "0 to +4: Slightly favorable\n"
                        "0 to -4: Slightly unfavorable\n"
                        "-5 to -9: Unfavorable conditions (alert enemies, bad weather)\n"
                        "-10 to -15: Extremely unfavorable (surrounded, injured, time pressure)"
                    )
                },
                "reasoning": {
                    "type": "string",
                    "description": "Brief explanation of why you assigned these modifiers"
                }
            },
            "required": [
                "action_description",
                "player_preparation",
                "cleverness_score",
                "technical_modifier",
                "environmental_modifier",
                "reasoning"
            ]
        }
    }
}


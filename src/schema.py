"""Strict output schema and semantic validators for review analysis."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from collections.abc import Iterable
from typing import Any


SCHEMA_VERSION = "1.7.0"

SENTIMENTS = ["positive", "neutral", "negative", "mixed", "uncertain"]
POLARITIES = ["positive", "neutral", "negative", "mixed"]
EXPERIENCE_STATUSES = ["used", "not_used", "delivery_only", "unclear"]
STAR_TEXT_ALIGNMENTS = [
    "aligned",
    "mild_mismatch",
    "strong_mismatch",
    "insufficient_text",
]
EXPECTATION_GAP_TYPES = [
    "none",
    "photo_description",
    "color_shade",
    "size_quantity",
    "product_form",
    "performance",
    "delivery",
    "price",
    "authenticity",
]
ACTION_AUDIENCES = [
    "product",
    "listing",
    "content",
    "customer_service",
]

ASPECT_CODES = [
    "product.efficacy.general_effect",
    "product.efficacy.speed_duration",
    "product.efficacy.cleansing",
    "product.efficacy.brightening_whitening",
    "product.efficacy.hair_styling",
    "product.efficacy.skin_texture",
    "product.sensory.scent",
    "product.sensory.texture_consistency",
    "product.sensory.absorption",
    "product.sensory.greasiness",
    "product.sensory.stickiness",
    "product.sensory.residue_staining",
    "product.sensory.comfort_irritation",
    "product.appearance.color_shade",
    "product.appearance.finish_shine",
    "product.appearance.design_look",
    "product.usability.ease_of_use",
    "product.usability.application_control",
    "product.usability.dispenser",
    "product.usability.instructions",
    "product.usability.handling_portability",
    "product.quality.material_build",
    "product.quality.durability_breakage",
    "product.quality.mechanical_electrical",
    "product.suitability.skin_hair_fit",
    "product.suitability.body_area_fit",
    "product.suitability.skill_professional_fit",
    "value.price_value",
    "value.size_quantity",
    "packaging.seal_leak_protection",
    "packaging.arrival_condition",
    "fulfillment.delivery",
    "fulfillment.item_accuracy",
    "fulfillment.return_refund",
    "fulfillment.seller_service",
    "listing_trust.photo_description_match",
    "listing_trust.authenticity",
]

ISSUE_CODES = [
    "no_effect",
    "insufficient_effect",
    "adverse_reaction",
    "texture_problem",
    "scent_problem",
    "residue_staining",
    "color_mismatch",
    "size_quantity_mismatch",
    "leakage_spillage",
    "opened_used_item",
    "damage_breakage",
    "durability_problem",
    "mechanical_malfunction",
    "broken_dispenser",
    "difficult_to_use",
    "wrong_item_variant",
    "missing_parts",
    "description_photo_mismatch",
    "counterfeit_suspected",
    "late_not_delivered",
    "return_refund_problem",
    "seller_support_problem",
    "price_value_problem",
    "other_explicit_issue",
]

SCENARIO_CODES = [
    "daily_routine",
    "travel",
    "gift",
    "home_household",
    "professional_salon",
    "beginner_practice",
    "sensitive_area",
    "teen_family",
    "client_use",
]

MOTIVATION_CODES = [
    "efficacy_claim",
    "price_value",
    "recommendation",
    "brand_familiarity",
    "repeat_purchase",
    "gift",
    "travel_portability",
    "availability",
    "professional_need",
    "specific_user_need",
    "appearance_preference",
    "convenience",
]

SPEECH_ACT_CODES = [
    "praise",
    "complaint",
    "recommendation",
    "warning",
    "suggestion",
    "comparison",
    "repurchase_intent",
    "rejection_no_repurchase",
    "return_refund_intent",
    "request_help",
    "uncertainty_hedging",
    "sarcasm_irony",
]


def _evidence_object(label_key: str, enum_values: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            label_key: {"type": "string", "enum": enum_values},
            "evidence": {
                "type": "string",
                "description": (
                    "Shortest exact, contiguous substring copied from the "
                    "review title or body."
                ),
            },
        },
        "required": [label_key, "evidence"],
    }


ANALYSIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "review_id": {
            "type": "string",
            "description": "Copy the input review_id exactly.",
        },
        "language": {"type": "string", "enum": ["en", "es"]},
        "sentiment": {"type": "string", "enum": SENTIMENTS},
        "sentiment_intensity": {"type": "integer", "enum": [1, 2, 3]},
        "sentiment_evidence": {
            "type": "array",
            "minItems": 1,
            "maxItems": 3,
            "items": {"type": "string"},
            "description": (
                "One to three exact source substrings supporting overall "
                "sentiment; mixed sentiment normally uses separate positive "
                "and negative snippets."
            ),
        },
        "aspects": {
            "type": "array",
            "maxItems": 4,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "aspect": {"type": "string", "enum": ASPECT_CODES},
                    "opinion": {
                        "type": "string",
                        "description": (
                            "Concise paraphrase of the reviewer's opinion."
                        ),
                    },
                    "polarity": {"type": "string", "enum": POLARITIES},
                    "evidence": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 3,
                        "items": {"type": "string"},
                        "description": (
                            "One to three exact source substrings supporting "
                            "this unique aspect."
                        ),
                    },
                },
                "required": ["aspect", "opinion", "polarity", "evidence"],
            },
        },
        "issue_types": {
            "type": "array",
            "maxItems": 6,
            "items": _evidence_object("issue", ISSUE_CODES),
        },
        "usage_scenarios": {
            "type": "array",
            "maxItems": 3,
            "items": _evidence_object("scenario", SCENARIO_CODES),
        },
        "purchase_motivations": {
            "type": "array",
            "maxItems": 3,
            "items": _evidence_object("motivation", MOTIVATION_CODES),
        },
        "expectation_gap": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "present": {"type": "boolean"},
                "type": {
                    "type": "string",
                    "enum": EXPECTATION_GAP_TYPES,
                },
                "evidence": {
                    "type": "array",
                    "maxItems": 3,
                    "items": {"type": "string"},
                    "description": (
                        "Exact source substrings, or an empty array only when "
                        "present is false."
                    ),
                },
            },
            "required": ["present", "type", "evidence"],
        },
        "speech_acts": {
            "type": "array",
            "maxItems": 4,
            "items": _evidence_object("speech_act", SPEECH_ACT_CODES),
        },
        "experience_status": {
            "type": "string",
            "enum": EXPERIENCE_STATUSES,
        },
        "star_text_alignment": {
            "type": "string",
            "enum": STAR_TEXT_ALIGNMENTS,
        },
        "recommended_actions": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "audience": {
                        "type": "string",
                        "enum": ACTION_AUDIENCES,
                    },
                    "action": {
                        "type": "string",
                        "description": (
                            "Narrow, review-grounded action; no unsupported "
                            "causal or medical claim."
                        ),
                    },
                    "evidence": {
                        "type": "string",
                        "description": (
                            "Exact source substring that motivates the action."
                        ),
                    },
                },
                "required": ["audience", "action", "evidence"],
            },
        },
        "confidence": {"type": "number"},
        "ambiguous": {"type": "boolean"},
        "analysis_note": {
            "type": "string",
            "description": (
                "Briefly explain ambiguity or a boundary decision; empty "
                "when no note is needed."
            ),
        },
    },
    "required": [
        "review_id",
        "language",
        "sentiment",
        "sentiment_intensity",
        "sentiment_evidence",
        "aspects",
        "issue_types",
        "usage_scenarios",
        "purchase_motivations",
        "expectation_gap",
        "speech_acts",
        "experience_status",
        "star_text_alignment",
        "recommended_actions",
        "confidence",
        "ambiguous",
        "analysis_note",
    ],
}


def _without_descriptions(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_descriptions(item)
            for key, item in value.items()
            if key != "description"
        }
    if isinstance(value, list):
        return [_without_descriptions(item) for item in value]
    return value


# The prompt carries semantic instructions, so verbose description strings do
# not need to be retransmitted in every API request. The structural contract is
# identical to ANALYSIS_SCHEMA.
API_ANALYSIS_SCHEMA: dict[str, Any] = _without_descriptions(ANALYSIS_SCHEMA)


class AnalysisValidationError(ValueError):
    """Raised when a model response violates schema or evidence rules."""


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def schema_hash() -> str:
    return hashlib.sha256(canonical_json(ANALYSIS_SCHEMA).encode()).hexdigest()


def api_schema_hash() -> str:
    return hashlib.sha256(
        canonical_json(API_ANALYSIS_SCHEMA).encode()
    ).hexdigest()


def _supports_no_repurchase(evidence: str) -> bool:
    text = f" {evidence.casefold()} "
    english_negation = any(
        marker in text
        for marker in [" won't ", " will not ", " wouldn't ", " would not ", " never "]
    )
    english_purchase = any(
        marker in text
        for marker in [
            " buy",
            " buying",
            " purchase",
            " purchasing",
            " order",
            " ordering",
            " repurchase",
            " reorder",
        ]
    )
    english_recurrence = any(
        marker in text
        for marker in [" again", " another", " repurchase", " reorder"]
    )
    spanish_negation = " no " in text or " nunca " in text
    spanish_recurrence = any(
        marker in text
        for marker in [
            " volver",
            " otra vez",
            " de nuevo",
            " recompr",
            " repetir",
        ]
    )
    spanish_purchase = any(
        marker in text
        for marker in [" compr", " pedir", " recompr", " repetir"]
    )
    return (
        english_negation and english_purchase and english_recurrence
    ) or (
        spanish_negation and spanish_recurrence and spanish_purchase
    )


def _contains_any(text: str, markers: Iterable[str]) -> bool:
    normalized = text.casefold()
    return any(marker in normalized for marker in markers)


def _evidence_context(source_text: str, evidence: str) -> str:
    source_folded = source_text.casefold()
    evidence_folded = evidence.casefold()
    index = source_folded.find(evidence_folded)
    if index < 0:
        return evidence
    left = max(
        source_folded.rfind(delimiter, 0, index)
        for delimiter in [".", "!", "?", "\n"]
    )
    right_candidates = [
        position
        for delimiter in [".", "!", "?", "\n"]
        if (position := source_folded.find(delimiter, index)) >= 0
    ]
    right = min(right_candidates) if right_candidates else len(source_text)
    return source_text[left + 1 : right + 1]


def _is_hypothetical_context(source_text: str, evidence: str) -> bool:
    context = f" {_evidence_context(source_text, evidence).casefold()} "
    markers = [
        " may ",
        " might ",
        " could ",
        " possibly ",
        " perhaps ",
        " maybe ",
        " may have to ",
        " might have to ",
        " podría ",
        " podria ",
        " puede que ",
        " quizá ",
        " quiza ",
        " quizás ",
        " quizas ",
        " tal vez ",
        " posiblemente ",
        " tendría que ",
        " tendria que ",
    ]
    return any(marker in context for marker in markers)


def _validate_aspect_semantics(
    aspect_code: str,
    evidences: list[str],
    context: str,
    *,
    source_text: str | None = None,
) -> None:
    evidence = " ".join(evidences)
    if (
        source_text is not None
        and aspect_code
        in {
            "product.suitability.skin_hair_fit",
            "product.suitability.body_area_fit",
            "product.suitability.skill_professional_fit",
        }
        and any(
            _is_hypothetical_context(source_text, item)
            for item in evidences
        )
    ):
        raise AnalysisValidationError(
            f"{context} is supported only by hypothetical or possible future "
            "fit language, not a realized suitability evaluation"
        )
    if aspect_code == "product.suitability.skill_professional_fit":
        markers = [
            "beginner",
            "novice",
            "amateur",
            "professional",
            "salon",
            "stylist",
            "practice",
            "practicing",
            "client",
            "principiante",
            "novato",
            "aficionado",
            "profesional",
            "salón",
            "salon",
            "estilista",
            "práctic",
            "practic",
            "cliente",
        ]
        if not _contains_any(evidence, markers):
            raise AnalysisValidationError(
                f"{context} lacks explicit beginner, practice, professional, "
                "salon, stylist, or client evidence"
            )
    elif aspect_code == "product.usability.handling_portability":
        markers = [
            "lightweight",
            "light weight",
            "heavy",
            "compact",
            "portable",
            "carry",
            "carrying",
            "travel",
            "handle",
            "grip",
            "hold",
            "storage",
            "small enough",
            "manageable",
            "maneuver",
            "ergonom",
            "ligero",
            "ligera",
            "liviano",
            "liviana",
            "pesado",
            "pesada",
            "compact",
            "portátil",
            "portatil",
            "llevar",
            "viaje",
            "viajar",
            "manejable",
            "agarre",
            "sujetar",
            "guardar",
            "almacen",
            "pequeñito",
            "pequeñita",
        ]
        if not _contains_any(evidence, markers):
            raise AnalysisValidationError(
                f"{context} lacks explicit weight, handling, compactness, "
                "storage, carrying, or travel evidence"
            )
    elif aspect_code == "product.efficacy.brightening_whitening":
        markers = [
            "whiten",
            "brighter",
            "brighten",
            "lighten",
            "illuminat",
            "dark spot",
            "teeth",
            "tooth",
            "skin tone",
            "complexion",
            "blanqu",
            "aclar",
            "ilumin",
            "mancha oscur",
            "diente",
            "tono de piel",
            "tez",
        ]
        if not _contains_any(evidence, markers):
            raise AnalysisValidationError(
                f"{context} lacks explicit teeth/skin whitening or "
                "brightening evidence; hair shine belongs to finish_shine"
            )
    elif aspect_code == "product.efficacy.cleansing":
        foam_markers = ["foam", "lather", "espuma"]
        cleansing_markers = [
            "clean",
            "wash",
            "rinse",
            "remove",
            "dirt",
            "makeup",
            "residue",
            "greasy",
            "oily",
            "limpi",
            "lav",
            "enjuag",
            "quit",
            "suciedad",
            "maquill",
            "residuo",
            "grasos",
            "grasa",
        ]
        if _contains_any(evidence, foam_markers) and not _contains_any(
            evidence, cleansing_markers
        ):
            raise AnalysisValidationError(
                f"{context} uses foam/lather alone as proof of cleansing; "
                "foaming is not the same as cleaning ability"
            )
    elif aspect_code == "product.suitability.skin_hair_fit":
        markers = [
            "oily skin",
            "dry skin",
            "sensitive skin",
            "combination skin",
            "mature skin",
            "acne-prone",
            "curly hair",
            "straight hair",
            "fine hair",
            "thin hair",
            "thick hair",
            "coarse hair",
            "wavy hair",
            "color-treated hair",
            "dyed hair",
            "piel grasa",
            "piel seca",
            "piel sensible",
            "piel mixta",
            "piel madura",
            "cabello rizado",
            "pelo rizado",
            "cabello liso",
            "pelo liso",
            "cabello fino",
            "pelo fino",
            "cabello grueso",
            "pelo grueso",
            "cabello ondulado",
            "pelo ondulado",
            "cabello teñido",
            "pelo teñido",
            "mucho pelo",
            "poco pelo",
        ]
        if not _contains_any(evidence, markers):
            raise AnalysisValidationError(
                f"{context} lacks an explicit skin or hair type/context; "
                "an effect on hair alone is not skin/hair suitability"
            )
    elif aspect_code == "product.usability.application_control":
        markers = [
            "spray",
            "squirt",
            "mist",
            "coat",
            "layer",
            "evenly",
            "amount",
            "dose",
            "control",
            "too much product",
            "waste product",
            "dispense",
            "roci",
            "pulver",
            "chorro",
            "capa",
            "uniform",
            "cantidad",
            "dosis",
            "control",
            "demasiado producto",
            "mucho producto",
            "pierde producto",
            "pierdes producto",
            "dosific",
        ]
        if not _contains_any(evidence, markers):
            raise AnalysisValidationError(
                f"{context} lacks spray, coating, dose, amount, or "
                "application-control evidence; generic difficulty applying "
                "belongs to ease_of_use"
            )
    elif aspect_code == "product.quality.material_build":
        if _contains_any(evidence, ["packaging", "package material"]):
            raise AnalysisValidationError(
                f"{context} evaluates packaging material, not the product's "
                "own material or build quality"
            )
        markers = [
            "material",
            "plastic",
            "metal",
            "wood",
            "sturdy",
            "solid",
            "flimsy",
            "cheaply made",
            "well made",
            "build",
            "construction",
            "synthetic",
            "plástico",
            "plastico",
            "madera",
            "resistente",
            "sólido",
            "solido",
            "endeble",
            "bien hecho",
            "construcción",
            "construccion",
            "sintético",
            "sintetico",
        ]
        if not _contains_any(evidence, markers):
            raise AnalysisValidationError(
                f"{context} lacks explicit product material, construction, "
                "sturdiness, or build-quality evidence; generic quality "
                "praise is not material/build"
            )
    elif aspect_code == "packaging.seal_leak_protection":
        markers = [
            "leak",
            "spill",
            "sealed",
            "unsealed",
            "seal was",
            "seal is",
            "not sealed",
            "tightly closed",
            "doesn't close",
            "does not close",
            "won't close",
            "will not close",
            "airtight",
            "fuga",
            "derram",
            "precint",
            "sellad",
            "sin sello",
            "cierre hermético",
            "cierre hermetico",
            "no cierra",
        ]
        if not _contains_any(evidence, markers):
            raise AnalysisValidationError(
                f"{context} lacks explicit sealing, closure, leakage, or "
                "spill-protection evidence"
            )
    elif aspect_code == "packaging.arrival_condition":
        markers = [
            "arriv",
            "received",
            "delivered",
            "good condition",
            "bad condition",
            "damaged",
            "broken",
            "open",
            "used",
            "dirty",
            "half full",
            "sealed",
            "leak",
            "lleg",
            "recib",
            "entreg",
            "buen estado",
            "mal estado",
            "dañad",
            "danad",
            "roto",
            "rota",
            "abiert",
            "usado",
            "usada",
            "sucio",
            "sucia",
            "medio vacío",
            "medio vacio",
            "precint",
            "derram",
        ]
        if not _contains_any(evidence, markers):
            raise AnalysisValidationError(
                f"{context} lacks explicit arrival, opening, damage, dirt, "
                "use, fill level, seal, or delivery-condition evidence"
            )


def _validate_issue_semantics(
    issue_code: str,
    evidence: str,
    context: str,
) -> None:
    if issue_code == "broken_dispenser":
        markers = [
            "broken",
            "cracked",
            "clogged",
            "stuck",
            "jammed",
            "won't pump",
            "will not pump",
            "won't spray",
            "will not spray",
            "doesn't dispense",
            "does not dispense",
            "doesn't work",
            "does not work",
            "malfunction",
            "defect",
            "roto",
            "rota",
            "quebrad",
            "atascad",
            "bloquead",
            "no funciona",
            "no sale",
            "no dispensa",
            "averiad",
            "defectuos",
        ]
        if not _contains_any(evidence, markers):
            raise AnalysisValidationError(
                f"{context} lacks an explicit broken, clogged, stuck, or "
                "non-functioning dispenser"
            )
        return
    if issue_code == "texture_problem":
        markers = [
            "texture",
            "consistency",
            "thick",
            "thin",
            "watery",
            "runny",
            "soft",
            "hard",
            "sticky",
            "greasy",
            "oily",
            "gel",
            "absorb",
            "plastic",
            "textura",
            "consistencia",
            "espes",
            "líquid",
            "liquid",
            "aguad",
            "bland",
            "demasiado duro",
            "demasiado dura",
            "muy duro",
            "muy dura",
            "pegajos",
            "gras",
            "aceitos",
            "gel",
            "absorb",
            "plástic",
            "plastic",
        ]
        if not _contains_any(evidence, markers):
            raise AnalysisValidationError(
                f"{context} lacks explicit product texture, consistency, "
                "softness, viscosity, greasiness, or absorption evidence"
            )
        return
    if issue_code not in {"no_effect", "insufficient_effect"}:
        return
    foam_markers = ["foam", "lather", "espuma"]
    effect_markers = [
        "effect",
        "work",
        "result",
        "change",
        "clean",
        "wash",
        "remove",
        "straight",
        "cover",
        "last",
        "dur",
        "efect",
        "funcion",
        "resultado",
        "cambio",
        "limpi",
        "lav",
        "quit",
        "alis",
        "cubr",
    ]
    if _contains_any(evidence, foam_markers) and not _contains_any(
        evidence, effect_markers
    ):
        raise AnalysisValidationError(
            f"{context} uses foam/lather alone as proof of efficacy failure"
        )


def _validate_scenario_semantics(
    scenario_code: str,
    evidence: str,
    context: str,
) -> None:
    if scenario_code != "sensitive_area":
        return
    markers = [
        "sensitive area",
        "delicate area",
        "underarm",
        "armpit",
        "eye area",
        "around my eyes",
        "bikini",
        "intimate area",
        "zona sensible",
        "zona delicada",
        "axila",
        "contorno de ojos",
        "alrededor de los ojos",
        "zona íntima",
        "zona intima",
        "ingles",
    ]
    if not _contains_any(evidence, markers):
        raise AnalysisValidationError(
            f"{context} lacks an explicit sensitive or delicate body area; "
            "a scar or skin concern alone is not a sensitive-area scenario"
        )


def _validate_speech_act_semantics(
    speech_act: str,
    evidence: str,
    context: str,
) -> None:
    if (
        speech_act == "rejection_no_repurchase"
        and not _supports_no_repurchase(evidence)
    ):
        raise AnalysisValidationError(
            f"{context} does not explicitly state no repurchase; "
            "not recommending is not the same as not buying again"
        )
    if speech_act == "warning":
        markers = [
            "do not buy",
            "don't buy",
            "dont buy",
            "avoid",
            "stay away",
            "beware",
            "be careful",
            "warning",
            "get something else",
            "no compr",
            "no lo compr",
            "evit",
            "cuidado",
            "ojo con",
            "advert",
            "aléjate",
            "alejate",
        ]
        if not _contains_any(evidence, markers):
            raise AnalysisValidationError(
                f"{context} lacks explicit caution, avoidance, or "
                "do-not-buy guidance; a negative statement alone is not a "
                "warning"
            )
        return
    if speech_act != "suggestion":
        return
    future_update_markers = [
        "i'll update",
        "i will update",
        "will update with",
        "update with photos",
        "actualizaré",
        "actualizare",
        "voy a actualizar",
        "subiré fotos",
        "subire fotos",
        "añadiré fotos",
        "anadire fotos",
    ]
    if _contains_any(evidence, future_update_markers):
        raise AnalysisValidationError(
            f"{context} is a future review-status update, not an improvement "
            "or usage suggestion"
        )


def _validate_motivation_semantics(
    motivation: str,
    evidence: str,
    context: str,
) -> None:
    if motivation != "professional_need":
        return
    markers = [
        "for my client",
        "for clients",
        "for the salon",
        "for my salon",
        "for work",
        "for professional use",
        "needed for",
        "need this for",
        "bought",
        "purchased",
        "ordered",
        "para mis clientes",
        "para clientes",
        "para el salón",
        "para el salon",
        "para mi salón",
        "para mi salon",
        "para trabajar",
        "para uso profesional",
        "necesit",
        "compr",
        "pedí",
        "pedi",
    ]
    if not _contains_any(evidence, markers):
        raise AnalysisValidationError(
            f"{context} states professional identity/context but does not "
            "explicitly say that professional work caused the purchase"
        )


def normalize_analysis(
    payload: Any,
    *,
    source_text: str | None = None,
) -> tuple[Any, list[dict[str, Any]]]:
    """Deterministically repair safe, presence-only semantic violations.

    The labeled evidence arrays represent label presence, so repeated copies
    or unsupported optional labels add no reliable information. Keeping the
    first supported item, dropping an unsupported optional item, and repairing
    logically forced sentiment/status values avoids spending additional API
    calls on mechanically resolvable errors. Every change is audited.
    """

    if not isinstance(payload, dict):
        return payload, []
    normalized = deepcopy(payload)
    events: list[dict[str, Any]] = []
    fields = {
        "issue_types": "issue",
        "usage_scenarios": "scenario",
        "purchase_motivations": "motivation",
        "speech_acts": "speech_act",
    }
    for field, label_key in fields.items():
        items = normalized.get(field)
        if not isinstance(items, list):
            continue
        seen: set[str] = set()
        kept: list[Any] = []
        for item in items:
            label = item.get(label_key) if isinstance(item, dict) else None
            if not isinstance(label, str) or label not in seen:
                kept.append(item)
                if isinstance(label, str):
                    seen.add(label)
                continue
            events.append(
                {
                    "operation": "drop_duplicate_label",
                    "field": field,
                    "label": label,
                    "dropped_evidence": item.get("evidence"),
                }
            )
        normalized[field] = kept

    aspects = normalized.get("aspects")
    if isinstance(aspects, list):
        kept_aspects: list[Any] = []
        for item in aspects:
            if not isinstance(item, dict):
                kept_aspects.append(item)
                continue
            aspect_code = item.get("aspect")
            evidences = item.get("evidence")
            if not isinstance(aspect_code, str) or not isinstance(
                evidences, list
            ):
                kept_aspects.append(item)
                continue
            try:
                _validate_aspect_semantics(
                    aspect_code,
                    [
                        evidence
                        for evidence in evidences
                        if isinstance(evidence, str)
                    ],
                    "normalization.aspect",
                    source_text=source_text,
                )
            except AnalysisValidationError as error:
                events.append(
                    {
                        "operation": "drop_unsupported_label",
                        "field": "aspects",
                        "label": aspect_code,
                        "evidence": evidences,
                        "reason": str(error),
                    }
                )
                continue
            kept_aspects.append(item)
        normalized["aspects"] = kept_aspects

    semantic_arrays = [
        (
            "issue_types",
            "issue",
            _validate_issue_semantics,
        ),
        (
            "usage_scenarios",
            "scenario",
            _validate_scenario_semantics,
        ),
        (
            "purchase_motivations",
            "motivation",
            _validate_motivation_semantics,
        ),
        (
            "speech_acts",
            "speech_act",
            _validate_speech_act_semantics,
        ),
    ]
    for field, label_key, validator in semantic_arrays:
        items = normalized.get(field)
        if not isinstance(items, list):
            continue
        kept_items: list[Any] = []
        for item in items:
            if not isinstance(item, dict):
                kept_items.append(item)
                continue
            label = item.get(label_key)
            evidence = item.get("evidence")
            if not isinstance(label, str) or not isinstance(evidence, str):
                kept_items.append(item)
                continue
            try:
                validator(label, evidence, f"normalization.{field}")
            except AnalysisValidationError as error:
                events.append(
                    {
                        "operation": "drop_unsupported_label",
                        "field": field,
                        "label": label,
                        "evidence": evidence,
                        "reason": str(error),
                    }
                )
                continue
            kept_items.append(item)
        normalized[field] = kept_items

    actions = normalized.get("recommended_actions")
    if isinstance(actions, list):
        kept_actions: list[Any] = []
        for item in actions:
            if not isinstance(item, dict):
                kept_actions.append(item)
                continue
            action = item.get("action")
            evidence = item.get("evidence")
            if not isinstance(action, str) or not isinstance(evidence, str):
                kept_actions.append(item)
                continue
            action_folded = f" {action.casefold()} "
            evidence_folded = f" {evidence.casefold()} "
            semantic_domains = [
                ["hair", "pelo", "cabello", "brillo", "shine"],
                ["magnet", "imán", "iman", "pelliz", "pinch"],
                [
                    "scent",
                    "smell",
                    "odor",
                    "olor",
                    "fragrance",
                    "fragancia",
                ],
                [
                    "irrit",
                    "pain",
                    "headache",
                    "dolor",
                    "dryness",
                    "sequedad",
                ],
                ["adhesion", "adhere", "suction", "pegar", "ventosa"],
                ["leak", "spill", "fuga", "derram"],
                ["price", "cost", "value", "precio", "valor"],
                [
                    "counterfeit",
                    "fake",
                    "authentic",
                    "falsif",
                    "autentic",
                ],
            ]
            unsupported_domains = [
                domain
                for domain in semantic_domains
                if any(marker in action_folded for marker in domain)
                and not any(marker in evidence_folded for marker in domain)
            ]
            if unsupported_domains:
                events.append(
                    {
                        "operation": "drop_unsupported_action",
                        "field": "recommended_actions",
                        "action": action,
                        "evidence": evidence,
                        "reason": (
                            "action introduces a semantic domain absent from "
                            "its evidence"
                        ),
                    }
                )
                continue
            kept_actions.append(item)
        normalized["recommended_actions"] = kept_actions

    normalized_aspects = normalized.get("aspects")
    if isinstance(normalized_aspects, list):
        polarities = {
            item.get("polarity")
            for item in normalized_aspects
            if isinstance(item, dict)
        }
        if (
            "positive" in polarities
            and "negative" in polarities
            and normalized.get("sentiment") != "mixed"
            and isinstance(normalized.get("sentiment_evidence"), list)
            and len(normalized["sentiment_evidence"]) >= 2
        ):
            previous = normalized.get("sentiment")
            normalized["sentiment"] = "mixed"
            events.append(
                {
                    "operation": "set_logically_forced_value",
                    "field": "sentiment",
                    "from": previous,
                    "to": "mixed",
                    "reason": (
                        "explicit positive and negative aspect polarities"
                    ),
                }
            )

    speech_items = normalized.get("speech_acts")
    speech_codes = (
        {
            item.get("speech_act")
            for item in speech_items
            if isinstance(item, dict)
        }
        if isinstance(speech_items, list)
        else set()
    )
    if (
        normalized.get("sentiment") == "uncertain"
        and "sarcasm_irony" not in speech_codes
    ):
        aspect_polarities = (
            {
                item.get("polarity")
                for item in normalized_aspects
                if isinstance(item, dict)
            }
            if isinstance(normalized_aspects, list)
            else set()
        )
        replacement: str | None = None
        if "praise" in speech_codes and "complaint" not in speech_codes:
            replacement = (
                "mixed" if "negative" in aspect_polarities else "positive"
            )
        elif "complaint" in speech_codes and "praise" not in speech_codes:
            replacement = (
                "mixed" if "positive" in aspect_polarities else "negative"
            )
        if replacement is not None:
            normalized["sentiment"] = replacement
            events.append(
                {
                    "operation": "set_logically_forced_value",
                    "field": "sentiment",
                    "from": "uncertain",
                    "to": replacement,
                    "reason": "explicit non-sarcastic speech act",
                }
            )

    experience_status = normalized.get("experience_status")
    normalized_aspects = normalized.get("aspects")
    if experience_status == "delivery_only" and isinstance(
        normalized_aspects, list
    ):
        has_non_delivery_aspect = any(
            isinstance(item, dict)
            and isinstance(item.get("aspect"), str)
            and not item["aspect"].startswith(("packaging.", "fulfillment."))
            for item in normalized_aspects
        )
        if has_non_delivery_aspect:
            normalized["experience_status"] = "unclear"
            events.append(
                {
                    "operation": "set_logically_forced_value",
                    "field": "experience_status",
                    "from": "delivery_only",
                    "to": "unclear",
                    "reason": "review contains a non-delivery product aspect",
                }
            )
    elif (
        experience_status == "used"
        and source_text is not None
        and isinstance(normalized_aspects, list)
    ):
        use_markers = [
            " use ",
            " used ",
            " using ",
            " tried ",
            " after ",
            " applied ",
            " wear ",
            " wore ",
            " favorite ",
            " uso ",
            " usé ",
            " use ",
            " usando ",
            " probé ",
            " probe ",
            " apliqué ",
            " aplique ",
            " después ",
            " despues ",
            " tras ",
            " gasté ",
            " gaste ",
            " llevo ",
        ]
        padded_source = f" {source_text.casefold()} "
        realized_prefixes = ("product.efficacy.", "product.sensory.")
        realized_codes = {
            "product.usability.ease_of_use",
            "product.usability.application_control",
            "product.usability.handling_portability",
            "product.quality.durability_breakage",
            "product.quality.mechanical_electrical",
        }
        has_realized_aspect = any(
            isinstance(item, dict)
            and isinstance(item.get("aspect"), str)
            and (
                item["aspect"].startswith(realized_prefixes)
                or item["aspect"] in realized_codes
            )
            for item in normalized_aspects
        )
        if (
            not _contains_any(padded_source, use_markers)
            and not has_realized_aspect
        ):
            normalized["experience_status"] = "unclear"
            events.append(
                {
                    "operation": "set_logically_forced_value",
                    "field": "experience_status",
                    "from": "used",
                    "to": "unclear",
                    "reason": (
                        "no explicit use marker or realized efficacy/sensory "
                        "aspect"
                    ),
                }
            )
    return normalized, events


def _expect_exact_keys(
    value: dict[str, Any], required: Iterable[str], context: str
) -> None:
    required_set = set(required)
    actual_set = set(value)
    if actual_set != required_set:
        missing = sorted(required_set - actual_set)
        extras = sorted(actual_set - required_set)
        raise AnalysisValidationError(
            f"{context} keys invalid; missing={missing}, extras={extras}"
        )


def _expect_enum(value: Any, allowed: Iterable[Any], context: str) -> None:
    if value not in set(allowed):
        raise AnalysisValidationError(
            f"{context}={value!r} is not an allowed value"
        )


def _expect_evidence(
    evidence: Any, source_text: str, context: str, *, allow_empty: bool = False
) -> None:
    if not isinstance(evidence, str):
        raise AnalysisValidationError(f"{context} evidence must be a string")
    if not evidence:
        if allow_empty:
            return
        raise AnalysisValidationError(f"{context} evidence is empty")
    if evidence not in source_text:
        raise AnalysisValidationError(
            f"{context} evidence is not an exact source substring: "
            f"{evidence!r}"
        )


def _expect_evidence_list(
    evidences: Any,
    source_text: str,
    context: str,
    *,
    min_items: int,
    max_items: int,
) -> None:
    if not isinstance(evidences, list):
        raise AnalysisValidationError(f"{context} must be an array")
    if not min_items <= len(evidences) <= max_items:
        raise AnalysisValidationError(
            f"{context} must contain {min_items} to {max_items} items"
        )
    if len(evidences) != len(set(evidences)):
        raise AnalysisValidationError(f"{context} contains duplicate evidence")
    for index, evidence in enumerate(evidences):
        _expect_evidence(
            evidence,
            source_text,
            f"{context}[{index}]",
        )


def _validate_labeled_evidence_array(
    items: Any,
    *,
    label_key: str,
    allowed: list[str],
    source_text: str,
    context: str,
    max_items: int,
) -> None:
    if not isinstance(items, list):
        raise AnalysisValidationError(f"{context} must be an array")
    if len(items) > max_items:
        raise AnalysisValidationError(
            f"{context} must contain no more than {max_items} items"
        )
    seen: set[str] = set()
    for index, item in enumerate(items):
        item_context = f"{context}[{index}]"
        if not isinstance(item, dict):
            raise AnalysisValidationError(f"{item_context} must be an object")
        _expect_exact_keys(item, [label_key, "evidence"], item_context)
        _expect_enum(item[label_key], allowed, f"{item_context}.{label_key}")
        if item[label_key] in seen:
            raise AnalysisValidationError(
                f"{context} contains duplicate {label_key}: {item[label_key]}"
            )
        seen.add(item[label_key])
        _expect_evidence(
            item["evidence"], source_text, f"{item_context}.evidence"
        )
        if label_key == "issue":
            _validate_issue_semantics(
                item[label_key], item["evidence"], item_context
            )
        elif label_key == "scenario":
            _validate_scenario_semantics(
                item[label_key], item["evidence"], item_context
            )
        elif label_key == "motivation":
            _validate_motivation_semantics(
                item[label_key], item["evidence"], item_context
            )
        elif label_key == "speech_act":
            _validate_speech_act_semantics(
                item[label_key], item["evidence"], item_context
            )
def validate_analysis(
    payload: Any,
    *,
    source_text: str,
    expected_review_id: str | None = None,
    expected_language: str | None = None,
) -> dict[str, Any]:
    """Validate schema, enums, identity, confidence, and exact evidence."""

    if not isinstance(payload, dict):
        raise AnalysisValidationError("analysis must be a JSON object")
    _expect_exact_keys(payload, ANALYSIS_SCHEMA["required"], "analysis")

    if not isinstance(payload["review_id"], str) or not payload["review_id"]:
        raise AnalysisValidationError("review_id must be a non-empty string")
    if expected_review_id and payload["review_id"] != expected_review_id:
        raise AnalysisValidationError(
            f"review_id mismatch: {payload['review_id']!r} "
            f"!= {expected_review_id!r}"
        )
    _expect_enum(payload["language"], ["en", "es"], "language")
    if expected_language and payload["language"] != expected_language:
        raise AnalysisValidationError(
            f"language mismatch: {payload['language']!r} "
            f"!= {expected_language!r}"
        )
    _expect_enum(payload["sentiment"], SENTIMENTS, "sentiment")

    intensity = payload["sentiment_intensity"]
    if isinstance(intensity, bool) or intensity not in {1, 2, 3}:
        raise AnalysisValidationError(
            "sentiment_intensity must be integer 1, 2, or 3"
        )
    _expect_evidence_list(
        payload["sentiment_evidence"],
        source_text,
        "sentiment_evidence",
        min_items=1,
        max_items=3,
    )
    if (
        payload["sentiment"] == "mixed"
        and len(payload["sentiment_evidence"]) < 2
    ):
        raise AnalysisValidationError(
            "mixed sentiment requires at least two separate evidence snippets"
        )

    aspects = payload["aspects"]
    if not isinstance(aspects, list):
        raise AnalysisValidationError("aspects must be an array")
    if len(aspects) > 4:
        raise AnalysisValidationError(
            "aspects must contain no more than 4 items"
        )
    seen_aspects: set[str] = set()
    for index, aspect in enumerate(aspects):
        context = f"aspects[{index}]"
        if not isinstance(aspect, dict):
            raise AnalysisValidationError(f"{context} must be an object")
        _expect_exact_keys(
            aspect,
            ["aspect", "opinion", "polarity", "evidence"],
            context,
        )
        _expect_enum(aspect["aspect"], ASPECT_CODES, f"{context}.aspect")
        if aspect["aspect"] in seen_aspects:
            raise AnalysisValidationError(
                f"duplicate aspect: {aspect['aspect']}"
            )
        seen_aspects.add(aspect["aspect"])
        if not isinstance(aspect["opinion"], str) or not aspect["opinion"]:
            raise AnalysisValidationError(
                f"{context}.opinion must be non-empty"
            )
        _expect_enum(aspect["polarity"], POLARITIES, f"{context}.polarity")
        _expect_evidence_list(
            aspect["evidence"],
            source_text,
            f"{context}.evidence",
            min_items=1,
            max_items=3,
        )
        _validate_aspect_semantics(
            aspect["aspect"],
            aspect["evidence"],
            context,
            source_text=source_text,
        )

    _validate_labeled_evidence_array(
        payload["issue_types"],
        label_key="issue",
        allowed=ISSUE_CODES,
        source_text=source_text,
        context="issue_types",
        max_items=6,
    )
    _validate_labeled_evidence_array(
        payload["usage_scenarios"],
        label_key="scenario",
        allowed=SCENARIO_CODES,
        source_text=source_text,
        context="usage_scenarios",
        max_items=3,
    )
    _validate_labeled_evidence_array(
        payload["purchase_motivations"],
        label_key="motivation",
        allowed=MOTIVATION_CODES,
        source_text=source_text,
        context="purchase_motivations",
        max_items=3,
    )
    _validate_labeled_evidence_array(
        payload["speech_acts"],
        label_key="speech_act",
        allowed=SPEECH_ACT_CODES,
        source_text=source_text,
        context="speech_acts",
        max_items=4,
    )
    aspect_polarities = {item["polarity"] for item in aspects}
    if (
        "positive" in aspect_polarities
        and "negative" in aspect_polarities
        and payload["sentiment"] != "mixed"
    ):
        raise AnalysisValidationError(
            "explicit positive and negative aspect evaluations require "
            "sentiment=mixed"
        )
    speech_codes = {
        item["speech_act"] for item in payload["speech_acts"]
    }
    if (
        payload["sentiment"] == "uncertain"
        and "sarcasm_irony" not in speech_codes
        and speech_codes & {"praise", "complaint"}
    ):
        raise AnalysisValidationError(
            "sentiment=uncertain is incompatible with an explicit praise or "
            "complaint; use positive, negative, or calibrated mixed"
        )

    gap = payload["expectation_gap"]
    if not isinstance(gap, dict):
        raise AnalysisValidationError("expectation_gap must be an object")
    _expect_exact_keys(gap, ["present", "type", "evidence"], "expectation_gap")
    if not isinstance(gap["present"], bool):
        raise AnalysisValidationError(
            "expectation_gap.present must be boolean"
        )
    _expect_enum(gap["type"], EXPECTATION_GAP_TYPES, "expectation_gap.type")
    if gap["present"]:
        if gap["type"] == "none":
            raise AnalysisValidationError(
                "expectation_gap.type cannot be none when present=true"
            )
        _expect_evidence_list(
            gap["evidence"],
            source_text,
            "expectation_gap.evidence",
            min_items=1,
            max_items=3,
        )
    else:
        if gap["type"] != "none" or gap["evidence"] != []:
            raise AnalysisValidationError(
                "when expectation_gap.present=false, type must be none and "
                "evidence must be an empty array"
            )

    _expect_enum(
        payload["experience_status"],
        EXPERIENCE_STATUSES,
        "experience_status",
    )
    _expect_enum(
        payload["star_text_alignment"],
        STAR_TEXT_ALIGNMENTS,
        "star_text_alignment",
    )

    actions = payload["recommended_actions"]
    if not isinstance(actions, list):
        raise AnalysisValidationError("recommended_actions must be an array")
    if len(actions) > 3:
        raise AnalysisValidationError(
            "recommended_actions must contain no more than 3 items"
        )
    for index, action in enumerate(actions):
        context = f"recommended_actions[{index}]"
        if not isinstance(action, dict):
            raise AnalysisValidationError(f"{context} must be an object")
        _expect_exact_keys(
            action, ["audience", "action", "evidence"], context
        )
        _expect_enum(
            action["audience"], ACTION_AUDIENCES, f"{context}.audience"
        )
        if not isinstance(action["action"], str) or not action["action"]:
            raise AnalysisValidationError(
                f"{context}.action must be non-empty"
            )
        _expect_evidence(
            action["evidence"], source_text, f"{context}.evidence"
        )

    confidence = payload["confidence"]
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not 0 <= confidence <= 1
    ):
        raise AnalysisValidationError(
            "confidence must be a number between 0 and 1"
        )
    if not isinstance(payload["ambiguous"], bool):
        raise AnalysisValidationError("ambiguous must be boolean")
    if not isinstance(payload["analysis_note"], str):
        raise AnalysisValidationError("analysis_note must be a string")
    if payload["ambiguous"] and not payload["analysis_note"].strip():
        raise AnalysisValidationError(
            "ambiguous=true requires a non-empty analysis_note"
        )
    return payload


__all__ = [
    "ACTION_AUDIENCES",
    "ANALYSIS_SCHEMA",
    "API_ANALYSIS_SCHEMA",
    "ASPECT_CODES",
    "AnalysisValidationError",
    "EXPECTATION_GAP_TYPES",
    "EXPERIENCE_STATUSES",
    "ISSUE_CODES",
    "MOTIVATION_CODES",
    "POLARITIES",
    "SCENARIO_CODES",
    "SCHEMA_VERSION",
    "SENTIMENTS",
    "SPEECH_ACT_CODES",
    "STAR_TEXT_ALIGNMENTS",
    "canonical_json",
    "api_schema_hash",
    "schema_hash",
    "normalize_analysis",
    "validate_analysis",
]

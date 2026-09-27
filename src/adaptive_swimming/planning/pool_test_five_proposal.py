from __future__ import annotations

from adaptive_swimming.domain.session_results import (
    CompletionStatus,
    GeneratedWorkout,
    WorkoutSessionResult,
    validate_session_result,
)
from adaptive_swimming.domain.workout import (
    BlockRole,
    EquipmentCode,
    ExerciseCode,
    IntensityCode,
    ProvenanceType,
    RestApplication,
    RestPolicy,
    SessionEnvironment,
    SetGroup,
    SetItem,
    SetType,
    Target,
    TargetType,
    WorkoutBlock,
    WorkoutSession,
)
from adaptive_swimming.evaluation.pace_calibration import PaceObservationKey
from adaptive_swimming.planning.recalibrated_target_review import (
    RecalibratedTargetReviewAction,
    RecalibratedTargetReviewDecision,
    RecalibratedTargetReviewSet,
    applicable_target_seconds,
)
from adaptive_swimming.planning.workout_progression import (
    WorkoutProgressionAssessment,
    WorkoutProgressionObjective,
    compare_workout_progression,
)
from adaptive_swimming.planning.workout_proposal import (
    AdaptationTraceEntry,
    NextWorkoutProposal,
    ProposalStatus,
    generated_text,
)

FINS_TARGET_KEY = PaceObservationKey(
    exercise=ExerciseCode.FREESTYLE,
    distance_meters=50,
    equipment=(EquipmentCode.FINS,),
    intensity=IntensityCode.UNRESOLVED,
)


def select_pool_test_five_target_decision(
    review_set: RecalibratedTargetReviewSet,
    review_decision_id: str,
) -> RecalibratedTargetReviewDecision:
    matches = tuple(
        decision
        for decision in review_set.decisions
        if decision.review_decision_id == review_decision_id
    )
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one Pool Test 5 target decision; found {len(matches)}.")
    decision = matches[0]
    if decision.action != RecalibratedTargetReviewAction.RETAIN_CURRENT_TARGET:
        raise ValueError("Pool Test 5 requires a retained current target decision.")
    if not decision.may_be_applied_to_future_workout:
        raise ValueError("Pool Test 5 target decision is not applicable.")
    if decision.proposal.key != FINS_TARGET_KEY:
        raise ValueError("Pool Test 5 target decision must reference the 50 m fins key.")
    if applicable_target_seconds(decision) != 65:
        raise ValueError("Pool Test 5 retained fins target must be 65 seconds.")
    return decision


def _item(
    *,
    sequence: int,
    distance_meters: int,
    exercise: ExerciseCode,
    repetitions: int = 1,
    intensity: IntensityCode = IntensityCode.UNRESOLVED,
    equipment: tuple[EquipmentCode, ...] = (),
    target: Target | None = None,
    instruction: str | None = None,
    text: str,
) -> SetItem:
    return SetItem(
        sequence=sequence,
        repetitions=repetitions,
        distance_meters=distance_meters,
        exercise=exercise,
        intensity=intensity,
        equipment=equipment,
        target=target,
        swimmer_instruction=instruction,
        source_text=generated_text(text),
    )


def build_pool_test_five_workout(target_seconds: int) -> WorkoutSession:
    if target_seconds != 65:
        raise ValueError("Pool Test 5 requires the retained 65-second fins target.")

    target = Target(
        target_type=TargetType.REPETITION_COMPLETION_TIME,
        raw_value="1:05",
        target_seconds=target_seconds,
    )
    blocks = (
        WorkoutBlock(
            sequence=1,
            role=BlockRole.WARM_UP,
            provenance_type=ProvenanceType.ENGINE_ADDED,
            source_text=generated_text("300 m recovery freestyle"),
            set_groups=(
                SetGroup(
                    sequence=1,
                    set_type=SetType.CONTINUOUS,
                    items=(
                        _item(
                            sequence=1,
                            distance_meters=300,
                            exercise=ExerciseCode.FREESTYLE,
                            intensity=IntensityCode.RECOVERY,
                            text="300 m recovery freestyle",
                        ),
                    ),
                    source_text=generated_text("300 m recovery freestyle"),
                ),
            ),
        ),
        WorkoutBlock(
            sequence=2,
            role=BlockRole.PREPARATION,
            provenance_type=ProvenanceType.ENGINE_ADDED,
            source_text=generated_text("200 m ordered preparation sequence"),
            set_groups=(
                SetGroup(
                    sequence=1,
                    set_type=SetType.ORDERED_SEQUENCE,
                    rest=RestPolicy(seconds=30, application=RestApplication.BETWEEN_ITEMS),
                    items=(
                        _item(
                            sequence=1,
                            distance_meters=50,
                            exercise=ExerciseCode.ASYMMETRIC,
                            text="50 m asymmetric",
                        ),
                        _item(
                            sequence=2,
                            distance_meters=50,
                            exercise=ExerciseCode.UNILATERAL,
                            text="50 m unilateral",
                        ),
                        _item(
                            sequence=3,
                            distance_meters=100,
                            exercise=ExerciseCode.FREESTYLE,
                            equipment=(EquipmentCode.PADDLES_INVERTED,),
                            text="100 m inverted-grip paddles",
                        ),
                    ),
                    source_text=generated_text(
                        "50 m asymmetric, 50 m unilateral, 100 m inverted-grip paddles"
                    ),
                ),
            ),
        ),
        WorkoutBlock(
            sequence=3,
            role=BlockRole.MAIN_SET,
            provenance_type=ProvenanceType.ENGINE_ADDED,
            source_text=generated_text("4 x 100 m aerobic freestyle"),
            set_groups=(
                SetGroup(
                    sequence=1,
                    set_type=SetType.REPEATED_INTERVAL,
                    rest=RestPolicy(seconds=40, application=RestApplication.BETWEEN_REPETITIONS),
                    items=(
                        _item(
                            sequence=1,
                            repetitions=4,
                            distance_meters=100,
                            exercise=ExerciseCode.FREESTYLE,
                            intensity=IntensityCode.AEROBIC,
                            instruction="Record each repetition time.",
                            text="4 x 100 m aerobic freestyle",
                        ),
                    ),
                    source_text=generated_text("4 x 100 m aerobic freestyle, 40 sec rest"),
                ),
            ),
        ),
        WorkoutBlock(
            sequence=4,
            role=BlockRole.MAIN_SET,
            provenance_type=ProvenanceType.ENGINE_ADDED,
            source_text=generated_text("4 x 50 m freestyle with fins at 1:05 target"),
            set_groups=(
                SetGroup(
                    sequence=1,
                    set_type=SetType.REPEATED_INTERVAL,
                    rest=RestPolicy(seconds=30, application=RestApplication.BETWEEN_REPETITIONS),
                    items=(
                        _item(
                            sequence=1,
                            repetitions=4,
                            distance_meters=50,
                            exercise=ExerciseCode.FREESTYLE,
                            equipment=(EquipmentCode.FINS,),
                            target=target,
                            instruction=(
                                "Complete each repetition in 1:05 or faster and record "
                                "cumulative elapsed readings."
                            ),
                            text="4 x 50 m with fins at 1:05 target",
                        ),
                    ),
                    source_text=generated_text("4 x 50 m fins, 30 sec rest"),
                ),
            ),
        ),
        WorkoutBlock(
            sequence=5,
            role=BlockRole.TECHNIQUE,
            provenance_type=ProvenanceType.ENGINE_ADDED,
            source_text=generated_text("4 x 25 m kickboard"),
            set_groups=(
                SetGroup(
                    sequence=1,
                    set_type=SetType.REPEATED_INTERVAL,
                    rest=RestPolicy(seconds=30, application=RestApplication.BETWEEN_REPETITIONS),
                    items=(
                        _item(
                            sequence=1,
                            repetitions=4,
                            distance_meters=25,
                            exercise=ExerciseCode.KICKBOARD_KICK,
                            equipment=(EquipmentCode.KICKBOARD,),
                            text="4 x 25 m kickboard",
                        ),
                    ),
                    source_text=generated_text("4 x 25 m kickboard, 30 sec rest"),
                ),
            ),
        ),
        WorkoutBlock(
            sequence=6,
            role=BlockRole.COOL_DOWN,
            provenance_type=ProvenanceType.ENGINE_ADDED,
            source_text=generated_text("300 m recovery freestyle"),
            set_groups=(
                SetGroup(
                    sequence=1,
                    set_type=SetType.CONTINUOUS,
                    items=(
                        _item(
                            sequence=1,
                            distance_meters=300,
                            exercise=ExerciseCode.FREESTYLE,
                            intensity=IntensityCode.RECOVERY,
                            text="300 m recovery freestyle",
                        ),
                    ),
                    source_text=generated_text("300 m recovery freestyle"),
                ),
            ),
        ),
    )
    return WorkoutSession(
        session_id="WT_ENGINE_POOL_TEST_005_V1",
        environment=SessionEnvironment.POOL,
        source_id="SRC_8C962466BDCC",
        source_sha256="8c962466bdcc1efa53f61787f84e6b6a216c4c5e6d0939520baa2d61d372b008",
        source_section=generated_text("Pool Test 5 adaptive progression proposal"),
        blocks=blocks,
    )


def build_pool_test_five_proposal(
    parent_generated_workout: GeneratedWorkout,
    previous_result: WorkoutSessionResult,
    review_set: RecalibratedTargetReviewSet,
    *,
    review_decision_id: str,
    proposal_id: str,
    generated_workout_id: str,
) -> tuple[NextWorkoutProposal, WorkoutProgressionAssessment]:
    validate_session_result(parent_generated_workout, previous_result)
    if previous_result.completion_status == CompletionStatus.NOT_STARTED:
        raise ValueError("Pool Test 5 requires a completed previous result.")
    if previous_result.safety_issue_reported:
        raise ValueError("Pool Test 5 cannot progress from a safety-flagged result.")
    decision = select_pool_test_five_target_decision(review_set, review_decision_id)
    proposed_workout = build_pool_test_five_workout(applicable_target_seconds(decision))
    generated = GeneratedWorkout(
        generated_workout_id=generated_workout_id,
        workout_version=1,
        workout=proposed_workout,
        pool_length_meters=parent_generated_workout.pool_length_meters,
        available_training_seconds=parent_generated_workout.available_training_seconds,
        equipment_available=parent_generated_workout.equipment_available,
        generation_reason="POOL_TEST_5_ADAPTIVE_PROGRESSION_PROPOSAL",
    )
    assessment = compare_workout_progression(
        parent=parent_generated_workout,
        candidate=generated,
        objective=WorkoutProgressionObjective.ADAPTIVE_PROGRESSION,
    )
    if not assessment.satisfies_objective:
        raise ValueError("Pool Test 5 candidate does not satisfy adaptive progression.")
    proposal = NextWorkoutProposal(
        proposal_id=proposal_id,
        proposal_version=1,
        parent_generated_workout_id=parent_generated_workout.generated_workout_id,
        previous_session_result_id=previous_result.session_result_id,
        status=ProposalStatus.PROPOSED,
        proposed_generated_workout=generated,
        adaptation_trace=(
            AdaptationTraceEntry(
                rule_id="ADAPTIVE_PROGRESSION_OBJECTIVE",
                description=(
                    f"Observed {len(assessment.structural_changes)} structural "
                    "parent-versus-candidate changes."
                ),
            ),
            AdaptationTraceEntry(
                rule_id="RETAIN_REVIEWED_FINS_TARGET",
                description=(
                    f"Applied retained decision {decision.review_decision_id} at 65 seconds."
                ),
            ),
            AdaptationTraceEntry(
                rule_id="DEFER_OTHER_REVIEW_ANCHORS",
                description="Applied no additional pace targets.",
            ),
        ),
        limitations=(
            "The candidate structure requires human review before persistence or acceptance.",
            "Structural difference does not establish training suitability.",
            "Untargeted swim duration and transition time remain unresolved.",
            "The builder performs no persistence or acceptance.",
        ),
    )
    return proposal, assessment

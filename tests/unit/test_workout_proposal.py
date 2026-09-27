import pytest
from pydantic import ValidationError

from adaptive_swimming.catalog.reference_workouts import (
    build_reference_workout,
)
from adaptive_swimming.domain.session_results import (
    CompletionStatus,
    GeneratedWorkout,
    WorkoutSessionResult,
)
from adaptive_swimming.domain.workout import (
    BlockRole,
    EquipmentCode,
    ProvenanceType,
)
from adaptive_swimming.planning.time_feasibility import (
    TimeFeasibilityStatus,
)
from adaptive_swimming.planning.workout_proposal import (
    NextWorkoutProposal,
    ProposalStatus,
    build_pool_test_two_proposal,
    build_pool_test_two_workout,
)


def test_pace_observation_sets_include_swimmer_instruction() -> None:
    workout = build_pool_test_two_workout()

    block_three_item = workout.blocks[2].set_groups[0].items[0]
    block_four_item = workout.blocks[3].set_groups[0].items[0]

    assert block_three_item.swimmer_instruction == "Record each repetition time."
    assert block_four_item.swimmer_instruction == "Record each repetition time."


def test_only_pace_observation_sets_request_time_recording() -> None:
    workout = build_pool_test_two_workout()

    instructed_items = [
        item
        for block in workout.blocks
        for set_group in block.set_groups
        for item in set_group.items
        if item.swimmer_instruction is not None
    ]

    assert len(instructed_items) == 2
    assert all(
        item.swimmer_instruction == "Record each repetition time." for item in instructed_items
    )


def build_parent_generated_workout() -> GeneratedWorkout:
    return GeneratedWorkout(
        generated_workout_id="GW_20260901_001_V1",
        workout_version=1,
        workout=build_reference_workout(),
        pool_length_meters=12.5,
        equipment_available=(
            EquipmentCode.FINS,
            EquipmentCode.PADDLES,
            EquipmentCode.KICKBOARD,
        ),
        generation_reason="BASELINE_SESSION",
    )


def build_previous_result() -> WorkoutSessionResult:
    return WorkoutSessionResult(
        session_result_id="SR_20260901_001_V2",
        generated_workout_id="GW_20260901_001_V1",
        result_version=2,
        completion_status=CompletionStatus.STOPPED_EARLY,
        completed_distance_meters=1100,
        actual_total_seconds=2700,
        perceived_exertion=5,
        equipment_used=(
            EquipmentCode.PADDLES,
            EquipmentCode.FINS,
        ),
        block_results=(),
        safety_issue_reported=False,
        notes=(
            "Available training time was 45 minutes. Blocks 1 through 4 were completed as written."
        ),
    )


def build_proposal() -> NextWorkoutProposal:
    return build_pool_test_two_proposal(
        build_parent_generated_workout(),
        build_previous_result(),
    )


def test_proposal_status_is_proposed() -> None:
    proposal = build_proposal()

    assert proposal.status == ProposalStatus.PROPOSED


def test_proposal_preserves_parent_and_previous_result_ids() -> None:
    proposal = build_proposal()

    assert proposal.parent_generated_workout_id == "GW_20260901_001_V1"
    assert proposal.previous_session_result_id == "SR_20260901_001_V2"


def test_proposed_workout_uses_sixty_minute_constraint() -> None:
    proposal = build_proposal()

    assert proposal.proposed_generated_workout.available_training_seconds == 3600


def test_proposed_workout_has_expected_distance() -> None:
    proposal = build_proposal()

    assert proposal.proposed_generated_workout.planned_distance_meters == 1500


def test_proposed_workout_uses_confirmed_pool_length() -> None:
    proposal = build_proposal()

    assert proposal.proposed_generated_workout.pool_length_meters == 12.5


def test_proposed_workout_has_six_ordered_blocks() -> None:
    workout = build_pool_test_two_workout()

    assert len(workout.blocks) == 6
    assert [block.sequence for block in workout.blocks] == [
        1,
        2,
        3,
        4,
        5,
        6,
    ]


def test_proposed_block_roles_match_structure() -> None:
    workout = build_pool_test_two_workout()

    assert [block.role for block in workout.blocks] == [
        BlockRole.WARM_UP,
        BlockRole.PREPARATION,
        BlockRole.MAIN_SET,
        BlockRole.MAIN_SET,
        BlockRole.TECHNIQUE,
        BlockRole.TECHNIQUE,
    ]


def test_every_proposed_block_is_engine_added() -> None:
    workout = build_pool_test_two_workout()

    assert all(block.provenance_type == ProvenanceType.ENGINE_ADDED for block in workout.blocks)


def test_every_proposed_instruction_is_labeled_as_engine_generated() -> None:
    workout = build_pool_test_two_workout()

    assert workout.source_section.startswith("Engine proposal:")

    for block in workout.blocks:
        assert block.source_text.startswith("Engine proposal:")

        for set_group in block.set_groups:
            assert set_group.source_text.startswith("Engine proposal:")

            for item in set_group.items:
                assert item.source_text.startswith("Engine proposal:")


def test_proposed_workout_contains_no_fixed_targets() -> None:
    workout = build_pool_test_two_workout()

    assert all(
        item.target is None
        for block in workout.blocks
        for set_group in block.set_groups
        for item in set_group.items
    )


def test_proposed_workout_equals_120_pool_lengths() -> None:
    proposal = build_proposal()
    generated = proposal.proposed_generated_workout

    pool_lengths = generated.planned_distance_meters / generated.pool_length_meters

    assert pool_lengths == 120


def test_proposed_workout_has_expected_rest() -> None:
    proposal = build_proposal()

    assert proposal.proposed_generated_workout.configured_rest_seconds == 540


def test_proposed_workout_timing_is_fully_unresolved() -> None:
    proposal = build_proposal()
    generated = proposal.proposed_generated_workout

    assert generated.known_swim_seconds == 0
    assert generated.unresolved_distance_meters == 1500


def test_proposal_round_trips_through_json() -> None:
    proposal = build_proposal()

    loaded = NextWorkoutProposal.model_validate_json(proposal.model_dump_json())

    assert loaded == proposal


def test_proposal_does_not_modify_parent_workout() -> None:
    parent = build_parent_generated_workout()
    previous_result = build_previous_result()

    build_pool_test_two_proposal(
        parent,
        previous_result,
    )

    assert parent.planned_distance_meters == 2600
    assert parent.generated_workout_id == ("GW_20260901_001_V1")


def test_proposal_does_not_modify_previous_result() -> None:
    parent = build_parent_generated_workout()
    previous_result = build_previous_result()

    build_pool_test_two_proposal(
        parent,
        previous_result,
    )

    assert previous_result.completed_distance_meters == 1100
    assert previous_result.completion_status == CompletionStatus.STOPPED_EARLY


@pytest.mark.parametrize(
    "status",
    (
        ProposalStatus.ACCEPTED,
        ProposalStatus.REJECTED,
    ),
)
def test_new_proposal_rejects_non_proposed_status(
    status: ProposalStatus,
) -> None:
    proposal = build_proposal()
    payload = proposal.model_dump()
    payload["status"] = status

    with pytest.raises(
        ValidationError,
        match="must initially be PROPOSED",
    ):
        NextWorkoutProposal.model_validate(payload)
        proposal.model_copy(update={"status": status}).model_validate(
            {
                **proposal.model_dump(),
                "status": status,
            }
        )


def test_proposal_rejects_parent_generated_workout_id() -> None:
    proposal = build_proposal()

    with pytest.raises(
        ValidationError,
        match="must use a new generated-workout ID",
    ):
        NextWorkoutProposal.model_validate(
            {
                **proposal.model_dump(),
                "proposed_generated_workout": {
                    **proposal.proposed_generated_workout.model_dump(),
                    "generated_workout_id": (proposal.parent_generated_workout_id),
                },
            }
        )


def test_proposal_rejects_invalid_previous_result_linkage() -> None:
    previous_result = build_previous_result().model_copy(
        update={"generated_workout_id": ("GW_20260901_999_V1")}
    )

    with pytest.raises(
        ValueError,
        match="does not belong",
    ):
        build_pool_test_two_proposal(
            build_parent_generated_workout(),
            previous_result,
        )


def test_adaptation_trace_contains_required_rules() -> None:
    proposal = build_proposal()

    rule_ids = {entry.rule_id for entry in proposal.adaptation_trace}

    assert rule_ids == {
        "TIME_BUDGET_60_MINUTES",
        "BASELINE_COMPLETION_EVIDENCE",
        "REDUCE_PLANNED_DISTANCE",
        "REDUCE_REPETITIVE_STRUCTURE",
        "PACE_CALIBRATION_REQUIRED",
        "PRESERVE_REST",
    }


def test_limitations_include_single_session_boundary() -> None:
    proposal = build_proposal()

    assert any(
        "one formally recorded pool session" in limitation for limitation in proposal.limitations
    )


def test_proposal_time_feasibility_remains_unresolved() -> None:
    proposal = build_proposal()
    feasibility = proposal.time_feasibility

    assert feasibility.available_seconds == 3600
    assert feasibility.known_swim_seconds == 0
    assert feasibility.configured_rest_seconds == 540
    assert feasibility.known_required_seconds == 540
    assert feasibility.remaining_after_known_seconds == 3060
    assert feasibility.unresolved_distance_meters == 1500
    assert feasibility.status == TimeFeasibilityStatus.UNRESOLVED


def test_proposal_does_not_claim_confirmed_time_fit() -> None:
    proposal = build_proposal()

    assert proposal.time_feasibility.status != TimeFeasibilityStatus.FITS_KNOWN_TIME
    assert any(
        "transition time remain unresolved" in limitation for limitation in proposal.limitations
    )

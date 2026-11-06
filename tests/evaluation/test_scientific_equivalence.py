"""Proven equivalences pass; wrong data and inconsistent statistics still fail."""
import copy
import math
import pytest
from evaluation.workflow import MissingEvidence, operand
from evaluation.workflow.scientific_equivalence import (
    distance_matrix, optimal_bipartition_profiles, partition_silhouette,
    partition_adjusted_rand,
)


DIST = [[0, 2, 3, 5], [2, 0, 7, 11], [3, 7, 0, 13], [5, 11, 13, 0]]
POINTS = [[0, 0], [.1, 80], [.2, 160], [3, 5], [3.1, 85], [3.2, 165]]


def test_distance_conversion_is_lossless_and_preserves_object_order():
    before = copy.deepcopy(DIST)
    assert distance_matrix([2, 3, 5, 7, 11, 13], DIST) == DIST
    assert distance_matrix(DIST, DIST) == DIST
    assert distance_matrix([3, 2, 5, 7, 11, 13], DIST) != DIST
    assert DIST == before


@pytest.mark.parametrize('value', [[2, 3], [True]*6, [math.nan]*6, [[0, 2], [2, 0]], None])
def test_incomplete_or_ambiguous_distances_are_rejected(value):
    with pytest.raises(MissingEvidence):
        distance_matrix(value, DIST)


@pytest.mark.parametrize('reference', [[[1, .5], [.5, 1]], [[0, 2], [3, 0]], [[0, -2], [-2, 0]], [[0, math.inf], [math.inf, 0]]])
def test_non_distance_reference_cannot_enable_conversion(reference):
    with pytest.raises(MissingEvidence):
        distance_matrix([2], reference)


def test_exact_optimum_ties_are_enumerated_independently_of_the_answer():
    profiles = optimal_bipartition_profiles(POINTS)
    assert {tuple(p['memberships']) for p in profiles} == {
        (0, 0, 1, 0, 0, 1), (0, 1, 1, 0, 1, 1)}
    assert all(p['noise_mask'] is None for p in profiles)
    assert (0, 0, 0, 1, 1, 1) not in {tuple(p['memberships']) for p in profiles}
    assert partition_silhouette(POINTS, [0, 0, 1, 0, 0, 1]) == pytest.approx(.637875528126367)
    assert partition_adjusted_rand([0, 0, 1, 1], ['b', 'b', 'a', 'a']) == 1
    assert partition_adjusted_rand([0, 0, 1, 1], [0, 1, 0, 1]) < 0


@pytest.mark.parametrize('points,labels', [(POINTS, [0]*6), (POINTS, [0, 1]), (POINTS, [True]*6), ([[0, 1], [2, math.inf]], [0, 1])])
def test_bad_source_or_partition_fails_closed(points, labels):
    with pytest.raises(MissingEvidence):
        partition_silhouette(points, labels)


def test_expression_arity_fails_with_missing_evidence():
    with pytest.raises(MissingEvidence):
        operand({'operation': 'partition_silhouette', 'args': [{'value': POINTS}]}, {})


def test_scientific_clustering_rule_accepts_a_proven_tie_but_not_wrong_statistics():
    from pathlib import Path
    from evaluation.workflow import score_workflow
    from evaluation.suites.reference_context import prediction_from_reference
    from src.utils.io import read_jsonl
    root = Path(__file__).resolve().parents[2]
    ref = next(row for row in read_jsonl(root/'tasks/mini/evaluation/references.jsonl.gz')
               if row['id'] == 'SMAS-0046')
    pred = prediction_from_reference(root, ref)
    for labels in [[0, 0, 1, 0, 0, 1], [0, 1, 1, 0, 1, 1], [0, 0, 0, 1, 1, 1]]:
        answer = copy.deepcopy(pred['final_answer'])
        answer['raw_labels'] = labels
        answer['raw_silhouette'] = partition_silhouette(POINTS, labels)
        answer['adjusted_rand'] = partition_adjusted_rand(labels, answer['standardized_labels'])
        row = {**pred, 'final_answer': answer}
        assert score_workflow(ref, row)['answer_pass'] is (labels != [0, 0, 0, 1, 1, 1])
        if labels != [0, 0, 0, 1, 1, 1]:
            answer['adjusted_rand'] = 1.0
            assert not score_workflow(ref, row)['answer_pass']

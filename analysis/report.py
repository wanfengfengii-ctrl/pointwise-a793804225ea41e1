from archive.schema import ReportObservation, ReportSnapshot
from sampling.restricted import RestrictedPairPlan

from .contrast import squared_color_difference
from .eligibility import IssueEvidence


V1_REPORT_BASIS = 'v1/full-pair-mean-squared-color-difference'
RESTRICTED_REPORT_BASIS = 'v2/restricted-pair-mean-squared-color-difference'


def build_report_draft(evidence: IssueEvidence) -> ReportSnapshot:
    left = evidence.left
    right = evidence.right
    squared = squared_color_difference(left.value, right.value)
    if isinstance(evidence.plan, RestrictedPairPlan):
        pair_count = len(evidence.plan.probabilities)
        probability = evidence.draw.probability
        estimate = squared / (pair_count * probability)
        return ReportSnapshot(
            basis=RESTRICTED_REPORT_BASIS,
            batch_id=evidence.plan.batch_id,
            freeze_id=evidence.plan.freeze_id,
            plan_id=evidence.plan.plan_id,
            draw_id=evidence.draw.draw_id,
            left=ReportObservation(left.piece_id, left.value, left.instrument_ref),
            right=ReportObservation(right.piece_id, right.value, right.instrument_ref),
            estimate=estimate,
            pair_count=pair_count,
            probability=probability,
        )
    return ReportSnapshot(
        basis=V1_REPORT_BASIS,
        batch_id=evidence.plan.batch_id,
        freeze_id=evidence.plan.freeze_id,
        plan_id=evidence.plan.plan_id,
        draw_id=evidence.draw.draw_id,
        left=ReportObservation(left.piece_id, left.value, left.instrument_ref),
        right=ReportObservation(right.piece_id, right.value, right.instrument_ref),
        estimate=squared,
    )

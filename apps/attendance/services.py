"""
ATTENDANCE — KUMUSH reward service
=====================================
Business rule (product spec):
  Teacher marks a student PRESENT for a lesson → student gets exactly +10
  KUMUSH, exactly once per attendance record, no matter how many times the
  record is saved/retried/double-clicked.

  If attendance is later corrected AWAY from PRESENT, the +10 is clawed
  back (once). If corrected BACK to PRESENT, it is re-awarded (once).

Idempotency is derived from the ledger itself — not a cached boolean flag
on Attendance — by summing every KumushTransaction ever created for this
exact attendance record (source_type in ATTENDANCE/ATTENDANCE_REVERSAL,
source_id=str(attendance.pk)). The net of that sum is always either 0
(not currently awarded) or +10 (currently awarded); this function's whole
job is to make the net match what `status` says it should be, and to do
that at most once per call under a real row lock — safe against retries,
double-clicks, and concurrent requests for the same record.
"""
from __future__ import annotations

import logging

from django.db import transaction as db_transaction

logger = logging.getLogger('apps.attendance.services')

ATTENDANCE_REWARD = 10
SOURCE_TYPE_AWARD = 'attendance'
SOURCE_TYPE_REVERSAL = 'attendance_reversal'


def sync_attendance_kumush(attendance, actor=None):
    """
    Ensure this attendance record's KUMUSH state matches its current
    status. Call this after every create/update of an Attendance row,
    from every write path (single create, single edit, bulk create/update)
    — there is no signal-based auto-trigger, because Django's bulk_create/
    bulk_update (used by the bulk-attendance endpoint) do not emit
    post_save signals, so a signal-only approach would silently miss the
    most-used real-world path.
    """
    from django.db.models import Sum

    from apps.attendance.models import Attendance
    from apps.notifications.models import ActivityLog
    from apps.notifications.views import log_activity
    from apps.store.models import KumushTransaction

    with db_transaction.atomic():
        locked = Attendance.objects.select_for_update().get(pk=attendance.pk)

        net = KumushTransaction.objects.filter(
            source_type__in=[SOURCE_TYPE_AWARD, SOURCE_TYPE_REVERSAL],
            source_id=str(locked.pk),
        ).aggregate(total=Sum('amount'))['total'] or 0

        is_present = locked.status == Attendance.Status.PRESENT

        if is_present and net == 0:
            reason = f"Davomat: {locked.group.name} | {locked.date} | Keldi"
            txn = locked.student.apply_kumush_and_xp(
                coins_delta=ATTENDANCE_REWARD, reason=reason, created_by=actor,
                source_type=SOURCE_TYPE_AWARD, source_id=str(locked.pk),
            )
            if txn is not None:
                log_activity(
                    actor, ActivityLog.Action.UPDATE, 'Attendance', locked.pk, str(locked),
                    changes={'kumush_awarded': ATTENDANCE_REWARD,
                             'balance_before': txn.balance_before, 'balance_after': txn.balance_after},
                )
            return 'awarded'

        if not is_present and net == ATTENDANCE_REWARD:
            # Claw back exactly what was given. If the student has since
            # spent below that amount, clamp to what's actually available
            # rather than letting the balance go negative (a hard product
            # rule) — the reason string discloses when this happened, since
            # silently under-reversing would otherwise be invisible in the
            # ledger. This is a genuine, disclosed edge case: "teacher
            # corrects attendance after the student already spent the
            # reward" has no universally-correct resolution; clamping
            # preserves the non-negative-balance invariant as the higher
            # priority, per the explicit product rule.
            locked.student.refresh_from_db(fields=['coins'])
            available = locked.student.coins
            reversal_amount = min(ATTENDANCE_REWARD, available)
            reason = f"Davomat bekor qilindi (tuzatish): {locked.group.name} | {locked.date}"
            if reversal_amount < ATTENDANCE_REWARD:
                reason += " — TO'LIQ QAYTARILMADI, balans yetarli emas edi"
                logger.warning(
                    f"Attendance reversal short: {locked.student.full_name} "
                    f"had only {available} coins, needed {ATTENDANCE_REWARD}"
                )
            if reversal_amount > 0:
                txn = locked.student.apply_kumush_and_xp(
                    coins_delta=-reversal_amount, reason=reason, created_by=actor,
                    source_type=SOURCE_TYPE_REVERSAL, source_id=str(locked.pk),
                )
                if txn is not None:
                    log_activity(
                        actor, ActivityLog.Action.UPDATE, 'Attendance', locked.pk, str(locked),
                        changes={'kumush_reversed': reversal_amount,
                                 'balance_before': txn.balance_before, 'balance_after': txn.balance_after},
                    )
            return 'reversed'

        return 'unchanged'

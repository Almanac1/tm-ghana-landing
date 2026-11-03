from django.db import transaction
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from .models import ClassDate, Reservation, Submission


@receiver(post_save, sender=Submission)
def submission_changed(sender, instance, raw=False, created=False, **kwargs):
    if not raw:
        from .email_queue import reconcile
        if instance.reservation_id and instance.class_date_id:
            Reservation.objects.filter(pk=instance.reservation_id).update(
                session_date=instance.session_date, session_type=instance.session_type)
        reconcile(instance, include_registration=created)
        if created:
            from .email_queue import deliver_immediate_safely
            transaction.on_commit(lambda pk=instance.pk: deliver_immediate_safely(pk))


@receiver(post_save, sender=ClassDate)
def session_changed(sender, instance, raw=False, **kwargs):
    if raw:
        return
    from .email_queue import reconcile
    for submission in Submission.objects.filter(class_date=instance):
        Submission.objects.filter(pk=submission.pk).update(session_date=instance.date.isoformat(), session_type=instance.session_type)
        if submission.reservation_id:
            Reservation.objects.filter(pk=submission.reservation_id).update(session_date=instance.date.isoformat(), session_type=instance.session_type)
        reconcile(submission)


@receiver(post_save, sender=Reservation)
def reservation_changed(sender, instance, raw=False, **kwargs):
    if raw:
        return
    for submission in Submission.objects.filter(reservation=instance):
        if submission.session_date != instance.session_date:
            matches = list(ClassDate.objects.filter(date=instance.session_date, session_type=instance.session_type, is_active=True))
            submission.class_date = matches[0] if len(matches) == 1 else None
            submission.session_date = instance.session_date
        submission.is_cancelled = instance.is_cancelled
        submission.save()


@receiver(pre_delete, sender=ClassDate)
@receiver(pre_delete, sender=Reservation)
def cancel_deleted(sender, instance, **kwargs):
    lookup = {"class_date" if sender == ClassDate else "reservation": instance}
    for submission in Submission.objects.filter(**lookup):
        submission.is_cancelled = True
        submission.save(update_fields=["is_cancelled"])

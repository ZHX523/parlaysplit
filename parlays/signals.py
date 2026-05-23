"""Invalidate OG preview cache when parlay content changes."""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from parlays.models import Parlay, ParlayLeg, Participant
from parlays.services.og_image import invalidate_parlay_og_cache


@receiver(post_save, sender=Parlay)
@receiver(post_save, sender=ParlayLeg)
@receiver(post_delete, sender=ParlayLeg)
@receiver(post_save, sender=Participant)
@receiver(post_delete, sender=Participant)
def bust_parlay_og_cache(sender, instance, **kwargs):
    parlay_id = instance.pk if sender is Parlay else instance.parlay_id
    invalidate_parlay_og_cache(parlay_id)

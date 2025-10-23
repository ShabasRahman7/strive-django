from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from .models import PasswordSetupToken, PasswordResetToken


@receiver(post_save, sender=PasswordSetupToken)
def cleanup_used_setup_tokens(sender, instance, **kwargs):
    """Clean up used password setup tokens immediately"""
    if instance.is_used:
        # Delete the token after a short delay to ensure the response is sent
        from django.utils import timezone
        from datetime import timedelta
        from django.db import transaction
        
        # Use a transaction to ensure atomicity
        with transaction.atomic():
            # Delete the token
            instance.delete()


@receiver(post_save, sender=PasswordResetToken)
def cleanup_used_reset_tokens(sender, instance, **kwargs):
    """Clean up used password reset tokens immediately"""
    if instance.is_used:
        from django.db import transaction
        
        # Use a transaction to ensure atomicity
        with transaction.atomic():
            # Delete the token
            instance.delete()



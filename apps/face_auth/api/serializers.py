from rest_framework import serializers


class EnrollSerializer(serializers.Serializer):
    frame   = serializers.CharField(help_text="Base64-encoded JPEG frame")
    consent = serializers.BooleanField()


class VerifyLoginSerializer(serializers.Serializer):
    face_pending_token = serializers.CharField()
    frames             = serializers.ListField(
        child=serializers.CharField(),
        min_length=1,
        help_text="Base64-encoded JPEG frames (1 yoki undan ko'p)",
    )


class OTPRequestSerializer(serializers.Serializer):
    # One of face_pending_token OR fallback_token is required.
    # fallback_token is longer-lived (10 min) and survives face_pending_token expiry.
    face_pending_token = serializers.CharField(required=False, allow_blank=True, default='')
    fallback_token     = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, data):
        if not data.get('face_pending_token') and not data.get('fallback_token'):
            raise serializers.ValidationError(
                "face_pending_token yoki fallback_token kiritilishi shart."
            )
        return data


class OTPVerifySerializer(serializers.Serializer):
    # Same: accept either token type
    face_pending_token     = serializers.CharField(required=False, allow_blank=True, default='')
    fallback_token         = serializers.CharField(required=False, allow_blank=True, default='')
    otp_verification_token = serializers.CharField()
    otp                    = serializers.CharField(min_length=6, max_length=6)

    def validate(self, data):
        if not data.get('face_pending_token') and not data.get('fallback_token'):
            raise serializers.ValidationError(
                "face_pending_token yoki fallback_token kiritilishi shart."
            )
        return data

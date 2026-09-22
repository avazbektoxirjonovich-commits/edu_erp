from django.contrib import admin

from .models import Competition, Participant, Result


@admin.register(Competition)
class CompetitionAdmin(admin.ModelAdmin):
    list_display  = ['name', 'grade_from', 'grade_to', 'status', 'registration_deadline',
                     'competition_date', 'created_by', 'created_at']
    list_filter   = ['status']
    search_fields = ['name']
    readonly_fields = ['created_by', 'created_at', 'updated_at']


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display  = ['first_name', 'last_name', 'phone', 'grade', 'status', 'competition', 'registered_at']
    list_filter   = ['status', 'grade', 'competition']
    search_fields = ['first_name', 'last_name', 'phone']
    readonly_fields = ['confirmed_by', 'confirmed_at', 'ip_address', 'registered_at']


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display  = ['participant', 'score', 'place', 'entered_by', 'entered_at']
    search_fields = ['participant__first_name', 'participant__last_name']
    readonly_fields = ['entered_by', 'entered_at']

from django.contrib import admin
from .models import Survey, Question, Option, Response, Answer


class OptionInline(admin.TabularInline):
    model = Option
    extra = 3
    fields = ["text", "order"]


class QuestionInline(admin.StackedInline):
    model = Question
    extra = 1
    fields = ["text", "question_type", "helper_text", "is_required", "order"]
    show_change_link = True  # lets you drill into a question to manage its options


@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    list_display = ["title", "is_published", "is_active", "starts_at", "ends_at", "created_at"]
    prepopulated_fields = {"slug": ["title"]}
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ["text", "survey", "question_type", "order", "is_required"]
    list_filter = ["survey", "question_type"]
    inlines = [OptionInline]


@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    list_display = ["survey", "respondent", "submitted_at"]
    list_filter = ["survey"]
    readonly_fields = ["submitted_at"]
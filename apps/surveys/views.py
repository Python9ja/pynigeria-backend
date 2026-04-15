from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.response import Response as DRFResponse
from rest_framework.views import APIView

from .models import Survey, Question, Option, Response, Answer
from .serializers import (
    SurveyListSerializer,
    SurveyDetailSerializer,
    ResponseSubmitSerializer,
    ResponseResultSerializer,
)


# ── Survey List & Detail ──────────────────────────────────────────────────────

class SurveyListView(generics.ListAPIView):
    """
    GET /api/surveys/
    Returns all published, active surveys. Public.
    Admins get all surveys including unpublished.
    """
    serializer_class = SurveyListSerializer

    def get_queryset(self):
        qs = Survey.objects.all().order_by("-created_at")
        if not self.request.user.is_staff:
            qs = qs.filter(is_published=True)
        return qs

    def get_permissions(self):
        return [AllowAny()]


class SurveyDetailView(generics.RetrieveAPIView):
    """
    GET /api/surveys/<slug>/
    Returns a survey with all its questions and options.
    """
    serializer_class = SurveyDetailSerializer
    lookup_field = "slug"

    def get_queryset(self):
        qs = Survey.objects.prefetch_related("questions__options")
        if not self.request.user.is_staff:
            qs = qs.filter(is_published=True)
        return qs

    def get_permissions(self):
        return [AllowAny()]


# ── Survey Submission ─────────────────────────────────────────────────────────

class SurveySubmitView(APIView):
    """
    POST /api/surveys/<slug>/submit/
    Submit a response to a survey.
    Anonymous surveys: no auth required.
    Non-anonymous: auth required.
    """

    def get_permissions(self):
        survey = Survey.objects.filter(slug=self.kwargs.get("slug")).first()
        if survey and survey.is_anonymous:
            return [AllowAny()]
        return [IsAuthenticated()]

    def post(self, request, slug):
        survey = get_object_or_404(Survey, slug=slug, is_published=True)

        # Check survey window
        if not survey.is_active:
            return DRFResponse(
                {"detail": "This survey is not currently active."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Prevent duplicate submissions for authenticated users
        if request.user.is_authenticated:
            already_submitted = Response.objects.filter(
                survey=survey, respondent=request.user
            ).exists()
            if already_submitted:
                return DRFResponse(
                    {"detail": "You have already submitted a response to this survey."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Validate
        serializer = ResponseSubmitSerializer(
            data=request.data,
            context={"survey": survey, "request": request},
        )
        if not serializer.is_valid():
            return DRFResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Save atomically
        with transaction.atomic():
            survey_response = Response.objects.create(
                survey=survey,
                respondent=request.user if request.user.is_authenticated else None,
            )

            for answer_data in serializer.validated_data["answers"]:
                question = Question.objects.get(id=answer_data["question_id"])
                answer = Answer.objects.create(
                    response=survey_response,
                    question=question,
                    text_value=answer_data.get("text_value", ""),
                )
                if answer_data.get("selected_option_ids"):
                    answer.selected_options.set(answer_data["selected_option_ids"])

        return DRFResponse(
            {"detail": "Response submitted successfully.", "response_id": survey_response.id},
            status=status.HTTP_201_CREATED,
        )


# ── Survey Results (admin only) ───────────────────────────────────────────────

class SurveyResultsView(APIView):
    """
    GET /api/surveys/<slug>/results/
    Returns aggregated results per question.
    Admin only.
    """
    permission_classes = [IsAdminUser]

    def get(self, request, slug):
        survey = get_object_or_404(Survey, slug=slug)
        questions = survey.questions.prefetch_related("options", "answers__selected_options")

        results = []

        for question in questions:
            q_data = {
                "question_id": question.id,
                "question_text": question.text,
                "question_type": question.question_type,
                "total_answers": question.answers.count(),
            }

            if question.question_type in ("single", "multiple", "boolean"):
                option_counts = {}
                for option in question.options.all():
                    count = option.answer_set.filter(
                        response__survey=survey
                    ).count()
                    option_counts[option.text] = count
                q_data["option_counts"] = option_counts

            elif question.question_type == "scale":
                values = [
                    int(a.text_value)
                    for a in question.answers.all()
                    if a.text_value.strip().isdigit()
                ]
                q_data["average"] = round(sum(values) / len(values), 2) if values else None
                q_data["distribution"] = {
                    str(i): values.count(i) for i in range(1, 6)
                }

            elif question.question_type in ("text", "textarea"):
                # Return raw responses — useful for open-ended questions
                q_data["responses"] = [
                    a.text_value
                    for a in question.answers.all()
                    if a.text_value.strip()
                ]

            results.append(q_data)

        return DRFResponse({
            "survey": survey.title,
            "total_responses": survey.responses.count(),
            "results": results,
        })


# ── Check if user already responded ──────────────────────────────────────────

class SurveyStatusView(APIView):
    """
    GET /api/surveys/<slug>/status/
    Returns whether the current user has already submitted.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        survey = get_object_or_404(Survey, slug=slug)
        has_responded = Response.objects.filter(
            survey=survey, respondent=request.user
        ).exists()
        return DRFResponse({
            "has_responded": has_responded,
            "is_active": survey.is_active,
        })
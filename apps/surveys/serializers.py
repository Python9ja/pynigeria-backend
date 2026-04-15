from rest_framework import serializers
from .models import Survey, Question, Option, Response, Answer


class OptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Option
        fields = ["id", "text", "order"]


class QuestionSerializer(serializers.ModelSerializer):
    options = OptionSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ["id", "text", "question_type", "helper_text", "is_required", "order", "options"]


class SurveyListSerializer(serializers.ModelSerializer):
    """Lightweight — for listing surveys (no questions)"""
    question_count = serializers.IntegerField(source="questions.count", read_only=True)
    response_count = serializers.IntegerField(source="responses.count", read_only=True)
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = Survey
        fields = [
            "id", "title", "slug", "description",
            "is_published", "is_active", "is_anonymous",
            "starts_at", "ends_at", "created_at",
            "question_count", "response_count",
        ]


class SurveyDetailSerializer(serializers.ModelSerializer):
    """Full — includes all questions and their options"""
    questions = QuestionSerializer(many=True, read_only=True)
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = Survey
        fields = [
            "id", "title", "slug", "description",
            "is_published", "is_active", "is_anonymous",
            "starts_at", "ends_at", "created_at", "questions",
        ]


# ── Submission ────────────────────────────────────────────────────────────────

class AnswerSubmitSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    text_value = serializers.CharField(required=False, allow_blank=True, default="")
    selected_option_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list,
    )

    def validate_question_id(self, value):
        if not Question.objects.filter(id=value).exists():
            raise serializers.ValidationError("Question does not exist.")
        return value

    def validate_selected_option_ids(self, value):
        if value:
            valid_ids = set(Option.objects.filter(id__in=value).values_list("id", flat=True))
            invalid = set(value) - valid_ids
            if invalid:
                raise serializers.ValidationError(f"Invalid option IDs: {invalid}")
        return value


class ResponseSubmitSerializer(serializers.Serializer):
    answers = AnswerSubmitSerializer(many=True)

    def validate_answers(self, answers):
        if not answers:
            raise serializers.ValidationError("At least one answer is required.")

        # Collect the survey from context (set in the view)
        survey = self.context.get("survey")
        if not survey:
            return answers

        required_question_ids = set(
            survey.questions.filter(is_required=True).values_list("id", flat=True)
        )
        answered_ids = {a["question_id"] for a in answers}
        missing = required_question_ids - answered_ids

        if missing:
            raise serializers.ValidationError(
                f"Required questions not answered: {missing}"
            )

        # Validate each answer matches its question type
        for answer in answers:
            try:
                question = Question.objects.get(id=answer["question_id"])
            except Question.DoesNotExist:
                continue

            if question.question_type in ("single", "multiple", "boolean"):
                if not answer.get("selected_option_ids"):
                    raise serializers.ValidationError(
                        f"Question '{question.text[:40]}' requires selected options."
                    )
            elif question.question_type in ("text", "textarea", "scale"):
                if not answer.get("text_value", "").strip():
                    raise serializers.ValidationError(
                        f"Question '{question.text[:40]}' requires a text value."
                    )

        return answers


# ── Results ───────────────────────────────────────────────────────────────────

class AnswerResultSerializer(serializers.ModelSerializer):
    selected_options = OptionSerializer(many=True, read_only=True)

    class Meta:
        model = Answer
        fields = ["id", "question", "text_value", "selected_options"]


class ResponseResultSerializer(serializers.ModelSerializer):
    answers = AnswerResultSerializer(many=True, read_only=True)

    class Meta:
        model = Response
        fields = ["id", "respondent", "submitted_at", "answers"]
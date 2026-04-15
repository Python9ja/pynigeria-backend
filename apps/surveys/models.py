from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Survey(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    is_published = models.BooleanField(default=False)
    is_anonymous = models.BooleanField(default=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    @property
    def is_active(self):
        from django.utils import timezone
        now = timezone.now()
        if self.starts_at and now < self.starts_at:
            return False
        if self.ends_at and now > self.ends_at:
            return False
        return self.is_published


class Question(models.Model):
    QUESTION_TYPES = [
        ("text", "Short Text"),
        ("textarea", "Long Text"),
        ("single", "Single Choice"),
        ("multiple", "Multiple Choice"),
        ("scale", "Scale 1–5"),
        ("boolean", "Yes / No"),
    ]
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField()
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES,default="single")
    helper_text = models.CharField(max_length=255, blank=True)  # optional subtitle/hint
    is_required = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"[{self.survey.title}] {self.text[:60]}"


class Option(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="options")
    text = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.text


class Response(models.Model):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="responses")
    respondent = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )  # null = anonymous
    submitted_at = models.DateTimeField(auto_now_add=True)
    session_key = models.CharField(max_length=64, blank=True)  # dedup anonymous submissions

    class Meta:
        # Prevent one user from submitting twice
        constraints = [
            models.UniqueConstraint(
                fields=["survey", "respondent"],
                condition=models.Q(respondent__isnull=False),
                name="one_response_per_user_per_survey"
            )
        ]

    def __str__(self):
        who = self.respondent or "Anonymous"
        return f"{self.survey.title} — {who} @ {self.submitted_at}"


class Answer(models.Model):
    response = models.ForeignKey(Response, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(Question, on_delete=models.PROTECT, related_name="answers")
    text_value = models.TextField(blank=True)           # for text/textarea/scale/boolean
    selected_options = models.ManyToManyField(Option, blank=True)  # for single/multiple

    def __str__(self):
        return f"Answer to: {self.question.text[:40]}"
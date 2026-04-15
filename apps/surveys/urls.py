from django.urls import path
from .views import (
    SurveyListView,
    SurveyDetailView,
    SurveySubmitView,
    SurveyResultsView,
    SurveyStatusView,
)

urlpatterns = [
    path("", SurveyListView.as_view(), name="survey-list"),
    path("<slug:slug>/", SurveyDetailView.as_view(), name="survey-detail"),
    path("<slug:slug>/submit/", SurveySubmitView.as_view(), name="survey-submit"),
    path("<slug:slug>/results/", SurveyResultsView.as_view(), name="survey-results"),
    path("<slug:slug>/status/", SurveyStatusView.as_view(), name="survey-status"),
]
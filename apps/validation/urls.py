from django.urls import path
from . import views
urlpatterns = [
    path('accounts/signup/', views.signup, name='signup'),
    path('pilot/', views.pilot_interest, name='pilot-interest'),
    path('information/', views.privacy, name='validation-privacy'),
    path('walkthrough/', views.walkthrough, name='walkthrough'),
    path('walkthrough/status/<uuid:pk>/', views.round_status, name='round-status'),
    path('walkthrough/<int:pk>/feedback/', views.feedback, name='round-feedback'),
    path('walkthrough/<int:pk>/dismiss/', views.dismiss_feedback, name='dismiss-feedback'),
    path('validation/', views.analytics, name='validation-dashboard'),
    path('validation/leads/<int:pk>/', views.lead_detail, name='validation-lead'),
]

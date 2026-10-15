from apps.workflow import teleradiology
from django.contrib import admin
from apps.accounts.views import DemoLoginView
from django.contrib.auth import views as auth_views
from django.urls import path
from apps.clinical.image_views import image_upload, sample_image, try_another_sample
from apps.clinical.assessment_views import quality_check, assessment_result
from apps.dashboard.views import dashboard, case_detail, new_assessment

from apps.workflow.views import clinician_review

from apps.workflow.report_views import case_report, report_stage

from apps.workflow.followup_views import followup_list, followup_detail

from apps.workflow.referrals import referral_list, referral_detail

from apps.accounts.public_views import landing

from django.urls import include

from .seo import robots, sitemap

urlpatterns = [
    path('robots.txt', robots, name='robots'),
    path('sitemap.xml', sitemap, name='sitemap'),
    path('', include('apps.validation.urls')),
    path('', landing, name='landing'),
    path('referrals/', referral_list, name='referral-list'),
    path('referrals/<int:pk>/', referral_detail, name='referral-detail'),
    path('follow-ups/', followup_list, name='followup-list'),
    path('follow-ups/<int:pk>/', followup_detail, name='followup-detail'),
    path('cases/<uuid:pk>/report.pdf', case_report, name='case-report'),
    path('cases/<uuid:pk>/report/', report_stage, name='case-report-stage'),
    path('cases/<uuid:pk>/review/', clinician_review, name='clinician-review'),
    path('cases/<uuid:pk>/quality/', quality_check, name='quality-check'),
    path('cases/<uuid:pk>/assessment/', assessment_result, name='assessment-result'),
    path('cases/<uuid:pk>/images/', image_upload, name='image-upload'),
    path('library/images/<int:pk>/', sample_image, name='sample-image'),
    path('cases/<uuid:pk>/try-another/', try_another_sample, name='try-another-sample'),
    path('teleradiology/', teleradiology.review_queue, name='teleradiology-queue'),
    path('teleradiology/reviews/<int:pk>/', teleradiology.review_detail, name='teleradiology-review'),
    path('teleradiology/reviews/<int:pk>/status/', teleradiology.review_status, name='teleradiology-status'),
    path('admin/', admin.site.urls),
    path('accounts/login/', DemoLoginView.as_view(), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('workspace/', dashboard, name='dashboard'),
    path('assessments/new/', new_assessment, name='new-assessment'),
    path('cases/<uuid:pk>/', case_detail, name='case-detail'),
]

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.http import FileResponse, Http404, HttpResponse
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)
import os
from apps.students.pdf_views import MonthlyReportPDFView


def serve_sw(request):
    sw_path = os.path.join(settings.BASE_DIR, 'static', 'sw.js')
    if not os.path.exists(sw_path):
        raise Http404
    return FileResponse(open(sw_path, 'rb'), content_type='application/javascript')


def robots_txt(request):
    base = request.build_absolute_uri('/').rstrip('/')
    lines = [
        'User-agent: *',
        'Disallow: /api/',
        'Disallow: /admin/',
        'Allow: /login/',
        f'Sitemap: {base}/sitemap.xml',
    ]
    return HttpResponse('\n'.join(lines), content_type='text/plain')


def sitemap_xml(request):
    base = request.build_absolute_uri('/').rstrip('/')
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'  <url><loc>{base}/login/</loc>'
        '<changefreq>monthly</changefreq><priority>1.0</priority></url>\n'
        '</urlset>'
    )
    return HttpResponse(xml, content_type='application/xml')

# ── API v1 routes ──
api_v1_urlpatterns = [
    path('auth/',          include('apps.accounts.urls')),
    path('branches/',      include('apps.branches.urls')),
    path('students/',      include('apps.students.urls')),
    path('teachers/',      include('apps.teachers.urls')),
    path('groups/',        include('apps.groups.urls')),
    path('attendance/',    include('apps.attendance.urls')),
    path('payments/',      include('apps.payments.urls')),
    path('dashboard/',     include('apps.dashboard.urls')),
    path('notifications/', include('apps.notifications.urls')),
    path('leaderboard/',   include('apps.students.leaderboard_urls')),
    path('homework/',      include('apps.homework.urls')),
    path('reports/monthly-pdf/', MonthlyReportPDFView.as_view(), name='monthly-pdf'),
    path('token/',         TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(),    name='token_refresh'),
    path('token/verify/',  TokenVerifyView.as_view(),     name='token_verify'),
]

# ── Frontend page routes ──
frontend_urlpatterns = [
    path('',             TemplateView.as_view(template_name='erp/dashboard.html'),       name='dashboard'),
    path('login/',       TemplateView.as_view(template_name='erp/login.html'),           name='login'),
    path('students/',    TemplateView.as_view(template_name='erp/students.html'),        name='students'),
    path('teachers/',    TemplateView.as_view(template_name='erp/teachers.html'),        name='teachers'),
    path('groups/',      TemplateView.as_view(template_name='erp/groups.html'),          name='groups'),
    path('attendance/',  TemplateView.as_view(template_name='erp/attendance.html'),      name='attendance'),
    path('payments/',    TemplateView.as_view(template_name='erp/payments.html'),        name='payments'),
    path('reports/',     TemplateView.as_view(template_name='erp/reports.html'),         name='reports'),
    path('leaderboard/', TemplateView.as_view(template_name='erp/leaderboard.html'),     name='leaderboard'),
    path('homework/',    TemplateView.as_view(template_name='erp/homework.html'),         name='homework'),
    path('activity/',   TemplateView.as_view(template_name='erp/activity.html'),         name='activity-log-page'),
    path('salary/',     TemplateView.as_view(template_name='erp/salary.html'),           name='salary'),
    path('parent/',     TemplateView.as_view(template_name='erp/parent_portal.html'),   name='parent-portal'),
    path('student/',          TemplateView.as_view(template_name='erp/student_portal.html'),   name='student_portal'),
    path('student/payments/', TemplateView.as_view(template_name='erp/student_payments.html'), name='student_payments'),
    path('student/groups/',   TemplateView.as_view(template_name='erp/student_groups.html'),   name='student_groups'),
    path('student/stats/',    TemplateView.as_view(template_name='erp/student_stats.html'),    name='student_stats'),
    path('student/settings/', TemplateView.as_view(template_name='erp/student_settings.html'),name='student_settings'),
    path('teacher/',          TemplateView.as_view(template_name='erp/teacher_portal.html'),   name='teacher_portal'),
    path('teacher/group/',    TemplateView.as_view(template_name='erp/teacher_group.html'),    name='teacher_group'),
    path('teacher/profile/',  TemplateView.as_view(template_name='erp/teacher_settings.html'),name='teacher_settings'),
]

urlpatterns = [
    path('admin/',       admin.site.urls),
    path('api/v1/',      include(api_v1_urlpatterns)),
    path('sw.js',        serve_sw,    name='service-worker'),
    path('robots.txt',   robots_txt,  name='robots'),
    path('sitemap.xml',  sitemap_xml, name='sitemap'),
] + frontend_urlpatterns

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,  document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    try:
        import debug_toolbar
        urlpatterns = [path('__debug__/', include(debug_toolbar.urls))] + urlpatterns
    except ImportError:
        pass

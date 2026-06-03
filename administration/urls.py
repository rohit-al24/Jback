from django.urls import path
from . import views

urlpatterns = [
    # Current user roles
    path("me/roles/", views.my_roles, name="my_roles"),

    # Master Admin — Colleges
    path("colleges/", views.colleges_list, name="colleges_list"),
    path("colleges/<int:college_id>/", views.college_detail, name="college_detail"),
    path("colleges/<int:college_id>/users/", views.college_users, name="college_users"),
    path("colleges/<int:college_id>/set-admin/", views.set_college_admin, name="set_college_admin"),

    # College Admin — Departments
    path("departments/", views.departments_list, name="departments_list"),
    path("departments/<int:dept_id>/", views.department_detail, name="department_detail"),
    path("departments/<int:dept_id>/add-staff/", views.dept_add_staff, name="dept_add_staff"),
    path("departments/<int:dept_id>/add-students/", views.dept_add_students, name="dept_add_students"),
    path("departments/<int:dept_id>/bulk-upload/", views.dept_bulk_upload, name="dept_bulk_upload"),

    # College Admin — Sensei
    path("sensei/", views.sensei_list, name="sensei_list"),
    path("sensei/<int:sensei_user_id>/classes/", views.sensei_assign_classes, name="sensei_assign_classes"),

    # College Admin — Classes
    path("classes/", views.classes_list, name="classes_list"),
    path("classes/<int:class_id>/", views.class_detail, name="class_detail"),
    path("classes/<int:class_id>/assign-students/", views.class_assign_students, name="class_assign_students"),
    path("classes/<int:class_id>/bulk-upload/", views.class_bulk_upload, name="class_bulk_upload"),

    # College Admin — Students
    path("students/", views.students_list, name="admin_students_list"),

    # College Admin — Staff
    path("staff/", views.staff_list, name="admin_staff_list"),

    # College Admin — Mentor Requests
    path("requests/", views.requests_list, name="admin_requests_list"),
    path("requests/<int:req_id>/respond/", views.request_respond, name="request_respond"),

    # Student — Mentor
    path("student/mentor/", views.student_mentor, name="student_mentor"),
    path("student/mentor/change-request/", views.student_mentor_change_request, name="mentor_change_request"),

    # Staff — Mentees
    path("staff/mentees/", views.staff_mentees, name="staff_mentees"),
]

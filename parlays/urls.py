from django.urls import path



from . import views



app_name = "parlays"



urlpatterns = [

    path("", views.landing, name="landing"),

    path("create/", views.create_parlay, name="create"),

    path("p/<uuid:pk>/", views.parlay_detail, name="detail"),

    path("p/<uuid:pk>/creator/", views.set_creator_session, name="set_creator"),


    path("p/<uuid:pk>/copy/", views.copy_link_fragment, name="copy_link"),

    path("ocr/<uuid:upload_id>/status/", views.ocr_status_partial, name="ocr_status"),

]



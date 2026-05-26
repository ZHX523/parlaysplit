from django.urls import path
from django.views.generic import RedirectView



from . import views



app_name = "parlays"



urlpatterns = [

    path("", views.landing, name="landing"),
    path("about/", views.about, name="about"),

    path("create/", views.create_parlay, name="create"),
    path(
        "find/",
        RedirectView.as_view(pattern_name="parlays:host_lookup", permanent=True),
        name="find",
    ),
    path("my-parlay/", views.host_lookup, name="host_lookup"),
    path("host/<str:host_code>/", views.host_parlay, name="host"),
    path("p/<slug:slug>/og.png", views.parlay_og_image, name="og_image"),
    path("p/<slug:slug>/", views.parlay_detail, name="detail"),
    path("p/<slug:slug>/creator/", views.set_creator_session, name="set_creator"),
    path("p/<slug:slug>/copy/", views.copy_link_fragment, name="copy_link"),
    path("p/<uuid:pk>/og.png", views.parlay_legacy_og_redirect, name="og_image_legacy"),
    path("p/<uuid:pk>/creator/", views.parlay_legacy_creator_redirect, name="set_creator_legacy"),
    path("p/<uuid:pk>/copy/", views.parlay_legacy_copy_redirect, name="copy_link_legacy"),
    path("p/<uuid:pk>/", views.parlay_legacy_redirect, name="detail_legacy"),

    path("ocr/<uuid:upload_id>/status/", views.ocr_status_partial, name="ocr_status"),

]



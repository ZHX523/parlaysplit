from decimal import Decimal



from django.conf import settings

from django.http import Http404, HttpResponse

from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from django.views.decorators.http import require_GET, require_http_methods

from .forms import (

    BetSlipLinkForm,

    default_legs_initial,

    legs_initial_from_text,

    OCRUploadForm,

    ParlayCreateForm,

    ParlayEditForm,

    ParticipantJoinForm,

)

from .models import (
    LegType,
    OCRUpload,
    OCRUploadStatus,
    Parlay,
    ParlayStatus,
    Participant,
    ParticipantStatus,
)

from .services.link_parser import parse_bet_slip_link

from .services.ocr import OCRService

from .opengraph import render_parlay_og_svg
from .services.og_image import get_parlay_og_etag, get_parlay_og_image_bytes
from .seo import build_page_meta, build_parlay_page_meta
from .utils import (
    clear_expired_host_codes,
    is_valid_host_code_format,
    normalize_host_code,
)

SUBMISSION_MANUAL = "manual"

SUBMISSION_SCREENSHOT = "screenshot"

SUBMISSION_LINK = "link"


def _require_active_parlay(parlay: Parlay) -> Parlay:
    """Raise 404 when the parlay TTL has passed (public and host access)."""
    parlay.clear_host_code_if_expired()
    if parlay.is_expired:
        raise Http404()
    return parlay


def _get_parlay_by_host_code(host_code: str) -> Parlay:
    clear_expired_host_codes()
    code = normalize_host_code(host_code)
    if not is_valid_host_code_format(code):
        raise Http404()
    parlay = get_object_or_404(
        Parlay.objects.prefetch_related("legs", "participants"),
        host_code=code,
    )
    return _require_active_parlay(parlay)


def _redirect_after_parlay_create(request, parlay):
    if not parlay.host_code:
        parlay.save()
    if not parlay.host_code_active:
        raise Http404()
    request.session[f"creator_{parlay.id}"] = True
    request.session[f"show_share_intro_{parlay.id}"] = True
    return redirect("parlays:host", host_code=parlay.host_code)


def _parlay_page_url(parlay, *, is_host_view: bool) -> str:
    if is_host_view:
        return reverse("parlays:host", kwargs={"host_code": parlay.host_code})
    return reverse("parlays:detail", kwargs={"slug": parlay.slug})


def landing(request):
    return render(
        request,
        "parlays/landing.html",
        {"meta": build_page_meta(request, "landing")},
    )





def _clear_ocr_session(request) -> None:
    for key in ("last_ocr_upload_id", "pending_ocr_review_id", "ocr_review_token"):
        request.session.pop(key, None)


def _review_initial_from_ocr(ocr_upload: OCRUpload) -> tuple[dict, list[dict], dict]:
    from .forms import legs_initial_from_ocr

    parsed = ocr_upload.parsed_data or {}
    wager = parsed.get("wager_amount") or ""
    initial = {
        "odds_american": parsed.get("odds_american") or None,
        "wager_amount": Decimal(wager) if wager else None,
    }
    legs_initial = legs_initial_from_ocr(parsed)
    ocr_meta = {
        "sportsbook": parsed.get("sportsbook", ""),
        "parlay_type": parsed.get("parlay_type", ""),
        "confidence": parsed.get("confidence"),
        "uncertain_fields": parsed.get("uncertain_fields") or [],
        "legs_structured": parsed.get("legs") or [],
    }
    return initial, legs_initial, ocr_meta





def _build_review_form(

    request,

    initial: dict | None = None,

    external_link: str = "",

    legs_initial: list[dict] | None = None,

):

    if request.method == "POST" and request.POST.get("action") == "create":

        return ParlayCreateForm(request.POST, external_link=external_link)

    return ParlayCreateForm(

        initial=initial or {},

        external_link=external_link,

        legs_initial=legs_initial or default_legs_initial(),

    )





@require_http_methods(["GET", "POST"])

def create_parlay(request):
    from django.urls import reverse

    method = request.GET.get("method") or request.POST.get("submission_method")

    ocr_upload = None
    ocr_meta = {"uncertain_fields": []}

    ocr_form = OCRUploadForm()

    link_form = BetSlipLinkForm()

    manual_form = ParlayCreateForm()

    form = None

    show_review = False

    external_link = request.session.get("pending_external_link", "")

    if request.method == "GET" and request.GET.get("discard_ocr"):
        _clear_ocr_session(request)
        return redirect(f"{reverse('parlays:create')}?method=screenshot")

    if request.method == "GET":
        review_token = request.GET.get("review")
        session_token = request.session.get("ocr_review_token")
        if review_token and session_token and review_token == session_token:
            request.session.pop("ocr_review_token", None)
            upload_id = request.session.get("pending_ocr_review_id")
            if upload_id:
                try:
                    ocr_upload = OCRUpload.objects.get(pk=upload_id)
                    method = SUBMISSION_SCREENSHOT
                    if ocr_upload.status == OCRUploadStatus.COMPLETED:
                        show_review = True
                except OCRUpload.DoesNotExist:
                    _clear_ocr_session(request)
        else:
            _clear_ocr_session(request)

    elif request.method == "POST":
        upload_id = request.session.get("pending_ocr_review_id") or request.POST.get(
            "ocr_upload_id"
        )
        if upload_id:
            try:
                ocr_upload = OCRUpload.objects.get(pk=upload_id)
                method = method or SUBMISSION_SCREENSHOT
            except OCRUpload.DoesNotExist:
                _clear_ocr_session(request)



    if request.session.get("pending_link_review"):

        method = SUBMISSION_LINK

        show_review = True



    if request.method == "POST":

        action = request.POST.get("action")



        if action == "upload_ocr":

            method = SUBMISSION_SCREENSHOT

            ocr_form = OCRUploadForm(request.POST, request.FILES)

            if ocr_form.is_valid():

                upload = OCRUpload.objects.create(image=ocr_form.cleaned_data["image"])

                OCRService.process_upload(upload)
                upload.refresh_from_db()

                if upload.status == OCRUploadStatus.COMPLETED:
                    import secrets

                    token = secrets.token_urlsafe(16)
                    request.session["pending_ocr_review_id"] = str(upload.id)
                    request.session["ocr_review_token"] = token
                    return redirect(
                        f"{reverse('parlays:create')}?method=screenshot&review={token}"
                    )

                ocr_upload = upload
                method = SUBMISSION_SCREENSHOT



        if action == "submit_link":

            method = SUBMISSION_LINK

            link_form = BetSlipLinkForm(request.POST)

            if link_form.is_valid():

                parsed = parse_bet_slip_link(link_form.cleaned_data["bet_slip_url"])

                request.session["pending_link_review"] = True

                request.session["pending_external_link"] = parsed.get("external_link", "")

                request.session["pending_link_initial"] = {}

                from django.urls import reverse



                return redirect(f"{reverse('parlays:create')}?method=link")



        if action == "create":

            method = request.POST.get("submission_method", method)



            if method == SUBMISSION_MANUAL:

                manual_form = ParlayCreateForm(request.POST)

                if manual_form.is_valid():

                    parlay = manual_form.save()

                    parlay.status = ParlayStatus.OPEN

                    parlay.save(update_fields=["status"])

                    manual_form.save_legs(parlay)

                    return _redirect_after_parlay_create(request, parlay)

                method = SUBMISSION_MANUAL

            else:

                external_link = request.POST.get("external_link", external_link)

                form = _build_review_form(request, external_link=external_link)

                if form.is_valid():

                    parlay = form.save(commit=False)

                    parlay.status = ParlayStatus.OPEN

                    if external_link:

                        parlay.external_link = external_link

                    parlay.save()

                    form.save_legs(parlay)

                    if ocr_upload:

                        ocr_upload.parlay = parlay

                        ocr_upload.save(update_fields=["parlay"])

                        if method == SUBMISSION_SCREENSHOT:
                            from parlays.services.ocr.feedback import (
                                schedule_ocr_scan_feedback,
                            )

                            schedule_ocr_scan_feedback(
                                str(ocr_upload.id),
                                str(parlay.id),
                                request.POST,
                            )

                    _clear_ocr_session(request)

                    request.session.pop("pending_link_review", None)

                    request.session.pop("pending_external_link", None)

                    request.session.pop("pending_link_initial", None)

                    return _redirect_after_parlay_create(request, parlay)

                show_review = True



    if show_review and form is None:

        initial = {}

        legs_initial = default_legs_initial()

        if request.session.get("pending_link_initial"):

            initial = dict(request.session["pending_link_initial"])

        elif ocr_upload and ocr_upload.status == OCRUploadStatus.COMPLETED:

            initial, legs_initial, ocr_meta = _review_initial_from_ocr(ocr_upload)

        form = _build_review_form(

            request,

            initial=initial,

            external_link=external_link,

            legs_initial=legs_initial,

        )



    if (
        not ocr_meta
        and ocr_upload
        and ocr_upload.status == OCRUploadStatus.COMPLETED
    ):
        _, _, ocr_meta = _review_initial_from_ocr(ocr_upload)

    return render(
        request,
        "parlays/create.html",
        {
            "form": form,
            "manual_form": manual_form,
            "ocr_form": ocr_form,
            "link_form": link_form,
            "ocr_upload": ocr_upload,
            "ocr_meta": ocr_meta,
            "submission_method": method,
            "show_review": show_review,
            "external_link": external_link,
            "leg_type_choices": LegType.choices,
            "max_legs": settings.MAX_LEGS,
            "meta": build_page_meta(request, "create"),
        },
    )





def ocr_status_partial(request, upload_id):
    upload = get_object_or_404(OCRUpload, pk=upload_id)
    session_id = request.session.get("pending_ocr_review_id")
    if session_id and str(upload.id) != str(session_id):
        raise Http404()
    return render(
        request,
        "parlays/partials/ocr_status.html",
        {"ocr_upload": upload},
    )





def _render_parlay_page(request, parlay, *, is_host_view: bool):
    _require_active_parlay(parlay)

    join_form = _join_form_for(request, parlay)

    edit_form = None

    ownership_action_error = None

    page_url = _parlay_page_url(parlay, is_host_view=is_host_view)



    if request.method == "POST":

        action = request.POST.get("action")



        if action == "join":

            if is_host_view:

                ownership_action_error = (

                    "Friends join on your public link — this page is for managing requests."

                )

                join_form = _join_form_for(request, parlay)

                if request.headers.get("HX-Request"):

                    return render(

                        request,

                        "parlays/partials/parlay_ownership_body.html",

                        _parlay_context(

                            request,

                            parlay,

                            join_form,

                            is_host_view=True,

                            ownership_action_error=ownership_action_error,

                        ),

                    )

                return redirect(page_url)

            else:

                join_form = _join_form_for(request, parlay, data=request.POST)

                join_ok = join_form.is_valid()

                if join_ok:

                    if not request.session.session_key:

                        request.session.create()

                    participant = join_form.save()

                    participant.session_key = request.session.session_key or ""

                    participant.save(update_fields=["session_key"])

                    parlay = get_object_or_404(

                        Parlay.objects.prefetch_related("legs", "participants"),

                        pk=parlay.pk,

                    )

                    join_form = _join_form_for(request, parlay)

                if request.headers.get("HX-Request"):

                    return render(

                        request,

                        "parlays/partials/parlay_ownership_body.html",

                        _parlay_context(

                            request,

                            parlay,

                            join_form,

                            is_host_view=is_host_view,

                            ownership_action_error=ownership_action_error,

                        ),

                    )

                if join_ok:

                    return redirect(page_url)



        if is_host_view and action in ("approve_participant", "remove_participant"):

            ownership_action_error = _handle_participant_action(

                request,

                parlay,

                action,

            )

            parlay = get_object_or_404(

                Parlay.objects.prefetch_related("legs", "participants"),

                pk=parlay.pk,

            )

            join_form = _join_form_for(request, parlay)

            if request.headers.get("HX-Request"):

                return render(

                    request,

                    "parlays/partials/parlay_ownership_body.html",

                    _parlay_context(

                        request,

                        parlay,

                        join_form,

                        is_host_view=True,

                        ownership_action_error=ownership_action_error,

                    ),

                )

            return redirect(page_url)



        if is_host_view and action == "close_parlay":

            if parlay.status == ParlayStatus.OPEN:

                parlay.status = ParlayStatus.LOCKED

                parlay.save(update_fields=["status", "updated_at"])

            return redirect(page_url)



        if is_host_view and action == "open_parlay":

            if parlay.status == ParlayStatus.LOCKED:

                parlay.status = ParlayStatus.OPEN

                parlay.save(update_fields=["status", "updated_at"])

            return redirect(page_url)



        if is_host_view and action == "edit":

            if parlay.friends_have_joined:

                return redirect(page_url)

            edit_form = ParlayEditForm(request.POST, instance=parlay)

            if edit_form.is_valid():

                edit_form.save()

                edit_form.save_legs(parlay)

                return redirect(page_url)



    if request.GET.get("partial") == "live":

        return render(

            request,

            "parlays/partials/parlay_live_details.html",

            {"parlay": parlay},

        )



    if request.GET.get("partial") == "ownership":

        return render(

            request,

            "parlays/partials/parlay_ownership_poll.html",

            _parlay_context(request, parlay, join_form, is_host_view=is_host_view),

        )



    if request.GET.get("partial") == "join-footer":

        return render(

            request,

            "parlays/partials/parlay_join_footer_partial.html",

            _parlay_context(request, parlay, join_form, is_host_view=is_host_view),

        )



    ctx = _parlay_context(request, parlay, join_form, is_host_view=is_host_view)

    ctx["meta"] = build_parlay_page_meta(request, parlay, is_host_view=is_host_view)

    ctx["page_url"] = page_url

    parlay_edits_locked = is_host_view and parlay.friends_have_joined

    ctx["edit_form"] = (

        edit_form or ParlayEditForm(instance=parlay)

        if is_host_view and not parlay_edits_locked

        else None

    )

    ctx["parlay_edits_locked"] = parlay_edits_locked

    ctx["is_creator"] = is_host_view

    ctx["show_share_intro"] = is_host_view and request.session.pop(

        f"show_share_intro_{parlay.id}",

        False,

    )

    ctx["host_url"] = parlay.host_url if is_host_view else None

    ctx["host_code"] = parlay.host_code if is_host_view else None

    ctx["host_code_expires_at"] = parlay.host_code_expires_at if is_host_view else None

    ctx["leg_type_choices"] = LegType.choices

    ctx["max_legs"] = settings.MAX_LEGS

    return render(request, "parlays/detail.html", ctx)





def _get_public_parlay_by_slug(slug: str) -> Parlay:
    parlay = get_object_or_404(
        Parlay.objects.prefetch_related("legs", "participants"),
        slug=slug,
    )
    if not parlay.is_public:
        raise Http404()
    return _require_active_parlay(parlay)


@require_http_methods(["GET", "POST"])
def parlay_detail(request, slug):
    parlay = _get_public_parlay_by_slug(slug)

    return _render_parlay_page(request, parlay, is_host_view=False)


def _redirect_parlay_legacy(request, pk, view_name: str):
    parlay = get_object_or_404(Parlay, pk=pk)
    return redirect(view_name, slug=parlay.slug, permanent=True)


@require_GET
def parlay_legacy_redirect(request, pk):
    return _redirect_parlay_legacy(request, pk, "parlays:detail")


@require_GET
def parlay_legacy_og_redirect(request, pk):
    return _redirect_parlay_legacy(request, pk, "parlays:og_image")


@require_GET
def parlay_legacy_creator_redirect(request, pk):
    return _redirect_parlay_legacy(request, pk, "parlays:set_creator")


@require_GET
def parlay_legacy_copy_redirect(request, pk):
    return _redirect_parlay_legacy(request, pk, "parlays:copy_link")





def _join_form_for(request, parlay, data=None):

    kwargs = {"parlay": parlay, "session_key": request.session.session_key or ""}

    if data is not None:

        return ParticipantJoinForm(data, **kwargs)

    return ParticipantJoinForm(**kwargs)





def _handle_participant_action(request, parlay, action: str) -> str | None:

    raw_id = request.POST.get("participant_id")

    if not raw_id:

        return "Invalid participant."

    participant = get_object_or_404(Participant, pk=raw_id, parlay=parlay)

    if action == "remove_participant":

        participant.delete()

        return None

    if participant.status != ParticipantStatus.PENDING:

        return "That request is no longer pending."

    if parlay.total_contributions + participant.contribution_amount > parlay.max_friends_stake:

        return (

            f"Cannot approve {participant.nickname}: friends split is already full."

        )

    participant.status = ParticipantStatus.APPROVED

    participant.save(update_fields=["status"])

    return None





def _join_footer_revision(
    *,
    show_join_form: bool,
    user_pending_request,
    user_approved_participant,
) -> str:
    approved = user_approved_participant
    return "|".join(
        [
            "1" if show_join_form else "0",
            str(user_pending_request.pk) if user_pending_request else "",
            str(approved.pk) if approved else "",
        ],
    )


def _parlay_context(
    request,
    parlay,
    join_form,
    *,
    is_host_view: bool,
    ownership_action_error=None,
):

    from .utils import build_ownership_bar, ownership_color



    is_creator = is_host_view
    page_url = _parlay_page_url(parlay, is_host_view=is_host_view)

    approved = list(

        parlay.participants.filter(status=ParticipantStatus.APPROVED).order_by("joined_at"),

    )

    pending = list(

        parlay.participants.filter(status=ParticipantStatus.PENDING).order_by("joined_at"),

    )

    rows = [

        {

            "is_host": True,

            "nickname": parlay.creator_nickname,

            "contribution": parlay.host_stake_amount,

            "ownership": parlay.host_ownership_percent(),

            "estimated": parlay.host_estimated_payout(),

            "color": ownership_color(is_host=True),

            "is_pending": False,

            "participant": None,

        },

    ]

    for friend_index, p in enumerate(approved):

        rows.append(

            {

                "is_host": False,

                "participant": p,

                "nickname": p.nickname,

                "contribution": p.contribution_amount,

                "ownership": parlay.ownership_percent_for(p.contribution_amount),

                "estimated": parlay.estimated_payout_for(p.contribution_amount),

                "color": ownership_color(is_host=False, friend_index=friend_index),

                "is_pending": False,

            }

        )

    for p in pending:

        rows.append(

            {

                "is_host": False,

                "participant": p,

                "nickname": p.nickname,

                "contribution": p.contribution_amount,

                "ownership": None,

                "estimated": None,

                "color": ownership_color(is_host=False, friend_index=len(approved)),

                "is_pending": True,

            }

        )

    session_key = request.session.session_key or ""

    user_pending_request = (

        parlay.participants.filter(

            session_key=session_key,

            status=ParticipantStatus.PENDING,

        ).first()

        if session_key

        else None

    )

    user_approved_participant = (

        parlay.participants.filter(

            session_key=session_key,

            status=ParticipantStatus.APPROVED,

        ).first()

        if session_key

        else None

    )

    has_pending_participants = bool(pending)

    show_join_form = (

        not is_host_view

        and parlay.status == ParlayStatus.OPEN

        and parlay.remaining_wager > 0

        and user_pending_request is None

    )

    join_form_is_top_up = bool(user_approved_participant and show_join_form)

    footer_revision = _join_footer_revision(
        show_join_form=show_join_form,
        user_pending_request=user_pending_request,
        user_approved_participant=user_approved_participant,
    )

    return {

        "parlay": parlay,

        "join_form": join_form,

        "participant_rows": rows,

        "ownership_segments": build_ownership_bar(

            [r for r in rows if not r.get("is_pending")],

        ),

        "total_contributions": parlay.total_contributions,

        "remaining_wager": parlay.remaining_wager,

        "share_url": parlay.share_url,

        "page_url": page_url,

        "ownership_poll_url": f"{page_url}?partial=ownership",

        "parlay_live_poll_url": f"{page_url}?partial=live" if not is_host_view else None,

        "is_creator": is_creator,

        "is_host_view": is_host_view,

        "has_pending_participants": has_pending_participants,

        "user_pending_request": user_pending_request,

        "user_approved_participant": user_approved_participant,

        "show_join_form": show_join_form,

        "join_form_is_top_up": join_form_is_top_up,

        "footer_revision": footer_revision,

        "join_footer_url": f"{page_url}?partial=join-footer",

        "should_poll_ownership": (not is_host_view) or (
            is_host_view and parlay.status == ParlayStatus.OPEN
        ),

        "ownership_action_error": ownership_action_error,

        "host_code_expires_at": parlay.host_code_expires_at if is_host_view else None,

    }





@require_GET
def parlay_og_image(request, slug):
    parlay = _get_public_parlay_by_slug(slug)

    fmt = (request.GET.get("format") or "png").lower()
    if fmt == "svg":
        return HttpResponse(
            render_parlay_og_svg(parlay),
            content_type="image/svg+xml",
        )

    etag = get_parlay_og_etag(parlay)
    timeout = getattr(settings, "OG_IMAGE_CACHE_TIMEOUT", 86400)
    cache_control = f"public, max-age={timeout}, stale-while-revalidate=3600"

    if request.META.get("HTTP_IF_NONE_MATCH") == etag:
        response = HttpResponse(status=304)
    else:
        png_bytes = get_parlay_og_image_bytes(parlay)
        response = HttpResponse(png_bytes, content_type="image/png")
        response["ETag"] = etag

    response["Cache-Control"] = cache_control
    response["X-Robots-Tag"] = "noindex"
    return response





@require_GET

def copy_link_fragment(request, slug):
    parlay = _get_public_parlay_by_slug(slug)

    return render(

        request,

        "parlays/partials/copy_link.html",

        {"share_url": parlay.share_url},

    )





@require_http_methods(["GET", "POST"])
def host_parlay(request, host_code):
    parlay = _get_parlay_by_host_code(host_code)
    request.session[f"creator_{parlay.id}"] = True
    return _render_parlay_page(request, parlay, is_host_view=True)


@require_http_methods(["GET", "POST"])
def host_lookup(request):
    clear_expired_host_codes()
    error = None
    submitted_code = ""
    if request.method == "POST":
        submitted_code = normalize_host_code(request.POST.get("host_code"))
        if is_valid_host_code_format(submitted_code):
            parlay = Parlay.objects.filter(host_code=submitted_code).first()
            if parlay and not parlay.is_expired and parlay.host_code_active:
                return redirect("parlays:host", host_code=parlay.host_code)
            if parlay and parlay.is_expired:
                parlay.clear_host_code_if_expired()
                error = (
                    "This parlay has expired. Parlays are available for "
                    f"{getattr(settings, 'HOST_CODE_TTL_HOURS', 72)} hours after creation."
                )
            else:
                error = "No parlay found for that code. Check the code and try again."
        else:
            error = (
                f"Enter a valid {getattr(settings, 'HOST_CODE_LENGTH', 6)}-character host code "
                "(letters and numbers)."
            )
    return render(
        request,
        "parlays/host_lookup.html",
        {
            "error": error,
            "submitted_code": submitted_code,
            "meta": build_page_meta(request, "host_lookup"),
            "host_code_length": getattr(settings, "HOST_CODE_LENGTH", 6),
        },
    )


def set_creator_session(request, slug):
    parlay = _get_public_parlay_by_slug(slug)
    if not parlay.host_code_active:
        raise Http404()
    request.session[f"creator_{parlay.id}"] = True
    return redirect("parlays:host", host_code=parlay.host_code)



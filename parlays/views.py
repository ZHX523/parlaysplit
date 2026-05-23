from decimal import Decimal



from django.conf import settings

from django.http import Http404, HttpResponse

from django.shortcuts import get_object_or_404, redirect, render

from django.views.decorators.http import require_GET, require_http_methods

from meta.views import Meta



from .forms import (

    BetSlipLinkForm,

    default_legs_initial,

    legs_initial_from_text,

    OCRUploadForm,

    ParlayCreateForm,

    ParlayEditForm,

    ParticipantJoinForm,

)

from .models import LegType, OCRUpload, OCRUploadStatus, Parlay, ParlayStatus, Sportsbook

from .services.link_parser import parse_bet_slip_link

from .services.ocr import OCRService

from .tasks import process_ocr_upload

from .utils import format_dollars



SUBMISSION_MANUAL = "manual"

SUBMISSION_SCREENSHOT = "screenshot"

SUBMISSION_LINK = "link"





def landing(request):

    meta = Meta(

        request=request,

        title="ParlaySplit — Coordinate group parlays without spreadsheet math",

        description=(

            "Share betting slips, track participation, and estimate payouts with friends. "

            "No wagers accepted — coordination only."

        ),

        url=request.build_absolute_uri(),

    )

    return render(

        request,

        "parlays/landing.html",

        {"meta": meta},

    )





def _review_initial_from_ocr(ocr_upload: OCRUpload) -> tuple[dict, list[dict]]:

    parsed = ocr_upload.parsed_data or {}

    wager = parsed.get("wager_amount") or ""

    initial = {

        "sportsbook": parsed.get("sportsbook", "") or Sportsbook.FANDUEL,

        "odds_american": parsed.get("odds_american") or None,

        "wager_amount": Decimal(wager) if wager else None,

    }

    legs_initial = legs_initial_from_text(parsed.get("leg_descriptions", ""))

    return initial, legs_initial





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

    method = request.GET.get("method") or request.POST.get("submission_method")

    ocr_upload = None

    ocr_form = OCRUploadForm()

    link_form = BetSlipLinkForm()

    manual_form = ParlayCreateForm()

    form = None

    show_review = False

    external_link = request.session.get("pending_external_link", "")



    upload_id = request.GET.get("ocr") or request.session.get("last_ocr_upload_id")

    if upload_id:

        try:

            ocr_upload = OCRUpload.objects.get(pk=upload_id)

            if ocr_upload.status == OCRUploadStatus.COMPLETED:

                method = SUBMISSION_SCREENSHOT

                show_review = True

        except OCRUpload.DoesNotExist:

            pass



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

                request.session["last_ocr_upload_id"] = str(upload.id)

                try:

                    process_ocr_upload.delay(str(upload.id))

                except Exception:

                    OCRService.process_upload(upload)

                return redirect(f"/create/?method=screenshot&ocr={upload.id}")



        if action == "submit_link":

            method = SUBMISSION_LINK

            link_form = BetSlipLinkForm(request.POST)

            if link_form.is_valid():

                parsed = parse_bet_slip_link(link_form.cleaned_data["bet_slip_url"])

                request.session["pending_link_review"] = True

                request.session["pending_external_link"] = parsed.get("external_link", "")

                request.session["pending_link_initial"] = {

                    "sportsbook": parsed.get("sportsbook", ""),

                }

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

                    request.session[f"creator_{parlay.id}"] = True

                    return redirect("parlays:detail", pk=parlay.id)

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

                    request.session.pop("last_ocr_upload_id", None)

                    request.session.pop("pending_link_review", None)

                    request.session.pop("pending_external_link", None)

                    request.session.pop("pending_link_initial", None)

                    request.session[f"creator_{parlay.id}"] = True

                    return redirect("parlays:detail", pk=parlay.id)

                show_review = True



    if show_review and form is None:

        initial = {}

        legs_initial = default_legs_initial()

        if request.session.get("pending_link_initial"):

            initial = dict(request.session["pending_link_initial"])

        elif ocr_upload and ocr_upload.status == OCRUploadStatus.COMPLETED:

            initial, legs_initial = _review_initial_from_ocr(ocr_upload)

        form = _build_review_form(

            request,

            initial=initial,

            external_link=external_link,

            legs_initial=legs_initial,

        )



    meta = Meta(

        request=request,

        title="Create a Parlay — ParlaySplit",

        description="Choose how to submit your bet slip for parlay analysis.",

    )

    return render(

        request,

        "parlays/create.html",

        {

            "form": form,

            "manual_form": manual_form,

            "ocr_form": ocr_form,

            "link_form": link_form,

            "ocr_upload": ocr_upload,

            "submission_method": method,

            "show_review": show_review,

            "external_link": external_link,

            "leg_type_choices": LegType.choices,

            "max_legs": settings.MAX_LEGS,

            "meta": meta,

        },

    )





def ocr_status_partial(request, upload_id):

    upload = get_object_or_404(OCRUpload, pk=upload_id)

    return render(

        request,

        "parlays/partials/ocr_status.html",

        {"ocr_upload": upload},

    )





@require_http_methods(["GET", "POST"])

def parlay_detail(request, pk):

    parlay = get_object_or_404(

        Parlay.objects.prefetch_related("legs", "participants"),

        pk=pk,

    )

    if not parlay.is_public:

        raise Http404()



    join_form = ParticipantJoinForm(parlay=parlay)

    edit_form = None

    is_creator = request.session.get(f"creator_{parlay.id}") is True



    if request.method == "POST":

        action = request.POST.get("action")



        if action == "join":

            join_form = ParticipantJoinForm(request.POST, parlay=parlay)

            join_ok = join_form.is_valid()

            if join_ok:

                participant = join_form.save()

                if request.session.session_key:

                    participant.session_key = request.session.session_key

                    participant.save(update_fields=["session_key"])

                parlay = get_object_or_404(

                    Parlay.objects.prefetch_related("legs", "participants"),

                    pk=pk,

                )

                join_form = ParticipantJoinForm(parlay=parlay)

            if request.headers.get("HX-Request"):

                return render(

                    request,

                    "parlays/partials/parlay_ownership_inner.html",

                    _parlay_context(request, parlay, join_form),

                )

            if join_ok:

                return redirect("parlays:detail", pk=parlay.id)



        if action == "edit" and is_creator:

            edit_form = ParlayEditForm(request.POST, instance=parlay)

            if edit_form.is_valid():

                edit_form.save()

                edit_form.save_legs(parlay)

                return redirect("parlays:detail", pk=parlay.id)



    if request.GET.get("partial") == "ownership":

        return render(

            request,

            "parlays/partials/parlay_ownership_inner.html",

            _parlay_context(request, parlay, join_form),

        )



    meta = Meta(

        request=request,

        title=f"Parlay by {parlay.creator_nickname} — ParlaySplit",

        description=_parlay_meta_description(parlay),

        url=request.build_absolute_uri(),

    )



    ctx = _parlay_context(request, parlay, join_form)

    ctx["meta"] = meta

    ctx["edit_form"] = edit_form or ParlayEditForm(instance=parlay) if is_creator else None

    ctx["is_creator"] = is_creator

    ctx["leg_type_choices"] = LegType.choices

    ctx["max_legs"] = settings.MAX_LEGS

    return render(request, "parlays/detail.html", ctx)





def _parlay_context(request, parlay, join_form):

    from .utils import build_ownership_bar, ownership_color



    participants = list(parlay.participants.order_by("joined_at"))

    rows = [

        {

            "is_host": True,

            "nickname": parlay.creator_nickname,

            "contribution": parlay.host_stake_amount,

            "ownership": parlay.host_ownership_percent(),

            "estimated": parlay.host_estimated_payout(),

            "color": ownership_color(is_host=True),

        },

    ]

    for friend_index, p in enumerate(participants):

        rows.append(

            {

                "is_host": False,

                "participant": p,

                "nickname": p.nickname,

                "contribution": p.contribution_amount,

                "ownership": parlay.ownership_percent_for(p.contribution_amount),

                "estimated": parlay.estimated_payout_for(p.contribution_amount),

                "color": ownership_color(is_host=False, friend_index=friend_index),

            }

        )

    return {

        "parlay": parlay,

        "join_form": join_form,

        "participant_rows": rows,

        "ownership_segments": build_ownership_bar(rows),

        "total_contributions": parlay.total_contributions,

        "remaining_wager": parlay.remaining_wager,

        "share_url": parlay.share_url,

    }





def _parlay_meta_description(parlay) -> str:

    legs = parlay.legs.count()

    odds = (

        f"+{parlay.odds_american}"

        if parlay.odds_american and parlay.odds_american > 0

        else str(parlay.odds_american or "")

    )

    payout = format_dollars(parlay.potential_payout) if parlay.potential_payout else "TBD"

    return (

        f"{legs}-leg parlay · {odds} · est. payout {payout}. "

        f"Join {parlay.creator_nickname}'s group on ParlaySplit."

    )





@require_GET

def copy_link_fragment(request, pk):

    parlay = get_object_or_404(Parlay, pk=pk)

    return render(

        request,

        "parlays/partials/copy_link.html",

        {"share_url": parlay.share_url},

    )





def set_creator_session(request, pk):

    parlay = get_object_or_404(Parlay, pk=pk)

    request.session[f"creator_{parlay.id}"] = True

    return redirect("parlays:detail", pk=parlay.id)



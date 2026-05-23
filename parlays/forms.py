from decimal import Decimal



from django import forms

from django.conf import settings

from django.core.exceptions import ValidationError



from .models import (

    LegType,

    Parlay,

    ParlayLeg,

    ParlayStatus,

    Participant,

    ParticipantStatus,

)

from .services.odds import american_odds_to_payout

from .utils import DEFAULT_CREATOR_NICKNAME, format_dollars, parse_currency





def parse_legs_from_data(data) -> list[dict]:

    types = data.getlist("leg_type")

    descriptions = data.getlist("leg_description")

    legs = []

    valid_types = {c[0] for c in LegType.choices}

    for leg_type, description in zip(types, descriptions):

        description = (description or "").strip()

        if not description:

            continue

        if leg_type not in valid_types:

            leg_type = LegType.MONEYLINE

        legs.append({"leg_type": leg_type, "description": description[:500]})

    return legs





def default_legs_initial() -> list[dict]:

    return [{"leg_type": LegType.MONEYLINE, "description": ""}]





def legs_initial_from_text(text: str) -> list[dict]:

    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]

    if not lines:

        return default_legs_initial()

    return [{"leg_type": LegType.MONEYLINE, "description": line} for line in lines]





class ParlayCreateForm(forms.ModelForm):

    class Meta:

        model = Parlay

        fields = [
            "odds_american",
            "wager_amount",
            "split_offered_percent",
        ]

        widgets = {
            "odds_american": forms.NumberInput(

                attrs={

                    "class": "input-field",

                    "placeholder": "+450",

                    "step": "1",

                },

            ),

            "wager_amount": forms.NumberInput(

                attrs={

                    "class": "input-field",

                    "placeholder": "25.00",

                    "step": "0.01",

                    "min": "0.01",

                },

            ),

            "split_offered_percent": forms.NumberInput(

                attrs={

                    "class": "input-field",

                    "placeholder": "50",

                    "step": "1",

                    "min": "1",

                    "max": "100",

                },

            ),

        }



    def __init__(self, *args, external_link: str = "", legs_initial=None, **kwargs):
        initial = kwargs.get("initial") or {}
        super().__init__(*args, **kwargs)
        self.external_link = external_link

        if not self.is_bound and not getattr(self.instance, "pk", None):

            self.initial["wager_amount"] = ""

            self.initial["split_offered_percent"] = ""

        if self.data and self.data.getlist("leg_type"):

            self.legs_initial = parse_legs_from_data(self.data) or default_legs_initial()

        else:

            self.legs_initial = legs_initial or default_legs_initial()



    def clean_wager_amount(self):

        value = self.cleaned_data.get("wager_amount")

        if value is None:

            raise ValidationError("Wager is required.")

        if value < settings.MIN_CONTRIBUTION:

            raise ValidationError(f"Wager must be at least {format_dollars(settings.MIN_CONTRIBUTION)}.")

        return value



    def clean_split_offered_percent(self):

        value = self.cleaned_data.get("split_offered_percent")

        if value is None:

            raise ValidationError("Split offered is required.")

        if value < Decimal("1") or value > Decimal("100"):

            raise ValidationError("Split offered must be between 1% and 100%.")

        return value



    def clean(self):

        cleaned = super().clean()

        legs = parse_legs_from_data(self.data)

        if not legs:

            raise ValidationError("Add at least one parlay leg with a description.")

        if len(legs) > settings.MAX_LEGS:

            raise ValidationError(f"Maximum {settings.MAX_LEGS} legs allowed.")

        cleaned["legs"] = legs



        odds = cleaned.get("odds_american")

        wager = cleaned.get("wager_amount")

        if odds is None:

            raise ValidationError("American odds are required.")

        payout = american_odds_to_payout(wager, odds)

        if payout is None:

            raise ValidationError("Enter valid odds and wager to calculate payout.")

        cleaned["potential_payout"] = payout

        return cleaned



    def save(self, commit=True):
        parlay = super().save(commit=False)
        parlay.potential_payout = self.cleaned_data["potential_payout"]
        if not parlay.creator_nickname:
            parlay.creator_nickname = DEFAULT_CREATOR_NICKNAME
        if self.external_link:
            parlay.external_link = self.external_link
        if commit:

            parlay.save()

            self.save_m2m()

        return parlay



    def save_legs(self, parlay: Parlay):

        parlay.legs.all().delete()

        for i, leg in enumerate(self.cleaned_data.get("legs", [])):

            ParlayLeg.objects.create(

                parlay=parlay,

                leg_type=leg["leg_type"],

                description=leg["description"],

                sort_order=i,

            )





class ParlayEditForm(ParlayCreateForm):

    class Meta(ParlayCreateForm.Meta):
        fields = [
            "odds_american",
            "wager_amount",
            "split_offered_percent",
        ]



    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:

            legs = self.instance.legs.order_by("sort_order")

            self.legs_initial = [

                {"leg_type": leg.leg_type, "description": leg.description}

                for leg in legs

            ] or default_legs_initial()





class ParticipantJoinForm(forms.ModelForm):

    contribution_amount = forms.CharField(

        label="Contribution ($)",

        widget=forms.TextInput(

            attrs={

                "class": "input-field",

                "placeholder": "$25.00",

                "inputmode": "decimal",

                "autocomplete": "off",

                "data-format-contribution": "",

            },

        ),

    )



    class Meta:

        model = Participant

        fields = ["nickname", "contribution_amount"]

        widgets = {

            "nickname": forms.TextInput(

                attrs={

                    "class": "input-field",

                    "placeholder": "Name",

                    "autocomplete": "name",

                },

            ),

        }



    def __init__(self, *args, parlay: Parlay | None = None, session_key: str = "", **kwargs):

        self.parlay = parlay

        self._session_key = session_key

        super().__init__(*args, **kwargs)

        if parlay and parlay.remaining_for_friends > 0:

            self.fields["contribution_amount"].widget.attrs["max"] = str(

                parlay.remaining_for_friends,

            )



    def save(self, commit=True):

        participant = super().save(commit=False)

        participant.contribution_amount = self.cleaned_data["contribution_amount"]

        participant.status = ParticipantStatus.PENDING

        if self.parlay:

            participant.parlay = self.parlay

        if commit:

            participant.save()

        return participant



    def clean_nickname(self):

        nickname = (self.cleaned_data.get("nickname") or "").strip()

        if not nickname:

            raise ValidationError("Name is required.")

        if len(nickname) > 64:

            raise ValidationError("Name is too long.")

        if self.parlay:

            if nickname.lower() == self.parlay.creator_nickname.lower():

                raise ValidationError(

                    f'"{self.parlay.creator_nickname}" is reserved for the host — use your own name.'

                )

            if self.parlay.participants.filter(nickname__iexact=nickname).exists():

                raise ValidationError("That name is already on this parlay.")

            session_key = getattr(self, "_session_key", None)

            if session_key and self.parlay.participants.filter(

                session_key=session_key,

                status=ParticipantStatus.PENDING,

            ).exists():

                raise ValidationError("You already have a pending request on this parlay.")

        return nickname



    def clean_contribution_amount(self):

        value = parse_currency(self.cleaned_data.get("contribution_amount"))

        if value is None:

            raise ValidationError("Contribution amount is required.")

        if value < settings.MIN_CONTRIBUTION:

            raise ValidationError(f"Minimum contribution is {format_dollars(settings.MIN_CONTRIBUTION)}.")

        if value > settings.MAX_CONTRIBUTION:

            raise ValidationError("Contribution amount is too large.")

        if self.parlay and value > self.parlay.max_friends_stake:

            raise ValidationError(

                f"Contribution cannot exceed {format_dollars(self.parlay.max_friends_stake)} "

                f"split offered to friends."

            )

        return value



    def clean(self):

        cleaned = super().clean()

        if self.parlay and self.parlay.status != ParlayStatus.OPEN:

            raise ValidationError("This parlay is not open for new participants.")

        if self.parlay and self.parlay.participant_count >= settings.MAX_PARTICIPANTS:

            raise ValidationError("This parlay has reached the maximum number of participants.")

        amount = cleaned.get("contribution_amount")

        if self.parlay and amount is not None:

            remaining = self.parlay.remaining_for_friends

            if amount > remaining:

                raise ValidationError(

                    f"Only {format_dollars(remaining)} of the split offered to friends is still available."

                )

        return cleaned





class BetSlipLinkForm(forms.Form):

    bet_slip_url = forms.URLField(

        widget=forms.URLInput(

            attrs={

                "class": "input-field",

                "placeholder": "Paste FanDuel or DraftKings share link",

                "inputmode": "url",

                "autocomplete": "off",

            },

        ),

        label="Shared bet link",

    )



    def clean_bet_slip_url(self):

        from .services.link_parser import is_supported_bet_link



        url = (self.cleaned_data.get("bet_slip_url") or "").strip()

        if not is_supported_bet_link(url):

            raise ValidationError(

                "Paste a valid FanDuel or DraftKings shared bet link "

                "(from the app's Share option on your bet slip)."

            )

        return url





class OCRUploadForm(forms.Form):

    image = forms.ImageField(

        widget=forms.ClearableFileInput(

            attrs={

                "class": "input-field",

                "accept": "image/*",

                "capture": "environment",

            },

        ),

    )



    def clean_image(self):

        image = self.cleaned_data["image"]

        if image.size > 10 * 1024 * 1024:

            raise ValidationError("Image must be under 10 MB.")

        return image



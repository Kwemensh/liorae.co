# myApp/forms.py
from django import forms

BUDGET_CHOICES = [
    ("50-75", "PHP 50k – 75k"),
    ("75-120", "PHP 75k – 120k"),
    ("120-200", "PHP 120k – 200k"),
    ("200+", "PHP 200k+"),
]

TIMELINE_CHOICES = [
    ("asap", "ASAP (0–2 weeks)"),
    ("1m", "1 month"),
    ("3m", "3 months"),
    ("6m+", "6+ months"),
]

SERVICE_LABELS = [
    "Content", "Reels", "Community", "Paid Social",
    "Landing Page", "CRM & Automation", "Analytics",
]

class ContactForm(forms.Form):
    full_name = forms.CharField(max_length=120)
    email = forms.EmailField()
    company = forms.CharField(max_length=120, required=False)
    website = forms.CharField(max_length=200, required=False)
    budget = forms.ChoiceField(choices=BUDGET_CHOICES)
    timeline = forms.ChoiceField(choices=TIMELINE_CHOICES)
    services = forms.MultipleChoiceField(
        choices=[(s, s) for s in SERVICE_LABELS],
        required=False
    )
    message = forms.CharField(widget=forms.Textarea)
    # simple honeypot
    hp = forms.CharField(required=False)  # if filled -> spam

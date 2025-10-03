from __future__ import annotations
import json, os, re, uuid, logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.views.decorators.http import require_POST

from .forms import ContactForm

logger = logging.getLogger(__name__)

# ------------------------------------------------------------
# Optional: load .env in dev
# ------------------------------------------------------------
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

# ------------------------------------------------------------
# OpenAI client (lazy + robust; prefers settings over env)
# ------------------------------------------------------------
try:
    from openai import OpenAI  # type: ignore
except Exception:  # library not installed
    OpenAI = None  # type: ignore

# Use a sentinel so we never call isinstance(OpenAI is None)
_SENTINEL = object()
_client_cache: object | None = _SENTINEL  # _SENTINEL = not built yet

def _mask(s: str) -> str:
    return f"{s[:4]}…{s[-4:]}" if s and len(s) > 8 else ("(set)" if s else "(missing)")

def _get_openai_client():
    """
    Returns a cached OpenAI client instance or None.
    Never raises if SDK/key are missing; logs why.
    """
    global _client_cache

    # If we've already tried to build it, return the cached result (client or None)
    if _client_cache is not _SENTINEL:
        return _client_cache  # may be None on previous failure

    # Not built yet — try now
    if OpenAI is None:
        logger.warning("OpenAI SDK not installed in this environment.")
        _client_cache = None
        return None

    key = getattr(settings, "OPENAI_API_KEY", None) or os.getenv("OPENAI_API_KEY")
    if not key:
        logger.warning("OPENAI_API_KEY not found (settings and env both empty).")
        _client_cache = None
        return None

    try:
        client = OpenAI(api_key=key)
        _client_cache = client
        logger.info("OpenAI client initialized (key=%s).", _mask(key))
        return client
    except Exception as e:
        logger.exception("Failed to create OpenAI client: %s", e)
        _client_cache = None
        return None

# ------------------------------------------------------------
# System prompt
# ------------------------------------------------------------
SYSTEM_PROMPT = """
You are Liora — a warm, capable, general-purpose AI companion for Lioraè Co.
Be kind, witty, concise, and actually useful. Match the user’s tone.
Use plain language. If feelings show up, acknowledge briefly, then problem-solve.
Ask at most one short follow-up when it truly helps.

Core behavior
- Be pragmatic and specific. Offer examples, checklists, and step-wise plans.
- If you don’t know, say so and suggest a next step (search, small test, expert).
- Safety: provide general info only (no medical/legal/financial guarantees). Encourage consulting a professional when appropriate.
- Avoid hallucinated specifics; prefer plain statements, small ranges, or “it depends + how to decide”.

About Lioraè Co. (facts you can use)
- What we do: strategy-first social media + content, light automation/CRM, dashboards, and funnels/landing pages.
- Outcomes: typical engagement lift within ~1–2 months; clearer pipeline/ROI within ~3–6 months (with consistent shipping).
- Ownership: all delivered assets, sites, and customized AI tools belong to the client.
- Cadence: weekly shipping and iteration; monthly retainers; upgrade or customize anytime.
- Channels & tools we’re fluent with: Instagram, TikTok, YouTube; Meta Ads, Google Ads; Figma/Notion; Shopify/Stripe; HubSpot; Klaviyo.
- Tone/brand: clear, friendly, no fluff; strategy first, creative with soul.

Service tiers (typical inclusions; scopes can be tailored)
1) IGNITE — “Smart Social Foundations” (approx. PHP 75,000 / month)
   - ~20 posts • 25 stories • 3 reels
   - AI-assisted captions/hashtags
   - Content calendar + auto-scheduling
   - Basic landing/portfolio + hosting
   - Monthly analytics report
   - Best for startups

2) SYNC — “Social + Web Alignment” (approx. PHP 95,000 / month)
   - ~30 posts • 35 stories • 6 reels
   - Campaign strategy & funnel planning
   - Landing page optimization + CRM hookups
   - AI trend suggestions + conversion copy
   - Lead & engagement dashboard
   - Lead-gen ready

3) VISION — “AI-Enhanced Growth Engine” (approx. PHP 120,000 / month, min. 3-month plan)
   - ~25 posts • 25 stories • 8 reels
   - Predictive campaign builder
   - Social listening & competitor analysis
   - Bi-weekly analytics & retargeting
   - Advanced dashboards & automation

4) AUTHORITY — “Omnipresence + Automation” (approx. PHP 150,000 / month)
   - Thought leadership + multi-channel presence
   - Heavier automation + repurposing

5) ASCEND — “Full Growth Ecosystem” (PHP 200,000+ / month)
   - Enterprise-style scope, >50 posts across platforms, multi-funnel orchestration

Process (how we work)
1) Discover & Audit — kickoff, goals, audience, baseline.
2) Strategy — messaging, pillars, campaign roadmap.
3) Setup — stack, scheduler, CRM, pixels, analytics.
4) Ship — weekly content (AI-assisted captions, best-time posting), light automations.
5) Review & Scale — dashboards, learnings, iterate, retarget, expand winners.

FAQs (quick answers)
- Do I need a website? Not required. We can ship a starter landing page in-package.
- How does AI help? Caption drafts, best-time posting, light automations, predictive prompts, time savings.
- Social-only? Yes—start with foundations; upgrade to funnels/automation later.
- When will results show? 1–2 months for engagement lift; 3–6 months for clearer ROI signals (depends on baseline, budget, and velocity).
- Who owns what? You do. We manage and optimize on your behalf.

Working style
- Keep answers crisp; use short lists, bold keywords sparingly, and avoid jargon.
- Default to practical frameworks (e.g., “3-step test plan”, “1-week sprint plan”, “hook-body-CTA”).
- Prefer examples tailored to the user’s niche when they’ve said it; otherwise suggest 2–3 niches as placeholders.

If the user asks about Lioraè services
- Offer to map them to a tier or design a custom scope.
- Suggest a 20-min discovery call for fit/brief + draft plan (typical response ~24h).
- Contact: hello@liorae.co (or direct the user to the “Contact” section if present).

Formatting & limits
- Use plain text or light Markdown. Avoid heavy decoration or emojis unless the user uses them.
- One follow-up question max, only if it significantly improves the answer.
- If a price/timeline/spec isn’t certain, state assumptions.

Refusals & sensitive content
- Decline unsafe/illegal requests; offer a safe alternative.
- Never claim professional, guaranteed outcomes; emphasize guidance and experiments.

Short self-description for context replies
- “I’m Liora, your friendly AI from Lioraè Co.—strategy-first social, content, and light automation that turns presence into pipeline.”

"""


# ------------------------------------------------------------
# Instant offline replies
# ------------------------------------------------------------


# ------------------------------------------------------------
# LLM helper
# ------------------------------------------------------------
def _llm_reply(user_msg: str) -> str:
    client = _get_openai_client()
    if not client:
        return ("Got it. I don’t have my full AI brain connected yet. "
                "Share your main channel (IG/TikTok/LinkedIn), audience, and desired outcome, "
                "and I’ll sketch a quick plan.")

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.7,
            max_tokens=600,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_msg},
            ],
            timeout=30,  # seconds
        )
        reply = (completion.choices[0].message.content or "").strip()
        return reply or "I blanked for a sec—mind asking that one more time?"
    except Exception as e:
        logger.exception("OpenAI call failed")
        if getattr(settings, "DEBUG", False):
            return f"(DEBUG) OpenAI error: {e}"
        return ("I hit a snag reaching my brain. "
                "Want to try again, or tell me the short version and I’ll help?")

# ------------------------------------------------------------
# Home (sets CSRF for chat)
# ------------------------------------------------------------
@ensure_csrf_cookie
def index(request):
    images = [
        "https://images.unsplash.com/photo-1521737604893-d14cc237f11d?auto=format&fit=crop&w=1600&q=80",
        "https://images.unsplash.com/photo-1522252234503-e356532cafd5?auto=format&fit=crop&w=1600&q=80",
        "https://images.unsplash.com/photo-1529101091764-c3526daf38fe?auto=format&fit=crop&w=1600&q=80",
        "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1600&q=80",
        "https://images.unsplash.com/photo-1556761175-4b46a572b786?auto=format&fit=crop&w=1600&q=80",
        "https://images.unsplash.com/photo-1519389950473-47ba0277781c?auto=format&fit=crop&w=1600&q=80",
        "https://images.unsplash.com/photo-1542744173-05336fcc7ad4?auto=format&fit=crop&w=1600&q=80",
        "https://images.unsplash.com/photo-1498050108023-c5249f4df085?auto=format&fit=crop&w=1600&q=80",
        "https://images.unsplash.com/photo-1529101091764-c3526daf38fe?auto=format&fit=crop&w=1600&q=80",
    ]
    steps = ["Discovery", "Strategy", "Tech Integration", "AI Empowerment", "Growth & Optimization"]
    faq = [
        ("Do I need a website to start?", "Not necessarily. We can ship a starter landing page so your brand has a clean digital home."),
        ("How does AI help a small team?", "From on-brand captioning to best-time posting and chatbot lead capture, AI saves hours and lifts consistency."),
        ("How long before I see results?", "Engagement typically uplifts within 1–2 months; conversions/ROI often clarify within 3–6 months with consistent campaigns."),
        ("Can I start with social only?", "Yes. Begin with IGNITE and upgrade to funnels/automation as you grow."),
    ]
    stats = [
        {"label": "Total Users",  "value": "50,789", "delta": "8.5% from yesterday",  "trend": "up"},
        {"label": "Total Orders", "value": "20,393", "delta": "1.3% from last week",  "trend": "up"},
        {"label": "Total Sales",  "value": "$60,000","delta": "4.3% from yesterday",  "trend": "down"},
        {"label": "Total Pending","value": "5,040",  "delta": "1.8% from yesterday",  "trend": "up"},
    ]
    tiers = [
        {"name":"IGNITE","price":"PHP 75,000 / month","tag":"Smart Social Foundations","badge":"Best for startups",
         "bullets":["20 posts • 25 stories • 3 reels","AI-assisted captions & hashtags","Content calendar + auto-scheduling",
                    "Basic landing/portfolio + hosting","Monthly analytics report"]},
        {"name":"SYNC","price":"PHP 95,000 / month","tag":"Social + Web Alignment","badge":"Lead-gen ready",
         "bullets":["30 posts • 35 stories • 6 reels","Campaign strategy & funnel planning","Landing page optimization + CRM",
                    "AI trend suggestions • conversion copy","Lead & engagement dashboard"]},
        {"name":"VISION","price":"PHP 120,000 / month","tag":"AI-Enhanced Growth Engine","badge":"Min. 3-month plan",
         "bullets":["25 posts • 25 stories • 8 reels","Predictive campaign builder","Social listening & competitor analysis",
                    "Bi-weekly analytics & retargeting","Advanced dashboards & automation"]},
        {"name":"AUTHORITY","price":"PHP 150,000 / month","tag":"Omnipresence + Automation","badge":"Thought leadership",
         "bullets":["40 posts • 40 stories • 10 reels","Omnichannel (IG/TikTok/FB/LinkedIn)","Sentiment heatmap & campaign intelligence",
                    "Dynamic website + CRM automation"]},
        {"name":"ASCEND","price":"PHP 200,000+ / month","tag":"Full Growth Ecosystem","badge":"Enterprise",
         "bullets":["50+ posts across platforms","Full funnel strategy & ad support","Weekly trend & business intelligence",
                    "Enterprise automation & personalization"],"wide":True},
    ]
    testimonials = [
        {"quote":"From scattered posts to a real funnel—we saw lift in 6 weeks.","author":"Amira","role":"COO"},
        {"quote":"Clean, premium, and measurable. Exactly what we needed.","author":"Rami","role":"CMO"},
        {"quote":"Finally feels like our brand—and it converts.","author":"Leah","role":"Founder"},
        {"quote":"Strategy-first content. The dashboards made ROI obvious.","author":"Noah","role":"Head of Growth"},
    ]
    compare_rows = [
        {"feature":"Posts / Stories / Reels","IGNITE":"20 / 25 / 3","SYNC":"30 / 35 / 6","VISION":"25 / 25 / 8","AUTHORITY":"40 / 40 / 10","ASCEND":"50+ / 50+ / 10+"},
        {"feature":"AI-assisted captions & hashtags","IGNITE":"✓","SYNC":"✓","VISION":"✓","AUTHORITY":"✓","ASCEND":"✓"},
        {"feature":"Content calendar & auto-scheduling","IGNITE":"✓","SYNC":"✓","VISION":"✓","AUTHORITY":"✓","ASCEND":"✓"},
        {"feature":"Campaign strategy & funnel planning","IGNITE":"—","SYNC":"✓","VISION":"✓","AUTHORITY":"✓","ASCEND":"✓"},
        {"feature":"Landing page / Website + CRM","IGNITE":"Basic site + hosting","SYNC":"Landing + CRM","VISION":"Optimization + CRM",
         "AUTHORITY":"Dynamic site + CRM automation","ASCEND":"Enterprise personalization"},
        {"feature":"Analytics cadence","IGNITE":"Monthly","SYNC":"Leads dashboard","VISION":"Bi-weekly + retargeting","AUTHORITY":"Advanced dashboards","ASCEND":"Weekly BI"},
        {"feature":"Social listening & competitor analysis","IGNITE":"—","SYNC":"—","VISION":"✓","AUTHORITY":"✓","ASCEND":"✓"},
        {"feature":"Ad support","IGNITE":"—","SYNC":"—","VISION":"—","AUTHORITY":"—","ASCEND":"✓"},
    ]
    logos = [
        {"src":"https://dummyimage.com/140x40/ffffff/0b0f1a.png&text=Stripe","alt":"Stripe"},
        {"src":"https://dummyimage.com/140x40/ffffff/0b0f1a.png&text=Shopify","alt":"Shopify"},
        {"src":"https://dummyimage.com/140x40/ffffff/0b0f1a.png&text=HubSpot","alt":"HubSpot"},
        {"src":"https://dummyimage.com/140x40/ffffff/0b0f1a.png&text=Notion","alt":"Notion"},
        {"src":"https://dummyimage.com/140x40/ffffff/0b0f1a.png&text=Figma","alt":"Figma"},
        {"src":"https://dummyimage.com/140x40/ffffff/0b0f1a.png&text=Klaviyo","alt":"Klaviyo"},
        {"src":"https://dummyimage.com/140x40/ffffff/0b0f1a.png&text=Meta+Ads","alt":"Meta Ads"},
        {"src":"https://dummyimage.com/140x40/ffffff/0b0f1a.png&text=Google+Ads","alt":"Google Ads"},
    ]
    service_labels = ["Content","Reels","Community","Paid Social","Landing Page","CRM & Automation","Analytics"]

    return render(request, "home.html", {
        "images": images, "steps": steps, "faq": faq, "stats": stats,
        "tiers": tiers, "testimonials": testimonials, "compare_rows": compare_rows,
        "logos": logos, "service_labels": service_labels,
        "og_image_url": "https://images.unsplash.com/photo-1556761175-4b46a572b786?auto=format&fit=crop&w=1600&q=80",
        "logo_url": "https://dummyimage.com/200x200/0b0f1a/ffffff.png&text=L", "ig_handle": "liorae",
    })

# ------------------------------------------------------------
# Chat endpoints
# ------------------------------------------------------------
@csrf_exempt
@require_POST
def chatbot_response(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")

    user_msg = (data.get("message") or "").strip()
    if not user_msg:
        return JsonResponse({"reply": "What’s on your mind?"})

    # LLM reply (or graceful fallback)
    return JsonResponse({"reply": _llm_reply(user_msg)})

# Back-compat with earlier widget
@csrf_exempt
@require_POST
def chat_start(request):
    cid = request.session.get("chat_cid") or str(uuid.uuid4())
    request.session["chat_cid"] = cid
    return JsonResponse({"conversation_id": cid})

@csrf_exempt
@require_POST
def chat_send(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")
    msg = (data.get("message") or "").strip()
   
    return JsonResponse({"reply": _llm_reply(msg)})

# ------------------------------------------------------------
# Tiny health probe (no secrets)
# ------------------------------------------------------------
def chat_health(request):
    key_settings = getattr(settings, "OPENAI_API_KEY", None)
    key_env = os.getenv("OPENAI_API_KEY")
    client_ok = bool(_get_openai_client())
    return JsonResponse({
        "sdk_installed": bool(OpenAI),
        "has_key_in_settings": bool(key_settings),
        "has_key_in_env": bool(key_env),
        "key_seen": _mask(key_settings or key_env or ""),
        "client_initialized": client_ok,
        "debug": bool(getattr(settings, "DEBUG", False)),
    })

# ------------------------------------------------------------
# Contact form
# ------------------------------------------------------------
def contact_submit(request):
    if request.method != "POST":
        return redirect("/#contact")

    form = ContactForm(request.POST)
    if not form.is_valid() or form.cleaned_data.get("hp"):
        return redirect("/#contact?ok=0")

    cd = form.cleaned_data

    # Auto-reply to client
    subject_client = "We got your inquiry — Lioraè Co."
    html_client = render_to_string("emails/contact_email_client.html", {"d": cd})
    text_client = render_to_string("emails/contact_email_client.txt", {"d": cd})
    msg_client = EmailMultiAlternatives(
        subject_client, text_client, settings.DEFAULT_FROM_EMAIL, [cd["email"]]
    )
    msg_client.attach_alternative(html_client, "text/html")
    msg_client.send(fail_silently=False)

    # Team notification
    subject_team = f"[New Inquiry] {cd['full_name']} — {cd.get('company','').strip() or 'No company'}"
    html_team = render_to_string("emails/contact_email_team.html", {"d": cd})
    text_team = render_to_string("emails/contact_email_team.txt", {"d": cd})
    msg_team = EmailMultiAlternatives(
        subject_team, text_team, settings.DEFAULT_FROM_EMAIL,
        [getattr(settings, "CONTACT_RECIPIENT", "hello@liorae.co")],
        reply_to=[cd["email"]],
    )
    msg_team.attach_alternative(html_team, "text/html")
    msg_team.send(fail_silently=False)

    return redirect("/#contact?ok=1")

def about(request):
    return render(request, "about.html")
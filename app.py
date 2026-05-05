import streamlit as st
import streamlit.components.v1 as components
import base64
import json
import os

from dotenv import load_dotenv
from analytics import track

load_dotenv()


def _redirect_top_level(url: str) -> None:
    """Send the browser to an external URL (breaks out of Streamlit iframes)."""
    if not url:
        return
    js_url = json.dumps(url)
    components.html(
        f"<script>window.top.location.href = {js_url};</script>",
        height=0,
        width=0,
    )

# =============================================
# PAGE CONFIG
# =============================================
st.set_page_config(
    page_title="SwimForm AI | Elite Biomechanics",
    page_icon="🏊",
    layout="centered",
    initial_sidebar_state="collapsed"
)

if "landing_tracked" not in st.session_state:
    track("landing_viewed", {"page": "landing"})
    st.session_state.landing_tracked = True

# =============================================
# CSS STYLING (Background & Theme)
# =============================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&family=Space+Mono:wght@700&display=swap');

    [data-testid="stAppViewContainer"] {
        background: #0a1628 !important;
        background: linear-gradient(180deg, #0a1628 0%, #0f2847 30%, #0e3d6b 60%, #0f2847 100%) !important;
        color: #f0fdff;
    }
    
    [data-testid="stHeader"] {
        background: transparent !important;
    }
    [data-testid="stSidebarNav"] {
        display: none !important;
    }
    .water-bg {
        position: fixed; top: 0; left: 0; width: 100%; height: 100%; z-index: 0;
        pointer-events: none;
    }
    .water-bg::before {
        content: ''; position: absolute; inset: 0;
        background: radial-gradient(ellipse at 20% 20%, rgba(6, 182, 212, 0.15) 0%, transparent 50%);
        animation: waterShimmer 8s ease-in-out infinite;
    }
    .lane-lines {
        position: fixed; top: 0; left: 0; width: 100%; height: 100%; z-index: 0; opacity: 0.03;
        pointer-events: none;
        background: repeating-linear-gradient(90deg, #22d3ee 0px, #22d3ee 4px, transparent 4px, transparent 150px);
    }
    @keyframes waterShimmer { 0%, 100% { opacity: 0.5; transform: translateY(0); } 50% { opacity: 1; transform: translateY(-20px); } }

    .bubble {
        position: fixed; border-radius: 50%; z-index: 0;
        pointer-events: none;
        background: radial-gradient(circle at 30% 30%, rgba(255,255,255,0.2), rgba(6, 182, 212, 0.05));
        animation: float 15s infinite ease-in-out;
    }
    .b1 { width: 80px; height: 80px; top: 20%; left: 10%; }
    .b2 { width: 40px; height: 40px; top: 60%; left: 85%; animation-delay: -5s; }
    @keyframes float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-40px); } }

    .cta-box {
        background: rgba(15, 40, 71, 0.6);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(6, 182, 212, 0.2);
        border-radius: 24px; padding: 40px; text-align: center;
        box-shadow: 0 20px 40px rgba(0,0,0,0.4);
    }
</style>

<div class="water-bg"></div>
<div class="lane-lines"></div>
<div class="bubble b1"></div>
<div class="bubble b2"></div>
""", unsafe_allow_html=True)

# =============================================
# CONFIG & SECRETS
# =============================================
import stripe

STRIPE_PAYMENT_LINK       = os.environ.get("STRIPE_PAYMENT_LINK", "")
STRIPE_PAYMENT_LINK_COACH = os.environ.get("STRIPE_PAYMENT_LINK_COACH", "")
STRIPE_PAYMENT_LINK_FOUNDING = os.environ.get("STRIPE_PAYMENT_LINK_FOUNDING", "")
POSTHOG_PUBLIC_KEY = os.environ.get("POSTHOG_PUBLIC_KEY", "")
POSTHOG_HOST = os.environ.get("POSTHOG_HOST", "https://us.i.posthog.com")
STRIPE_SECRET_KEY         = os.environ.get("STRIPE_SECRET_KEY", "")
IS_DEV                    = os.environ.get("IS_DEV", "false").lower() == "true"

stripe.api_key = STRIPE_SECRET_KEY

if "paid" not in st.session_state:
    st.session_state.paid = False
if "report_mode" not in st.session_state:
    st.session_state.report_mode = "swimmer"

def show_landing_page():
    if POSTHOG_PUBLIC_KEY:
        st.markdown(f"""
    <script>
    !function(t,e){{var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){{function g(t,e){{var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){{t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}}}(p=t.createElement("script")).type="text/javascript",p.crossOrigin="anonymous",p.async=!0,p.src=s.api_host.replace(".i.posthog.com","-assets.i.posthog.com")+"/static/array.js",(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);var u=e;for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],u.toString=function(t){{var e="posthog";return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e}},u.people.toString=function(){{return u.toString(1)+".people (stub)"}},o="init capture register register_once register_for_session unregister unregister_for_session getFeatureFlag getFeatureFlagPayload isFeatureEnabled reloadFeatureFlags updateEarlyAccessFeatureEnrollment getEarlyAccessFeatures on onFeatureFlags onSessionId getSurveys getActiveMatchingSurveys renderSurvey canRenderSurvey identify setPersonProperties group resetGroups setPersonPropertiesForFlags resetPersonPropertiesForFlags setGroupPropertiesForFlags resetGroupPropertiesForFlags reset opt_in_capturing opt_out_capturing has_opted_in_capturing has_opted_out_capturing clear_opt_in_out_capturing debug".split(" "),n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])}},e.__SV=1)}}(document,window.posthog||[]);
    posthog.init('{POSTHOG_PUBLIC_KEY}', {{api_host:'{POSTHOG_HOST}', person_profiles:'identified_only'}});
    </script>
    """, unsafe_allow_html=True)

    # --- 1. Header ---
    st.markdown("""
    <div style="padding: 20px 0; display: flex; justify-content: center; align-items: center; position: relative; z-index: 1;">
        <div style="font-family: 'Space Mono', monospace; font-size: 2.5rem; font-weight: 700; color: white; display: flex; align-items: center; gap: 12px;">
            <svg width="30" height="30" viewBox="0 0 32 32"><circle cx="16" cy="16" r="14" fill="none" stroke="currentColor" stroke-width="2"/><path d="M 8 16 Q 16 12 24 16" stroke="currentColor" stroke-width="2.5" fill="none"/></svg>
            SWIMFORM AI
        </div>
    </div>
    <div style="
        background: linear-gradient(90deg, #0f2027, #203a43, #2c5364);
        padding: 25px;
        border-radius: 12px;
        text-align: center;
        color: white;
        margin-bottom: 25px;
        position: relative; z-index: 1;
    ">
        <h3 style="margin-top: 0; font-weight: 400;">
            ⚡ Video analysis powered by Pose-Estimation AI
        </h3>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
<div style="text-align: center; margin: 10px 0 40px; position: relative; z-index: 1;">
    <h1 style="color: white; font-size: 2.4rem; font-weight: 800; margin: 0 0 12px; line-height: 1.15;">
        Find your 3 biggest freestyle <span style="color: #22d3ee;">speed leaks</span> in 90 seconds.
    </h1>
    <p style="color: #94a3b8; font-size: 1.05rem; max-width: 640px; margin: 0 auto; line-height: 1.5;">
        Frame-by-frame biomechanics analysis from a single side-view clip. Built by a 4 x 70.3 + 1 x 140.6 Ironman finisher who got tired of guessing.
    </p>
</div>
""", unsafe_allow_html=True)

    st.markdown("""
<div style="max-width: 720px; margin: 0 auto 30px; padding: 18px 24px; background: linear-gradient(135deg, rgba(34, 211, 238, 0.12), rgba(16, 185, 129, 0.08)); border: 1px solid rgba(34, 211, 238, 0.4); border-radius: 16px; position: relative; z-index: 1; text-align: center;">
    <div style="display: inline-block; background: #22d3ee; color: #0a1628; font-size: 0.7rem; font-weight: 800; letter-spacing: 1.5px; padding: 4px 12px; border-radius: 12px; margin-bottom: 10px;">LAUNCH SPECIAL</div>
    <p style="color: white; font-size: 1.05rem; margin: 0 0 4px; font-weight: 600;">
        <span style="color: #10b981; font-weight: 800;">$0.99</span> per analysis <span style="color: #94a3b8; text-decoration: line-through; font-weight: 400; font-size: 0.95rem;">$4.99</span> · through May 31
    </p>
    <p style="color: #94a3b8; font-size: 0.85rem; margin: 0;">
        We're collecting real-world feedback before going public. Help us tune the model and get a full report at near-cost.
    </p>
</div>
""", unsafe_allow_html=True)

    # --- 3. VIDEO & HUD (Mobile Optimized) ---
    def get_video_base64(video_path):
        if not os.path.exists(video_path): return None
        with open(video_path, "rb") as f: data = f.read()
        return base64.b64encode(data).decode()
    
    video_file_name = "hero_demo.mp4" 
    video_b64 = get_video_base64(video_file_name)
    
    if not video_b64:
        st.info(f"ℹ️ Place a file named '{video_file_name}' in the root to see the video demo.")
    else:
        html_code = f"""
        <!DOCTYPE html>
        <html>
        <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&display=swap');
            body {{ margin: 0; background: transparent; overflow: hidden; }}
    
            .container {{
                position: relative; width: 100%; max-width: 780px; margin: 0 auto;
                border-radius: 24px; overflow: hidden; border: 1px solid rgba(34, 211, 238, 0.3);
                box-shadow: 0 30px 60px rgba(0,0,0,0.5);
            }}
    
            video {{ width: 100%; display: block; object-fit: cover; }}
    
            .hud-layer {{
                position: absolute; top: 0; left: 0; width: 100%; height: 100%;
                z-index: 10; pointer-events: none; font-family: 'Space Mono', monospace;
            }}
    
            .metric-node {{ position: absolute; display: flex; align-items: center; transition: all 0.3s ease; }}
    
            .target-circle {{
                width: 14px; height: 14px; border: 2px solid #22d3ee; border-radius: 50%;
                background: rgba(34, 211, 238, 0.1); box-shadow: 0 0 10px rgba(34, 211, 238, 0.5);
            }}
    
            .connect-line {{ height: 1px; width: 20px; background: #22d3ee; opacity: 0.6; }}
    
            .data-box {{
                background: rgba(10, 22, 40, 0.9); backdrop-filter: blur(8px);
                border: 1px solid rgba(34, 211, 238, 0.2); padding: 8px 10px; border-radius: 8px;
                min-width: 120px; animation: float 4s ease-in-out infinite;
            }}
    
            .label {{ font-size: 8px; color: #94a3b8; text-transform: uppercase; margin-bottom: 2px; }}
            .value-row {{ display: flex; justify-content: space-between; align-items: baseline; }}
            .main-val {{ font-size: 14px; font-weight: 700; color: #fff; }}
            
            .status-tag {{ font-size: 8px; padding: 1px 4px; border-radius: 4px; font-weight: 700; margin-left: 6px; }}
            .fix {{ background: rgba(255, 71, 87, 0.2); color: #ff4757; border: 1px solid #ff4757; }}
            .ok {{ background: rgba(16, 185, 129, 0.2); color: #10b981; border: 1px solid #10b981; }}
    
            @keyframes float {{ 0%, 100% {{ transform: translateY(0px); }} 50% {{ transform: translateY(-5px); }} }}
    
            /* POSITIONING */
            .pos-glide {{ top: 12%; left: 5%; }}
            .pos-roll  {{ top: 12%; right: 5%; flex-direction: row-reverse; }}
            .pos-evf   {{ bottom: 18%; left: 5%; }}
            .pos-kick  {{ bottom: 12%; right: 5%; flex-direction: row-reverse; }}

            /* DESKTOP UPSCALING */
            @media (min-width: 600px) {{
                .target-circle {{ width: 20px; height: 20px; }}
                .connect-line {{ width: 30px; }}
                .data-box {{ padding: 10px 14px; min-width: 160px; }}
                .label {{ font-size: 9px; }}
                .main-val {{ font-size: 18px; }}
                .status-tag {{ font-size: 9px; }}
                .pos-glide {{ top: 15%; left: 10%; }}
                .pos-roll  {{ top: 15%; right: 10%; }}
                .pos-evf   {{ bottom: 20%; left: 15%; }}
                .pos-kick  {{ bottom: 15%; right: 15%; }}
            }}
        </style>
        </head>
        <body>
        <div class="container">
            <video autoplay muted loop playsinline><source src="data:video/mp4;base64,{video_b64}" type="video/mp4"></video>
            <div class="hud-layer">
                <div class="metric-node pos-glide"><div class="target-circle"></div><div class="connect-line"></div><div class="data-box"><div class="label">Glide Ratio</div><div class="value-row"><span class="main-val">1%</span><span class="status-tag fix">FIX</span></div></div></div>
                <div class="metric-node pos-roll"><div class="target-circle"></div><div class="connect-line"></div><div class="data-box"><div class="label">Body Roll</div><div class="value-row"><span class="main-val">65°</span><span class="status-tag ok">OK</span></div></div></div>
                <div class="metric-node pos-evf"><div class="target-circle"></div><div class="connect-line"></div><div class="data-box"><div class="label">Early Vertical Forearm</div><div class="value-row"><span class="main-val">43°</span><span class="status-tag fix">FIX</span></div></div></div>
                <div class="metric-node pos-kick"><div class="target-circle"></div><div class="connect-line"></div><div class="data-box"><div class="label">Kick Depth</div><div class="value-row"><span class="main-val">0.33m</span><span class="status-tag ok">GOOD</span></div></div></div>
            </div>
        </div>
        </body>
        </html>
        """
        components.html(html_code, height=450)

    # --- Loom Demo Video ---
    st.markdown("""
    <div style="text-align: center; margin: 40px 0 20px; position: relative; z-index: 1;">
        <p style="color: #22d3ee; font-size: 0.85rem; font-weight: 700; letter-spacing: 1px; margin-bottom: 8px;">🎬 SEE IT IN ACTION</p>
        <h2 style="color: white; font-size: 1.8rem; margin: 0 0 20px;">Watch a Real Analysis — Start to Report</h2>
    </div>
    <div style="position: relative; padding-bottom: 62.5%; height: 0; border-radius: 16px; overflow: hidden; border: 1px solid rgba(34,211,238,0.2); box-shadow: 0 20px 40px rgba(0,0,0,0.4); max-width: 780px; margin: 0 auto 50px; z-index: 1;">
        <iframe 
            src="https://www.loom.com/embed/db63de9d2f6647e891aa28ab598c9de1?hide_owner=true&hide_share=true&hide_title=true&hideEmbedTopBar=true" 
            frameborder="0" 
            webkitallowfullscreen mozallowfullscreen allowfullscreen 
            style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;">
        </iframe>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
<style>
.process-section { padding: 40px 0 20px 0; text-align: center; position: relative; z-index: 1; width: 100%; }
.process-title { font-size: 2.4rem; font-weight: 700; margin-bottom: 40px; color: white !important; }

.process-grid { 
    display: flex; 
    justify-content: center; 
    align-items: stretch; 
    gap: 12px; 
    flex-wrap: nowrap; 
    max-width: 780px; 
    margin: 0 auto; 
}

.process-card { 
    background: linear-gradient(180deg, rgba(20,50,90,0.9), rgba(15,40,71,0.9)); 
    border-radius: 20px; 
    padding: 22px 14px; 
    width: 220px; 
    border: 1px solid rgba(34,211,238,0.15); 
    text-align: center; 
    display: flex; flex-direction: column; align-items: center;
    box-shadow: 0 10px 20px rgba(0,0,0,0.2);
    cursor: default;
    text-decoration: none;
}

.process-number { 
    width: 32px; height: 32px; margin-bottom: 12px; border-radius: 50%; 
    background: #0a1628;
    color: white;
    border: none;
    font-weight: 800; 
    display: flex; align-items: center; justify-content: center; flex-shrink: 0; 
}

.process-card h3 { color: #22d3ee !important; margin-bottom: 8px; font-size: 1.05rem; min-height: 30px; display: flex; align-items: center; justify-content: center;}
.process-card p { color: #94a3b8 !important; font-size: 0.85rem; line-height: 1.35; margin: 0; text-align: center; }
.process-arrow { font-size: 1.4rem; color: rgba(34,211,238,0.4); font-weight: bold; align-self: center; }

.angle-list { 
    text-align: center !important; 
    font-size: 0.72rem !important; 
    color: #cbd5e1 !important; 
    margin-top: 5px; 
    width: 100%; 
    padding-left: 0;
}
.angle-list span { display: block; margin-bottom: 2px; }
.highlight { color: #10b981; font-weight: 700; }

@media (max-width: 768px) { 
    .process-grid { flex-wrap: wrap; }
    .process-arrow { display: none; } 
    .process-card { width: 45%; }
}
</style>

<div class="process-section">
    <div class="process-title">How it works</div>
    <div class="process-grid">
        <div class="process-card">
            <div class="process-number">1</div>
            <h3>Upload Video</h3>
            <p>10–15s side-view freestyle clip. Phone camera works fine.</p>
        </div>
        <div class="process-arrow">→</div>
        <div class="process-card">
            <div class="process-number">2</div>
            <h3>Choose Angle View</h3>
            <div class="angle-list">
                <span>Side & Underwater <span class="highlight">(Best)</span></span>
                <span>Side & Above water</span>
                <span>Front & Underwater</span>
                <span>Front & Above water</span>
            </div>
        </div>
        <div class="process-arrow">→</div>
        <div class="process-card">
            <div class="process-number">3</div>
            <h3>Get Report</h3>
            <p>AI analysis in 90s. Annotated video + PDF report.</p>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

    st.markdown("""
<div style="max-width: 720px; margin: 50px auto 30px; padding: 32px; background: rgba(15, 40, 71, 0.4); border: 1px solid rgba(34, 211, 238, 0.15); border-radius: 20px; position: relative; z-index: 1;">
    <p style="color: #22d3ee; font-size: 0.8rem; font-weight: 700; letter-spacing: 1.5px; margin: 0 0 16px; text-align: center;">WHY I BUILT THIS</p>
    <p style="color: #cbd5e1; font-size: 0.98rem; line-height: 1.6; margin: 0 0 24px; text-align: center;">
        I'm Carlos — 4 x 70.3 and 1 x 140.6 Ironman finisher based in Houston. I got tired of training more without swimming faster. Built SwimForm AI to find what I couldn't see at full speed. Same race, two years apart:
    </p>
    <div style="display: flex; justify-content: center; align-items: center; gap: 24px; flex-wrap: wrap; margin: 0 auto;">
        <div style="text-align: center; min-width: 130px;">
            <div style="color: #64748b; font-size: 0.75rem; font-weight: 700; letter-spacing: 1px; margin-bottom: 6px;">BEFORE</div>
            <div style="color: #94a3b8; font-size: 1.8rem; font-weight: 800; font-family: 'Space Mono', monospace;">1:05:03</div>
            <div style="color: #64748b; font-size: 0.75rem; margin-top: 4px;">70.3 swim split</div>
        </div>
        <div style="color: #22d3ee; font-size: 1.5rem; font-weight: 800;">→</div>
        <div style="text-align: center; min-width: 130px;">
            <div style="color: #10b981; font-size: 0.75rem; font-weight: 700; letter-spacing: 1px; margin-bottom: 6px;">AFTER</div>
            <div style="color: white; font-size: 1.8rem; font-weight: 800; font-family: 'Space Mono', monospace;">0:44:17</div>
            <div style="color: #64748b; font-size: 0.75rem; margin-top: 4px;">70.3 swim split</div>
        </div>
    </div>
    <p style="color: #22d3ee; font-size: 1.1rem; font-weight: 700; margin: 20px 0 0; text-align: center;">
        −20:46 off the same race. Technique was the unlock.
    </p>
</div>
""", unsafe_allow_html=True)

    # --- Pricing & CTA ---
    st.markdown("""
<style>
.pricing-grid { display: flex; gap: 20px; justify-content: center; flex-wrap: wrap; position: relative; z-index: 1; margin-bottom: 20px; }
.pricing-card { flex: 1; min-width: 260px; max-width: 360px; background: rgba(15, 40, 71, 0.6); backdrop-filter: blur(12px); border: 1px solid rgba(6, 182, 212, 0.2); border-radius: 24px; padding: 32px 28px; text-align: center; box-shadow: 0 20px 40px rgba(0,0,0,0.4); position: relative; }
.pricing-card.coach { border-color: rgba(6, 182, 212, 0.5); }
.pricing-card.founding { border-color: rgba(16, 185, 129, 0.5); }
.badge { position: absolute; top: -14px; left: 50%; transform: translateX(-50%); background: #06b6d4; color: #0a1628; font-size: 0.75rem; font-weight: 800; padding: 4px 16px; border-radius: 20px; letter-spacing: 1px; white-space: nowrap; }
.badge.green { background: #10b981; color: #0a1628; }
.price-label { font-size: 0.8rem; color: #22d3ee; font-weight: 700; letter-spacing: 1px; margin-bottom: 6px; }
.price-row { display: flex; justify-content: center; align-items: baseline; gap: 10px; margin: 0 0 4px; }
.price { font-size: 3rem; font-weight: 800; color: white; margin: 0; }
.price-was { font-size: 1.25rem; color: #64748b; text-decoration: line-through; font-weight: 600; }
.price-sub { font-size: 0.85rem; color: #64748b; margin-bottom: 16px; }
.feature-list { list-style: none; padding: 0; margin: 0 0 24px; text-align: left; }
.feature-list li { color: #94a3b8; font-size: 0.88rem; padding: 5px 0; border-bottom: 1px solid rgba(255,255,255,0.05); }
.feature-list li::before { content: "✓ "; color: #22d3ee; font-weight: 700; }
@media (max-width: 600px) { .pricing-grid { flex-direction: column; align-items: center; } }
</style>
<div class="pricing-grid">
    <div class="pricing-card founding">
        <div class="badge green">LAUNCH PRICE</div>
        <div class="price-label">SWIMMER REPORT</div>
        <div class="price-row">
            <div class="price">$0.99</div>
            <div class="price-was">$4.99</div>
        </div>
        <div class="price-sub">/ video · launch price</div>
        <ul class="feature-list">
            <li>Overall technique score</li>
            <li>Top 3 issues in plain English</li>
            <li>Personalized drill cards</li>
            <li>Annotated video</li>
            <li>PDF report</li>
        </ul>
    </div>
    <div class="pricing-card coach">
        <div class="badge">MOST DATA</div>
        <div class="price-label">COACH REPORT</div>
        <div class="price-row">
            <div class="price">$6.99</div>
        </div>
        <div class="price-sub">/ video</div>
        <ul class="feature-list">
            <li>Everything in Swimmer PLUS:</li>
            <li>Full metrics with thresholds &amp; zones</li>
            <li>Component sub-scores</li>
            <li>CSV frame data export</li>
            <li>Analysis charts</li>
            <li>Detailed technique panel in video</li>
        </ul>
    </div>
</div>
""", unsafe_allow_html=True)

    def _add_utm(url: str, content: str) -> str:
        if not url:
            return url
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}utm_source=swimformai&utm_medium=landing&utm_campaign=launch&utm_content={content}"

    swimmer_link = STRIPE_PAYMENT_LINK_FOUNDING if STRIPE_PAYMENT_LINK_FOUNDING else STRIPE_PAYMENT_LINK
    swimmer_price_label = "0.99_launch" if STRIPE_PAYMENT_LINK_FOUNDING else "4.99"
    swimmer_link_with_utm = _add_utm(swimmer_link, "swimmer_launch")
    coach_link_with_utm = _add_utm(STRIPE_PAYMENT_LINK_COACH, "coach")

    # Fire rendered events ONCE per session, not on every rerun
    if swimmer_link and "rendered_swimmer" not in st.session_state:
        track("checkout_button_rendered", {"tier": "swimmer", "price": swimmer_price_label})
        st.session_state.rendered_swimmer = True
    if STRIPE_PAYMENT_LINK_COACH and "rendered_coach" not in st.session_state:
        track("checkout_button_rendered", {"tier": "coach", "price": "6.99"})
        st.session_state.rendered_coach = True

    if swimmer_link and STRIPE_PAYMENT_LINK_COACH:
        pending_checkout = st.session_state.pop("checkout_redirect_url", None)
        if pending_checkout:
            _redirect_top_level(pending_checkout)
            st.stop()

        st.markdown(
            """
<style>
.checkout-cta-area { margin: 12px 0 24px; position: relative; z-index: 1; }
.checkout-cta-area div[data-testid="column"] { min-width: 240px; }
.checkout-cta-area button {
    border-radius: 12px !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    padding: 14px 20px !important;
    min-height: 52px;
    transition: transform 0.15s ease, box-shadow 0.15s ease !important;
}
.checkout-cta-area button[kind="primary"] {
    background: linear-gradient(135deg, #06b6d4, #0891b2) !important;
    border: 1px solid transparent !important;
    color: white !important;
    box-shadow: 0 8px 16px rgba(6, 182, 212, 0.3) !important;
}
.checkout-cta-area button[kind="secondary"] {
    background: rgba(15, 40, 71, 0.6) !important;
    border: 1px solid rgba(34, 211, 238, 0.4) !important;
    color: #22d3ee !important;
}
.checkout-cta-area button:hover {
    transform: translateY(-2px);
    box-shadow: 0 12px 20px rgba(6, 182, 212, 0.4) !important;
}
</style>
<div class="checkout-cta-area"></div>
""",
            unsafe_allow_html=True,
        )

        col_swimmer, col_coach = st.columns(2, gap="medium")
        with col_swimmer:
            if st.button(
                "🏊 Get Swimmer Report — $0.99 →",
                type="primary",
                use_container_width=True,
                key="checkout_swimmer_cta",
            ):
                track(
                    "checkout_clicked",
                    {
                        "tier": "swimmer",
                        "price": swimmer_price_label,
                        "destination": "stripe",
                    },
                )
                st.session_state.checkout_redirect_url = swimmer_link_with_utm
                st.rerun()
        with col_coach:
            if st.button(
                "📊 Get Coach Report →",
                type="secondary",
                use_container_width=True,
                key="checkout_coach_cta",
            ):
                track(
                    "checkout_clicked",
                    {
                        "tier": "coach",
                        "price": "6.99",
                        "destination": "stripe",
                    },
                )
                st.session_state.checkout_redirect_url = coach_link_with_utm
                st.rerun()
    else:
        if not swimmer_link:
            st.info("Swimmer payment link not configured.")
        if not STRIPE_PAYMENT_LINK_COACH:
            st.info("Coach payment link not configured.")

    if IS_DEV:
        if st.button("Developer: Skip to Dashboard", use_container_width=True):
            st.session_state.paid = True
            st.session_state.report_mode = "coach"
            st.rerun()

    # --- 4. The Analysis Engine (Full Restore) ---
    st.markdown('<h2 style="text-align:center; font-size:2.5rem; margin:60px 0 40px; position: relative; z-index: 1;">The Analysis Engine</h2>', unsafe_allow_html=True)
    st.markdown("""
    <style>
    .feature-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; width: 100%; margin-bottom: 50px; position: relative; z-index: 1; }
    .f-card { background: rgba(15, 23, 42, 0.55); border: 1px solid rgba(148, 163, 184, 0.18); border-radius: 20px; padding: 30px 20px; text-align: center; height: 100%; box-sizing: border-box; display: flex; flex-direction: column; align-items: center; }
    .f-icon { font-size: 3rem; margin-bottom: 15px; }
    .f-card h3 { color: #22d3ee; font-size: 1.25rem; margin: 0 0 10px 0; }
    .f-card p { color: #94a3b8; font-size: 0.9rem; line-height: 1.5; margin: 0; }
    @media (max-width: 900px) { .feature-grid { grid-template-columns: repeat(2, 1fr); } }
    @media (max-width: 600px) { .feature-grid { grid-template-columns: 1fr; } }
    </style>
    """, unsafe_allow_html=True)

    features = [
        ("📊", "6 Biometrics", "Stroke rate, DPS, entry angle, elbow drop, body rotation, and kick depth measured frame-by-frame."),
        ("🎯", "Ranked Issues", "We rank your 1-3 biggest speed leaks so you know exactly what to fix first."),
        ("🏊", "Drill Prescription", "Personalized drills with rep counts and focus cues to correct your specific flaws."),
        ("🎥", "Pro Comparison", "Your stroke overlaid with Olympic-level reference footage for visual alignment."),
        ("📈", "Progress Charting", "Upload follow-up videos to track improvement across all metrics session-over-session."),
        ("⚡", "90-Sec Turnaround", "Proprietary AI processing delivers a deep-dive PDF report while you're still at the pool.")
    ]

    cards_html = "".join([f'<div class="f-card"><div class="f-icon">{icon}</div><h3>{title}</h3><p>{desc}</p></div>' for icon, title, desc in features])
    st.markdown(f'<div class="feature-grid">{cards_html}</div>', unsafe_allow_html=True)

    # --- Footer ---
    st.markdown("""
    <div style="text-align: center; margin-top: 100px; padding: 40px 0; border-top: 1px solid rgba(6, 182, 212, 0.1); color: #64748b; font-size: 0.8rem; position: relative; z-index: 1;">
        © 2026 SwimForm AI · Professional Biomechanics for Every Lane · <a href="mailto:info@swimform-ai.com" style="color: #22d3ee; text-decoration: none;">Support</a>
    </div>
    """, unsafe_allow_html=True)

# =============================================
# MAIN ROUTER
# =============================================
q = st.query_params

# Admin bypass (secret token in URL)
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")
ADMIN_TOKEN_2 = os.environ.get("ADMIN_TOKEN_2", "")
valid_tokens = [t for t in [ADMIN_TOKEN, ADMIN_TOKEN_2] if t]
if valid_tokens and q.get("admin") in valid_tokens:
    st.session_state.paid = True
    st.session_state.report_mode = "coach"
    st.query_params.clear()
    st.query_params["verified"] = "admin"
    st.rerun()

if "session_id" in q and not st.session_state.paid:
    session_id = q.get("session_id")
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        if session.payment_status == "paid":
            st.session_state.paid = True
            st.session_state.report_mode = session.metadata.get("report_mode", "swimmer")
            st.query_params.clear()
            st.query_params["verified"] = session_id
            st.balloons()
            st.rerun()
        else:
            st.warning("Payment not completed. Please try again.")
            st.query_params.clear()
    except Exception:
        st.error("Could not verify payment. Please contact support.")
        st.query_params.clear()

if st.session_state.paid:
    st.switch_page("pages/2_Dashboard.py")
else:
    show_landing_page()

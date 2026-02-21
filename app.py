import streamlit as st
import streamlit.components.v1 as components
import base64
import os

# =============================================
# PAGE CONFIG
# =============================================
st.set_page_config(
    page_title="SwimForm AI | Elite Biomechanics",
    page_icon="🏊",
    layout="centered",
    initial_sidebar_state="collapsed"
)

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
STRIPE_PAYMENT_LINK = "https://buy.stripe.com/test_8x2eVdaBSe7mf2JaIEao800"
IS_DEV = True

if "paid" not in st.session_state:
    st.session_state.paid = False

def show_landing_page():
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

    # --- 2. How It Works ---
    st.markdown("""
    <style>
    .process-section { padding: 40px 0 60px 0; text-align: center; position: relative; z-index: 1; width: 100%; }
    .process-title { font-size: 2.8rem; font-weight: 700; margin-bottom: 50px; color: white !important; }
    
    .process-grid { 
        display: flex; 
        justify-content: center; 
        align-items: stretch; 
        gap: 10px; 
        flex-wrap: nowrap; 
        max-width: 900px; 
        margin: 0 auto; 
    }
    
    .process-card { 
        background: linear-gradient(180deg, rgba(20,50,90,0.9), rgba(15,40,71,0.9)); 
        border-radius: 20px; 
        padding: 20px 12px; 
        width: 175px; 
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
    
    .process-card h3 { color: #22d3ee !important; margin-bottom: 8px; font-size: 1rem; min-height: 30px; display: flex; align-items: center; justify-content: center;}
    .process-card p { color: #94a3b8 !important; font-size: 0.8rem; line-height: 1.3; margin: 0; text-align: center; }
    .process-arrow { font-size: 1.2rem; color: rgba(34,211,238,0.4); font-weight: bold; align-self: center; }
    
    .angle-list { 
        text-align: center !important; 
        font-size: 0.7rem !important; 
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
                <h3>Pay $4.99</h3>
                <p>Secure checkout via Stripe. Instant access.</p>
            </div>
            <div class="process-arrow">→</div>
            <div class="process-card">
                <div class="process-number">2</div>
                <h3>Upload Video</h3>
                <p>10–15s clip. Ensure good lighting.</p>
            </div>
            <div class="process-arrow">→</div>
            <div class="process-card">
                <div class="process-number">3</div>
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
                <div class="process-number">4</div>
                <h3>Get Report</h3>
                <p>AI analysis in 90s. Download PDF + video.</p>
            </div>
        </div>
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

    # --- Pricing & CTA ---
    col1, col2, col3 = st.columns([1, 1.8, 1])
    with col2:
        st.markdown("""
        <div class="cta-box">
            <div style="font-size: 0.9rem; color: #22d3ee; font-weight: 700; margin-bottom: 8px; letter-spacing: 1px;">INSTANT ANALYSIS</div>
            <div style="font-size: 3.5rem; font-weight: 800; color: white;">$4.99 <span style="font-size: 1rem; color: #64748b; font-weight: 400;">/ video</span></div>
            <p style="color: #94a3b8; margin: 15px 0 30px;">Full PDF Report • Side-by-Side Playback • Drill Cards</p>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
        st.link_button("🏊 Get My Biomechanics Report →", STRIPE_PAYMENT_LINK, type="primary", use_container_width=True)

        if IS_DEV:
            if st.button("Developer: Skip to Dashboard", use_container_width=True):
                st.session_state.paid = True
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
        ("📊", "7 Biometrics", "Stroke rate, DPS, entry angle, elbow drop, and body rotation measured frame-by-frame."),
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
        © 2026 SwimForm AI · Professional Biomechanics for Every Lane · <a href="mailto:support@swimform.ai" style="color: #22d3ee; text-decoration: none;">Support</a>
    </div>
    """, unsafe_allow_html=True)

# =============================================
# MAIN ROUTER
# =============================================
q = st.query_params
if q.get("success") == "true":
    st.session_state.paid = True
    st.query_params.clear()          
    st.balloons()
    st.rerun()                       

if st.session_state.paid:
    # Ensure the path below matches your exact file structure
    st.switch_page("pages/2_Dashboard.py")
else:
    show_landing_page()

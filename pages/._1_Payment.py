import streamlit as st

try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False

# ─────────────────────────────────────────────
# PAYMENT PAGE
# ─────────────────────────────────────────────

st.set_page_config(
    page_title="Get Access - Freestyle Swim Analyzer",
    page_icon="💳",
    layout="wide"
)

# Custom CSS for payment page
PAYMENT_CSS = """
<style>
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #0f172a 100%);
    }
    .payment-hero {
        text-align: center;
        padding: 40px 20px;
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(10px);
        border-radius: 24px;
        border: 1px solid rgba(100, 116, 139, 0.3);
        margin: 20px auto;
        max-width: 700px;
    }
    .price-box {
        background: linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%);
        border-radius: 20px;
        padding: 50px;
        text-align: center;
        color: white;
        margin: 30px auto;
        max-width: 500px;
        box-shadow: 0 20px 60px rgba(6, 182, 212, 0.3);
    }
    .price-amount {
        font-size: 4em;
        font-weight: 800;
        margin: 20px 0;
    }
    .feature-list {
        background: rgba(30, 41, 59, 0.8);
        border-radius: 16px;
        padding: 30px;
        margin: 20px auto;
        max-width: 600px;
    }
    .feature-item {
        display: flex;
        align-items: center;
        margin: 15px 0;
        font-size: 1.1em;
    }
    .feature-icon {
        color: #22c55e;
        font-size: 1.5em;
        margin-right: 15px;
    }
    h1, h2, h3 { color: #f8fafc !important; }
    p, span, label { color: #cbd5e1; }
    .stButton > button {
        background: linear-gradient(135deg, #22c55e 0%, #10b981 100%);
        color: white;
        border: none;
        border-radius: 12px;
        padding: 16px 48px;
        font-size: 1.3em;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 30px rgba(34, 197, 94, 0.4);
    }
</style>
"""

st.markdown(PAYMENT_CSS, unsafe_allow_html=True)

# Check for payment success/cancel
query_params = st.query_params
if query_params.get("payment") == "success":
    st.session_state.payment_completed = True
    st.session_state.analysis_unlocked = True
    st.success("✅ Payment successful! Redirecting to dashboard...")
    st.balloons()
    st.query_params.clear()
    
    # Auto-redirect to dashboard after 2 seconds
    st.markdown("""
    <meta http-equiv="refresh" content="2;url=./2_Dashboard" />
    """, unsafe_allow_html=True)
    
    if st.button("Go to Dashboard Now"):
        st.switch_page("pages/2_Dashboard.py")
    st.stop()

elif query_params.get("payment") == "cancel":
    st.warning("⚠️ Payment cancelled. You can try again below.")
    st.query_params.clear()

# Check if already paid
if st.session_state.get("payment_completed", False):
    st.success("✅ You already have access!")
    if st.button("Go to Dashboard"):
        st.switch_page("pages/2_Dashboard.py")
    st.stop()

# Hero Section
st.markdown("""
<div class="payment-hero">
    <h1 style="font-size: 2.5em; margin-bottom: 15px;">🏊 Get Unlimited Access</h1>
    <p style="font-size: 1.2em; color: #cbd5e1;">
        One-time payment for lifetime access to professional swim analysis
    </p>
</div>
""", unsafe_allow_html=True)

# Pricing Box
st.markdown("""
<div class="price-box">
    <div style="font-size: 1.3em; opacity: 0.9;">One-Time Payment</div>
    <div class="price-amount">$29</div>
    <div style="font-size: 1.1em; opacity: 0.9;">Lifetime Access • No Subscriptions</div>
</div>
""", unsafe_allow_html=True)

# What's Included
st.markdown("""
<div class="feature-list">
    <h2 style="text-align: center; margin-bottom: 30px;">What's Included</h2>
    
    <div class="feature-item">
        <span class="feature-icon">✓</span>
        <span>Unlimited video analysis</span>
    </div>
    
    <div class="feature-item">
        <span class="feature-icon">✓</span>
        <span>Advanced biomechanical metrics (EVF, body roll, alignment)</span>
    </div>
    
    <div class="feature-item">
        <span class="feature-icon">✓</span>
        <span>AI-powered pose detection with MediaPipe</span>
    </div>
    
    <div class="feature-item">
        <span class="feature-icon">✓</span>
        <span>Annotated video output with visual overlays</span>
    </div>
    
    <div class="feature-item">
        <span class="feature-icon">✓</span>
        <span>Comprehensive PDF performance reports</span>
    </div>
    
    <div class="feature-item">
        <span class="feature-icon">✓</span>
        <span>Multi-view support (underwater, above water, side, front)</span>
    </div>
    
    <div class="feature-item">
        <span class="feature-icon">✓</span>
        <span>Export analysis data and charts</span>
    </div>
    
    <div class="feature-item">
        <span class="feature-icon">✓</span>
        <span>Lifetime updates and improvements</span>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Payment Section
col_left, col_center, col_right = st.columns([1, 2, 1])

with col_center:
    if not STRIPE_AVAILABLE:
        st.error("⚠️ Stripe not installed. Run: `pip install stripe`")
        st.info("For testing, you can skip payment:")
        if st.button("Skip Payment (Demo Mode)", use_container_width=True):
            st.session_state.payment_completed = True
            st.session_state.analysis_unlocked = True
            st.success("✅ Demo access granted!")
            st.switch_page("pages/2_Dashboard.py")
    else:
        # Get Stripe configuration from secrets
        try:
            stripe_secret = st.secrets.get("stripe", {}).get("secret_key")
            stripe_price_id = st.secrets.get("stripe", {}).get("price_id")
            
            if stripe_secret and stripe_price_id:
                stripe.api_key = stripe_secret
                
                # Checkout button
                st.markdown("""
                <div style="text-align: center; margin: 30px 0;">
                    <p style="font-size: 1.1em; color: #cbd5e1; margin-bottom: 20px;">
                        🔒 Secure payment powered by Stripe
                    </p>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button("💳 Proceed to Secure Checkout", type="primary", use_container_width=True):
                    try:
                        # Get base URL from secrets or use default
                        base_url = st.secrets.get("stripe", {}).get("base_url", "https://yourapp.streamlit.app")
                        
                        # Create Stripe Checkout Session
                        checkout_session = stripe.checkout.Session.create(
                            payment_method_types=['card'],
                            line_items=[{
                                'price': stripe_price_id,
                                'quantity': 1,
                            }],
                            mode='payment',
                            success_url=f"{base_url}/1_Payment?payment=success",
                            cancel_url=f"{base_url}/1_Payment?payment=cancel",
                        )
                        
                        # Redirect to Stripe Checkout
                        st.markdown(f'<meta http-equiv="refresh" content="0;url={checkout_session.url}">', unsafe_allow_html=True)
                        st.info(f"Redirecting to secure checkout... [Click here if not redirected]({checkout_session.url})")
                        
                    except Exception as e:
                        st.error(f"Error creating checkout session: {str(e)}")
                        st.info("For testing, you can skip payment:")
                        if st.button("Skip Payment (Demo Mode)", use_container_width=True):
                            st.session_state.payment_completed = True
                            st.session_state.analysis_unlocked = True
                            st.success("✅ Demo access granted!")
                            st.switch_page("pages/2_Dashboard.py")
            else:
                st.warning("⚠️ Stripe configuration missing. Add your Stripe keys to `.streamlit/secrets.toml`")
                st.info("For testing, you can skip payment:")
                if st.button("Skip Payment (Demo Mode)", use_container_width=True):
                    st.session_state.payment_completed = True
                    st.session_state.analysis_unlocked = True
                    st.success("✅ Demo access granted!")
                    st.switch_page("pages/2_Dashboard.py")
                    
        except Exception as e:
            st.error(f"Stripe initialization error: {e}")
            st.info("For testing, you can skip payment:")
            if st.button("Skip Payment (Demo Mode)", use_container_width=True):
                st.session_state.payment_completed = True
                st.session_state.analysis_unlocked = True
                st.success("✅ Demo access granted!")
                st.switch_page("pages/2_Dashboard.py")

# Money-back guarantee
st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown("""
<div style="text-align: center; padding: 20px; color: #64748b; border-top: 1px solid rgba(100, 116, 139, 0.3); margin-top: 40px;">
    <p>🔒 Secure payment • 💯 Satisfaction guaranteed • 📧 Support included</p>
    <p style="font-size: 0.9em;">Need help? Contact support@swimanalyzer.ai</p>
</div>
""", unsafe_allow_html=True)

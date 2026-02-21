# Stripe Payment Integration Setup

This guide explains how to set up Stripe payment for single video analysis.

## Overview

The app now includes:
- ✅ **Video-first workflow**: Upload video → Select type → Pay → Analyze
- ✅ **Mobile-optimized encoding**: H.264 baseline profile for better mobile phone compatibility
- ✅ **Stripe integration**: Single payment for single analysis

## Stripe Setup Steps

### 1. Create a Stripe Account
1. Go to [https://stripe.com](https://stripe.com) and sign up
2. Complete your account setup

### 2. Get Your API Keys
1. Go to [Stripe Dashboard](https://dashboard.stripe.com)
2. Navigate to **Developers** → **API keys**
3. Copy your **Publishable key** (starts with `pk_test_` or `pk_live_`)
4. Copy your **Secret key** (starts with `sk_test_` or `sk_live_`)

### 3. Create a Product and Price
1. In Stripe Dashboard, go to **Products** → **Add Product**
2. Create a product:
   - **Name**: Single Video Analysis
   - **Description**: Full swim technique analysis with PDF report
   - **Price**: $9.99 (or your preferred amount)
   - **Billing period**: One time
3. After creating, copy the **Price ID** (starts with `price_`)

### 4. Configure Streamlit Secrets
1. Copy the example file:
   ```bash
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   ```

2. Edit `.streamlit/secrets.toml` and add your actual Stripe keys:
   ```toml
   [stripe]
   publishable_key = "pk_test_YOUR_KEY_HERE"
   secret_key = "sk_test_YOUR_KEY_HERE"
   price_id = "price_YOUR_PRICE_ID_HERE"
   base_url = "http://localhost:8501"  # For local testing
   ```

3. **Important**: Never commit `secrets.toml` to git!

### 5. Test the Integration
1. Start the app: `streamlit run app.py`
2. Upload a video
3. Select video type
4. Click "Pay & Analyze"
5. Use Stripe test cards:
   - Success: `4242 4242 4242 4242`
   - Decline: `4000 0000 0000 0002`

### 6. Production Deployment

For production (Streamlit Cloud):
1. Go to your app settings in Streamlit Cloud
2. Navigate to **Secrets**
3. Add your production Stripe keys:
   ```toml
   [stripe]
   publishable_key = "pk_live_YOUR_KEY"
   secret_key = "sk_live_YOUR_KEY"
   price_id = "price_YOUR_LIVE_PRICE_ID"
   base_url = "https://yourapp.streamlit.app"
   ```

## Workflow for Users

1. **Upload Video** - Users upload their swimming video (MP4, MOV, AVI)
2. **Select Type** - Choose camera view (Side/Front) and position (Underwater/Above Water)
3. **Payment** - Pay $9.99 for single analysis
4. **Analysis** - Video is processed with full technique analysis
5. **Download** - Get PDF report, annotated video, and CSV data

## Mobile Video Encoding

The app now uses mobile-optimized encoding:
- **H.264 Baseline Profile** - Maximum compatibility with mobile browsers
- **Level 3.0** - Supports most mobile devices
- **Bitrate limiting** - 2Mbps max for smooth mobile playback
- **FastStart flag** - Enables progressive download
- **YUV420p pixel format** - Required for mobile Safari

This ensures videos play smoothly on:
- iOS Safari
- Android Chrome
- Mobile Firefox
- All major mobile browsers

## Troubleshooting

### Payment button not showing
- Check that `stripe>=7.0.0` is in `requirements.txt`
- Verify `secrets.toml` exists with correct keys
- Check app logs for Stripe initialization errors

### Videos not playing on mobile
- Ensure ffmpeg is installed on your server
- Check that encoding completed successfully
- Verify video uses H.264 baseline profile

### Testing mode
If Stripe is not configured, the app shows a "Skip Payment (Testing Mode)" button for development.

## Security Notes

1. **Never expose your secret key** in client-side code
2. **Always use HTTPS** in production
3. **Validate payments server-side** before granting access
4. **Use webhook verification** for production (optional, for robust payment confirmation)

## Next Steps

For subscription-based access (multiple analyses), you'll need to:
1. Create a subscription Product in Stripe
2. Implement customer portal
3. Add session management for authenticated users
4. Track analysis credits/quotas

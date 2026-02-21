import streamlit as st
import streamlit.components.v1 as components
import cv2
import numpy as np
import math
import statistics
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
import tempfile
import os
import datetime
import pandas as pd
import matplotlib.pyplot as plt
from collections import deque
import io
import zipfile
import urllib.request

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch

# MoviePy for video encoding (pure Python, no ffmpeg binary needed)
try:
    from moviepy.editor import VideoFileClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False

# Stripe for payment processing
try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False

# ─────────────────────────────────────────────
# MEDIAPIPE TASKS API
# ─────────────────────────────────────────────

try:
    import mediapipe as mp
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
    MEDIAPIPE_TASKS_AVAILABLE = True
except ImportError:
    MEDIAPIPE_TASKS_AVAILABLE = False
    st.error("MediaPipe Tasks not installed → pip install mediapipe>=0.10.0")

# ─────────────────────────────────────────────
# CUSTOM CSS - Enhanced for new UI
# ─────────────────────────────────────────────

CUSTOM_CSS = """
<style>
    .stApp { background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #0f172a 100%); }
    .metric-card { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(10px); border-radius: 16px; padding: 20px; border: 1px solid rgba(100, 116, 139, 0.3); margin-bottom: 16px; }
    .metric-card-green { border-left: 4px solid #22c55e; background: rgba(34, 197, 94, 0.1); }
    .metric-card-red   { border-left: 4px solid #ef4444; background: rgba(239, 68, 68, 0.1); }
    .metric-card-yellow{ border-left: 4px solid #eab308; background: rgba(234, 179, 8, 0.1); }
    .score-card { background: linear-gradient(135deg, #0891b2 0%, #2563eb 100%); border-radius: 16px; padding: 24px; color: white; margin-bottom: 24px; }
    .alignment-card { background: linear-gradient(135deg, #059669 0%, #10b981 100%); border-radius: 16px; padding: 20px; color: white; margin-bottom: 16px; }
    .evf-card { background: linear-gradient(135deg, #7c3aed 0%, #a855f7 100%); border-radius: 16px; padding: 20px; color: white; margin-bottom: 16px; }
    .diagnostic-box { background: rgba(30, 41, 59, 0.8); border-radius: 12px; padding: 16px; margin: 8px 0; border-left: 3px solid #06b6d4; }
    .diagnostic-warning { border-left-color: #f59e0b; }
    .diagnostic-error { border-left-color: #ef4444; }
    .stButton > button { background: linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%); color: white; border: none; border-radius: 12px; padding: 12px 24px; font-weight: 600; transition: all 0.3s ease; }
    .stButton > button:hover { transform: translateY(-2px); box-shadow: 0 10px 20px rgba(6, 182, 212, 0.3); }
    h1, h2, h3 { color: #f8fafc !important; }
    p, span, label { color: #cbd5e1; }
    .phase-badge { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; }
    .phase-entry { background: #3b82f6; color: white; }
    .phase-pull { background: #22c55e; color: white; }
    .phase-push { background: #f59e0b; color: black; }
    .phase-recovery { background: #6b7280; color: white; }
</style>
"""

# ─────────────────────────────────────────────
# SWIM METRICS VISUALIZATION COMPONENT
# ─────────────────────────────────────────────

def get_viz_zone_class(value, good_range, ok_range):
    """Return CSS class based on value zone"""
    if good_range[0] <= value <= good_range[1]:
        return "good"
    elif ok_range[0] <= value <= ok_range[1]:
        return "ok"
    return "bad"

def get_viz_zone_label(value, good_range, ok_range):
    """Return label based on value zone"""
    if good_range[0] <= value <= good_range[1]:
        return "✓ Good"
    elif ok_range[0] <= value <= ok_range[1]:
        return "◐ OK"
    return "✗ Fix"

def get_viz_zone_color(value, good_range, ok_range):
    """Return hex color based on value zone"""
    if good_range[0] <= value <= good_range[1]:
        return "#22c55e"
    elif ok_range[0] <= value <= ok_range[1]:
        return "#eab308"
    return "#ef4444"

def get_alignment_silhouette(deviation):
    """Generate SVG for body alignment visualization"""
    color = get_viz_zone_color(deviation, (0, 8), (0, 15))
    offset = deviation * 1.5
    
    return f'''
    <svg viewBox="0 0 100 140" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <filter id="glow1" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
                <feMerge><feMergeNode in="coloredBlur"/><feMergeNode in="SourceGraphic"/></feMerge>
            </filter>
            <linearGradient id="bodyGrad1" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:{color};stop-opacity:0.8" />
                <stop offset="100%" style="stop-color:{color};stop-opacity:0.4" />
            </linearGradient>
        </defs>
        <line x1="50" y1="5" x2="50" y2="135" stroke="white" stroke-width="1" stroke-dasharray="4,4" opacity="0.3"/>
        <g filter="url(#glow1)">
            <ellipse cx="50" cy="18" rx="10" ry="12" fill="url(#bodyGrad1)"/>
            <rect x="46" y="28" width="8" height="8" fill="{color}" opacity="0.7"/>
            <ellipse cx="50" cy="42" rx="22" ry="8" fill="url(#bodyGrad1)"/>
            <ellipse cx="{50 + offset * 0.3}" cy="65" rx="18" ry="20" fill="url(#bodyGrad1)"/>
            <ellipse cx="{50 + offset * 0.6}" cy="90" rx="16" ry="10" fill="url(#bodyGrad1)"/>
            <ellipse cx="{42 + offset * 0.8}" cy="115" rx="7" ry="20" fill="{color}" opacity="0.6"/>
            <ellipse cx="{58 + offset * 0.8}" cy="115" rx="7" ry="20" fill="{color}" opacity="0.6"/>
        </g>
        <circle cx="50" cy="18" r="3" fill="white" opacity="0.8"/>
        <circle cx="{50 + offset * 0.5}" cy="65" r="3" fill="white" opacity="0.8"/>
        <circle cx="{50 + offset * 0.8}" cy="115" r="3" fill="white" opacity="0.8"/>
        <line x1="50" y1="18" x2="{50 + offset * 0.5}" y2="65" stroke="{color}" stroke-width="2"/>
        <line x1="{50 + offset * 0.5}" y1="65" x2="{50 + offset * 0.8}" y2="115" stroke="{color}" stroke-width="2"/>
    </svg>
    '''

def get_evf_silhouette(angle):
    """Generate SVG for EVF visualization"""
    color = get_viz_zone_color(angle, (0, 25), (0, 40))
    forearm_length = 35
    forearm_end_x = 55 + forearm_length * math.sin(math.radians(angle))
    forearm_end_y = 55 + forearm_length * math.cos(math.radians(angle))
    
    return f'''
    <svg viewBox="0 0 100 140" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <filter id="glow2" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
                <feMerge><feMergeNode in="coloredBlur"/><feMergeNode in="SourceGraphic"/></feMerge>
            </filter>
            <linearGradient id="bodyGrad2" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:{color};stop-opacity:0.8" />
                <stop offset="100%" style="stop-color:{color};stop-opacity:0.4" />
            </linearGradient>
        </defs>
        <line x1="0" y1="30" x2="100" y2="30" stroke="#0ea5e9" stroke-width="2" opacity="0.5"/>
        <text x="5" y="25" fill="#0ea5e9" font-size="8" opacity="0.7">water</text>
        <line x1="55" y1="55" x2="55" y2="95" stroke="white" stroke-width="1" stroke-dasharray="3,3" opacity="0.3"/>
        <g filter="url(#glow2)">
            <ellipse cx="30" cy="35" rx="10" ry="8" fill="url(#bodyGrad2)"/>
            <ellipse cx="45" cy="55" rx="20" ry="12" fill="url(#bodyGrad2)" transform="rotate(-15, 45, 55)"/>
            <line x1="35" y1="50" x2="20" y2="25" stroke="{color}" stroke-width="6" stroke-linecap="round" opacity="0.4"/>
            <circle cx="55" cy="48" r="5" fill="{color}"/>
            <line x1="55" y1="48" x2="55" y2="55" stroke="{color}" stroke-width="7" stroke-linecap="round"/>
            <circle cx="55" cy="55" r="4" fill="{color}"/>
            <line x1="55" y1="55" x2="{forearm_end_x}" y2="{forearm_end_y}" stroke="{color}" stroke-width="6" stroke-linecap="round"/>
            <ellipse cx="{forearm_end_x}" cy="{forearm_end_y + 5}" rx="5" ry="8" fill="{color}"/>
            <ellipse cx="60" cy="70" rx="12" ry="8" fill="url(#bodyGrad2)"/>
            <line x1="65" y1="75" x2="85" y2="110" stroke="{color}" stroke-width="8" stroke-linecap="round" opacity="0.6"/>
            <line x1="55" y1="75" x2="75" y2="115" stroke="{color}" stroke-width="8" stroke-linecap="round" opacity="0.6"/>
        </g>
        <text x="{60 + 10 * math.sin(math.radians(angle/2))}" y="{62 + 10 * math.cos(math.radians(angle/2))}" fill="white" font-size="8">{angle:.0f}°</text>
    </svg>
    '''

def get_roll_silhouette(roll_angle):
    """Generate SVG for body roll visualization"""
    color = get_viz_zone_color(roll_angle, (35, 55), (25, 65))
    display_angle = roll_angle - 45
    cos_val = math.cos(math.radians(display_angle))
    sin_val = math.sin(math.radians(display_angle))
    
    return f'''
    <svg viewBox="0 0 100 140" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <filter id="glow3" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
                <feMerge><feMergeNode in="coloredBlur"/><feMergeNode in="SourceGraphic"/></feMerge>
            </filter>
            <linearGradient id="bodyGrad3" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:{color};stop-opacity:0.8" />
                <stop offset="100%" style="stop-color:{color};stop-opacity:0.4" />
            </linearGradient>
        </defs>
        <text x="50" y="12" fill="#64748b" font-size="8" text-anchor="middle">TOP VIEW</text>
        <line x1="50" y1="20" x2="50" y2="130" stroke="white" stroke-width="1" stroke-dasharray="4,4" opacity="0.2"/>
        <line x1="10" y1="70" x2="90" y2="70" stroke="white" stroke-width="1" stroke-dasharray="4,4" opacity="0.2"/>
        <polygon points="50,25 45,35 55,35" fill="#64748b" opacity="0.5"/>
        <g transform="rotate({display_angle}, 50, 70)" filter="url(#glow3)">
            <ellipse cx="50" cy="30" rx="8" ry="10" fill="url(#bodyGrad3)"/>
            <ellipse cx="50" cy="50" rx="30" ry="10" fill="url(#bodyGrad3)"/>
            <ellipse cx="20" cy="40" rx="8" ry="15" fill="{color}" opacity="0.5" transform="rotate(-30, 20, 40)"/>
            <ellipse cx="80" cy="55" rx="8" ry="15" fill="{color}" opacity="0.5" transform="rotate(20, 80, 55)"/>
            <ellipse cx="50" cy="70" rx="20" ry="15" fill="url(#bodyGrad3)"/>
            <ellipse cx="50" cy="90" rx="18" ry="10" fill="url(#bodyGrad3)"/>
            <ellipse cx="42" cy="110" rx="6" ry="18" fill="{color}" opacity="0.5"/>
            <ellipse cx="58" cy="115" rx="6" ry="18" fill="{color}" opacity="0.5"/>
        </g>
        <g transform="translate(50, 70)">
            <line x1="0" y1="0" x2="35" y2="0" stroke="white" stroke-width="1" opacity="0.3"/>
            <line x1="0" y1="0" x2="{35 * cos_val}" y2="{35 * sin_val}" stroke="{color}" stroke-width="2"/>
        </g>
    </svg>
    '''

def get_kick_silhouette(depth, symmetry):
    """Generate SVG for kick visualization"""
    color = get_viz_zone_color(depth, (0.15, 0.35), (0.10, 0.45))
    kick_amplitude = depth * 80
    sym_offset = symmetry * 0.5
    
    return f'''
    <svg viewBox="0 0 100 140" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <filter id="glow4" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
                <feMerge><feMergeNode in="coloredBlur"/><feMergeNode in="SourceGraphic"/></feMerge>
            </filter>
            <linearGradient id="bodyGrad4" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:{color};stop-opacity:0.8" />
                <stop offset="100%" style="stop-color:{color};stop-opacity:0.4" />
            </linearGradient>
        </defs>
        <line x1="10" y1="45" x2="90" y2="45" stroke="white" stroke-width="1" stroke-dasharray="4,4" opacity="0.3"/>
        <g filter="url(#glow4)" opacity="0.4">
            <ellipse cx="20" cy="40" rx="12" ry="8" fill="{color}"/>
            <ellipse cx="35" cy="45" rx="15" ry="10" fill="{color}"/>
        </g>
        <ellipse cx="55" cy="45" rx="12" ry="10" fill="url(#bodyGrad4)" filter="url(#glow4)"/>
        <rect x="70" y="{45 - kick_amplitude/2}" width="3" height="{kick_amplitude}" fill="{color}" opacity="0.3" rx="1"/>
        <g filter="url(#glow4)">
            <line x1="55" y1="45" x2="90" y2="{45 - kick_amplitude/2 + sym_offset}" stroke="{color}" stroke-width="10" stroke-linecap="round"/>
            <ellipse cx="92" cy="{45 - kick_amplitude/2 + sym_offset}" rx="6" ry="3" fill="{color}" transform="rotate(-20, 92, {45 - kick_amplitude/2 + sym_offset})"/>
        </g>
        <g filter="url(#glow4)" opacity="0.7">
            <line x1="55" y1="50" x2="90" y2="{50 + kick_amplitude/2 - sym_offset}" stroke="{color}" stroke-width="10" stroke-linecap="round"/>
            <ellipse cx="92" cy="{50 + kick_amplitude/2 - sym_offset}" rx="6" ry="3" fill="{color}" transform="rotate(20, 92, {50 + kick_amplitude/2 - sym_offset})"/>
        </g>
        <text x="75" y="130" fill="#64748b" font-size="8">depth: {depth:.2f}</text>
        <text x="10" y="130" fill="#64748b" font-size="8">sym: {symmetry:.1f}°</text>
    </svg>
    '''

def get_swim_metrics_html(metrics: dict) -> str:
    """Generate complete HTML for swim metrics visualization"""
    
    h_dev = metrics.get('horizontal_deviation', 0)
    v_drop = metrics.get('vertical_drop', 0)
    evf = metrics.get('evf_angle', 0)
    dropped_elbow_pct = metrics.get('dropped_elbow_pct', 0)
    roll = metrics.get('body_roll', 45)
    kick_d = metrics.get('kick_depth', 0.25)
    kick_s = metrics.get('kick_symmetry', 0)
    
    # Alignment now considers vertical drop as the primary issue
    h_class = get_viz_zone_class(v_drop, (0, 8), (0, 15))
    h_label = get_viz_zone_label(v_drop, (0, 8), (0, 15))
    h_color = get_viz_zone_color(v_drop, (0, 8), (0, 15))
    
    # EVF class considers dropped elbow percentage
    if dropped_elbow_pct > 50:
        evf_class = "bad"
        evf_label = "🚨 DROPPED"
        evf_color = "#ef4444"
    elif dropped_elbow_pct > 20:
        evf_class = "ok"
        evf_label = "⚠️ Dropping"
        evf_color = "#eab308"
    else:
        evf_class = get_viz_zone_class(evf, (0, 25), (0, 40))
        evf_label = get_viz_zone_label(evf, (0, 25), (0, 40))
        evf_color = get_viz_zone_color(evf, (0, 25), (0, 40))
    
    roll_class = get_viz_zone_class(roll, (35, 55), (25, 65))
    roll_label = get_viz_zone_label(roll, (35, 55), (25, 65))
    roll_color = get_viz_zone_color(roll, (35, 55), (25, 65))
    
    kick_class = get_viz_zone_class(kick_d, (0.15, 0.35), (0.10, 0.45))
    kick_label = get_viz_zone_label(kick_d, (0.15, 0.35), (0.10, 0.45))
    kick_color = get_viz_zone_color(kick_d, (0.15, 0.35), (0.10, 0.45))
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: transparent;
                color: white;
                padding: 10px;
            }}
            .metrics-grid {{
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 16px;
            }}
            .metric-card {{
                background: rgba(30, 41, 59, 0.9);
                border-radius: 16px;
                padding: 16px;
                border: 1px solid rgba(100, 116, 139, 0.3);
            }}
            .metric-card.good {{ border-left: 4px solid #22c55e; }}
            .metric-card.ok {{ border-left: 4px solid #eab308; }}
            .metric-card.bad {{ border-left: 4px solid #ef4444; }}
            .metric-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 12px;
            }}
            .metric-title {{
                font-size: 13px;
                font-weight: 600;
                color: #94a3b8;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            .metric-badge {{
                padding: 3px 8px;
                border-radius: 12px;
                font-size: 10px;
                font-weight: 600;
            }}
            .metric-badge.good {{ background: rgba(34, 197, 94, 0.2); color: #22c55e; }}
            .metric-badge.ok {{ background: rgba(234, 179, 8, 0.2); color: #eab308; }}
            .metric-badge.bad {{ background: rgba(239, 68, 68, 0.2); color: #ef4444; }}
            .metric-content {{
                display: flex;
                gap: 16px;
                align-items: center;
            }}
            .silhouette-container {{
                width: 80px;
                height: 110px;
                flex-shrink: 0;
            }}
            .metric-details {{ flex: 1; }}
            .metric-value {{
                font-size: 28px;
                font-weight: 700;
                line-height: 1;
                margin-bottom: 4px;
            }}
            .metric-value.good {{ color: #22c55e; }}
            .metric-value.ok {{ color: #eab308; }}
            .metric-value.bad {{ color: #ef4444; }}
            .metric-unit {{
                font-size: 14px;
                color: #64748b;
                font-weight: 400;
            }}
            .range-bar {{
                height: 6px;
                background: #334155;
                border-radius: 3px;
                margin: 12px 0 6px 0;
                position: relative;
                overflow: hidden;
            }}
            .range-zone {{
                position: absolute;
                height: 100%;
                border-radius: 3px;
            }}
            .range-zone.ok-zone {{ background: rgba(234, 179, 8, 0.3); }}
            .range-zone.good-zone {{ background: rgba(34, 197, 94, 0.5); }}
            .range-indicator {{
                position: absolute;
                top: -3px;
                width: 12px;
                height: 12px;
                border-radius: 50%;
                transform: translateX(-50%);
                border: 2px solid white;
                box-shadow: 0 2px 6px rgba(0,0,0,0.3);
            }}
            .range-labels {{
                display: flex;
                justify-content: space-between;
                font-size: 9px;
                color: #64748b;
            }}
            .range-labels .warn {{ color: #f59e0b; }}
        </style>
    </head>
    <body>
        <div class="metrics-grid">
            <!-- Body Alignment -->
            <div class="metric-card {h_class}">
                <div class="metric-header">
                    <span class="metric-title">Body Alignment</span>
                    <span class="metric-badge {h_class}">{h_label}</span>
                </div>
                <div class="metric-content">
                    <div class="silhouette-container">{get_alignment_silhouette(v_drop)}</div>
                    <div class="metric-details">
                        <div class="metric-value {h_class}">{v_drop:.1f}<span class="metric-unit">°</span></div>
                        <div style="font-size: 10px; color: #64748b; margin-bottom: 6px;">Vertical drop (hip sink)</div>
                        <div class="range-bar">
                            <div class="range-zone ok-zone" style="left: 0%; width: 60%;"></div>
                            <div class="range-zone good-zone" style="left: 0%; width: 32%;"></div>
                            <div class="range-indicator" style="left: {min(100, v_drop / 25 * 100):.1f}%; background: {h_color};"></div>
                        </div>
                        <div class="range-labels">
                            <span>Streamlined</span>
                            <span class="warn">Sinking →</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- EVF -->
            <div class="metric-card {evf_class}">
                <div class="metric-header">
                    <span class="metric-title">Early Vertical Forearm</span>
                    <span class="metric-badge {evf_class}">{evf_label}</span>
                </div>
                <div class="metric-content">
                    <div class="silhouette-container">{get_evf_silhouette(evf)}</div>
                    <div class="metric-details">
                        <div class="metric-value {evf_class}">{evf:.1f}<span class="metric-unit">°</span></div>
                        <div style="font-size: 10px; color: {'#ef4444' if dropped_elbow_pct > 30 else '#64748b'}; margin-bottom: 6px;">
                            {'🚨 ' if dropped_elbow_pct > 50 else ''}Dropped elbow: {dropped_elbow_pct:.0f}% of catch
                        </div>
                        <div class="range-bar">
                            <div class="range-zone ok-zone" style="left: 0%; width: 66%;"></div>
                            <div class="range-zone good-zone" style="left: 0%; width: 42%;"></div>
                            <div class="range-indicator" style="left: {min(100, evf / 60 * 100):.1f}%; background: {evf_color};"></div>
                        </div>
                        <div class="range-labels">
                            <span>High elbow</span>
                            <span class="warn">Dropped elbow →</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Body Roll -->
            <div class="metric-card {roll_class}">
                <div class="metric-header">
                    <span class="metric-title">Body Roll</span>
                    <span class="metric-badge {roll_class}">{roll_label}</span>
                </div>
                <div class="metric-content">
                    <div class="silhouette-container">{get_roll_silhouette(roll)}</div>
                    <div class="metric-details">
                        <div class="metric-value {roll_class}">{roll:.1f}<span class="metric-unit">°</span></div>
                        <div class="range-bar">
                            <div class="range-zone ok-zone" style="left: 31%; width: 50%;"></div>
                            <div class="range-zone good-zone" style="left: 44%; width: 25%;"></div>
                            <div class="range-indicator" style="left: {min(100, roll / 80 * 100):.1f}%; background: {roll_color};"></div>
                        </div>
                        <div class="range-labels">
                            <span class="warn">← Too flat</span>
                            <span class="warn">Over-rotation →</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Kick -->
            <div class="metric-card {kick_class}">
                <div class="metric-header">
                    <span class="metric-title">Kick Depth</span>
                    <span class="metric-badge {kick_class}">{kick_label}</span>
                </div>
                <div class="metric-content">
                    <div class="silhouette-container">{get_kick_silhouette(kick_d, kick_s)}</div>
                    <div class="metric-details">
                        <div class="metric-value {kick_class}">{kick_d:.2f}</div>
                        <div style="font-size: 11px; color: #64748b; margin-bottom: 8px;">Symmetry: {kick_s:.1f}°</div>
                        <div class="range-bar">
                            <div class="range-zone ok-zone" style="left: 17%; width: 58%;"></div>
                            <div class="range-zone good-zone" style="left: 25%; width: 33%;"></div>
                            <div class="range-indicator" style="left: {min(100, kick_d / 0.6 * 100):.1f}%; background: {kick_color};"></div>
                        </div>
                        <div class="range-labels">
                            <span class="warn">← Shallow</span>
                            <span class="warn">Too deep →</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return html

def render_swim_metrics_component(metrics: dict, height: int = 420):
    """Render swim metrics visualization in Streamlit"""
    html = get_swim_metrics_html(metrics)
    components.html(html, height=height, scrolling=False)

# ─────────────────────────────────────────────
# CONSTANTS & DEFAULTS - Updated thresholds
# ─────────────────────────────────────────────

DEFAULT_CONF_THRESHOLD = 0.5
DEFAULT_YAW_THRESHOLD = 0.15
MIN_BREATH_GAP_S = 1.0
MIN_BREATH_HOLD_FRAMES = 4

# Alignment thresholds
DEFAULT_HORIZONTAL_DEV_GOOD = (0, 8)   # degrees - shoulder-hip-ankle alignment
DEFAULT_HORIZONTAL_DEV_OK = (0, 15)

# Torso lean thresholds
DEFAULT_TORSO_GOOD = (4, 12)
DEFAULT_TORSO_OK   = (0, 18)

# EVF thresholds - now based on plane angle
DEFAULT_EVF_ANGLE_GOOD = (0, 25)   # degrees from vertical plane
DEFAULT_EVF_ANGLE_OK = (0, 40)

# Legacy forearm thresholds (for display compatibility)
DEFAULT_FOREARM_GOOD = (0, 35)
DEFAULT_FOREARM_OK   = (0, 60)

# Roll thresholds
DEFAULT_ROLL_GOOD = (35, 55)
DEFAULT_ROLL_OK   = (25, 65)

# Kick thresholds - now relative to hip-ankle span
DEFAULT_KICK_SYM_MAX_GOOD = 15
DEFAULT_KICK_DEPTH_GOOD = (0.15, 0.35)  # Relative to hip-ankle span
DEFAULT_KICK_DEPTH_OK = (0.10, 0.45)

# Breathing penalty during pull
BREATH_PULL_PENALTY = 15  # Points deducted for breathing during pull phase

# ─────────────────────────────────────────────
# DATA MODELS - Enhanced
# ─────────────────────────────────────────────

class SwimPhase(Enum):
    ENTRY = "Entry"
    PULL = "Pull"
    PUSH = "Push"
    RECOVERY = "Recovery"

class CameraView(Enum):
    SIDE = "Side View"
    FRONT = "Front View"
    TOP = "Top View"
    UNKNOWN = "Unknown"

class WaterPosition(Enum):
    UNDERWATER = "Underwater"
    ABOVE_WATER = "Above Water"
    MIXED = "Mixed/Waterline"
    UNKNOWN = "Unknown"

@dataclass
class VideoContext:
    """Detected video context for adaptive analysis"""
    camera_view: CameraView = CameraView.UNKNOWN
    water_position: WaterPosition = WaterPosition.UNKNOWN
    swimming_direction: str = "left_to_right"  # or "right_to_left"
    confidence: float = 0.0
    detection_frames: int = 0
    
    # Color analysis results
    avg_blue_ratio: float = 0.0
    has_lane_lines: bool = False
    has_splash: bool = False
    
    # Landmark visibility stats
    upper_body_visible_pct: float = 0.0
    lower_body_visible_pct: float = 0.0
    
    def get_available_metrics(self) -> List[str]:
        """Return list of metrics available for this view"""
        metrics = []
        
        if self.camera_view == CameraView.SIDE:
            if self.water_position == WaterPosition.UNDERWATER:
                metrics = ["evf", "body_alignment", "kick_depth", "stroke_phase", "torso_lean"]
            else:  # Above water
                metrics = ["recovery_arm", "breathing", "head_position", "stroke_rate"]
        
        elif self.camera_view == CameraView.FRONT:
            if self.water_position == WaterPosition.UNDERWATER:
                metrics = ["body_roll", "hand_entry_width", "kick_symmetry", "streamline"]
            else:
                metrics = ["entry_angle", "breathing_side", "catch_width"]
        
        elif self.camera_view == CameraView.TOP:
            metrics = ["body_roll", "stroke_symmetry", "kick_width", "streamline"]
        
        else:
            # Unknown - provide basic metrics
            metrics = ["body_roll", "stroke_rate", "breathing"]
        
        return metrics
    
    def get_description(self) -> str:
        """Get human-readable description of detected context"""
        return f"{self.camera_view.value} • {self.water_position.value}"

@dataclass
class AthleteProfile:
    height_cm: float
    discipline: str

@dataclass
class FrameMetrics:
    time_s: float
    elbow_angle: float
    knee_left: float
    knee_right: float
    kick_symmetry: float
    kick_depth_proxy: float  # Now relative to hip-ankle span
    symmetry_hips: float
    score: float
    body_roll: float
    torso_lean: float
    forearm_vertical: float
    phase: str
    breath_state: str
    confidence: float = 1.0
    # New metrics
    horizontal_deviation: float = 0.0  # Combined alignment score
    vertical_drop: float = 0.0         # Hip/leg sinking angle
    evf_plane_angle: float = 0.0       # EVF quality score
    is_dropped_elbow: bool = False     # True if elbow below wrist (bad!)
    evf_status: str = ""               # Descriptive EVF status
    alignment_status: str = ""         # Descriptive alignment status
    wrist_velocity_y: float = 0.0      # For phase detection
    alignment_score: float = 100.0     # Sub-score for alignment
    evf_score: float = 100.0           # Sub-score for EVF
    breathing_during_pull: bool = False
    # Glide metrics
    is_gliding: bool = False           # True if in glide phase
    glide_score: float = 100.0         # Quality of glide (streamline)
    arm_extension: float = 0.0         # How extended the lead arm is (0-1)

@dataclass
class SessionSummary:
    duration_s: float
    avg_score: float
    avg_body_roll: float
    max_body_roll: float
    stroke_rate: float
    breaths_per_min: float
    breath_left: int
    breath_right: int
    total_strokes: int
    avg_kick_symmetry: float
    avg_kick_depth: float
    kick_status: str
    avg_confidence: float
    best_frame_bytes: Optional[bytes] = None
    worst_frame_bytes: Optional[bytes] = None
    # New summary metrics
    avg_horizontal_deviation: float = 0.0
    avg_vertical_drop: float = 0.0      # Hip/leg sinking
    avg_evf_angle: float = 0.0
    dropped_elbow_frames: int = 0       # Count of frames with dropped elbow
    dropped_elbow_pct: float = 0.0      # Percentage of pull frames with dropped elbow
    avg_alignment_score: float = 100.0
    avg_evf_score: float = 100.0
    breaths_during_pull: int = 0
    total_breaths: int = 0
    diagnostics: List[str] = field(default_factory=list)
    # Video context
    video_context: Optional[VideoContext] = None
    available_metrics: Dict = field(default_factory=dict)
    # Glide metrics
    glide_ratio: float = 0.0           # Percentage of stroke cycle spent gliding
    avg_glide_score: float = 0.0       # Average quality of glide phases
    glide_frames: int = 0              # Number of frames in glide
    total_analyzed_frames: int = 0     # Total frames analyzed

# ─────────────────────────────────────────────
# HELPERS - Enhanced calculations
# ─────────────────────────────────────────────

def calculate_angle(a, b, c):
    """Calculate angle at point b given points a, b, c"""
    ba = np.array(a) - np.array(b)
    bc = np.array(c) - np.array(b)
    cosang = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-8)
    return np.degrees(np.arccos(np.clip(cosang, -1, 1)))

def compute_torso_lean(lm_pixel: Dict):
    """Compute torso lean angle from vertical"""
    mid_s = ((lm_pixel["left_shoulder"][0] + lm_pixel["right_shoulder"][0]) / 2,
             (lm_pixel["left_shoulder"][1] + lm_pixel["right_shoulder"][1]) / 2)
    mid_h = ((lm_pixel["left_hip"][0] + lm_pixel["right_hip"][0]) / 2,
             (lm_pixel["left_hip"][1] + lm_pixel["right_hip"][1]) / 2)
    dy = mid_s[1] - mid_h[1]
    dx = mid_s[0] - mid_h[0]
    return math.degrees(math.atan2(dy, dx))

def compute_forearm_vertical(lm_pixel: Dict):
    """Legacy forearm vertical calculation for display"""
    dx = lm_pixel["left_wrist"][0] - lm_pixel["left_elbow"][0]
    dy = lm_pixel["left_wrist"][1] - lm_pixel["left_elbow"][1]
    return abs(math.degrees(math.atan2(dx, -dy)))

def compute_horizontal_deviation(lm_pixel: Dict) -> Tuple[float, float, str]:
    """
    Calculate body alignment including VERTICAL sinking (not just lateral).
    
    Measures:
    1. Lateral deviation (snake swimming / hip sway)
    2. Vertical drop (hip/leg sinking below shoulders)
    
    Returns:
        - total_deviation: combined alignment score (lower is better)
        - vertical_drop: how much hips sink below shoulder line (in degrees)
        - status: descriptive status
    """
    # Get midpoints
    mid_shoulder = np.array([
        (lm_pixel["left_shoulder"][0] + lm_pixel["right_shoulder"][0]) / 2,
        (lm_pixel["left_shoulder"][1] + lm_pixel["right_shoulder"][1]) / 2
    ])
    mid_hip = np.array([
        (lm_pixel["left_hip"][0] + lm_pixel["right_hip"][0]) / 2,
        (lm_pixel["left_hip"][1] + lm_pixel["right_hip"][1]) / 2
    ])
    mid_ankle = np.array([
        (lm_pixel["left_ankle"][0] + lm_pixel["right_ankle"][0]) / 2,
        (lm_pixel["left_ankle"][1] + lm_pixel["right_ankle"][1]) / 2
    ])
    
    # Calculate body length for normalization
    body_length = np.linalg.norm(mid_ankle - mid_shoulder)
    if body_length < 10:
        return 0.0, 0.0, "No data"
    
    # 1. LATERAL DEVIATION (side-to-side snake swimming)
    ideal_line = mid_ankle - mid_shoulder
    ideal_len = np.linalg.norm(ideal_line)
    
    if ideal_len > 1:
        ideal_unit = ideal_line / ideal_len
        to_hip = mid_hip - mid_shoulder
        proj_len = np.dot(to_hip, ideal_unit)
        proj_point = mid_shoulder + proj_len * ideal_unit
        lateral_dev_pixels = np.linalg.norm(mid_hip - proj_point)
        lateral_deviation = math.degrees(math.atan2(lateral_dev_pixels, body_length / 2))
    else:
        lateral_deviation = 0.0
    
    # 2. VERTICAL DROP (hips/legs sinking - critical for drag!)
    # In a streamlined position, shoulder-hip-ankle should be roughly horizontal
    # In image coordinates: higher Y = lower in water (sinking)
    
    # Calculate angle from horizontal: how much are legs/hips dropping?
    dx = mid_ankle[0] - mid_shoulder[0]
    dy = mid_ankle[1] - mid_shoulder[1]  # Positive = ankles below shoulders (sinking)
    
    # Body angle from horizontal (0° = flat, positive = feet sinking)
    body_angle_from_horizontal = math.degrees(math.atan2(dy, abs(dx) + 0.001))
    
    # Also check hip drop specifically
    hip_dx = mid_hip[0] - mid_shoulder[0]
    hip_dy = mid_hip[1] - mid_shoulder[1]
    hip_drop_angle = math.degrees(math.atan2(hip_dy, abs(hip_dx) + 0.001))
    
    # Vertical drop is the max of body angle and hip drop (only count sinking, not rising)
    vertical_drop = max(0, body_angle_from_horizontal, hip_drop_angle)
    
    # Combined deviation score
    total_deviation = lateral_deviation + vertical_drop
    
    # Status determination
    if vertical_drop > 15:
        status = "Sinking hips/legs"
    elif vertical_drop > 8:
        status = "Slight hip drop"
    elif lateral_deviation > 10:
        status = "Snake swimming"
    elif total_deviation <= 8:
        status = "Good alignment"
    else:
        status = "OK alignment"
    
    return total_deviation, vertical_drop, status

def compute_evf_plane_angle(lm_pixel: Dict) -> Tuple[float, bool, str]:
    """
    Calculate Early Vertical Forearm quality.
    
    Good EVF requires:
    1. Forearm near vertical (pointing down)
    2. Elbow HIGHER than wrist (high elbow catch) - CRITICAL!
    3. Elbow staying near surface while hand reaches deep
    
    Returns:
        - effective_angle: EVF quality score (lower is better, includes penalties)
        - is_dropped_elbow: True if elbow is below wrist (bad technique!)
        - evf_status: descriptive status string
    """
    # Use the arm that's more likely in the pull phase (lower wrist = catching water)
    left_wrist_y = lm_pixel["left_wrist"][1]
    right_wrist_y = lm_pixel["right_wrist"][1]
    
    if left_wrist_y > right_wrist_y:
        shoulder = np.array(lm_pixel["left_shoulder"])
        elbow = np.array(lm_pixel["left_elbow"])
        wrist = np.array(lm_pixel["left_wrist"])
    else:
        shoulder = np.array(lm_pixel["right_shoulder"])
        elbow = np.array(lm_pixel["right_elbow"])
        wrist = np.array(lm_pixel["right_wrist"])
    
    # === CHECK 1: Is elbow HIGHER than wrist? ===
    # In image coordinates: lower Y value = higher position in frame
    # For good EVF, elbow.y should be LESS than wrist.y (elbow above wrist)
    elbow_wrist_diff = wrist[1] - elbow[1]  # Positive = good (wrist below elbow)
    elbow_above_wrist = elbow_wrist_diff > 10  # Need meaningful difference
    
    # === CHECK 2: Forearm angle from vertical ===
    forearm = wrist - elbow
    vertical = np.array([0, 1])  # Down in image coordinates
    
    forearm_len = np.linalg.norm(forearm)
    if forearm_len < 1:
        return 0.0, False, "No data"
    
    cos_angle = np.dot(forearm, vertical) / forearm_len
    forearm_angle = math.degrees(math.acos(np.clip(cos_angle, -1, 1)))
    
    # === CHECK 3: Elbow drop relative to shoulder ===
    # Elbow shouldn't drop too far below shoulder during catch
    elbow_drop_from_shoulder = elbow[1] - shoulder[1]  # Positive = elbow below shoulder
    excessive_elbow_drop = elbow_drop_from_shoulder > 80  # Threshold in pixels
    
    # === DETERMINE EVF QUALITY ===
    is_dropped_elbow = not elbow_above_wrist or excessive_elbow_drop
    
    if is_dropped_elbow:
        evf_status = "DROPPED ELBOW"
        # Heavy penalty - this is the main technique flaw you identified
        effective_angle = forearm_angle + 35
    elif forearm_angle <= 20 and elbow_above_wrist:
        evf_status = "Excellent EVF"
        effective_angle = forearm_angle
    elif forearm_angle <= 30:
        evf_status = "Good EVF"
        effective_angle = forearm_angle
    elif forearm_angle <= 45:
        evf_status = "OK EVF"
        effective_angle = forearm_angle
    else:
        evf_status = "Sweeping (no catch)"
        effective_angle = forearm_angle + 10  # Small penalty for sweep
    
    return effective_angle, is_dropped_elbow, evf_status

def compute_kick_depth_relative(lm_pixel: Dict):
    """
    NEW: Calculate kick depth relative to hip-ankle span
    This normalizes for body size and camera angle
    """
    # Hip-ankle span (body length reference)
    hip_y = (lm_pixel["left_hip"][1] + lm_pixel["right_hip"][1]) / 2
    ankle_y = (lm_pixel["left_ankle"][1] + lm_pixel["right_ankle"][1]) / 2
    hip_ankle_span = abs(ankle_y - hip_y)
    
    if hip_ankle_span < 10:  # Avoid division by zero
        return 0.0
    
    # Knee deviation from hip-ankle line
    knee_l_y = lm_pixel["left_knee"][1]
    knee_r_y = lm_pixel["right_knee"][1]
    
    # Expected knee position if legs were straight (midpoint of hip-ankle)
    expected_knee_y = (hip_y + ankle_y) / 2
    
    # Kick depth is the deviation of knees from this expected position
    left_dev = abs(knee_l_y - expected_knee_y)
    right_dev = abs(knee_r_y - expected_knee_y)
    
    # Average deviation normalized by hip-ankle span
    kick_depth = (left_dev + right_dev) / (2 * hip_ankle_span)
    
    return kick_depth

def detect_phase_enhanced(lm_pixel: Dict, elbow_angle: float, prev_wrist_y: Optional[float], fps: float):
    """
    NEW: Enhanced phase detection using elbow angle + wrist vertical velocity
    """
    wrist_y = min(lm_pixel["left_wrist"][1], lm_pixel["right_wrist"][1])
    shoulder_y = min(lm_pixel["left_shoulder"][1], lm_pixel["right_shoulder"][1])
    
    # Calculate wrist velocity if we have previous position
    wrist_velocity_y = 0.0
    if prev_wrist_y is not None:
        wrist_velocity_y = (wrist_y - prev_wrist_y) * fps  # pixels per second
    
    underwater = wrist_y > shoulder_y + 20
    
    # Phase detection logic
    if not underwater:
        phase = "Recovery"
    elif elbow_angle > 140:
        phase = "Entry"
    elif elbow_angle > 90:
        # Distinguish Pull from Push using wrist velocity
        if wrist_velocity_y > 50:  # Wrist moving down = Pull
            phase = "Pull"
        else:
            phase = "Pull"  # Default to Pull in this elbow range
    else:
        # Low elbow angle
        if wrist_velocity_y < -30:  # Wrist moving up = Push exit
            phase = "Push"
        else:
            phase = "Push"
    
    return phase, wrist_velocity_y, wrist_y

def compute_glide_metrics(lm_pixel: Dict, phase: str, elbow_angle: float, horizontal_dev: float) -> Tuple[bool, float, float]:
    """
    Compute glide metrics for freestyle swimming.
    
    GLIDE ASSESSMENT:
    ================
    Glide is the brief "catch-up" or extension phase where the lead arm is fully 
    extended forward while the other arm completes its stroke. Good glide:
    
    1. Maximizes distance per stroke (DPS)
    2. Reduces energy expenditure 
    3. Maintains streamlined position
    4. Allows momentary rest between strokes
    
    DETECTION CRITERIA:
    - Phase: Entry or early Pull (arm extended forward)
    - Lead arm fully extended (elbow angle > 150°)
    - Good body alignment (low horizontal deviation)
    - Streamlined position
    
    QUALITY FACTORS:
    - Arm extension: How straight is the lead arm (elbow angle)
    - Body alignment: Is the body streamlined during glide
    - Duration: Longer glide (within reason) = more efficient
    
    Returns:
        - is_gliding: Boolean, True if currently in glide phase
        - glide_score: 0-100, quality of the glide position
        - arm_extension: 0-1, how extended the lead arm is
    """
    
    # Get arm measurements
    # Find the lead arm (the one that's more extended/forward)
    left_elbow_angle = calculate_angle(
        lm_pixel["left_shoulder"], 
        lm_pixel["left_elbow"], 
        lm_pixel["left_wrist"]
    )
    right_elbow_angle = calculate_angle(
        lm_pixel["right_shoulder"], 
        lm_pixel["right_elbow"], 
        lm_pixel["right_wrist"]
    )
    
    # Lead arm is the one with higher elbow angle (more extended)
    lead_elbow_angle = max(left_elbow_angle, right_elbow_angle)
    
    # Calculate arm extension (0-1 scale)
    # 180° = fully extended = 1.0
    # 90° = bent = 0.0
    arm_extension = max(0, min(1, (lead_elbow_angle - 90) / 90))
    
    # Determine if in glide phase
    # Glide occurs during Entry phase or very early Pull when arm is extended
    is_gliding = False
    
    if phase in ("Entry", "Pull"):
        # Check if lead arm is sufficiently extended (>140°)
        if lead_elbow_angle > 140:
            # Check if body is reasonably streamlined
            if horizontal_dev < 15:  # Not too much body deviation
                is_gliding = True
    
    # Calculate glide quality score
    glide_score = 0.0
    
    if is_gliding:
        # Base score from arm extension (40 points max)
        extension_score = arm_extension * 40
        
        # Body alignment score (40 points max)
        # Lower deviation = higher score
        if horizontal_dev <= 5:
            alignment_score = 40
        elif horizontal_dev <= 10:
            alignment_score = 30
        elif horizontal_dev <= 15:
            alignment_score = 20
        else:
            alignment_score = 10
        
        # Elbow angle bonus (20 points max)
        # 170°+ = excellent extension
        if lead_elbow_angle >= 170:
            angle_bonus = 20
        elif lead_elbow_angle >= 160:
            angle_bonus = 15
        elif lead_elbow_angle >= 150:
            angle_bonus = 10
        else:
            angle_bonus = 5
        
        glide_score = extension_score + alignment_score + angle_bonus
    
    return is_gliding, glide_score, arm_extension

def get_zone_color(val, good, ok):
    """Return color based on value zone"""
    if good[0] <= val <= good[1]: 
        return (0, 180, 0)  # Green
    if ok[0] <= val <= ok[1]: 
        return (0, 220, 220)  # Yellow/Amber
    return (220, 0, 0)  # Red

def get_zone_status(val, good, ok):
    """Return status string based on value zone"""
    if good[0] <= val <= good[1]: 
        return "Good"
    if ok[0] <= val <= ok[1]: 
        return "OK"
    return "Needs Work"

def detect_local_minimum(arr, threshold=10):
    """Detect stroke based on elbow angle local minimum"""
    if len(arr) < 3: 
        return False
    mid = len(arr) // 2
    return arr[mid] < min(arr[:mid] + arr[mid+1:]) and (arr[mid] + threshold) <= min(arr[:mid] + arr[mid+1:])

# ─────────────────────────────────────────────
# VIDEO CONTEXT DETECTION
# ─────────────────────────────────────────────

class VideoContextDetector:
    """Analyzes video frames to detect camera angle and water position"""
    
    def __init__(self):
        self.frame_analyses = []
        self.detection_complete = False
        self.context = VideoContext()
        self.video_width = 0
        self.video_height = 0
        
    def analyze_frame(self, frame: np.ndarray, landmarks_pixel: Optional[Dict] = None) -> None:
        """Analyze a single frame for context detection"""
        if self.detection_complete:
            return
        
        # Store video dimensions from first frame
        if self.video_height == 0:
            self.video_height, self.video_width = frame.shape[:2]
            
        analysis = {
            'color': self._analyze_color(frame),
            'landmarks': self._analyze_landmarks(landmarks_pixel) if landmarks_pixel else None,
            'edges': self._detect_lane_lines(frame),
            'splash': self._detect_splash(frame)
        }
        self.frame_analyses.append(analysis)
        
        # After analyzing enough frames, make determination
        if len(self.frame_analyses) >= 30:
            self._finalize_detection()
    
    def _analyze_color(self, frame: np.ndarray) -> Dict:
        """Analyze color distribution for water detection"""
        h, w = frame.shape[:2]
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Blue/cyan detection
        lower_blue = np.array([85, 50, 50])
        upper_blue = np.array([130, 255, 255])
        blue_mask = cv2.inRange(hsv, lower_blue, upper_blue)
        blue_ratio = np.sum(blue_mask > 0) / (h * w)
        
        # White/bright detection (splash/surface indicator)
        lower_white = np.array([0, 0, 200])
        upper_white = np.array([180, 30, 255])
        white_mask = cv2.inRange(hsv, lower_white, upper_white)
        white_ratio = np.sum(white_mask > 0) / (h * w)
        
        # Split frame into thirds for regional analysis
        top_third = hsv[:h//3, :]
        middle_third = hsv[h//3:2*h//3, :]
        bottom_third = hsv[2*h//3:, :]
        
        top_gray = gray[:h//3, :]
        bottom_gray = gray[2*h//3:, :]
        
        # Saturation analysis
        top_saturation = np.mean(top_third[:,:,1])
        bottom_saturation = np.mean(bottom_third[:,:,1])
        saturation_gradient = bottom_saturation - top_saturation
        
        # Brightness analysis
        top_brightness = np.mean(top_third[:,:,2])
        bottom_brightness = np.mean(bottom_third[:,:,2])
        brightness_gradient = top_brightness - bottom_brightness
        
        # Bright spots in top region
        bright_spots_top = cv2.inRange(top_third, np.array([0, 0, 180]), np.array([180, 60, 255]))
        bright_ratio_top = np.sum(bright_spots_top > 0) / (top_third.shape[0] * top_third.shape[1])
        
        # Sky detection
        sky_mask = cv2.inRange(top_third, np.array([90, 20, 150]), np.array([130, 100, 255]))
        sky_ratio = np.sum(sky_mask > 0) / (top_third.shape[0] * top_third.shape[1])
        
        # === HORIZONTAL LINE DETECTION ===
        edges = cv2.Canny(gray, 50, 150)
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=80, minLineLength=w//6, maxLineGap=20)
        horizontal_line_count = 0
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                angle = abs(math.degrees(math.atan2(y2-y1, x2-x1)))
                if angle < 15 or angle > 165:  # Near horizontal
                    horizontal_line_count += 1
        
        # === TEXTURE VARIANCE ===
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        texture_variance = laplacian.var()
        
        # === SKIN TONE DETECTION ===
        lower_skin = np.array([0, 20, 70])
        upper_skin = np.array([20, 150, 255])
        skin_mask = cv2.inRange(hsv, lower_skin, upper_skin)
        skin_ratio = np.sum(skin_mask > 0) / (h * w)
        
        # === COLOR VARIANCE ===
        b, g, r = cv2.split(frame)
        color_variance = np.std([np.mean(b), np.mean(g), np.mean(r)])
        
        # === NEW: UNDERWATER-SPECIFIC INDICATORS ===
        
        # 1. Surface ripples at TOP of frame (underwater looking up)
        # Underwater footage shows wavy surface distortion at top
        top_edges = cv2.Canny(top_gray, 30, 100)
        top_edge_density = np.sum(top_edges > 0) / (top_gray.shape[0] * top_gray.shape[1])
        
        # 2. Pool bottom detection (darker region at bottom with lane markings)
        # Pool bottom is typically darker and has distinct lane lines
        bottom_edges = cv2.Canny(bottom_gray, 30, 100)
        bottom_edge_density = np.sum(bottom_edges > 0) / (bottom_gray.shape[0] * bottom_gray.shape[1])
        
        # 3. Detect if bottom is darker than top (underwater: pool bottom darker)
        # Above water: top (sky/ceiling) often darker or similar to water
        bottom_brightness_val = np.mean(bottom_gray)
        top_brightness_val = np.mean(top_gray)
        bottom_darker = bottom_brightness_val < top_brightness_val - 10
        
        # 4. Check for uniform blue saturation (underwater indicator)
        sat_uniformity = 1.0 - (abs(top_saturation - bottom_saturation) / max(top_saturation, bottom_saturation, 1))
        
        # 5. Detect vertical/diagonal lines in bottom (pool floor T-marks)
        bottom_lines = cv2.HoughLinesP(bottom_edges, 1, np.pi/180, threshold=30, minLineLength=h//10, maxLineGap=10)
        vertical_lines_bottom = 0
        if bottom_lines is not None:
            for line in bottom_lines:
                x1, y1, x2, y2 = line[0]
                angle = abs(math.degrees(math.atan2(y2-y1, x2-x1)))
                if 70 < angle < 110:  # Near vertical
                    vertical_lines_bottom += 1
        
        # 6. Check for wavy distortion pattern at top (water surface from below)
        # High frequency variations in the top region indicate looking up at surface
        top_laplacian = cv2.Laplacian(top_gray, cv2.CV_64F)
        top_texture = top_laplacian.var()
        
        # 7. Lane rope appearance: from above = crisp horizontal lines
        # From below = blurry, distorted by water
        # Check sharpness of detected lines
        
        return {
            'blue_ratio': blue_ratio,
            'white_ratio': white_ratio,
            'sky_ratio': sky_ratio,
            'avg_brightness': np.mean(frame),
            'saturation_gradient': saturation_gradient,
            'brightness_gradient': brightness_gradient,
            'bright_ratio_top': bright_ratio_top,
            'top_saturation': top_saturation,
            'bottom_saturation': bottom_saturation,
            # Above-water indicators
            'horizontal_lines': horizontal_line_count,
            'texture_variance': texture_variance,
            'skin_ratio': skin_ratio,
            'color_variance': color_variance,
            # Underwater indicators
            'top_edge_density': top_edge_density,
            'bottom_edge_density': bottom_edge_density,
            'bottom_darker': bottom_darker,
            'sat_uniformity': sat_uniformity,
            'vertical_lines_bottom': vertical_lines_bottom,
            'top_texture': top_texture,
        }
    
    def _analyze_landmarks(self, lm_pixel: Dict) -> Dict:
        """Analyze landmark positions for camera angle detection"""
        if not lm_pixel:
            return None
        
        # Calculate distances for view detection
        try:
            # Shoulder width (X distance)
            shoulder_width = abs(lm_pixel["left_shoulder"][0] - lm_pixel["right_shoulder"][0])
            
            # Shoulder-hip depth (Y distance in side view, minimal in front view)
            shoulder_y = (lm_pixel["left_shoulder"][1] + lm_pixel["right_shoulder"][1]) / 2
            hip_y = (lm_pixel["left_hip"][1] + lm_pixel["right_hip"][1]) / 2
            torso_height = abs(hip_y - shoulder_y)
            
            # Hip width
            hip_width = abs(lm_pixel["left_hip"][0] - lm_pixel["right_hip"][0])
            
            # Check visibility of different body parts
            # Upper body: shoulders, elbows, wrists
            # Lower body: hips, knees, ankles
            
            return {
                'shoulder_width': shoulder_width,
                'torso_height': torso_height,
                'hip_width': hip_width,
                'width_to_height_ratio': shoulder_width / (torso_height + 1),
                'hip_to_shoulder_ratio': hip_width / (shoulder_width + 1)
            }
        except:
            return None
    
    def _detect_lane_lines(self, frame: np.ndarray) -> bool:
        """Detect pool lane lines (indicates underwater pool view)"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        
        # Look for horizontal lines (lane lines on pool bottom)
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=100, 
                                 minLineLength=100, maxLineGap=10)
        
        if lines is None:
            return False
        
        horizontal_lines = 0
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = abs(math.atan2(y2-y1, x2-x1) * 180 / np.pi)
            if angle < 15 or angle > 165:  # Near horizontal
                horizontal_lines += 1
        
        return horizontal_lines >= 2
    
    def _detect_splash(self, frame: np.ndarray) -> float:
        """Detect splash/turbulence (indicates surface/above water)"""
        # Splash appears as high-frequency white regions
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # High contrast areas
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        variance = laplacian.var()
        
        # White bubble detection
        _, white_thresh = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY)
        white_ratio = np.sum(white_thresh > 0) / (frame.shape[0] * frame.shape[1])
        
        return variance * white_ratio
    
    def _finalize_detection(self) -> None:
        """Make final determination based on collected analyses"""
        if not self.frame_analyses:
            return
        
        # Aggregate all metrics
        avg_blue = np.mean([a['color']['blue_ratio'] for a in self.frame_analyses])
        avg_white = np.mean([a['color']['white_ratio'] for a in self.frame_analyses])
        has_pool_bottom_lanes = sum([1 for a in self.frame_analyses if a['edges']]) > len(self.frame_analyses) * 0.3
        avg_splash = np.mean([a['splash'] for a in self.frame_analyses])
        
        # Regional analysis
        avg_top_sat = np.mean([a['color']['top_saturation'] for a in self.frame_analyses])
        avg_bottom_sat = np.mean([a['color']['bottom_saturation'] for a in self.frame_analyses])
        avg_bright_gradient = np.mean([a['color']['brightness_gradient'] for a in self.frame_analyses])
        
        # Above-water indicators
        avg_horizontal_lines = np.mean([a['color'].get('horizontal_lines', 0) for a in self.frame_analyses])
        avg_texture = np.mean([a['color'].get('texture_variance', 0) for a in self.frame_analyses])
        avg_color_variance = np.mean([a['color'].get('color_variance', 0) for a in self.frame_analyses])
        
        # Underwater indicators
        avg_top_edge_density = np.mean([a['color'].get('top_edge_density', 0) for a in self.frame_analyses])
        avg_bottom_edge_density = np.mean([a['color'].get('bottom_edge_density', 0) for a in self.frame_analyses])
        bottom_darker_pct = np.mean([1 if a['color'].get('bottom_darker', False) else 0 for a in self.frame_analyses])
        avg_sat_uniformity = np.mean([a['color'].get('sat_uniformity', 0) for a in self.frame_analyses])
        avg_vertical_lines_bottom = np.mean([a['color'].get('vertical_lines_bottom', 0) for a in self.frame_analyses])
        avg_top_texture = np.mean([a['color'].get('top_texture', 0) for a in self.frame_analyses])
        
        # === BALANCED SCORING SYSTEM ===
        above_water_score = 0
        underwater_score = 0
        
        # ==========================================
        # ABOVE-WATER INDICATORS
        # ==========================================
        
        # 1. Many horizontal lines from floating lane ropes (seen from above)
        # Above-water typically has 50+ crisp horizontal lines
        if avg_horizontal_lines > 50:
            above_water_score += 4
        elif avg_horizontal_lines > 35:
            above_water_score += 3
        elif avg_horizontal_lines > 20:
            above_water_score += 1
        # Few horizontal lines suggests underwater
        elif avg_horizontal_lines < 15:
            underwater_score += 2
        
        # 2. High overall texture (surface ripples from above)
        if avg_texture > 90:
            above_water_score += 3
        elif avg_texture > 70:
            above_water_score += 2
        # Low texture suggests underwater (more uniform)
        elif avg_texture < 50:
            underwater_score += 2
        elif avg_texture < 70:
            underwater_score += 1
        
        # 3. Top brighter than bottom (sky/ceiling above)
        if avg_bright_gradient > 10:
            above_water_score += 2
        elif avg_bright_gradient > 0:
            above_water_score += 1
        
        # 4. White/splash ratio
        if avg_white > 0.02:
            above_water_score += 1
        
        # ==========================================
        # UNDERWATER INDICATORS
        # ==========================================
        
        # 5. Bottom darker than top (pool floor is darker)
        if bottom_darker_pct > 0.6:
            underwater_score += 3
        elif bottom_darker_pct > 0.3:
            underwater_score += 2
        
        # 6. High saturation uniformity (underwater is uniformly blue)
        if avg_sat_uniformity > 0.92:
            underwater_score += 3
        elif avg_sat_uniformity > 0.85:
            underwater_score += 2
        elif avg_sat_uniformity > 0.75:
            underwater_score += 1
        # Low uniformity suggests above water (different regions)
        elif avg_sat_uniformity < 0.7:
            above_water_score += 1
        
        # 7. Vertical lines at bottom (pool floor T-marks)
        if avg_vertical_lines_bottom > 3:
            underwater_score += 2
        elif avg_vertical_lines_bottom > 1:
            underwater_score += 1
        
        # 8. Edge density patterns
        # Underwater: more edges at top (wavy surface) or bottom (pool floor)
        # Above water: edges more distributed
        if avg_top_edge_density > 0.08 and avg_bottom_edge_density > 0.06:
            underwater_score += 1
        
        # 9. Pool bottom lane lines detected by edge detector
        if has_pool_bottom_lanes and avg_horizontal_lines < 30:
            underwater_score += 2
        
        # 10. Color variance - underwater has moderate to low variance
        if avg_color_variance < 30:
            underwater_score += 2
        elif avg_color_variance < 45:
            underwater_score += 1
        elif avg_color_variance > 60:
            above_water_score += 1
        
        # 11. High blue ratio with uniform saturation = underwater
        if avg_blue > 0.8 and avg_sat_uniformity > 0.85:
            underwater_score += 2
        
        # ==========================================
        # FINAL DETERMINATION
        # ==========================================
        
        # Calculate difference
        score_diff = above_water_score - underwater_score
        
        if score_diff >= 3:
            self.context.water_position = WaterPosition.ABOVE_WATER
            water_confidence = min(0.95, 0.6 + score_diff * 0.05)
        elif score_diff <= -3:
            self.context.water_position = WaterPosition.UNDERWATER
            water_confidence = min(0.95, 0.6 + abs(score_diff) * 0.05)
        elif score_diff > 0:
            self.context.water_position = WaterPosition.ABOVE_WATER
            water_confidence = 0.55 + score_diff * 0.05
        elif score_diff < 0:
            self.context.water_position = WaterPosition.UNDERWATER
            water_confidence = 0.55 + abs(score_diff) * 0.05
        else:
            # Tie - use aspect ratio as tiebreaker
            # Underwater footage tends to be more square, above-water more wide
            aspect_ratio = self.video_width / self.video_height if self.video_height > 0 else 1.0
            if aspect_ratio > 1.6:
                self.context.water_position = WaterPosition.ABOVE_WATER
                water_confidence = 0.55
            else:
                self.context.water_position = WaterPosition.UNDERWATER
                water_confidence = 0.55
        
        # === CAMERA VIEW DETECTION ===
        # Use multiple signals: video aspect ratio, landmark geometry, body orientation
        
        # Signal 1: Video aspect ratio (very reliable!)
        # Side view swimming videos are typically very wide (3:1 to 5:1 ratio)
        # Front view videos are more square or portrait
        video_aspect_ratio = self.video_width / self.video_height if hasattr(self, 'video_height') and self.video_height > 0 else 1.0
        
        side_view_score = 0
        front_view_score = 0
        top_view_score = 0
        
        # Wide video strongly suggests side view
        if video_aspect_ratio > 3.0:
            side_view_score += 3
        elif video_aspect_ratio > 2.0:
            side_view_score += 2
        elif video_aspect_ratio < 1.0:  # Portrait
            front_view_score += 2
        
        # Signal 2: Landmark geometry (if available)
        landmark_analyses = [a['landmarks'] for a in self.frame_analyses if a['landmarks']]
        
        if landmark_analyses:
            avg_width_height = np.mean([l['width_to_height_ratio'] for l in landmark_analyses])
            avg_hip_shoulder = np.mean([l['hip_to_shoulder_ratio'] for l in landmark_analyses])
            
            # For side view: shoulders appear stacked (small X diff)
            # But torso height varies based on body angle
            if avg_width_height < 0.5:
                side_view_score += 2
            elif avg_width_height > 3.0 and avg_hip_shoulder > 0.8:
                front_view_score += 2
            elif avg_width_height > 3.0:
                # High ratio could be side view with horizontal body OR top view
                # Use video aspect ratio to disambiguate
                if video_aspect_ratio > 2.5:
                    side_view_score += 1  # Wide video = probably side view
                else:
                    top_view_score += 1
        
        # Signal 3: Above water typically means side view (most common filming angle)
        if self.context.water_position == WaterPosition.ABOVE_WATER:
            side_view_score += 1  # Slight bias toward side view for above-water
        
        # Determine camera view
        max_score = max(side_view_score, front_view_score, top_view_score)
        
        if side_view_score == max_score:
            self.context.camera_view = CameraView.SIDE
            view_confidence = min(0.9, 0.4 + side_view_score * 0.1)
        elif front_view_score == max_score:
            self.context.camera_view = CameraView.FRONT
            view_confidence = min(0.85, 0.4 + front_view_score * 0.1)
        else:
            self.context.camera_view = CameraView.TOP
            view_confidence = min(0.7, 0.4 + top_view_score * 0.1)
        
        # Set overall confidence
        self.context.confidence = (water_confidence + view_confidence) / 2
        self.context.avg_blue_ratio = avg_blue
        self.context.has_lane_lines = has_pool_bottom_lanes
        self.context.has_splash = avg_splash > 300
        self.context.detection_frames = len(self.frame_analyses)
        
        self.detection_complete = True
    
    def get_context(self) -> VideoContext:
        """Get the detected video context"""
        if not self.detection_complete and self.frame_analyses:
            self._finalize_detection()
        return self.context
    
    def force_context(self, camera_view: CameraView, water_position: WaterPosition) -> None:
        """Manually override detected context"""
        self.context.camera_view = camera_view
        self.context.water_position = water_position
        self.context.confidence = 1.0  # Manual = 100% confidence
        self.detection_complete = True


def get_metrics_for_context(context: VideoContext) -> Dict:
    """Return metric configurations based on video context"""
    
    base_metrics = {
        'stroke_rate': True,
        'breathing': True,
    }
    
    if context.camera_view == CameraView.SIDE:
        if context.water_position == WaterPosition.UNDERWATER:
            return {
                **base_metrics,
                'evf': True,
                'body_alignment': True,
                'vertical_drop': True,
                'kick_depth': True,
                'stroke_phase': True,
                'torso_lean': True,
                'dropped_elbow': True,
                # Not available in this view
                'body_roll': False,  # Need front view for accurate roll
                'hand_entry_width': False,
            }
        else:  # Above water
            return {
                **base_metrics,
                'recovery_arm': True,
                'head_position': True,
                'breathing_timing': True,
                # Limited underwater metrics
                'evf': False,
                'body_alignment': False,
                'kick_depth': False,
            }
    
    elif context.camera_view == CameraView.FRONT:
        if context.water_position == WaterPosition.UNDERWATER:
            return {
                **base_metrics,
                'body_roll': True,
                'hand_entry_width': True,
                'kick_symmetry': True,
                'streamline': True,
                # Not available in front view
                'evf': False,
                'body_alignment': False,
            }
        else:
            return {
                **base_metrics,
                'entry_angle': True,
                'breathing_side': True,
                'catch_width': True,
            }
    
    elif context.camera_view == CameraView.TOP:
        return {
            **base_metrics,
            'body_roll': True,
            'stroke_symmetry': True,
            'kick_width': True,
        }
    
    # Unknown - provide basic metrics only
    return base_metrics

# ─────────────────────────────────────────────
# VISUAL PANELS - Enhanced
# ─────────────────────────────────────────────

def draw_simplified_silhouette(frame, x, y, color=(180,180,180), th=3):
    """Draw a simple stick figure silhouette"""
    cv2.circle(frame, (x, y-50), 18, color, th)
    cv2.line(frame, (x, y-32), (x, y+70), color, th+2)
    cv2.line(frame, (x, y-10), (x-45, y+30), color, th)
    cv2.line(frame, (x, y-10), (x+45, y+30), color, th)
    cv2.line(frame, (x, y+70), (x-35, y+130), color, th)
    cv2.line(frame, (x, y+70), (x+35, y+130), color, th)

def draw_technique_panel_enhanced(frame, origin_x, title, metrics_dict, phase, is_ideal=False, breath_side='N'):
    """
    Enhanced technique panel with separate alignment and EVF indicators
    (Silhouette removed for cleaner video output)
    """
    h, w = frame.shape[:2]
    px, py = origin_x - 160, 30
    pw, ph = 320, 380  # Reduced height since silhouette removed
    
    # Semi-transparent background
    ov = frame.copy()
    cv2.rectangle(ov, (px, py), (px+pw, py+ph), (0,0,0), -1)
    cv2.addWeighted(ov, 0.65, frame, 0.35, 0, frame)

    # Title
    cv2.putText(frame, title.upper(), (px+10, py+30), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                (255,255,255) if not is_ideal else (200,200,255), 2)

    y_offset = py + 55
    
    # 1. Horizontal Alignment Score
    h_dev = metrics_dict.get('horizontal_deviation', 0)
    h_color = get_zone_color(h_dev, DEFAULT_HORIZONTAL_DEV_GOOD, DEFAULT_HORIZONTAL_DEV_OK)
    cv2.putText(frame, f"Alignment: {h_dev:.1f}°", (px+10, y_offset), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, h_color, 2)
    # Visual indicator bar
    bar_len = int(min(h_dev / 20, 1.0) * 100)
    cv2.rectangle(frame, (px+180, y_offset-12), (px+180+bar_len, y_offset-2), h_color, -1)
    y_offset += 30

    # 2. EVF Score (during Pull/Push phases)
    evf_angle = metrics_dict.get('evf_plane_angle', 0)
    if phase in ("Pull", "Push"):
        evf_color = get_zone_color(evf_angle, DEFAULT_EVF_ANGLE_GOOD, DEFAULT_EVF_ANGLE_OK)
        cv2.putText(frame, f"EVF Angle: {evf_angle:.1f}°", (px+10, y_offset), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, evf_color, 2)
        bar_len = int(min(evf_angle / 60, 1.0) * 100)
        cv2.rectangle(frame, (px+180, y_offset-12), (px+180+bar_len, y_offset-2), evf_color, -1)
    else:
        cv2.putText(frame, "EVF: n/a (Recovery)", (px+10, y_offset), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (128, 128, 128), 2)
    y_offset += 30

    # 3. Torso Lean
    torso = metrics_dict.get('torso_lean', 8)
    tc = get_zone_color(abs(torso), DEFAULT_TORSO_GOOD, DEFAULT_TORSO_OK)
    cv2.putText(frame, f"Torso Lean: {torso:.1f}°", (px+10, y_offset), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, tc, 2)
    # Visual torso line
    tlen = 60
    tdx = tlen * math.sin(math.radians(torso))
    tdy = tlen * math.cos(math.radians(torso))
    cv2.line(frame, (px+250, y_offset+20), (int(px+250+tdx), int(py+y_offset+20+tdy)), tc, 4)
    y_offset += 35

    # 4. Body Roll
    roll = metrics_dict.get('body_roll', 45)
    rc = get_zone_color(roll, DEFAULT_ROLL_GOOD, DEFAULT_ROLL_OK)
    cv2.putText(frame, f"Body Roll: {roll:.1f}°", (px+10, y_offset), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, rc, 2)
    # Visual roll indicator
    rdx = 50 * math.cos(math.radians(roll))
    rdy = 50 * math.sin(math.radians(roll))
    cv2.line(frame, (px+250, y_offset+10), (int(px+250+rdx), int(y_offset+10+rdy)), rc, 4)
    y_offset += 35

    # 5. Kick Depth (relative to hip-ankle span)
    kick_depth = metrics_dict.get('kick_depth', 0.25)
    kdc = get_zone_color(kick_depth, DEFAULT_KICK_DEPTH_GOOD, DEFAULT_KICK_DEPTH_OK)
    cv2.putText(frame, f"Kick Depth: {kick_depth:.2f}", (px+10, y_offset), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, kdc, 2)
    # Visual bar
    bar_len = int(min(kick_depth / 0.5, 1.0) * 100)
    cv2.rectangle(frame, (px+180, y_offset-12), (px+180+bar_len, y_offset-2), kdc, -1)
    y_offset += 35

    # 6. Kick Symmetry
    kick_sym = metrics_dict.get('kick_symmetry', 0)
    ksc = get_zone_color(kick_sym, (0, DEFAULT_KICK_SYM_MAX_GOOD), (0, 25))
    cv2.putText(frame, f"Kick Sym: {kick_sym:.1f}°", (px+10, y_offset), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, ksc, 2)
    y_offset += 35

    # 7. Phase indicator with color coding
    phase_colors = {
        "Entry": (59, 130, 246),    # Blue
        "Pull": (34, 197, 94),      # Green
        "Push": (245, 158, 11),     # Amber
        "Recovery": (107, 114, 128) # Gray
    }
    phase_color = phase_colors.get(phase, (200, 200, 200))
    cv2.putText(frame, f"Phase: {phase}", (px+10, y_offset), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, phase_color, 2)
    y_offset += 35

    # 8. Breathing indicator with warning if during pull
    breathing_during_pull = metrics_dict.get('breathing_during_pull', False)
    if breath_side != 'N':
        if breathing_during_pull:
            bcolor = (0, 0, 255)  # Red warning
            btxt = f"⚠ BREATH DURING PULL ({breath_side})"
        else:
            bcolor = (255,165,0) if breath_side == 'L' else (0,191,255)
            btxt = f"Breath: {'Left' if breath_side == 'L' else 'Right'}"
        cv2.putText(frame, btxt, (px+10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.55, bcolor, 2)
    else:
        cv2.putText(frame, "Breath: Neutral", (px+10, y_offset), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180,180,180), 2)
    y_offset += 35

    # Overall score at bottom
    score = metrics_dict.get('score', 0)
    score_color = (0, 255, 0) if score >= 70 else (0, 220, 220) if score >= 50 else (0, 0, 255)
    cv2.putText(frame, f"Score: {score:.0f}/100", (px+10, y_offset), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, score_color, 2)

    # Footer
    stxt = "IDEAL REFERENCE" if is_ideal else "YOUR STROKE"
    cv2.putText(frame, stxt, (px+10, py+ph-15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180,180,180), 1)

def draw_overlay_zones(frame, lm_pixel, horizontal_dev, evf_angle, phase):
    """
    Draw color-coded overlay zones on the swimmer
    Green = Good, Amber = OK, Red = Needs Work
    """
    h, w = frame.shape[:2]
    
    # Draw alignment line (shoulder-hip-ankle)
    mid_shoulder = (
        int((lm_pixel["left_shoulder"][0] + lm_pixel["right_shoulder"][0]) / 2),
        int((lm_pixel["left_shoulder"][1] + lm_pixel["right_shoulder"][1]) / 2)
    )
    mid_hip = (
        int((lm_pixel["left_hip"][0] + lm_pixel["right_hip"][0]) / 2),
        int((lm_pixel["left_hip"][1] + lm_pixel["right_hip"][1]) / 2)
    )
    mid_ankle = (
        int((lm_pixel["left_ankle"][0] + lm_pixel["right_ankle"][0]) / 2),
        int((lm_pixel["left_ankle"][1] + lm_pixel["right_ankle"][1]) / 2)
    )
    
    # Color based on alignment
    align_color = get_zone_color(horizontal_dev, DEFAULT_HORIZONTAL_DEV_GOOD, DEFAULT_HORIZONTAL_DEV_OK)
    # Draw body line
    cv2.line(frame, mid_shoulder, mid_hip, align_color, 3)
    cv2.line(frame, mid_hip, mid_ankle, align_color, 3)
    
    # Draw EVF indicator during pull/push
    if phase in ("Pull", "Push"):
        # Find the pulling arm (lower wrist)
        if lm_pixel["left_wrist"][1] > lm_pixel["right_wrist"][1]:
            elbow = (int(lm_pixel["left_elbow"][0]), int(lm_pixel["left_elbow"][1]))
            wrist = (int(lm_pixel["left_wrist"][0]), int(lm_pixel["left_wrist"][1]))
        else:
            elbow = (int(lm_pixel["right_elbow"][0]), int(lm_pixel["right_elbow"][1]))
            wrist = (int(lm_pixel["right_wrist"][0]), int(lm_pixel["right_wrist"][1]))
        
        evf_color = get_zone_color(evf_angle, DEFAULT_EVF_ANGLE_GOOD, DEFAULT_EVF_ANGLE_OK)
        cv2.line(frame, elbow, wrist, evf_color, 4)
        
        # Draw ideal vertical line from elbow for reference
        cv2.line(frame, elbow, (elbow[0], elbow[1] + 80), (100, 100, 100), 2, cv2.LINE_AA)

# ─────────────────────────────────────────────
# ANALYZER CLASS – Enhanced with new metrics
# ─────────────────────────────────────────────

class SwimAnalyzer:
    # Use LITE model for faster downloads and sufficient accuracy for swimming analysis
    # Heavy model: ~120MB, Lite model: ~8MB
    MODEL_URL_LITE = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task"
    MODEL_URL_HEAVY = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task"
    MODEL_FILENAME_LITE = "pose_landmarker_lite.task"
    MODEL_FILENAME_HEAVY = "pose_landmarker_heavy.task"
    
    # Default to lite for cloud deployment
    USE_LITE_MODEL = True

    def __init__(self, athlete: AthleteProfile, conf_thresh, yaw_thresh, 
                 manual_camera_view: Optional[CameraView] = None,
                 manual_water_position: Optional[WaterPosition] = None,
                 use_heavy_model: bool = False):
        self.athlete = athlete
        self.conf_thresh = conf_thresh
        self.yaw_thresh = yaw_thresh
        self.use_heavy_model = use_heavy_model

        self.landmarker = self._init_landmarker()
        
        # Video context detection
        self.context_detector = VideoContextDetector()
        self.video_context = VideoContext()
        self.available_metrics = {}
        
        # Manual override if provided
        if manual_camera_view and manual_water_position:
            self.context_detector.force_context(manual_camera_view, manual_water_position)
            self.video_context = self.context_detector.get_context()
            self.available_metrics = get_metrics_for_context(self.video_context)

        self.metrics: List[FrameMetrics] = []
        self.stroke_times = []
        self.breath_l = self.breath_r = 0
        self.breath_side = 'N'
        self.breath_persist = 0
        self.last_breath = -1000
        self.elbow_win = deque(maxlen=9)
        self.time_win = deque(maxlen=9)
        self.best_dev = float('inf')
        self.worst_dev = -float('inf')
        self.best_bytes = self.worst_bytes = None

        # Smoothing buffers
        self.torso_buffer = deque(maxlen=7)
        self.forearm_buffer = deque(maxlen=7)
        self.kick_depth_buffer = deque(maxlen=7)
        self.horizontal_dev_buffer = deque(maxlen=7)
        self.evf_buffer = deque(maxlen=7)
        self.vertical_drop_buffer = deque(maxlen=7)
        
        # Track last timestamp and wrist position
        self.last_timestamp_ms = -1
        self.prev_wrist_y = None
        
        # Breathing during pull tracking
        self.breaths_during_pull = 0
        
        # Dropped elbow tracking (only during Pull phase for catch analysis)
        self.dropped_elbow_frames = 0
        self.pull_phase_frames = 0
        
        # Glide tracking
        self.glide_frames = 0

    @st.cache_resource
    @staticmethod
    def _download_model(model_url: str, model_path: str, model_size: str):
        """Download model with caching to avoid repeated downloads"""
        if not os.path.exists(model_path):
            st.info(f"⏳ First run: Downloading MediaPipe Pose model ({model_size})...")
            try:
                urllib.request.urlretrieve(model_url, model_path)
                st.success("✅ Model downloaded successfully!")
            except Exception as e:
                st.error(f"Failed to download model: {e}")
                raise
        return model_path

    def _init_landmarker(self):
        if not MEDIAPIPE_TASKS_AVAILABLE:
            raise RuntimeError("MediaPipe Tasks not available")

        # Choose model based on setting
        if self.use_heavy_model:
            model_url = self.MODEL_URL_HEAVY
            model_filename = self.MODEL_FILENAME_HEAVY
            model_size = "~120 MB - may take a minute"
        else:
            model_url = self.MODEL_URL_LITE
            model_filename = self.MODEL_FILENAME_LITE
            model_size = "~8 MB"
        
        # Download with caching
        model_path = SwimAnalyzer._download_model(model_url, model_filename, model_size)

        base_options = python.BaseOptions(
            model_asset_path=model_path,
            delegate=python.BaseOptions.Delegate.CPU
        )
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            output_segmentation_masks=False
        )
        return vision.PoseLandmarker.create_from_options(options)

    def process(self, frame, t, timestamp_ms, fps=30.0):
        """
        Process a frame with pose detection.
        
        Args:
            frame: BGR image frame
            t: Real time in seconds (for metrics/stroke timing)
            timestamp_ms: Monotonically increasing timestamp in milliseconds for MediaPipe
            fps: Frames per second for velocity calculations
        """
        if self.landmarker is None:
            return frame, None

        # Ensure timestamp is strictly increasing
        if timestamp_ms <= self.last_timestamp_ms:
            timestamp_ms = self.last_timestamp_ms + 1
        self.last_timestamp_ms = timestamp_ms

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        result = self.landmarker.detect_for_video(mp_image, timestamp_ms)

        if not result.pose_landmarks:
            # Analyze frame for context detection (even without landmarks)
            if not self.context_detector.detection_complete:
                self.context_detector.analyze_frame(frame, None)
                # Check if detection just completed
                if self.context_detector.detection_complete:
                    self.video_context = self.context_detector.get_context()
                    self.available_metrics = get_metrics_for_context(self.video_context)
            return frame, None

        landmarks = result.pose_landmarks[0]
        h, w = frame.shape[:2]

        landmark_names = [
            "nose", "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
            "left_wrist", "right_wrist", "left_hip", "right_hip",
            "left_knee", "right_knee", "left_ankle", "right_ankle"
        ]
        indices = [0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]

        lm_pixel = {}
        vis_sum = 0.0
        vis_count = 0

        for name, idx in zip(landmark_names, indices):
            lm = landmarks[idx]
            lm_pixel[name] = (lm.x * w, lm.y * h)
            vis_sum += lm.visibility
            vis_count += 1

        conf = vis_sum / vis_count if vis_count > 0 else 0.0
        
        # === POSE VALIDATION ===
        # Reject false positives where MediaPipe detects pool lane markings as a person
        # A valid human pose should have:
        # 1. Reasonable body proportions (not too stretched or compressed)
        # 2. Shoulder width > 0 (not a single line)
        # 3. Body parts in realistic relative positions
        # 4. NOT be a pool floor marking (dark blue in bottom of frame)
        
        def validate_pose(lm_pixel, frame_bgr, frame_h, frame_w):
            """Validate that detected pose is actually a human, not a pool lane marking"""
            try:
                # Get key measurements
                left_shoulder = np.array(lm_pixel["left_shoulder"])
                right_shoulder = np.array(lm_pixel["right_shoulder"])
                left_hip = np.array(lm_pixel["left_hip"])
                right_hip = np.array(lm_pixel["right_hip"])
                nose = np.array(lm_pixel["nose"])
                left_ankle = np.array(lm_pixel["left_ankle"])
                right_ankle = np.array(lm_pixel["right_ankle"])
                
                # 1. Shoulder width should be reasonable (not near zero)
                shoulder_width = np.linalg.norm(left_shoulder - right_shoulder)
                min_shoulder_width = min(frame_w, frame_h) * 0.02  # At least 2% of frame
                if shoulder_width < min_shoulder_width:
                    return False, "shoulders too narrow"
                
                # 2. Hip width should be reasonable
                hip_width = np.linalg.norm(left_hip - right_hip)
                if hip_width < min_shoulder_width * 0.5:
                    return False, "hips too narrow"
                
                # 3. Torso length should be reasonable
                mid_shoulder = (left_shoulder + right_shoulder) / 2
                mid_hip = (left_hip + right_hip) / 2
                torso_length = np.linalg.norm(mid_shoulder - mid_hip)
                
                # Torso should be at least as long as shoulder width (roughly)
                if torso_length < shoulder_width * 0.3:
                    return False, "torso too short"
                
                # 4. Body shouldn't be extremely elongated (like a lane line)
                body_height = max(
                    np.linalg.norm(nose - mid_hip),
                    torso_length
                )
                body_width = max(shoulder_width, hip_width)
                
                aspect_ratio = body_height / (body_width + 1)
                if aspect_ratio > 15:
                    return False, "too elongated"
                
                # 5. Nose should be reasonably close to shoulders
                nose_to_shoulders = np.linalg.norm(nose - mid_shoulder)
                if nose_to_shoulders > torso_length * 3:
                    return False, "head too far from body"
                
                # 6. All key points should be within frame bounds
                margin = 0.1
                for name, (x, y) in lm_pixel.items():
                    if x < -frame_w * margin or x > frame_w * (1 + margin):
                        return False, f"{name} out of frame horizontally"
                    if y < -frame_h * margin or y > frame_h * (1 + margin):
                        return False, f"{name} out of frame vertically"
                
                # === POOL FLOOR MARKING DETECTION ===
                # Pool floor markings are:
                # - Located in bottom portion of frame (in above-water footage)
                # - Dark blue/teal colored (not skin tones)
                
                # 7. Check if all major body points are in bottom 60% of frame
                all_points = [nose, left_shoulder, right_shoulder, mid_hip, left_ankle, right_ankle]
                points_in_bottom = sum(1 for p in all_points if p[1] > frame_h * 0.4)
                
                if points_in_bottom >= 5:  # Most points in bottom portion
                    # Sample colors around the detected "body"
                    all_x = [p[0] for p in all_points]
                    all_y = [p[1] for p in all_points]
                    min_x = max(0, int(min(all_x)) - 10)
                    max_x = min(frame_w-1, int(max(all_x)) + 10)
                    min_y = max(0, int(min(all_y)) - 10)
                    max_y = min(frame_h-1, int(max(all_y)) + 10)
                    
                    if max_x > min_x + 20 and max_y > min_y + 20:
                        roi = frame_bgr[min_y:max_y, min_x:max_x]
                        
                        if roi.size > 100:
                            hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
                            
                            # Check for dark pool marking colors (dark blue/teal tiles)
                            lower_pool_mark = np.array([85, 30, 20])
                            upper_pool_mark = np.array([135, 255, 140])
                            pool_mark_mask = cv2.inRange(hsv_roi, lower_pool_mark, upper_pool_mark)
                            pool_mark_ratio = np.sum(pool_mark_mask > 0) / (roi.shape[0] * roi.shape[1])
                            
                            # Check for skin tones
                            lower_skin = np.array([0, 20, 70])
                            upper_skin = np.array([25, 150, 255])
                            skin_mask = cv2.inRange(hsv_roi, lower_skin, upper_skin)
                            skin_ratio = np.sum(skin_mask > 0) / (roi.shape[0] * roi.shape[1])
                            
                            # If mostly dark pool marking color and very little skin = reject
                            if pool_mark_ratio > 0.25 and skin_ratio < 0.08:
                                return False, "pool floor marking detected"
                            
                            # Check for cyan/teal water color (pool water around marking)
                            lower_water = np.array([80, 30, 100])
                            upper_water = np.array([110, 255, 255])
                            water_mask = cv2.inRange(hsv_roi, lower_water, upper_water)
                            water_ratio = np.sum(water_mask > 0) / (roi.shape[0] * roi.shape[1])
                            
                            # If very high water color + pool marking and no skin = floor marking
                            if (water_ratio + pool_mark_ratio) > 0.7 and skin_ratio < 0.05:
                                return False, "pool floor marking (water + marking colors)"
                
                # 8. Check minimum body size relative to frame
                body_area = body_width * body_height
                frame_area = frame_w * frame_h
                body_ratio = body_area / frame_area
                
                if body_ratio < 0.003:  # Less than 0.3% of frame = too small
                    return False, "detected body too small"
                
                return True, "valid"
                
            except Exception as e:
                return False, f"validation error: {e}"
        
        is_valid_pose, validation_reason = validate_pose(lm_pixel, frame, h, w)
        if not is_valid_pose:
            # Not a valid human pose - skip this frame
            return frame, None
        
        # Continue context detection with landmarks
        was_complete = self.context_detector.detection_complete
        if not was_complete:
            self.context_detector.analyze_frame(frame, lm_pixel)
            
            # Update context once detection completes
            if self.context_detector.detection_complete:
                self.video_context = self.context_detector.get_context()
                self.available_metrics = get_metrics_for_context(self.video_context)
        
        if conf < self.conf_thresh:
            return frame, None

        # Check for inverted video (upside-down footage)
        # CRITICAL FIX: Do NOT flip above-water footage!
        # Above-water footage perspective is always correct from the viewer's standpoint.
        # Only consider flipping for confirmed UNDERWATER footage where camera might be inverted.
        is_inverted = False
        
        # ONLY consider flipping if we have HIGH CONFIDENCE that this is underwater footage
        # AND the pose clearly indicates inversion
        is_confirmed_underwater = (
            self.context_detector.detection_complete and 
            self.video_context.water_position == WaterPosition.UNDERWATER and
            self.video_context.confidence > 0.7
        )
        
        if is_confirmed_underwater:
            # Get average positions
            avg_hip_y = (lm_pixel["left_hip"][1] + lm_pixel["right_hip"][1]) / 2
            avg_shoulder_y = (lm_pixel["left_shoulder"][1] + lm_pixel["right_shoulder"][1]) / 2
            
            # Calculate torso height for threshold
            torso_height = abs(avg_hip_y - avg_shoulder_y)
            
            # Only consider inverted if hips are VERY significantly above shoulders
            # (more than 50% of torso height, to be very conservative)
            hip_above_threshold = avg_shoulder_y - avg_hip_y > torso_height * 0.5
            
            # Additional check: nose should be well below shoulders in inverted footage
            nose_below_shoulders = False
            if "nose" in lm_pixel:
                nose_below_shoulders = lm_pixel["nose"][1] > avg_shoulder_y + torso_height * 0.3
            
            # Additional check: ankles should be above hips in inverted footage
            avg_ankle_y = (lm_pixel["left_ankle"][1] + lm_pixel["right_ankle"][1]) / 2
            ankles_above_hips = avg_ankle_y < avg_hip_y
            
            # Require ALL conditions for flipping
            is_inverted = hip_above_threshold and nose_below_shoulders and ankles_above_hips
        
        if is_inverted:
            frame = cv2.flip(frame, -1)
            try:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                
                self.last_timestamp_ms += 1
                result = self.landmarker.detect_for_video(mp_image, self.last_timestamp_ms)
                
                if result.pose_landmarks:
                    landmarks = result.pose_landmarks[0]
                    for name, idx in zip(landmark_names, indices):
                        lm = landmarks[idx]
                        lm_pixel[name] = (lm.x * w, lm.y * h)
                # If no landmarks after flip, continue with flipped coordinates
                # (just invert the Y coordinates of existing landmarks)
                else:
                    for name in lm_pixel:
                        x, y = lm_pixel[name]
                        lm_pixel[name] = (w - x, h - y)
            except Exception:
                # If re-detection fails, just use flipped coordinates
                for name in lm_pixel:
                    x, y = lm_pixel[name]
                    lm_pixel[name] = (w - x, h - y)

        # Calculate basic metrics
        elbow = min(
            calculate_angle(lm_pixel["left_shoulder"], lm_pixel["left_elbow"], lm_pixel["left_wrist"]),
            calculate_angle(lm_pixel["right_shoulder"], lm_pixel["right_elbow"], lm_pixel["right_wrist"])
        )

        roll = abs(math.degrees(math.atan2(
            lm_pixel["left_shoulder"][1] - lm_pixel["right_shoulder"][1],
            lm_pixel["left_shoulder"][0] - lm_pixel["right_shoulder"][0]
        )))

        knee_l = calculate_angle(lm_pixel["left_hip"], lm_pixel["left_knee"], lm_pixel["left_ankle"])
        knee_r = calculate_angle(lm_pixel["right_hip"], lm_pixel["right_knee"], lm_pixel["right_ankle"])
        kick_sym = abs(knee_l - knee_r)

        symmetry_hips = abs(lm_pixel["left_hip"][0] - lm_pixel["right_hip"][0]) / w * 100

        # NEW: Enhanced phase detection with wrist velocity
        phase, wrist_velocity_y, current_wrist_y = detect_phase_enhanced(
            lm_pixel, elbow, self.prev_wrist_y, fps
        )
        self.prev_wrist_y = current_wrist_y

        # NEW: Calculate horizontal deviation (body alignment) - now returns tuple
        horizontal_dev_raw, vertical_drop_raw, alignment_status = compute_horizontal_deviation(lm_pixel)
        
        # NEW: Calculate EVF plane angle - now returns tuple with dropped elbow detection
        evf_angle_raw, is_dropped_elbow, evf_status = compute_evf_plane_angle(lm_pixel)
        
        # NEW: Calculate kick depth relative to hip-ankle span
        kick_depth_raw = compute_kick_depth_relative(lm_pixel)

        # Breathing detection
        yaw = 0
        if "nose" in lm_pixel:
            mid_s = (lm_pixel["left_shoulder"][0] + lm_pixel["right_shoulder"][0]) / 2
            shoulder_width = abs(lm_pixel["right_shoulder"][0] - lm_pixel["left_shoulder"][0])
            if shoulder_width > 0:
                yaw = (lm_pixel["nose"][0] - mid_s) / shoulder_width

        breathing_during_pull = False
        if abs(yaw) > self.yaw_thresh:
            side = 'R' if yaw > 0 else 'L'
            if side == self.breath_side:
                self.breath_persist += 1
            else:
                self.breath_persist = 1
                self.breath_side = side
            if self.breath_persist >= MIN_BREATH_HOLD_FRAMES and t - self.last_breath >= MIN_BREATH_GAP_S:
                if side == 'L': 
                    self.breath_l += 1
                else: 
                    self.breath_r += 1
                self.last_breath = t
                
                # NEW: Check if breathing during pull phase
                if phase == "Pull":
                    breathing_during_pull = True
                    self.breaths_during_pull += 1

        # Stroke detection
        self.elbow_win.append(elbow)
        self.time_win.append(t)
        if len(self.elbow_win) >= 9 and detect_local_minimum(list(self.elbow_win)):
            ct = self.time_win[4]
            if not self.stroke_times or ct - self.stroke_times[-1] >= 0.5:
                self.stroke_times.append(ct)

        # Calculate legacy metrics for compatibility
        torso_raw = compute_torso_lean(lm_pixel)
        forearm_raw = compute_forearm_vertical(lm_pixel)

        # Smooth all metrics
        self.torso_buffer.append(torso_raw)
        self.forearm_buffer.append(forearm_raw)
        self.kick_depth_buffer.append(kick_depth_raw)
        self.horizontal_dev_buffer.append(horizontal_dev_raw)
        self.evf_buffer.append(evf_angle_raw)
        self.vertical_drop_buffer.append(vertical_drop_raw)

        torso = statistics.mean(self.torso_buffer) if self.torso_buffer else torso_raw
        forearm = statistics.mean(self.forearm_buffer) if self.forearm_buffer else forearm_raw
        kick_depth = statistics.mean(self.kick_depth_buffer) if self.kick_depth_buffer else kick_depth_raw
        horizontal_dev = statistics.mean(self.horizontal_dev_buffer) if self.horizontal_dev_buffer else horizontal_dev_raw
        evf_angle = statistics.mean(self.evf_buffer) if self.evf_buffer else evf_angle_raw
        vertical_drop = statistics.mean(self.vertical_drop_buffer) if self.vertical_drop_buffer else vertical_drop_raw
        roll_abs = abs(roll)
        
        # Track dropped elbow ONLY during Pull phase (the catch)
        # Dropped elbow is primarily a catch problem - during push the elbow naturally drops
        # Also only count when elbow angle is in catch range (>100°)
        if phase == "Pull" and elbow > 100:
            self.pull_phase_frames += 1
            if is_dropped_elbow:
                self.dropped_elbow_frames += 1

        # Draw landmarks
        for lm in landmarks:
            x, y = int(lm.x * w), int(lm.y * h)
            cv2.circle(frame, (x, y), 3, (0, 255, 128), -1)

        # NEW: Draw color-coded overlay zones
        draw_overlay_zones(frame, lm_pixel, horizontal_dev, evf_angle, phase)

        # Calculate sub-scores
        # Alignment score (0-100)
        if horizontal_dev <= DEFAULT_HORIZONTAL_DEV_GOOD[1]:
            alignment_score = 100
        elif horizontal_dev <= DEFAULT_HORIZONTAL_DEV_OK[1]:
            alignment_score = 100 - ((horizontal_dev - DEFAULT_HORIZONTAL_DEV_GOOD[1]) / 
                                     (DEFAULT_HORIZONTAL_DEV_OK[1] - DEFAULT_HORIZONTAL_DEV_GOOD[1]) * 30)
        else:
            alignment_score = max(0, 70 - (horizontal_dev - DEFAULT_HORIZONTAL_DEV_OK[1]) * 2)

        # EVF score (only during Pull/Push)
        if phase in ("Pull", "Push"):
            if evf_angle <= DEFAULT_EVF_ANGLE_GOOD[1]:
                evf_score = 100
            elif evf_angle <= DEFAULT_EVF_ANGLE_OK[1]:
                evf_score = 100 - ((evf_angle - DEFAULT_EVF_ANGLE_GOOD[1]) / 
                                   (DEFAULT_EVF_ANGLE_OK[1] - DEFAULT_EVF_ANGLE_GOOD[1]) * 30)
            else:
                evf_score = max(0, 70 - (evf_angle - DEFAULT_EVF_ANGLE_OK[1]))
        else:
            evf_score = 100  # Don't penalize during recovery

        # Calculate overall score with new components
        # Weight distribution: Alignment 25%, EVF 25%, Roll 15%, Kick 15%, Torso 10%, Breathing 10%
        
        # Roll score
        if DEFAULT_ROLL_GOOD[0] <= roll_abs <= DEFAULT_ROLL_GOOD[1]:
            roll_score = 100
        elif DEFAULT_ROLL_OK[0] <= roll_abs <= DEFAULT_ROLL_OK[1]:
            roll_score = 80
        else:
            roll_score = max(0, 60 - abs(roll_abs - 45))

        # Kick score
        kick_sym_score = max(0, 100 - (kick_sym / DEFAULT_KICK_SYM_MAX_GOOD * 30))
        if DEFAULT_KICK_DEPTH_GOOD[0] <= kick_depth <= DEFAULT_KICK_DEPTH_GOOD[1]:
            kick_depth_score = 100
        elif DEFAULT_KICK_DEPTH_OK[0] <= kick_depth <= DEFAULT_KICK_DEPTH_OK[1]:
            kick_depth_score = 80
        else:
            kick_depth_score = 60
        kick_score = (kick_sym_score + kick_depth_score) / 2

        # Torso score
        if DEFAULT_TORSO_GOOD[0] <= abs(torso) <= DEFAULT_TORSO_GOOD[1]:
            torso_score = 100
        elif DEFAULT_TORSO_OK[0] <= abs(torso) <= DEFAULT_TORSO_OK[1]:
            torso_score = 80
        else:
            torso_score = 60

        # NEW: Breathing penalty
        breath_penalty = BREATH_PULL_PENALTY if breathing_during_pull else 0
        
        # NEW: Compute glide metrics
        is_gliding, glide_score, arm_extension = compute_glide_metrics(
            lm_pixel, phase, elbow, horizontal_dev
        )
        
        # Track glide frames
        if is_gliding:
            self.glide_frames += 1

        # Weighted overall score (updated to include glide)
        # Weight distribution: Alignment 20%, EVF 20%, Roll 15%, Kick 15%, Torso 10%, Glide 10%, Breathing 10%
        score = (
            alignment_score * 0.20 +
            evf_score * 0.20 +
            roll_score * 0.15 +
            kick_score * 0.15 +
            torso_score * 0.10 +
            (glide_score if is_gliding else 70) * 0.10 +  # Glide score or neutral
            100 * 0.10  # Base breathing score
        ) - breath_penalty

        score = max(0, min(100, score))

        # Prepare metrics dict for panel
        metrics_dict = {
            'horizontal_deviation': horizontal_dev,
            'evf_plane_angle': evf_angle,
            'torso_lean': torso,
            'body_roll': roll_abs,
            'kick_depth': kick_depth,
            'kick_symmetry': kick_sym,
            'breathing_during_pull': breathing_during_pull,
            'score': score,
            'is_gliding': is_gliding,
            'glide_score': glide_score
        }

        # Draw enhanced technique panels
        draw_technique_panel_enhanced(frame, w-180, "YOUR STROKE", metrics_dict, phase, False, self.breath_side)
        
        # Ideal reference values
        ideal_metrics = {
            'horizontal_deviation': 3.0,
            'evf_plane_angle': 15.0,
            'torso_lean': 8.0,
            'body_roll': 45.0,
            'kick_depth': 0.25,
            'kick_symmetry': 5.0,
            'breathing_during_pull': False,
            'score': 95,
            'is_gliding': True,
            'glide_score': 90
        }
        draw_technique_panel_enhanced(frame, 180, "IDEAL REFERENCE", ideal_metrics, "Pull", True, 'N')

        # Track best/worst frames during Pull phase
        if phase == "Pull":
            dev = abs(elbow - 110) + horizontal_dev + evf_angle * 0.5
            if dev < self.best_dev:
                self.best_dev = dev
                _, buf = cv2.imencode('.jpg', frame)
                self.best_bytes = buf.tobytes()
            if dev > self.worst_dev:
                self.worst_dev = dev
                _, buf = cv2.imencode('.jpg', frame)
                self.worst_bytes = buf.tobytes()

        # Store metrics
        metrics = FrameMetrics(
            time_s=t,
            elbow_angle=elbow,
            knee_left=knee_l,
            knee_right=knee_r,
            kick_symmetry=kick_sym,
            kick_depth_proxy=kick_depth,
            symmetry_hips=symmetry_hips,
            score=score,
            body_roll=roll_abs,
            torso_lean=torso,
            forearm_vertical=forearm,
            phase=phase,
            breath_state=self.breath_side if self.breath_side != 'N' else "-",
            confidence=conf,
            horizontal_deviation=horizontal_dev,
            vertical_drop=vertical_drop,
            evf_plane_angle=evf_angle,
            is_dropped_elbow=is_dropped_elbow,
            evf_status=evf_status,
            alignment_status=alignment_status,
            wrist_velocity_y=wrist_velocity_y,
            alignment_score=alignment_score,
            evf_score=evf_score,
            breathing_during_pull=breathing_during_pull,
            is_gliding=is_gliding,
            glide_score=glide_score,
            arm_extension=arm_extension
        )
        self.metrics.append(metrics)

        return frame, score

    def close(self):
        if hasattr(self, 'landmarker') and self.landmarker:
            self.landmarker.close()

    def get_summary(self):
        if not self.metrics:
            return SessionSummary(0,0,0,0,0,0,0,0,0,0,0,"No data",1.0,None,None)
        
        # Ensure video context is finalized
        if not self.context_detector.detection_complete:
            self.video_context = self.context_detector.get_context()
            self.available_metrics = get_metrics_for_context(self.video_context)

        d = self.metrics[-1].time_s
        high_conf_metrics = [m for m in self.metrics if m.confidence >= DEFAULT_CONF_THRESHOLD]
        
        if not high_conf_metrics:
            high_conf_metrics = self.metrics

        scores = [m.score for m in high_conf_metrics]
        rolls = [m.body_roll for m in high_conf_metrics]
        ksyms = [m.kick_symmetry for m in high_conf_metrics]
        kdepths = [m.kick_depth_proxy for m in high_conf_metrics]
        confs = [m.confidence for m in self.metrics]
        h_devs = [m.horizontal_deviation for m in high_conf_metrics]
        v_drops = [m.vertical_drop for m in high_conf_metrics]
        evf_angles = [m.evf_plane_angle for m in high_conf_metrics if m.phase in ("Pull", "Push")]
        alignment_scores = [m.alignment_score for m in high_conf_metrics]
        evf_scores = [m.evf_score for m in high_conf_metrics if m.phase in ("Pull", "Push")]

        # Stroke rate calculation
        sr = 0
        if len(self.stroke_times) >= 2:
            dur = self.stroke_times[-1] - self.stroke_times[0]
            if dur > 0.1: 
                sr = 60 * (len(self.stroke_times)-1) / dur

        bpm = (self.breath_l + self.breath_r) / (d/60) if d > 0 else 0

        avg_kick_sym = statistics.mean(ksyms) if ksyms else 0
        avg_kick_depth = statistics.mean(kdepths) if kdepths else 0
        
        # Determine kick status
        kick_sym_ok = avg_kick_sym < DEFAULT_KICK_SYM_MAX_GOOD
        kick_depth_ok = DEFAULT_KICK_DEPTH_GOOD[0] < avg_kick_depth < DEFAULT_KICK_DEPTH_GOOD[1]
        if kick_sym_ok and kick_depth_ok:
            kick_status = "Good"
        elif kick_sym_ok or kick_depth_ok:
            kick_status = "OK"
        else:
            kick_status = "Needs Work"

        # Calculate dropped elbow percentage
        dropped_elbow_pct = (self.dropped_elbow_frames / self.pull_phase_frames * 100) if self.pull_phase_frames > 0 else 0
        
        # Calculate averages
        avg_h_dev = statistics.mean(h_devs) if h_devs else 0
        avg_v_drop = statistics.mean(v_drops) if v_drops else 0
        avg_evf = statistics.mean(evf_angles) if evf_angles else 0
        avg_roll = statistics.mean(rolls) if rolls else 0

        # Generate diagnostics - prioritized by importance
        diagnostics = []
        
        # 1. DROPPED ELBOW - Most critical EVF issue
        if dropped_elbow_pct > 50:
            diagnostics.append(f"🚨 DROPPED ELBOW detected in {dropped_elbow_pct:.0f}% of catch frames - this is your #1 priority! Keep elbow HIGH and above wrist during the catch.")
        elif dropped_elbow_pct > 20:
            diagnostics.append(f"⚠️ Dropped elbow detected in {dropped_elbow_pct:.0f}% of catch frames - focus on 'elbow up' cue during entry and catch.")
        
        # 2. VERTICAL DROP / SINKING - Critical for drag
        if avg_v_drop > 15:
            diagnostics.append("🚨 SINKING HIPS/LEGS - your lower body is dragging. Focus on: head position (look down), core engagement, and kick from hips.")
        elif avg_v_drop > 8:
            diagnostics.append("⚠️ Slight hip drop detected - engage core and press chest down slightly to lift hips.")
        
        # 3. Horizontal alignment (lateral)
        if avg_h_dev > DEFAULT_HORIZONTAL_DEV_OK[1]:
            diagnostics.append("⚠️ Body alignment deviation - you may be 'snake swimming'. Focus on rotating around your spine axis.")
        
        # 4. EVF angle (if not already flagged for dropped elbow)
        if dropped_elbow_pct <= 20:
            if avg_evf > DEFAULT_EVF_ANGLE_OK[1]:
                diagnostics.append("⚠️ EVF needs work - focus on 'fingertips down, elbow up' during the catch.")
            elif avg_evf > DEFAULT_EVF_ANGLE_GOOD[1]:
                diagnostics.append("💡 EVF is OK - work on reaching forward then dropping fingertips before pulling.")

        # 5. Breathing during pull
        if self.breaths_during_pull > 0:
            diagnostics.append(f"⚠️ {self.breaths_during_pull} breath(s) during pull phase - breathe during recovery to maintain EVF.")

        # 6. Body roll
        if avg_roll < DEFAULT_ROLL_GOOD[0]:
            diagnostics.append("💡 Body roll is too flat - aim for 35-55° rotation to engage lats.")
        elif avg_roll > DEFAULT_ROLL_GOOD[1]:
            diagnostics.append("⚠️ Excessive body roll - this may cause energy leaks and over-rotation.")

        # 7. Breathing balance
        breath_balance = abs(self.breath_l - self.breath_r)
        if breath_balance > 5:
            side = "left" if self.breath_l > self.breath_r else "right"
            diagnostics.append(f"💡 Breathing is asymmetric (favoring {side}) - practice bilateral breathing.")

        # Calculate glide metrics
        glide_metrics = [m for m in high_conf_metrics if m.is_gliding]
        glide_ratio = (len(glide_metrics) / len(high_conf_metrics) * 100) if high_conf_metrics else 0
        avg_glide_score = statistics.mean([m.glide_score for m in glide_metrics]) if glide_metrics else 0
        
        # 8. GLIDE assessment
        if glide_ratio < 10:
            diagnostics.append("🚨 MINIMAL GLIDE detected - you're rushing your stroke! Extend your lead arm and glide briefly after each entry to maximize distance per stroke.")
        elif glide_ratio < 20:
            diagnostics.append("⚠️ Low glide ratio ({:.0f}%) - try extending your lead arm longer before starting the catch. This improves efficiency.".format(glide_ratio))
        elif glide_ratio > 40:
            diagnostics.append("💡 High glide ratio ({:.0f}%) - good for distance swimming! For sprints, you may want to reduce glide time.".format(glide_ratio))
        elif avg_glide_score < 60 and glide_ratio >= 15:
            diagnostics.append("💡 Glide detected but form could improve - focus on full arm extension and streamlined body during glide phase.")

        if not diagnostics:
            diagnostics.append("✅ Great technique! Keep up the good work.")

        return SessionSummary(
            duration_s=d,
            avg_score=statistics.mean(scores) if scores else 0,
            avg_body_roll=avg_roll,
            max_body_roll=max(rolls) if rolls else 0,
            stroke_rate=sr,
            breaths_per_min=bpm,
            breath_left=self.breath_l,
            breath_right=self.breath_r,
            total_strokes=len(self.stroke_times),
            avg_kick_symmetry=avg_kick_sym,
            avg_kick_depth=avg_kick_depth,
            kick_status=kick_status,
            avg_confidence=statistics.mean(confs) if confs else 1.0,
            best_frame_bytes=self.best_bytes,
            worst_frame_bytes=self.worst_bytes,
            avg_horizontal_deviation=avg_h_dev,
            avg_vertical_drop=avg_v_drop,
            avg_evf_angle=avg_evf,
            dropped_elbow_frames=self.dropped_elbow_frames,
            dropped_elbow_pct=dropped_elbow_pct,
            avg_alignment_score=statistics.mean(alignment_scores) if alignment_scores else 100,
            avg_evf_score=statistics.mean(evf_scores) if evf_scores else 100,
            breaths_during_pull=self.breaths_during_pull,
            total_breaths=self.breath_l + self.breath_r,
            diagnostics=diagnostics,
            video_context=self.video_context,
            available_metrics=self.available_metrics,
            # Glide metrics
            glide_ratio=glide_ratio,
            avg_glide_score=avg_glide_score,
            glide_frames=self.glide_frames,
            total_analyzed_frames=len(high_conf_metrics)
        )

# ─────────────────────────────────────────────
# PLOTS - Enhanced with new metrics
# ─────────────────────────────────────────────

def generate_plots(analyzer: SwimAnalyzer):
    if not analyzer.metrics:
        return io.BytesIO()

    times = [m.time_s for m in analyzer.metrics]
    plt.style.use('dark_background')
    fig, axs = plt.subplots(5, 1, figsize=(10, 14), sharex=True)

    # 1. Body Alignment (Horizontal Deviation)
    axs[0].plot(times, [m.horizontal_deviation for m in analyzer.metrics], 
                label="Horizontal Deviation", color='#06b6d4', linewidth=1.5)
    axs[0].axhspan(0, DEFAULT_HORIZONTAL_DEV_GOOD[1], color='green', alpha=0.2, label='Good Zone')
    axs[0].axhspan(DEFAULT_HORIZONTAL_DEV_GOOD[1], DEFAULT_HORIZONTAL_DEV_OK[1], 
                   color='yellow', alpha=0.2, label='OK Zone')
    axs[0].set_ylabel("Degrees")
    axs[0].set_title("Body Alignment (Shoulder-Hip-Ankle Deviation)")
    axs[0].legend(loc='upper right')
    axs[0].set_ylim(0, 30)

    # 2. EVF Angle
    pull_push_times = [m.time_s for m in analyzer.metrics if m.phase in ("Pull", "Push")]
    pull_push_evf = [m.evf_plane_angle for m in analyzer.metrics if m.phase in ("Pull", "Push")]
    axs[1].scatter(pull_push_times, pull_push_evf, label="EVF Angle (Pull/Push)", 
                   color='#a855f7', s=10, alpha=0.7)
    axs[1].axhspan(0, DEFAULT_EVF_ANGLE_GOOD[1], color='green', alpha=0.2)
    axs[1].axhspan(DEFAULT_EVF_ANGLE_GOOD[1], DEFAULT_EVF_ANGLE_OK[1], color='yellow', alpha=0.2)
    axs[1].set_ylabel("Degrees")
    axs[1].set_title("Early Vertical Forearm Angle (lower is better)")
    axs[1].legend(loc='upper right')
    axs[1].set_ylim(0, 60)

    # 3. Body Roll
    axs[2].plot(times, [m.body_roll for m in analyzer.metrics], 
                label="Body Roll", color='#f59e0b', linewidth=1.5)
    axs[2].axhspan(DEFAULT_ROLL_GOOD[0], DEFAULT_ROLL_GOOD[1], color='green', alpha=0.2)
    axs[2].axhline(45, color='white', linestyle='--', alpha=0.5, label='Ideal (45°)')
    axs[2].set_ylabel("Degrees")
    axs[2].set_title("Body Roll Over Time")
    axs[2].legend(loc='upper right')

    # 4. Kick Metrics
    ax4 = axs[3]
    ax4.plot(times, [m.kick_symmetry for m in analyzer.metrics], 
             label="Kick Symmetry", color='#ef4444', linewidth=1.5)
    ax4.axhline(DEFAULT_KICK_SYM_MAX_GOOD, color='red', linestyle='--', alpha=0.5)
    ax4.set_ylabel("Symmetry (°)", color='#ef4444')
    ax4.tick_params(axis='y', labelcolor='#ef4444')
    
    ax4b = ax4.twinx()
    ax4b.plot(times, [m.kick_depth_proxy for m in analyzer.metrics], 
              label="Kick Depth", color='#22c55e', linewidth=1.5, alpha=0.7)
    ax4b.axhspan(DEFAULT_KICK_DEPTH_GOOD[0], DEFAULT_KICK_DEPTH_GOOD[1], 
                 color='green', alpha=0.1)
    ax4b.set_ylabel("Depth (normalized)", color='#22c55e')
    ax4b.tick_params(axis='y', labelcolor='#22c55e')
    ax4.set_title("Kick Metrics")
    
    # Combined legend
    lines1, labels1 = ax4.get_legend_handles_labels()
    lines2, labels2 = ax4b.get_legend_handles_labels()
    ax4.legend(lines1 + lines2, labels1 + labels2, loc='upper right')

    # 5. Overall Score with sub-scores
    axs[4].plot(times, [m.score for m in analyzer.metrics], 
                label="Overall Score", color='#22c55e', linewidth=2)
    axs[4].plot(times, [m.alignment_score for m in analyzer.metrics], 
                label="Alignment Score", color='#06b6d4', linewidth=1, alpha=0.7)
    axs[4].plot(times, [m.evf_score for m in analyzer.metrics], 
                label="EVF Score", color='#a855f7', linewidth=1, alpha=0.7)
    axs[4].axhline(70, color='yellow', linestyle='--', alpha=0.5, label='Good threshold')
    axs[4].set_xlabel("Time (seconds)")
    axs[4].set_ylabel("Score")
    axs[4].set_title("Technique Scores Over Time")
    axs[4].legend(loc='lower right')
    axs[4].set_ylim(0, 105)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf

# ─────────────────────────────────────────────
# PDF REPORT - Enhanced
# ─────────────────────────────────────────────

def generate_pdf_report(summary: SessionSummary, filename: str, plot_buffer: io.BytesIO) -> io.BytesIO:
    buffer = io.BytesIO()
    pdf = SimpleDocTemplate(
        buffer, 
        pagesize=letter, 
        topMargin=0.75*inch, 
        bottomMargin=0.5*inch,
        leftMargin=0.75*inch,
        rightMargin=0.75*inch
    )
    styles = getSampleStyleSheet()
    
    # Custom styles with proper spacing
    styles.add(ParagraphStyle(
        name='CustomTitle', 
        fontSize=20,  # Reduced from 24 to prevent overlap
        textColor=colors.HexColor('#06b6d4'), 
        spaceAfter=12,
        spaceBefore=0,
        alignment=1  # Center alignment
    ))
    styles.add(ParagraphStyle(
        name='ReportSubtitle', 
        fontSize=12, 
        textColor=colors.HexColor('#64748b'), 
        spaceAfter=20,
        alignment=1  # Center alignment
    ))
    styles.add(ParagraphStyle(name='DiagnosticGood', fontSize=10, textColor=colors.HexColor('#22c55e'), leftIndent=15, spaceAfter=6))
    styles.add(ParagraphStyle(name='DiagnosticWarn', fontSize=10, textColor=colors.HexColor('#f59e0b'), leftIndent=15, spaceAfter=6))
    styles.add(ParagraphStyle(name='DiagnosticError', fontSize=10, textColor=colors.HexColor('#ef4444'), leftIndent=15, spaceAfter=6))

    story = []
    
    # Title - centered and properly sized
    story.append(Paragraph("Freestyle Swimming Technique Analysis", styles['CustomTitle']))
    story.append(Paragraph(f"Analysis Report • {datetime.datetime.now().strftime('%B %d, %Y')}", styles['ReportSubtitle']))
    story.append(Spacer(1, 0.15*inch))

    # Session Information
    story.append(Paragraph("Session Information", styles['Heading2']))
    session_data = [
        ['File', filename[:40] + '...' if len(filename) > 40 else filename],  # Truncate long filenames
        ['Duration', f"{summary.duration_s:.1f} seconds"],
        ['Analyzed', datetime.datetime.now().strftime("%Y-%m-%d %H:%M")],
        ['Detection Confidence', f"{summary.avg_confidence*100:.1f}%"]
    ]
    t = Table(session_data, colWidths=[1.8*inch, 4.2*inch])
    t.setStyle(TableStyle([
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('TEXTCOLOR', (0,0), (0,-1), colors.HexColor('#64748b')),
        ('ALIGN', (0,0), (0,-1), 'RIGHT'),
        ('RIGHTPADDING', (0,0), (0,-1), 12),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.25*inch))

    # Overall Score Card
    story.append(Paragraph("Overall Performance", styles['Heading2']))
    score_color = colors.HexColor('#22c55e') if summary.avg_score >= 70 else colors.HexColor('#f59e0b') if summary.avg_score >= 50 else colors.HexColor('#ef4444')
    story.append(Paragraph(f"<font size='32' color='{score_color}'><b>{summary.avg_score:.1f}/100</b></font>", styles['Normal']))
    story.append(Spacer(1, 0.15*inch))

    # Sub-Scores
    story.append(Paragraph("Component Scores", styles['Heading3']))
    subscore_data = [
        ['Component', 'Score', 'Status'],
        ['Body Alignment', f"{summary.avg_alignment_score:.1f}", get_zone_status(summary.avg_horizontal_deviation, DEFAULT_HORIZONTAL_DEV_GOOD, DEFAULT_HORIZONTAL_DEV_OK)],
        ['EVF (Pull Phase)', f"{summary.avg_evf_score:.1f}", f"Dropped: {summary.dropped_elbow_pct:.0f}%" if summary.dropped_elbow_pct > 10 else get_zone_status(summary.avg_evf_angle, DEFAULT_EVF_ANGLE_GOOD, DEFAULT_EVF_ANGLE_OK)],
        ['Body Roll', f"{summary.avg_body_roll:.1f}°", get_zone_status(summary.avg_body_roll, DEFAULT_ROLL_GOOD, DEFAULT_ROLL_OK)],
        ['Kick', summary.kick_status, summary.kick_status],
    ]
    t = Table(subscore_data, colWidths=[2*inch, 1.3*inch, 1.7*inch])
    t.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e3a5f')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('ALIGN', (1,0), (-1,-1), 'CENTER'),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.25*inch))

    # Performance Metrics
    story.append(Paragraph("Performance Metrics", styles['Heading2']))
    metrics_data = [
        ['Metric', 'Value', 'Notes'],
        ['Stroke Rate', f"{summary.stroke_rate:.1f} spm", 'strokes per minute'],
        ['Total Strokes', f"{summary.total_strokes}", ''],
        ['Breaths/min', f"{summary.breaths_per_min:.1f}", f"Left: {summary.breath_left}  Right: {summary.breath_right}"],
        ['Breaths During Pull', f"{summary.breaths_during_pull}", 'Ideally 0'],
        ['Dropped Elbow', f"{summary.dropped_elbow_pct:.0f}%", 'of catch frames'],
        ['Vertical Drop', f"{summary.avg_vertical_drop:.1f}°", 'hip sink angle'],
        ['Max Body Roll', f"{summary.max_body_roll:.1f}°", 'peak rotation'],
        ['Avg EVF Angle', f"{summary.avg_evf_angle:.1f}°", 'lower is better'],
        ['Kick Depth', f"{summary.avg_kick_depth:.2f}", 'relative to hip-ankle'],
        ['Kick Symmetry', f"{summary.avg_kick_symmetry:.1f}°", 'L-R difference'],
    ]
    t = Table(metrics_data, colWidths=[1.8*inch, 1.2*inch, 2*inch])
    t.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e3a5f')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('ALIGN', (1,0), (1,-1), 'CENTER'),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.25*inch))

    # Diagnostics
    story.append(Paragraph("Coaching Insights", styles['Heading2']))
    for diag in summary.diagnostics:
        if diag.startswith("✅"):
            style = styles['DiagnosticGood']
        elif diag.startswith("⚠️"):
            style = styles['DiagnosticError']
        else:
            style = styles['DiagnosticWarn']
        story.append(Paragraph(diag, style))
        story.append(Spacer(1, 0.1*inch))

    # Best & Worst Frames
    if summary.best_frame_bytes or summary.worst_frame_bytes:
        story.append(Spacer(1, 0.3*inch))
        story.append(Paragraph("Best & Worst Frames (Pull Phase)", styles['Heading2']))
        if summary.best_frame_bytes:
            img = RLImage(io.BytesIO(summary.best_frame_bytes))
            img.drawWidth = 3*inch
            img.drawHeight = 2*inch
            story.append(Paragraph("Best Pull Frame:", styles['Normal']))
            story.append(img)
        if summary.worst_frame_bytes:
            img = RLImage(io.BytesIO(summary.worst_frame_bytes))
            img.drawWidth = 3*inch
            img.drawHeight = 2*inch
            story.append(Paragraph("Worst Pull Frame:", styles['Normal']))
            story.append(img)

    # Charts
    if plot_buffer.getvalue():
        story.append(PageBreak())
        story.append(Paragraph("Analysis Charts", styles['Heading2']))
        plot_buffer.seek(0)
        img = RLImage(plot_buffer)
        # Scale to fit page (letter is 8.5x11, with margins we have ~7x9 usable)
        img.drawWidth = 6.5*inch
        img.drawHeight = 8.5*inch
        story.append(img)

    pdf.build(story)
    buffer.seek(0)
    return buffer

# ─────────────────────────────────────────────
# CSV & ZIP - Enhanced
# ─────────────────────────────────────────────

def export_to_csv(analyzer: SwimAnalyzer):
    if not analyzer.metrics:
        return io.BytesIO()
    data = {
        'time_s': [m.time_s for m in analyzer.metrics],
        'phase': [m.phase for m in analyzer.metrics],
        'score': [m.score for m in analyzer.metrics],
        'alignment_score': [m.alignment_score for m in analyzer.metrics],
        'evf_score': [m.evf_score for m in analyzer.metrics],
        'horizontal_deviation': [m.horizontal_deviation for m in analyzer.metrics],
        'evf_plane_angle': [m.evf_plane_angle for m in analyzer.metrics],
        'body_roll': [m.body_roll for m in analyzer.metrics],
        'torso_lean': [m.torso_lean for m in analyzer.metrics],
        'kick_symmetry': [m.kick_symmetry for m in analyzer.metrics],
        'kick_depth': [m.kick_depth_proxy for m in analyzer.metrics],
        'elbow_angle': [m.elbow_angle for m in analyzer.metrics],
        'wrist_velocity_y': [m.wrist_velocity_y for m in analyzer.metrics],
        'breath_state': [m.breath_state for m in analyzer.metrics],
        'breathing_during_pull': [m.breathing_during_pull for m in analyzer.metrics],
        'confidence': [m.confidence for m in analyzer.metrics],
    }
    df = pd.DataFrame(data)
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return buf

def create_results_bundle(video_path, csv_buf, pdf_buf, timestamp):
    """Create ZIP with just video, PDF report, and CSV data"""
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zipf:
        if os.path.exists(video_path):
            with open(video_path, 'rb') as f:
                zipf.writestr(f"annotated_video_{timestamp}.mp4", f.read())
        zipf.writestr(f"technique_report_{timestamp}.pdf", pdf_buf.getvalue())
        zipf.writestr(f"frame_data_{timestamp}.csv", csv_buf.getvalue())
    zip_buf.seek(0)
    return zip_buf

# ─────────────────────────────────────────────
# MAIN APP - Enhanced UI
# ─────────────────────────────────────────────

def main():
    st.set_page_config(layout="wide", page_title="Freestyle Swim Analyzer Pro v2")
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # Check for payment success via query parameters
    query_params = st.query_params
    if query_params.get("payment") == "success":
        st.session_state.payment_completed = True
        st.session_state.analysis_unlocked = True
        st.success("✅ Payment successful! You can now analyze your video.")
        # Clear query params to avoid re-triggering
        st.query_params.clear()
    elif query_params.get("payment") == "cancel":
        st.warning("⚠️ Payment cancelled. You can try again when ready.")
        st.query_params.clear()

    st.title("🏊 Freestyle Swim Technique Analyzer Pro v2")
    st.markdown("AI-powered analysis with **enhanced biomechanical metrics**")
    
    # Important notice about video requirements
    st.warning("⚠️ **Full body must be visible for an accurate analysis.** Ensure the swimmer's entire body (head to feet) is in frame throughout the video.")

    if not MEDIAPIPE_TASKS_AVAILABLE:
        st.error("MediaPipe Tasks not installed. Run: pip install mediapipe>=0.10.14")
        return

    with st.sidebar:
        st.header("⚙️ Athlete & Settings")
        
        # Height input with feet/inches conversion
        st.subheader("Height")
        height_unit = st.radio("Unit", ["cm", "ft/in"], horizontal=True, label_visibility="collapsed")
        
        if height_unit == "cm":
            height = st.slider("Height (cm)", 150, 210, 170)
        else:
            col_ft, col_in = st.columns(2)
            with col_ft:
                feet = st.number_input("Feet", min_value=4, max_value=7, value=5)
            with col_in:
                inches = st.number_input("Inches", min_value=0, max_value=11, value=7)
            # Convert to cm
            height = int((feet * 12 + inches) * 2.54)
            st.caption(f"= {height} cm")
        
        # Discipline selection with explanation
        st.subheader("Discipline")
        discipline = st.selectbox("Select discipline", ["pool", "triathlon", "open water"], label_visibility="collapsed")
        
        # Discipline explanations
        discipline_info = {
            "pool": "🏊 **Pool Swimming**: Optimized for controlled environment with walls for push-offs. Focuses on precise technique metrics, flip turn timing, and maintaining consistent stroke rate.",
            "triathlon": "🏃 **Triathlon**: Balances efficiency with energy conservation. Slightly relaxed thresholds for body position since wetsuit buoyancy helps. Emphasizes sustainable stroke rate.",
            "open water": "🌊 **Open Water**: Accounts for waves, currents, and sighting. More tolerant of head position variations and body roll changes needed for navigation."
        }
        st.info(discipline_info[discipline])
        
        st.divider()
        
        # Detection Settings with explanations
        st.subheader("Detection Settings")
        
        conf_thresh = st.slider("Confidence Threshold", 0.3, 0.7, DEFAULT_CONF_THRESHOLD, 0.05)
        st.caption("""
        **What it does**: Filters out frames where pose detection is uncertain.  
        **Ideal setting**: **0.5** (default) - balances accuracy with data retention.  
        ↑ Higher = stricter, fewer frames analyzed but more accurate.  
        ↓ Lower = more frames but may include errors from splashing/bubbles.
        """)
        
        yaw_thresh = st.slider("Breath Detection Sensitivity", 0.05, 0.3, DEFAULT_YAW_THRESHOLD, 0.01)
        st.caption("""
        **What it does**: Detects head rotation for breath timing analysis.  
        **Ideal setting**: **0.15** (default) - catches most breaths without false positives.  
        ↑ Higher = only detects very pronounced head turns.  
        ↓ Lower = more sensitive, may count minor head movements as breaths.
        """)
        
        st.divider()
        
        # Show what metrics are available based on view
        with st.expander("📊 Metrics by View Type"):
            st.markdown("""
            **Side View + Underwater** *(Most metrics)*
            - EVF (Early Vertical Forearm)
            - Body alignment & vertical drop
            - Kick depth
            - Stroke phases
            - Dropped elbow detection
            
            **Side View + Above Water**
            - Recovery arm position
            - Head position
            - Breathing timing
            
            **Front View + Underwater**
            - Body roll
            - Hand entry width
            - Kick symmetry
            
            **Front View + Above Water**
            - Entry angle
            - Breathing side
            """)

    athlete = AthleteProfile(height, discipline)

    # ═══════════════════════════════════════════════════════════════
    # STEP 1: VIDEO UPLOAD
    # ═══════════════════════════════════════════════════════════════

    st.subheader("📹 Step 1: Upload Your Video")
    uploaded = st.file_uploader("Upload swimming video", type=["mp4", "mov", "avi", "MOV", "MP4", "AVI"])

    if uploaded:
        file_size_mb = len(uploaded.getvalue()) / (1024 * 1024)
        st.success(f"✅ Video uploaded: **{uploaded.name}** ({file_size_mb:.1f} MB)")

    st.divider()

    # ═══════════════════════════════════════════════════════════════
    # STEP 2: VIDEO TYPE SELECTION (only shown after upload)
    # ═══════════════════════════════════════════════════════════════

    video_type = None
    selected_camera = None
    selected_water = None

    if uploaded:
        st.subheader("📹 Step 2: Select Video Type")
        st.markdown("**Choose the type that matches your uploaded video** for accurate analysis.")

        col1, col2 = st.columns(2)

        with col1:
            video_type = st.radio(
                "Select video type:",
                options=[
                    "Side View - Underwater",
                    "Side View - Above Water",
                    "Front View - Underwater",
                    "Front View - Above Water"
                ],
                index=None,
                help="Choose the type that best matches your video. Side view = camera sees swimmer from the side. Front view = camera faces the swimmer."
            )

        with col2:
            st.markdown("""
            **📐 Side View**: Camera positioned to see the swimmer from the side (most common for technique analysis)

            **👤 Front View**: Camera faces the swimmer head-on (good for body roll and symmetry)

            **🌊 Above Water**: Camera is above the water surface

            **🤿 Underwater**: Camera is below the water surface
            """)

        # Map selection to enums
        video_type_map = {
            "Side View - Underwater": (CameraView.SIDE, WaterPosition.UNDERWATER),
            "Side View - Above Water": (CameraView.SIDE, WaterPosition.ABOVE_WATER),
            "Front View - Underwater": (CameraView.FRONT, WaterPosition.UNDERWATER),
            "Front View - Above Water": (CameraView.FRONT, WaterPosition.ABOVE_WATER),
        }

        if video_type:
            selected_camera, selected_water = video_type_map[video_type]
            st.success(f"✅ Selected: **{video_type}** - Ready to analyze!")
        else:
            st.info("👆 Please select your video type above to start analysis.")

        st.divider()

        # ═══════════════════════════════════════════════════════════════
        # STEP 3: PAYMENT FOR SINGLE ANALYSIS
        # ═══════════════════════════════════════════════════════════════

        if video_type:
            st.subheader("💳 Step 3: Payment")

            # Initialize session state for payment tracking
            if 'payment_completed' not in st.session_state:
                st.session_state.payment_completed = False
            if 'analysis_unlocked' not in st.session_state:
                st.session_state.analysis_unlocked = False

            if not st.session_state.payment_completed:
                st.markdown("""
                **Single Video Analysis** - $9.99

                ✓ Full technique analysis
                ✓ Detailed PDF report
                ✓ Downloadable annotated video
                ✓ CSV data export
                """)

                if STRIPE_AVAILABLE:
                    # Initialize Stripe with your keys (stored in Streamlit secrets)
                    # You'll need to add these to .streamlit/secrets.toml:
                    # [stripe]
                    # publishable_key = "pk_test_..."
                    # secret_key = "sk_test_..."
                    # price_id = "price_..."  # Your Stripe Price ID for single analysis

                    try:
                        stripe_secret = st.secrets.get("stripe", {}).get("secret_key")
                        stripe_price_id = st.secrets.get("stripe", {}).get("price_id")

                        if stripe_secret and stripe_price_id:
                            stripe.api_key = stripe_secret

                            col1, col2 = st.columns([1, 2])
                            with col1:
                                if st.button("🚀 Pay & Analyze ($9.99)", type="primary"):
                                    # Create Stripe Checkout Session
                                    try:
                                        # Get base URL from secrets or use current
                                        base_url = st.secrets.get("stripe", {}).get("base_url", "https://yourapp.streamlit.app")

                                        checkout_session = stripe.checkout.Session.create(
                                            payment_method_types=['card'],
                                            line_items=[{
                                                'price': stripe_price_id,
                                                'quantity': 1,
                                            }],
                                            mode='payment',
                                            success_url=f"{base_url}?payment=success",
                                            cancel_url=f"{base_url}?payment=cancel",
                                        )

                                        # Redirect to Stripe Checkout
                                        st.markdown(f'<meta http-equiv="refresh" content="0; url={checkout_session.url}" />', unsafe_allow_html=True)
                                        st.info(f"Redirecting to payment... [Click here if not redirected]({checkout_session.url})")

                                    except Exception as e:
                                        st.error(f"Payment error: {e}")
                        else:
                            st.warning("⚠️ Stripe configuration missing. Add your Stripe keys to `.streamlit/secrets.toml`")
                            # For testing/development: allow bypass
                            if st.button("🧪 Skip Payment (Testing Mode)"):
                                st.session_state.payment_completed = True
                                st.session_state.analysis_unlocked = True
                                st.rerun()

                    except Exception as e:
                        st.error(f"Stripe initialization error: {e}")
                        # Fallback for testing
                        if st.button("🧪 Skip Payment (Testing Mode)"):
                            st.session_state.payment_completed = True
                            st.session_state.analysis_unlocked = True
                            st.rerun()
                else:
                    st.warning("⚠️ Stripe not installed. Run: `pip install stripe`")
                    # For testing: allow bypass
                    if st.button("🧪 Skip Payment (Testing Mode)"):
                        st.session_state.payment_completed = True
                        st.session_state.analysis_unlocked = True
                        st.rerun()

                st.divider()
            else:
                st.success("✅ Payment Completed - Analysis Unlocked!")
                st.divider()

    if uploaded and video_type and st.session_state.get('analysis_unlocked', False):
        # Use the user-selected video type (mandatory override)
        manual_camera_view = selected_camera
        manual_water_position = selected_water
        
        try:
            analyzer = SwimAnalyzer(
                athlete, conf_thresh, yaw_thresh,
                manual_camera_view=manual_camera_view,
                manual_water_position=manual_water_position
            )
        except Exception as e:
            st.error(f"Failed to initialize analyzer: {e}")
            return

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_in:
            tmp_in.write(uploaded.getvalue())
            input_path = tmp_in.name

        cap = cv2.VideoCapture(input_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # Write to temporary file with OpenCV
        temp_out_path = tempfile.mktemp(suffix=".avi")
        fourcc = cv2.VideoWriter_fourcc(*'XVID')  # Use XVID for intermediate
        writer = cv2.VideoWriter(temp_out_path, fourcc, fps, (w, h))

        # Progress bars for processing and encoding
        st.markdown("### ⏳ Processing Video")
        processing_progress = st.progress(0)
        processing_status = st.empty()
        
        frame_idx = 0
        try:
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret: 
                    break

                timestamp_ms = frame_idx * 33 + 1
                real_t = frame_idx / fps

                annotated, _ = analyzer.process(frame, real_t, timestamp_ms, fps)
                writer.write(annotated)

                frame_idx += 1
                if total > 0:
                    pct = frame_idx / total
                    processing_progress.progress(min(pct, 1.0))
                processing_status.text(f"🎬 Analyzing frame {frame_idx}/{total} ({frame_idx/total*100:.1f}%)")

            cap.release()
            writer.release()
            
            processing_status.text("✅ Frame analysis complete!")
            
            # ═══════════════════════════════════════════════════════════════
            # ENCODING WITH PROGRESS BAR
            # ═══════════════════════════════════════════════════════════════
            
            st.markdown("### 🎥 Encoding Video")
            encoding_progress = st.progress(0)
            encoding_status = st.empty()
            
            encoding_status.text("🔄 Encoding video for browser playback (0%)...")
            out_path = tempfile.mktemp(suffix=".mp4")
            
            encoding_success = False
            
            # Method 1: Use MoviePy with progress callback
            if MOVIEPY_AVAILABLE:
                try:
                    encoding_status.text("🔄 Encoding video (initializing)...")
                    encoding_progress.progress(0.1)
                    
                    clip = VideoFileClip(temp_out_path)
                    duration = clip.duration
                    
                    # Custom progress logger for moviepy
                    class ProgressLogger:
                        def __init__(self, progress_bar, status_text, duration):
                            self.progress_bar = progress_bar
                            self.status_text = status_text
                            self.duration = duration
                            self.last_pct = 0
                        
                        def __call__(self, t=None, *args, **kwargs):
                            if t is not None and self.duration > 0:
                                pct = min(t / self.duration, 1.0)
                                if pct - self.last_pct > 0.02:  # Update every 2%
                                    self.progress_bar.progress(pct)
                                    self.status_text.text(f"🔄 Encoding video ({pct*100:.0f}%)...")
                                    self.last_pct = pct
                    
                    encoding_progress.progress(0.2)
                    encoding_status.text("🔄 Encoding video (20%)...")
                    
                    # Mobile-optimized encoding settings
                    clip.write_videofile(
                        out_path,
                        codec='libx264',
                        audio=False,
                        preset='medium',  # Better quality/size ratio than 'fast'
                        ffmpeg_params=[
                            '-pix_fmt', 'yuv420p',  # Critical for mobile compatibility
                            '-profile:v', 'baseline',  # H.264 baseline profile for max mobile compatibility
                            '-level', '3.0',  # Compatible with most mobile devices
                            '-movflags', '+faststart',  # Enable streaming/progressive download
                            '-crf', '23',  # Constant rate factor for good quality
                            '-maxrate', '2M',  # Limit bitrate for mobile playback
                            '-bufsize', '4M'  # Buffer size for rate control
                        ],
                        logger=None  # Suppress moviepy output
                    )
                    clip.close()
                    encoding_success = True
                    
                    encoding_progress.progress(1.0)
                    encoding_status.text("✅ Encoding complete!")
                    
                except Exception as e:
                    encoding_status.text(f"⚠️ MoviePy encoding failed: {e}. Trying fallback...")
                    encoding_progress.progress(0.3)
            
            # Method 2: Fallback to ffmpeg binary if available
            if not encoding_success:
                import subprocess
                try:
                    encoding_status.text("🔄 Encoding with ffmpeg (50%)...")
                    encoding_progress.progress(0.5)
                    
                    # Mobile-optimized ffmpeg encoding
                    subprocess.run([
                        'ffmpeg', '-y', '-i', temp_out_path,
                        '-c:v', 'libx264',
                        '-preset', 'medium',  # Better quality/size balance
                        '-profile:v', 'baseline',  # H.264 baseline for mobile compatibility
                        '-level', '3.0',  # Mobile-compatible level
                        '-crf', '23',  # Good quality
                        '-maxrate', '2M',  # Limit bitrate for mobile
                        '-bufsize', '4M',  # Buffer size
                        '-pix_fmt', 'yuv420p',  # Critical for compatibility
                        '-movflags', '+faststart',  # Enable streaming
                        out_path
                    ], check=True, capture_output=True, timeout=120)
                    encoding_success = True
                    
                    encoding_progress.progress(1.0)
                    encoding_status.text("✅ Encoding complete!")
                    
                except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                    encoding_status.text("⚠️ ffmpeg not available, using fallback...")
                    encoding_progress.progress(0.7)
            
            # Method 3: Last resort - just use the AVI file (may not play in browser)
            if not encoding_success:
                import shutil
                out_path = temp_out_path.replace('.avi', '.mp4')
                shutil.copy(temp_out_path, out_path)
                encoding_progress.progress(1.0)
                encoding_status.text("⚠️ Video encoding limited - download the video for best playback")
                st.warning("⚠️ Video encoding limited - download the video for best playback")
            
            # Clean up temp AVI
            try:
                os.unlink(temp_out_path)
            except:
                pass

            try:
                os.unlink(input_path)
            except:
                pass

            summary = analyzer.get_summary()
            plot_buf = generate_plots(analyzer)
            pdf_buf = generate_pdf_report(summary, uploaded.name, plot_buf)
            csv_buf = export_to_csv(analyzer)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            
            video_bytes = None
            if os.path.exists(out_path):
                with open(out_path, 'rb') as f:
                    video_bytes = f.read()
            
            zip_buf = create_results_bundle(out_path, csv_buf, pdf_buf, timestamp)

            analyzer.close()

            try:
                os.unlink(out_path)
            except:
                pass

            st.success("✅ Analysis complete!")
            
            # Display video type information - User selected vs Auto-detected
            st.markdown("### 📹 Video Type")
            
            col_user, col_auto = st.columns(2)
            
            with col_user:
                user_ctx_icon = "🎥" if selected_camera == CameraView.SIDE else "👤"
                user_water_icon = "🤿" if selected_water == WaterPosition.UNDERWATER else "☀️"
                st.markdown(f"""
                <div style="background: rgba(34, 197, 94, 0.15); border-radius: 12px; padding: 16px; border-left: 4px solid #22c55e;">
                    <span style="color: #94a3b8; font-size: 12px; text-transform: uppercase;">Your Selection (Used for Analysis)</span>
                    <div style="font-size: 18px; font-weight: 600; color: #22c55e; margin-top: 4px;">
                        {user_ctx_icon} {selected_camera.value} &nbsp;•&nbsp; {user_water_icon} {selected_water.value}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            with col_auto:
                if summary.video_context:
                    ctx = summary.video_context
                    ctx_icon = "🎥" if ctx.camera_view == CameraView.SIDE else "👤" if ctx.camera_view == CameraView.FRONT else "🔝"
                    water_icon = "🤿" if ctx.water_position == WaterPosition.UNDERWATER else "☀️" if ctx.water_position == WaterPosition.ABOVE_WATER else "〰️"
                    confidence_color = "#22c55e" if ctx.confidence >= 0.7 else "#eab308" if ctx.confidence >= 0.5 else "#ef4444"
                    
                    # Check if auto-detection matches user selection
                    matches = (ctx.camera_view == selected_camera and ctx.water_position == selected_water)
                    match_icon = "✅" if matches else "⚠️"
                    border_color = "#22c55e" if matches else "#eab308"
                    
                    st.markdown(f"""
                    <div style="background: rgba(30, 41, 59, 0.8); border-radius: 12px; padding: 16px; border-left: 4px solid {border_color};">
                        <span style="color: #94a3b8; font-size: 12px; text-transform: uppercase;">Auto-Detection Result {match_icon}</span>
                        <div style="font-size: 18px; font-weight: 600; color: white; margin-top: 4px;">
                            {ctx_icon} {ctx.camera_view.value} &nbsp;•&nbsp; {water_icon} {ctx.water_position.value}
                        </div>
                        <div style="font-size: 12px; color: {confidence_color}; margin-top: 4px;">Confidence: {ctx.confidence*100:.0f}%</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if not matches:
                        st.caption("ℹ️ Auto-detection differs from your selection. Your selection is used for analysis.")
                else:
                    st.markdown("""
                    <div style="background: rgba(30, 41, 59, 0.8); border-radius: 12px; padding: 16px; border-left: 4px solid #64748b;">
                        <span style="color: #94a3b8; font-size: 12px;">Auto-Detection</span>
                        <div style="font-size: 14px; color: #64748b; margin-top: 4px;">Not enough data for detection</div>
                    </div>
                    """, unsafe_allow_html=True)

            # NEW: Render visual metrics component with body silhouettes
            st.subheader("📊 Technique Breakdown")
            metrics_for_viz = {
                'horizontal_deviation': summary.avg_horizontal_deviation,
                'vertical_drop': summary.avg_vertical_drop,
                'evf_angle': summary.avg_evf_angle,
                'dropped_elbow_pct': summary.dropped_elbow_pct,
                'body_roll': summary.avg_body_roll,
                'kick_depth': summary.avg_kick_depth,
                'kick_symmetry': summary.avg_kick_symmetry,
            }
            render_swim_metrics_component(metrics_for_viz, height=440)

            # Display score cards in columns
            col1, col2, col3 = st.columns(3)
            
            with col1:
                score_color = "#22c55e" if summary.avg_score >= 70 else "#eab308" if summary.avg_score >= 50 else "#ef4444"
                score_status = "Excellent" if summary.avg_score >= 80 else "Good" if summary.avg_score >= 70 else "Fair" if summary.avg_score >= 50 else "Needs Work"
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, rgba(6,182,212,0.2) 0%, rgba(37,99,235,0.2) 100%); border: 2px solid {score_color}; border-radius: 16px; padding: 20px; text-align: center;">
                    <h4 style="color: #94a3b8; margin: 0 0 8px 0; font-size: 14px;">OVERALL SCORE</h4>
                    <div style="font-size: 48px; font-weight: bold; color: {score_color};">{summary.avg_score:.1f}</div>
                    <div style="font-size: 12px; color: {score_color}; font-weight: 600;">{score_status}</div>
                    <div style="font-size: 11px; color: #64748b; margin-top: 8px;">🎯 Ideal: 70+ (Good) | 80+ (Excellent)</div>
                </div>
                """, unsafe_allow_html=True)

            with col2:
                align_color = "#22c55e" if summary.avg_vertical_drop <= 8 else "#eab308" if summary.avg_vertical_drop <= 15 else "#ef4444"
                align_status = "Streamlined" if summary.avg_vertical_drop <= 5 else "Good" if summary.avg_vertical_drop <= 8 else "Hip Drop" if summary.avg_vertical_drop <= 15 else "Sinking"
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, rgba(5,150,105,0.2) 0%, rgba(16,185,129,0.2) 100%); border: 2px solid {align_color}; border-radius: 16px; padding: 20px; text-align: center;">
                    <h4 style="color: #94a3b8; margin: 0 0 8px 0; font-size: 14px;">BODY ALIGNMENT</h4>
                    <div style="font-size: 48px; font-weight: bold; color: {align_color};">{summary.avg_vertical_drop:.1f}°</div>
                    <div style="font-size: 12px; color: {align_color}; font-weight: 600;">{align_status}</div>
                    <div style="font-size: 11px; color: #64748b; margin-top: 8px;">🎯 Ideal: &lt;8° (flat body position)</div>
                </div>
                """, unsafe_allow_html=True)

            with col3:
                evf_color = "#22c55e" if summary.dropped_elbow_pct <= 10 else "#eab308" if summary.dropped_elbow_pct <= 30 else "#ef4444"
                evf_status = "High Elbow" if summary.dropped_elbow_pct <= 10 else "Some Drop" if summary.dropped_elbow_pct <= 30 else "Dropped Elbow"
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, rgba(124,58,237,0.2) 0%, rgba(168,85,247,0.2) 100%); border: 2px solid {evf_color}; border-radius: 16px; padding: 20px; text-align: center;">
                    <h4 style="color: #94a3b8; margin: 0 0 8px 0; font-size: 14px;">EVF (CATCH)</h4>
                    <div style="font-size: 48px; font-weight: bold; color: {evf_color};">{summary.dropped_elbow_pct:.0f}%</div>
                    <div style="font-size: 12px; color: {evf_color}; font-weight: 600;">{evf_status}</div>
                    <div style="font-size: 11px; color: #64748b; margin-top: 8px;">🎯 Ideal: &lt;10% dropped elbow frames</div>
                </div>
                """, unsafe_allow_html=True)

            # Metrics row
            cols = st.columns(5)
            cols[0].metric("Stroke Rate", f"{summary.stroke_rate:.1f} spm")
            cols[1].metric("Breaths/min", f"{summary.breaths_per_min:.1f}")
            cols[2].metric("Avg Body Roll", f"{summary.avg_body_roll:.1f}°")
            cols[3].metric("Kick Status", summary.kick_status)
            cols[4].metric("Breaths in Pull", f"{summary.breaths_during_pull}", 
                          delta="Good" if summary.breaths_during_pull == 0 else "Reduce",
                          delta_color="normal" if summary.breaths_during_pull == 0 else "inverse")

            # Diagnostics section
            st.subheader("🎯 Coaching Insights")
            for diag in summary.diagnostics:
                if diag.startswith("✅"):
                    st.success(diag)
                elif diag.startswith("🚨") or diag.startswith("⚠️"):
                    st.error(diag)
                else:
                    st.warning(diag)

            # Best/Worst frames
            st.subheader("📸 Key Frames")
            col1, col2 = st.columns(2)
            with col1:
                if summary.best_frame_bytes:
                    st.image(summary.best_frame_bytes, caption="Best Pull Frame")
                else:
                    st.info("No best frame captured")
            with col2:
                if summary.worst_frame_bytes:
                    st.image(summary.worst_frame_bytes, caption="Worst Pull Frame")
                else:
                    st.info("No worst frame captured")

            # Video player - use st.video for cross-platform compatibility
            st.subheader("🎬 Annotated Video")
            if video_bytes:
                # st.video works better across platforms
                st.video(video_bytes, format="video/mp4")
                
                # Also provide download link for the video separately
                st.download_button(
                    "⬇️ Download Annotated Video",
                    video_bytes,
                    f"annotated_swim_{timestamp}.mp4",
                    "video/mp4"
                )

            # Download button
            st.download_button(
                "📦 Download Full Results (ZIP)",
                zip_buf,
                f"swim_analysis_{timestamp}.zip",
                "application/zip"
            )

        except Exception as e:
            st.error(f"Error during processing: {str(e)}")
            import traceback
            st.code(traceback.format_exc())

if __name__ == "__main__":
    main()

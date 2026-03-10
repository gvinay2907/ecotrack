from flask import (
    Flask, render_template, redirect,
    url_for, request, flash, send_file, jsonify
)

from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin,
    login_user, login_required,
    logout_user, current_user
)

from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
import smtplib
from email.message import EmailMessage
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import numpy as np
from sklearn.linear_model import LinearRegression, LogisticRegression

import cv2
import numpy as np
from werkzeug.utils import secure_filename
import os

# PDF
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter

# ---------------- LOAD ENV ----------------
load_dotenv()

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# ---------------- APP SETUP ----------------
app = Flask(__name__)
app.config['SECRET_KEY'] = 'sdgsecret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sdgos.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


# ---------------- MODELS ----------------

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(150))
    family_name = db.Column(db.String(150))
    members = db.Column(db.Integer, default=1)
    location = db.Column(db.String(100))
    location_type = db.Column(db.String(50), default="Urban")
    eco_points = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class UsageLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    date = db.Column(db.DateTime, default=datetime.utcnow)

    water = db.Column(db.Float)
    electricity = db.Column(db.Float)
    waste = db.Column(db.Float)
    co2 = db.Column(db.Float)
    score = db.Column(db.Float)

    water_co2 = db.Column(db.Float, default=0)
    energy_co2 = db.Column(db.Float, default=0)
    waste_co2 = db.Column(db.Float, default=0)

    user = db.relationship('User', backref=db.backref('logs', lazy=True))


# ---------------- USER LOADER ----------------

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==============================
# EMAIL ALERT FUNCTIONS (BUILT-IN)
# ==============================

def send_email_with_html(to_email, subject, html_content):
    """Send HTML email"""
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        print("⚠️ Email not configured")
        return False
    
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f'EcoTrack Pro <{EMAIL_ADDRESS}>'
        msg['To'] = to_email
        
        # Plain text fallback
        text = f"EcoTrack Pro Notification\n\nView this email in HTML for the best experience.\n\nDashboard: http://localhost:5000"
        
        part1 = MIMEText(text, 'plain')
        part2 = MIMEText(html_content, 'html')
        
        msg.attach(part1)
        msg.attach(part2)
        
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
        
        print(f"✅ Email sent to {to_email}")
        return True
        
    except Exception as e:
        print(f"❌ Email error: {e}")
        return False


def send_high_risk_alert(user_email, score, co2, risk_level, recommendations):
    """Send critical sustainability alert"""
    
    html = f"""
    <html>
    <head>
        <style>
            body {{ margin: 0; padding: 0; font-family: Arial, sans-serif; background: #0a0e1a; }}
            .container {{ max-width: 600px; margin: 40px auto; background: rgba(255,255,255,0.05); border-radius: 24px; overflow: hidden; }}
            .header {{ background: linear-gradient(135deg, #ef4444, #dc2626); padding: 40px; text-align: center; color: white; }}
            .content {{ padding: 40px; color: white; }}
            .metric {{ background: rgba(255,255,255,0.08); border-radius: 16px; padding: 20px; margin: 20px 0; }}
            .metric-value {{ font-size: 32px; font-weight: 700; color: #ef4444; }}
            .recommendation {{ background: rgba(255,255,255,0.05); border-left: 3px solid #10b981; padding: 15px; margin: 10px 0; }}
            .button {{ display: inline-block; padding: 15px 30px; background: #10b981; color: white; text-decoration: none; border-radius: 12px; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 style="font-size: 64px; margin: 0;">🚨</h1>
                <h2>Critical Sustainability Alert</h2>
            </div>
            <div class="content">
                <div style="background: rgba(239,68,68,0.15); border-left: 4px solid #ef4444; padding: 20px; border-radius: 12px;">
                    <h3 style="color: #fca5a5; margin-top: 0;">⚠️ Immediate Action Required</h3>
                    <p>Your household's environmental impact has reached critical levels.</p>
                </div>
                
                <div class="metric">
                    <div style="color: rgba(255,255,255,0.6); margin-bottom: 8px;">Sustainability Score</div>
                    <div class="metric-value">{score}/100</div>
                </div>
                
                <div class="metric">
                    <div style="color: rgba(255,255,255,0.6); margin-bottom: 8px;">Daily CO₂ Emissions</div>
                    <div class="metric-value">{co2} kg</div>
                </div>
                
                <h3 style="color: #fbbf24;">🎯 Immediate Actions:</h3>
                {''.join([f'<div class="recommendation">✓ {rec}</div>' for rec in recommendations[:4]])}
                
                <div style="text-align: center;">
                    <a href="http://localhost:5000/dashboard" class="button">View Detailed Analysis →</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    return send_email_with_html(
        user_email,
        '🚨 Critical Sustainability Alert - Immediate Action Required',
        html
    )


def send_achievement_alert(user_email, achievement_name, description, points_earned, total_points, badge="🏆"):
    """Send achievement notification"""
    
    html = f"""
    <html>
    <head>
        <style>
            body {{ margin: 0; padding: 0; font-family: Arial, sans-serif; background: #0a0e1a; }}
            .container {{ max-width: 600px; margin: 40px auto; background: rgba(255,255,255,0.05); border-radius: 24px; overflow: hidden; }}
            .header {{ background: linear-gradient(135deg, #10b981, #059669); padding: 40px; text-align: center; color: white; }}
            .content {{ padding: 40px; color: white; text-align: center; }}
            .badge {{ font-size: 80px; margin: 20px 0; }}
            .metric {{ background: rgba(16,185,129,0.2); border-radius: 16px; padding: 20px; margin: 20px 0; }}
            .button {{ display: inline-block; padding: 15px 30px; background: #10b981; color: white; text-decoration: none; border-radius: 12px; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 style="font-size: 64px; margin: 0;">🎉</h1>
                <h2>Achievement Unlocked!</h2>
            </div>
            <div class="content">
                <div class="badge">{badge}</div>
                <h2 style="color: #34d399;">{achievement_name}</h2>
                <p style="font-size: 18px;">{description}</p>
                
                <div class="metric">
                    <h3 style="margin: 10px 0;">+{points_earned} Eco Points</h3>
                    <p>Total: {total_points} points</p>
                </div>
                
                <a href="http://localhost:5000/carbon-wallet" class="button">View Your Progress →</a>
            </div>
        </div>
    </body>
    </html>
    """
    
    return send_email_with_html(
        user_email,
        f'🎉 Achievement Unlocked: {achievement_name}',
        html
    )


def send_weekly_report_email(user_email, avg_score, total_co2, entries, insights, week_start, week_end):
    """Send weekly summary report"""
    
    html = f"""
    <html>
    <head>
        <style>
            body {{ margin: 0; padding: 0; font-family: Arial, sans-serif; background: #0a0e1a; }}
            .container {{ max-width: 600px; margin: 40px auto; background: rgba(255,255,255,0.05); border-radius: 24px; overflow: hidden; }}
            .header {{ background: linear-gradient(135deg, #3b82f6, #2563eb); padding: 40px; text-align: center; color: white; }}
            .content {{ padding: 40px; color: white; }}
            .stat {{ background: rgba(255,255,255,0.08); border-radius: 12px; padding: 15px; margin: 10px 0; text-align: center; }}
            .insight {{ background: rgba(255,255,255,0.05); border-left: 3px solid #10b981; padding: 15px; margin: 10px 0; }}
            .button {{ display: inline-block; padding: 15px 30px; background: #10b981; color: white; text-decoration: none; border-radius: 12px; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 style="font-size: 64px; margin: 0;">📊</h1>
                <h2>Your Weekly Impact Report</h2>
                <p>Week of {week_start} - {week_end}</p>
            </div>
            <div class="content">
                <div class="stat">
                    <h3>Average Score</h3>
                    <h2 style="color: #10b981; margin: 10px 0;">{avg_score}/100</h2>
                </div>
                
                <div class="stat">
                    <h3>Total CO₂</h3>
                    <h2 style="color: #fbbf24; margin: 10px 0;">{total_co2} kg</h2>
                </div>
                
                <div class="stat">
                    <h3>Entries Logged</h3>
                    <h2 style="color: #3b82f6; margin: 10px 0;">{entries}</h2>
                </div>
                
                <h3 style="color: #10b981; margin-top: 30px;">📈 Weekly Insights:</h3>
                {''.join([f'<div class="insight">{insight}</div>' for insight in insights])}
                
                <div style="text-align: center;">
                    <a href="http://localhost:5000/analytics" class="button">View Full Analytics →</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    return send_email_with_html(
        user_email,
        f'📊 Your Weekly Sustainability Report - {week_start}',
        html
    )


# ==============================
# WASTE FILL LEVEL ESTIMATION
# ==============================

def estimate_fill_level(image_path):
    img = cv2.imread(image_path)

    if img is None:
        return 0

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY_INV)

    total_pixels = thresh.shape[0] * thresh.shape[1]
    filled_pixels = cv2.countNonZero(thresh)

    fill_ratio = filled_pixels / total_pixels

    return min(max(fill_ratio, 0), 1)


def calculate_waste_from_image(image_path, bin_volume_liters=10):
    fill_ratio = estimate_fill_level(image_path)
    density = 0.15
    waste_kg = bin_volume_liters * fill_ratio * density

    return round(waste_kg, 2), round(fill_ratio * 100, 1)


# ---------------- AI RECOMMENDATION ENGINE ----------------

def generate_family_recommendations(user, water, electricity, waste):
    """Enhanced recommendations for premium UI"""
    recommendations = []

    water_limit = 135 * user.members
    energy_limit = 90 * user.members
    waste_limit = 0.5 * user.members

    # WATER
    if water > water_limit * 1.2:
        recommendations.append(
            f"🚨 Critical: Water usage is {round((water/water_limit - 1)*100)}% above target. Install low-flow fixtures immediately."
        )
    elif water > water_limit:
        recommendations.append(
            f"⚠️ Water usage is {round((water/water_limit - 1)*100)}% above target. Consider shorter showers and fix leaks."
        )
    else:
        recommendations.append(
            f"✅ Excellent water management! You're {round((1 - water/water_limit)*100)}% below target."
        )

    # ELECTRICITY
    if electricity > energy_limit * 1.2:
        recommendations.append(
            f"🚨 Critical: Energy consumption is {round((electricity/energy_limit - 1)*100)}% over limit. Switch to LED bulbs and energy-efficient appliances."
        )
    elif electricity > energy_limit:
        recommendations.append(
            f"⚠️ Energy usage is {round((electricity/energy_limit - 1)*100)}% high. Unplug devices when not in use."
        )
    else:
        recommendations.append(
            f"✅ Great energy efficiency! You're {round((1 - electricity/energy_limit)*100)}% under target."
        )

    # WASTE
    if waste > waste_limit * 1.2:
        recommendations.append(
            f"🚨 Critical: Waste generation is {round((waste/waste_limit - 1)*100)}% excessive. Start composting and improve recycling."
        )
    elif waste > waste_limit:
        recommendations.append(
            f"⚠️ Waste is {round((waste/waste_limit - 1)*100)}% above sustainable levels. Reduce single-use plastics."
        )
    else:
        recommendations.append(
            f"✅ Outstanding waste management! You're {round((1 - waste/waste_limit)*100)}% below target."
        )

    recommendations.append("💡 Pro Tip: Track daily to maintain your streak and earn bonus points!")

    return recommendations


def generate_individual_recommendations(water, electricity, waste, members):
    """Enhanced individual recommendations"""
    recommendations = []

    if members > 0:
        per_water = water / members
        per_energy = electricity / members
        per_waste = waste / members
    else:
        per_water = per_energy = per_waste = 0

    individual_water_limit = 135
    individual_energy_limit = 90
    individual_waste_limit = 0.5

    if per_water > individual_water_limit:
        recommendations.append(
            f"💧 Your personal water footprint: {round(per_water)} L/day. Reduce by {round(per_water - individual_water_limit)} L to reach optimal."
        )
    else:
        recommendations.append(
            f"✅ Your water usage ({round(per_water)} L/day) is sustainable!"
        )

    if per_energy > individual_energy_limit:
        recommendations.append(
            f"⚡ Your energy consumption: {round(per_energy)} kWh. Cut {round(per_energy - individual_energy_limit)} kWh to improve score."
        )
    else:
        recommendations.append(
            f"✅ Your energy habits ({round(per_energy)} kWh/day) are excellent!"
        )

    if per_waste > individual_waste_limit:
        recommendations.append(
            f"🗑️ Personal waste: {round(per_waste, 2)} kg/day. Reduce by {round(per_waste - individual_waste_limit, 2)} kg for better impact."
        )
    else:
        recommendations.append(
            f"✅ Your waste generation ({round(per_waste, 2)} kg/day) is optimal!"
        )

    recommendations.append("🎯 Challenge: Reduce your top impact category by 10% this week!")

    return recommendations


# ---------------- HELPER FUNCTIONS FOR PREMIUM UI ----------------

def calculate_user_rank(user_id):
    """Calculate user's global rank"""
    users = User.query.order_by(User.eco_points.desc()).all()
    for idx, user in enumerate(users, 1):
        if user.id == user_id:
            return idx
    return 0


def calculate_days_active(user):
    """Calculate days since user joined"""
    if user.created_at:
        delta = datetime.utcnow() - user.created_at
        return delta.days
    return 0


def calculate_streak(user_id):
    """Calculate consecutive days of logging"""
    logs = UsageLog.query.filter_by(user_id=user_id)\
        .order_by(UsageLog.date.desc()).all()
    
    if not logs:
        return 0
    
    streak = 1
    for i in range(len(logs) - 1):
        diff = (logs[i].date.date() - logs[i+1].date.date()).days
        if diff == 1:
            streak += 1
        else:
            break
    
    return streak


def get_analytics_summary(user_id):
    """Get summary analytics for dashboard"""
    logs = UsageLog.query.filter_by(user_id=user_id).all()
    
    if not logs:
        return {
            'avg_score': 0,
            'total_co2': 0,
            'total_co2_saved': 0,
            'best_day_score': 0,
            'improvement': 0
        }
    
    recent_30 = logs[-30:] if len(logs) >= 30 else logs
    recent_60 = logs[-60:-30] if len(logs) >= 60 else []
    
    avg_score = sum(log.score for log in recent_30) / len(recent_30)
    total_co2 = sum(log.co2 for log in logs)
    best_day_score = max(log.score for log in logs)
    
    if recent_60:
        prev_avg = sum(log.score for log in recent_60) / len(recent_60)
        improvement = round(((avg_score - prev_avg) / prev_avg) * 100, 1)
    else:
        improvement = 0
    
    baseline_co2_per_day = 25
    days_logged = len(logs)
    baseline_total = baseline_co2_per_day * days_logged
    total_co2_saved = max(0, baseline_total - total_co2)
    
    return {
        'avg_score': round(avg_score, 1),
        'total_co2': round(total_co2, 2),
        'total_co2_saved': round(total_co2_saved, 2),
        'best_day_score': round(best_day_score, 1),
        'improvement': improvement
    }


def adaptive_adjustment(user_id, base_score):
    logs = UsageLog.query.filter_by(user_id=user_id)\
        .order_by(UsageLog.date.desc()).limit(7).all()

    if len(logs) < 5:
        return base_score

    avg_score = sum(log.score for log in logs) / len(logs)

    if avg_score > 80:
        base_score += 2
    elif avg_score < 50:
        base_score -= 3

    return max(0, min(100, base_score))


# ---------------- ROUTES ----------------

@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        existing_user = User.query.filter_by(email=request.form['email']).first()
        if existing_user:
            flash("Email already registered. Please login.", "warning")
            return redirect(url_for("login"))

        user = User(
            email=request.form['email'],
            password=request.form['password'],
            family_name=request.form.get('family_name'),
            members=int(request.form.get('members', 1)),
            location=request.form.get('location'),
            location_type=request.form.get('location_type', 'Urban'),
            eco_points=0,
            created_at=datetime.utcnow()
        )

        db.session.add(user)
        db.session.commit()

        flash("Account created successfully! Welcome to EcoTrack Pro!", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(email=request.form['email']).first()

        if user and user.password == request.form['password']:
            login_user(user)
            flash(f"Welcome back, {user.family_name}!", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid credentials. Please try again.", "danger")

    return render_template("login.html")


@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    analytics = get_analytics_summary(current_user.id)
    
    water = electricity = waste = score = co2 = car_km = 0
    risk_level = "Not Calculated"
    
    individual_co2 = 0
    individual_score = 0
    individual_risk_level = ""
    
    family_recommendations = []
    individual_recommendations = []
    
    water_co2 = energy_co2 = waste_co2 = 0
    fill_percent = 0
    waste_type = "Mixed"

    if request.method == "POST":
        water = float(request.form.get("water", 0))
        electricity = float(request.form.get("electricity", 0))

        use_ai = request.form.get("use_ai_detection") == "true"
        
        if use_ai:
            uploaded_file = request.files.get("waste_image")
            if uploaded_file and uploaded_file.filename != "":
                filename = secure_filename(uploaded_file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                uploaded_file.save(filepath)
                waste, fill_percent = calculate_waste_from_image(filepath)
                waste_type = "AI Detected"
            else:
                waste = 0
                flash("AI detection selected but no photo was uploaded.", "warning")
        else:
            waste = float(request.form.get("waste") or 0)
            waste_type = "Manual Entry"
            fill_percent = 0

        water_co2 = round(water * 0.0003, 2)
        energy_co2 = round(electricity * 0.85, 2)
        waste_co2 = round(waste * 0.5, 2)
        co2 = round(water_co2 + energy_co2 + waste_co2, 2)
        
        # Real-World Impact Logic: Driving Equivalency (1 km ≈ 0.2 kg CO2)
        car_km = round(co2 / 0.2, 1)

        members = current_user.members if current_user.members > 0 else 1

        base_score = 100 - ((water * 0.02) + (electricity * 1.2) + (waste * 2))
        base_score = max(0, min(100, base_score))
        score = adaptive_adjustment(current_user.id, base_score)

        if score >= 75:
            risk_level = "LOW - Sustainable"
        elif score >= 50:
            risk_level = "MODERATE - Needs Attention"
        else:
            risk_level = "HIGH - Critical"

        individual_co2 = round(co2 / members, 2)
        individual_score = round(score, 2)

        if individual_score >= 75:
            individual_risk_level = "LOW - Sustainable"
        elif individual_score >= 50:
            individual_risk_level = "MODERATE"
        else:
            individual_risk_level = "HIGH - Critical"

        family_recommendations = generate_family_recommendations(
            current_user, water, electricity, waste
        )
        individual_recommendations = generate_individual_recommendations(
            water, electricity, waste, members
        )

        points_earned = 15
        if score >= 75:
            points_earned += 10
        if fill_percent > 0:
            points_earned += 5
        
        current_user.eco_points += points_earned
        
        log = UsageLog(
            user_id=current_user.id,
            water=water,
            electricity=electricity,
            waste=waste,
            co2=co2,
            score=score,
            water_co2=water_co2,
            energy_co2=energy_co2,
            waste_co2=waste_co2
        )

        db.session.add(log)
        db.session.commit()
        
        flash(f"Entry logged successfully via {waste_type}! Impact equivalent to {car_km}km drive.", "success")
        
        if score < 50:
            try:
                send_high_risk_alert(
                    user_email=current_user.email,
                    score=round(score, 1),
                    co2=co2,
                    risk_level=risk_level,
                    recommendations=family_recommendations[:3]
                )
                flash("⚠️ High risk alert email sent!", "warning")
            except Exception as e:
                print(f"Email failed: {e}")
        
        if current_user.eco_points == 100:
            send_achievement_alert(current_user.email, "First 100 Points", "First 100 points!", 100, current_user.eco_points, "🌟")
        elif current_user.eco_points == 500:
            send_achievement_alert(current_user.email, "Eco Warrior", "500 eco points!", 500, current_user.eco_points, "🏆")
        elif current_user.eco_points == 1000:
            send_achievement_alert(current_user.email, "Sustainability Champion", "1000 points!", 1000, current_user.eco_points, "👑")
        
        streak = calculate_streak(current_user.id)
        if streak == 7:
            send_achievement_alert(current_user.email, "7-Day Streak Master", "7 consecutive days!", 50, current_user.eco_points, "🔥")
            flash("🔥 7-day streak unlocked!", "success")

    return render_template(
        "dashboard.html",
        water=water,
        electricity=electricity,
        waste=waste,
        waste_type=waste_type,
        score=score,
        co2=co2,
        car_km=car_km,
        co2_saved=analytics['total_co2_saved'],
        water_co2=water_co2,
        energy_co2=energy_co2,
        waste_co2=waste_co2,
        risk_level=risk_level,
        individual_co2=individual_co2,
        individual_score=individual_score,
        individual_risk_level=individual_risk_level,
        family_recommendations=family_recommendations,
        individual_recommendations=individual_recommendations,
        fill_percent=fill_percent,
        daily_avg=analytics['avg_score']
    )


@app.route("/analytics")
@login_required
def analytics():
    logs = UsageLog.query.filter_by(user_id=current_user.id)\
        .order_by(UsageLog.date.desc()).limit(90).all()

    logs = logs[::-1]

    dates = [log.date.strftime("%d %b") for log in logs]
    scores = [log.score for log in logs]
    co2_values = [log.co2 for log in logs]

    total_water = sum(log.water_co2 for log in logs)
    total_energy = sum(log.energy_co2 for log in logs)
    total_waste = sum(log.waste_co2 for log in logs)
    
    analytics_summary = get_analytics_summary(current_user.id)

    return render_template(
        "analytics.html",
        dates=dates,
        scores=scores,
        co2_values=co2_values,
        total_water=total_water,
        total_energy=total_energy,
        total_waste=total_waste,
        avg_score=analytics_summary['avg_score'],
        total_co2=analytics_summary['total_co2'],
        best_day_score=analytics_summary['best_day_score'],
        improvement=analytics_summary['improvement']
    )


@app.route("/carbon-wallet")
@login_required
def carbon_wallet():
    logs = UsageLog.query.filter_by(user_id=current_user.id).all()
    total_entries = len(logs)
    
    current_month = datetime.utcnow().month
    monthly_logs = [log for log in logs if log.date.month == current_month]
    monthly_earned = len(monthly_logs) * 15
    
    total_earned = total_entries * 15
    total_redeemed = total_earned - current_user.eco_points
    
    rank = calculate_user_rank(current_user.id)

    return render_template(
        "carbon_wallet.html",
        eco_points=current_user.eco_points,
        total_entries=total_entries,
        total_earned=total_earned,
        total_redeemed=max(0, total_redeemed),
        monthly_earned=monthly_earned,
        rank=rank
    )


@app.route("/sdg-impact")
@login_required
def sdg_impact():
    logs = UsageLog.query.filter_by(user_id=current_user.id).all()

    total_water = sum(log.water for log in logs)
    total_energy = sum(log.electricity for log in logs)
    total_waste = sum(log.waste for log in logs)
    total_co2 = sum(log.co2 for log in logs)
    
    innovation_score = 72
    biodiversity_score = 65
    
    your_score = sum(log.score for log in logs) / len(logs) if logs else 0
    
    return render_template(
        "sdg_impact.html",
        total_water=total_water,
        total_energy=total_energy,
        total_waste=total_waste,
        total_co2=total_co2,
        innovation_score=innovation_score,
        biodiversity_score=biodiversity_score,
        your_score=round(your_score, 1),
        total_impact_score=8.7
    )


@app.route("/weekly-report")
@login_required
def weekly_report():
    logs = UsageLog.query.filter_by(user_id=current_user.id)\
        .order_by(UsageLog.date.desc()).limit(14).all()

    logs = logs[::-1]

    if len(logs) < 7:
        flash("Not enough data for weekly analysis. Keep logging!", "info")
        return render_template(
            "weekly_report.html",
            avg_score=0,
            total_co2=0,
            weekly_insights=["Log daily entries for 7 days to unlock weekly insights!"]
        )

    current_week = logs[-7:]
    previous_week = logs[:-7] if len(logs) >= 14 else []

    curr_avg_water = sum(l.water for l in current_week) / len(current_week)
    prev_avg_water = sum(l.water for l in previous_week) / len(previous_week) if previous_week else curr_avg_water

    curr_avg_energy = sum(l.electricity for l in current_week) / len(current_week)
    prev_avg_energy = sum(l.electricity for l in previous_week) / len(previous_week) if previous_week else curr_avg_energy

    curr_avg_waste = sum(l.waste for l in current_week) / len(current_week)
    prev_avg_waste = sum(l.waste for l in previous_week) / len(previous_week) if previous_week else curr_avg_waste

    avg_score = sum(l.score for l in current_week) / len(current_week)
    total_co2 = sum(l.co2 for l in current_week)

    weekly_insights = []

    water_change = ((curr_avg_water - prev_avg_water) / prev_avg_water) * 100 if prev_avg_water else 0
    if water_change > 5:
        weekly_insights.append(f"💧 Water usage increased by {round(water_change,1)}%")
    elif water_change < -5:
        weekly_insights.append(f"✅ Water usage decreased by {abs(round(water_change,1))}%")

    energy_change = ((curr_avg_energy - prev_avg_energy) / prev_avg_energy) * 100 if prev_avg_energy else 0
    if energy_change > 5:
        weekly_insights.append(f"⚡ Electricity increased by {round(energy_change,1)}%")
    elif energy_change < -5:
        weekly_insights.append(f"✅ Electricity decreased by {abs(round(energy_change,1))}%")

    waste_change = ((curr_avg_waste - prev_avg_waste) / prev_avg_waste) * 100 if prev_avg_waste else 0
    if waste_change > 5:
        weekly_insights.append(f"🗑️ Waste increased by {round(waste_change,1)}%")
    elif waste_change < -5:
        weekly_insights.append(f"✅ Waste reduced by {abs(round(waste_change,1))}%")

    if avg_score < 50:
        weekly_insights.append("⚠️ Performance needs improvement")
    elif avg_score > 75:
        weekly_insights.append("🌟 Outstanding performance")

    if not weekly_insights:
        weekly_insights.append("📊 Metrics are stable compared to last week")
    
    week_start = (datetime.utcnow() - timedelta(days=7)).strftime("%b %d")
    week_end = datetime.utcnow().strftime("%b %d, %Y")
    
    try:
        send_weekly_report_email(current_user.email, round(avg_score, 1), round(total_co2, 1), len(current_week), weekly_insights, week_start, week_end)
        flash("📧 Weekly report sent to your email!", "info")
    except Exception as e:
        print(f"Weekly email failed: {e}")

    return render_template("weekly_report.html", avg_score=round(avg_score,2), total_co2=round(total_co2,2), weekly_insights=weekly_insights)


@app.route("/leaderboard")
@login_required
def leaderboard():
    users = User.query.order_by(User.eco_points.desc()).limit(100).all()
    your_rank = calculate_user_rank(current_user.id)
    if your_rank > 1:
        user_above = User.query.order_by(User.eco_points.desc()).offset(your_rank - 2).first()
        points_to_next = user_above.eco_points - current_user.eco_points + 1
    else:
        points_to_next = 0
    
    total_users = User.query.count()
    all_logs = UsageLog.query.all()
    global_co2_saved = sum(log.co2 for log in all_logs) * 0.3
    
    top_10_count = max(1, total_users // 10)
    top_10_user = User.query.order_by(User.eco_points.desc()).offset(top_10_count - 1).first()
    top_10_threshold = top_10_user.eco_points if top_10_user else 0
    
    return render_template("leaderboard.html", users=users, your_rank=your_rank, points_to_next=points_to_next, total_users=total_users, global_co2_saved=round(global_co2_saved, 0), top_10_threshold=top_10_threshold)


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        current_user.family_name = request.form.get("family_name")
        current_user.members = int(request.form.get("members", 1))
        current_user.location = request.form.get("location")
        current_user.location_type = request.form.get("location_type", "Urban")
        db.session.commit()
        flash("Profile Updated Successfully!", "success")
        return redirect(url_for("profile"))

    days_active = calculate_days_active(current_user)
    streak = calculate_streak(current_user.id)
    total_entries = len(current_user.logs)
    analytics = get_analytics_summary(current_user.id)
    global_rank = calculate_user_rank(current_user.id)
    member_since = current_user.created_at.strftime("%b %Y") if current_user.created_at else "Recently"

    return render_template("profile.html", days_active=days_active, streak=streak, total_entries=total_entries, total_co2_saved=analytics['total_co2_saved'], global_rank=global_rank, member_since=member_since)


@app.route("/report")
@login_required
def report():
    filename = f"EcoTrack_Report_{current_user.family_name}_{datetime.now().strftime('%Y%m%d')}.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []
    elements.append(Paragraph(f"EcoTrack Pro - Sustainability Report", styles["Title"]))
    elements.append(Spacer(1, 0.3 * inch))
    elements.append(Paragraph(f"Family: {current_user.family_name}", styles["Heading2"]))
    analytics = get_analytics_summary(current_user.id)
    elements.append(Paragraph(f"Average Score: {analytics['avg_score']}", styles["Normal"]))
    elements.append(Paragraph(f"Total CO₂ Saved: {analytics['total_co2_saved']} kg", styles["Normal"]))
    doc.build(elements)
    return send_file(filename, as_attachment=True)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("login"))


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
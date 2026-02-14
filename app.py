from flask import Flask, render_template, request, redirect, session
from flask_socketio import SocketIO, emit, join_room
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)
app.secret_key = "railway_secret"

socketio = SocketIO(app, async_mode="eventlet")

# ==========================
# DATABASE CONFIG
# ==========================

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://")

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ==========================
# MODELS
# ==========================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    application_number = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))


class Profile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    about = db.Column(db.Text)
    linkedin = db.Column(db.String(200))
    github = db.Column(db.String(200))
    skills_teach = db.Column(db.String(200))
    skills_learn = db.Column(db.String(200))


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer)
    receiver_id = db.Column(db.Integer)
    message = db.Column(db.Text)

# Create tables
with app.app_context():
    db.create_all()

# ==========================
# ROUTES
# ==========================

@app.route("/")
def home():
    return redirect("/login")

# SIGNUP
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name")
        app_no = request.form.get("application_number")
        password = request.form.get("password")

        if User.query.filter_by(application_number=app_no).first():
            return "Application number already exists!"

        user = User(name=name, application_number=app_no, password=password)
        db.session.add(user)
        db.session.commit()

        return redirect("/login")

    return render_template("signup.html")

# LOGIN
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        app_no = request.form.get("application_number")
        password = request.form.get("password")

        user = User.query.filter_by(
            application_number=app_no,
            password=password
        ).first()

        if user:
            session["user_id"] = user.id
            session["name"] = user.name
            return redirect("/dashboard")

        return "Invalid credentials"

    return render_template("login.html")

# DASHBOARD
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    users = User.query.filter(User.id != session["user_id"]).all()

    return render_template(
        "dashboard.html",
        name=session["name"],
        users=users
    )

# PROFILE
@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "user_id" not in session:
        return redirect("/login")

    profile = Profile.query.filter_by(user_id=session["user_id"]).first()

    if request.method == "POST":
        about = request.form.get("about")
        linkedin = request.form.get("linkedin")
        github = request.form.get("github")
        skills_teach = request.form.get("skills_teach")
        skills_learn = request.form.get("skills_learn")

        if not profile:
            profile = Profile(user_id=session["user_id"])

        profile.about = about
        profile.linkedin = linkedin
        profile.github = github
        profile.skills_teach = skills_teach
        profile.skills_learn = skills_learn

        db.session.add(profile)
        db.session.commit()

    return render_template("profile.html", profile=profile)

# CHAT
@app.route("/chat/<int:receiver_id>")
def chat(receiver_id):
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    messages = Message.query.filter(
        ((Message.sender_id == user_id) & (Message.receiver_id == receiver_id)) |
        ((Message.sender_id == receiver_id) & (Message.receiver_id == user_id))
    ).all()

    room = f"{min(user_id, receiver_id)}_{max(user_id, receiver_id)}"

    return render_template(
        "chat.html",
        messages=messages,
        user_id=user_id,
        receiver_id=receiver_id,
        room=room
    )

@socketio.on("join_room")
def handle_join(data):
    join_room(data["room"])

@socketio.on("send_message")
def handle_message(data):
    msg = Message(
        sender_id=data["sender_id"],
        receiver_id=data["receiver_id"],
        message=data["message"]
    )

    db.session.add(msg)
    db.session.commit()

    emit("receive_message", data, room=data["room"])

# LOGOUT
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# RUN
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port)

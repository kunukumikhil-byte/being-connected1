from flask import Flask, render_template, request, redirect, session
from flask_socketio import SocketIO, emit, join_room
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "railway_secret_key"

socketio = SocketIO(app, async_mode="eventlet")

DB_PATH = "database.db"

# ==============================
# DATABASE INITIALIZATION
# ==============================

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        application_number TEXT UNIQUE,
        password TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        about TEXT,
        skills_teach TEXT,
        skills_learn TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id INTEGER,
        receiver_id INTEGER,
        message TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ==============================
# HOME
# ==============================

@app.route("/")
def home():
    return redirect("/login")

# ==============================
# SIGNUP
# ==============================

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name")
        app_no = request.form.get("application_number")
        password = request.form.get("password")

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        try:
            c.execute(
                "INSERT INTO users (name, application_number, password) VALUES (?, ?, ?)",
                (name, app_no, password)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return "Application number already exists!"

        conn.close()
        return redirect("/login")

    return render_template("signup.html")

# ==============================
# LOGIN
# ==============================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        app_no = request.form.get("application_number")
        password = request.form.get("password")

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        c.execute(
            "SELECT * FROM users WHERE application_number=? AND password=?",
            (app_no, password)
        )

        user = c.fetchone()
        conn.close()

        if user:
            session["user_id"] = user[0]
            session["name"] = user[1]
            return redirect("/dashboard")

        return "Invalid credentials"

    return render_template("login.html")

# ==============================
# DASHBOARD
# ==============================

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Show all other users
    c.execute("SELECT id, name FROM users WHERE id != ?", (session["user_id"],))
    users = c.fetchall()

    conn.close()

    return render_template(
        "dashboard.html",
        name=session["name"],
        users=users
    )

# ==============================
# PROFILE
# ==============================

@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    if request.method == "POST":
        about = request.form.get("about")
        skills_teach = request.form.get("skills_teach")
        skills_learn = request.form.get("skills_learn")

        # Remove old profile
        c.execute("DELETE FROM profiles WHERE user_id=?", (session["user_id"],))

        # Insert new profile
        c.execute(
            "INSERT INTO profiles (user_id, about, skills_teach, skills_learn) VALUES (?, ?, ?, ?)",
            (session["user_id"], about, skills_teach, skills_learn)
        )

        conn.commit()

    c.execute("SELECT * FROM profiles WHERE user_id=?", (session["user_id"],))
    profile_data = c.fetchone()

    conn.close()

    return render_template("profile.html", profile=profile_data)

# ==============================
# CHAT
# ==============================

@app.route("/chat/<int:receiver_id>")
def chat(receiver_id):
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        SELECT sender_id, message FROM messages
        WHERE (sender_id=? AND receiver_id=?)
        OR (sender_id=? AND receiver_id=?)
        ORDER BY id ASC
    """, (user_id, receiver_id, receiver_id, user_id))

    messages = c.fetchall()
    conn.close()

    room = f"{min(user_id, receiver_id)}_{max(user_id, receiver_id)}"

    return render_template(
        "chat.html",
        messages=messages,
        user_id=user_id,
        receiver_id=receiver_id,
        room=room
    )

# ==============================
# SOCKET EVENTS
# ==============================

@socketio.on("join_room")
def handle_join(data):
    join_room(data["room"])

@socketio.on("send_message")
def handle_message(data):
    sender_id = data["sender_id"]
    receiver_id = data["receiver_id"]
    message = data["message"]
    room = data["room"]

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute(
        "INSERT INTO messages (sender_id, receiver_id, message) VALUES (?, ?, ?)",
        (sender_id, receiver_id, message)
    )

    conn.commit()
    conn.close()

    emit("receive_message", data, room=room)

# ==============================
# LOGOUT
# ==============================

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ==============================
# RUN (RAILWAY READY)
# ==============================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port)


import csv
import io
import json
import os
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (
    Flask, flash, redirect, render_template,
    request, session, url_for, make_response
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get(
    "SECRET_KEY", "change-this-secret-key-before-deployment"
)

DB_PATH = os.path.join(os.path.dirname(__file__), "choicecraft.db")


def db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database():
    with db_connection() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS comparisons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                data_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
        db.commit()


def login_required(view):
    @wraps(view)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return decorated


# AUTOMATIC EVALUATION ENGINE

def evaluate(payload):

    title = str(payload.get("title", "")).strip()
    criteria = payload.get("criteria", [])
    alternatives = payload.get("alternatives", [])

    if not title:
        raise ValueError("Enter a comparison title.")

    if not isinstance(criteria, list) or not 2 <= len(criteria) <= 8:
        raise ValueError("Add between 2 and 8 criteria.")

    if not isinstance(alternatives, list) or not 2 <= len(alternatives) <= 10:
        raise ValueError("Add between 2 and 10 alternatives.")

    clean_criteria = []
    total_weight = 0
    criterion_names = set()

    for item in criteria:
        name = str(item.get("name", "")).strip()
        kind = str(item.get("kind", "")).lower()

        try:
            weight = float(item.get("weight", 0))
        except (TypeError, ValueError):
            raise ValueError("Weights must be numeric.")

        if not name or name.lower() in criterion_names:
            raise ValueError("Criterion names must be unique.")

        if kind not in ("benefit", "cost"):
            raise ValueError("Choose Benefit or Cost.")

        if weight <= 0:
            raise ValueError("Weights must be greater than zero.")

        criterion_names.add(name.lower())
        total_weight += weight

        clean_criteria.append({
            "name": name,
            "kind": kind,
            "weight": weight
        })

    # Normalize weights
    for criterion in clean_criteria:
        criterion["normalized_weight"] = (
            criterion["weight"] / total_weight
        )

    clean_alternatives = []
    alternative_names = set()

    for item in alternatives:
        name = str(item.get("name", "")).strip()
        values = item.get("values", [])

        if not name or name.lower() in alternative_names:
            raise ValueError("Alternative names must be unique.")

        if not isinstance(values, list) or len(values) != len(clean_criteria):
            raise ValueError("Enter one value for every criterion.")

        parsed_values = []

        for value in values:
            try:
                number = float(value)
            except (TypeError, ValueError):
                raise ValueError("All specification values must be numeric.")

            if number < 0:
                raise ValueError("Values cannot be negative.")

            parsed_values.append(number)

        alternative_names.add(name.lower())

        clean_alternatives.append({
            "name": name,
            "values": parsed_values
        })

    # Generate automatic ratings
    ratings = [
        [0.0 for _ in clean_criteria]
        for _ in clean_alternatives
    ]

    for j, criterion in enumerate(clean_criteria):

        values = [alt["values"][j] for alt in clean_alternatives]

        minimum = min(values)
        maximum = max(values)

        for i, value in enumerate(values):

            if maximum == minimum:
                score = 10.0

            elif criterion["kind"] == "benefit":
                score = 1 + 9 * (
                    (value - minimum) / (maximum - minimum)
                )

            else:
                score = 1 + 9 * (
                    (maximum - value) / (maximum - minimum)
                )

            ratings[i][j] = round(score, 2)

    # Calculate weighted scores
    results = []

    for i, alternative in enumerate(clean_alternatives):

        contributions = [
            round(
                ratings[i][j] *
                clean_criteria[j]["normalized_weight"], 3
            )
            for j in range(len(clean_criteria))
        ]

        total_score = sum(contributions)

        results.append({
            "name": alternative["name"],
            "values": alternative["values"],
            "ratings": ratings[i],
            "contributions": contributions,
            "score": round(total_score, 3)
        })

    # Rank alternatives
    results.sort(
        key=lambda result: result["score"],
        reverse=True
    )

    for rank, result in enumerate(results, start=1):
        result["rank"] = rank

    winner = results[0]

    # Generate explanation
    best_index = max(
        range(len(clean_criteria)),
        key=lambda j: winner["contributions"][j]
    )

    best_criterion = clean_criteria[best_index]

    explanation = (
        f'{winner["name"]} ranked first with a score of '
        f'{winner["score"]:.3f}/10. Its largest weighted '
        f'contribution came from {best_criterion["name"]}, '
        f'contributing {winner["contributions"][best_index]:.3f} points. '
        f'The result is based on the specifications and weights entered.'
    )

    return {
        "title": title,
        "criteria": clean_criteria,
        "alternatives": clean_alternatives,
        "results": results,
        "winner": winner["name"],
        "explanation": explanation
    }


# HOME

@app.route("/")
def home():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    return render_template("home.html")


# REGISTRATION

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or len(password) < 8:
            flash(
                "Enter your name, email and a password of at least 8 characters.",
                "danger"
            )
            return render_template("register.html")

        try:
            with db_connection() as db:
                db.execute(
                    """
                    INSERT INTO users
                    (name, email, password_hash, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        name,
                        email,
                        generate_password_hash(password),
                        datetime.now().isoformat(timespec="seconds")
                    )
                )
                db.commit()

            flash("Account created. Please log in.", "success")
            return redirect(url_for("login"))

        except sqlite3.IntegrityError:
            flash("Email is already registered.", "danger")

    return render_template("register.html")


# LOGIN

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        with db_connection() as db:
            user = db.execute(
                "SELECT * FROM users WHERE email = ?",
                (email,)
            ).fetchone()

        if user and check_password_hash(
            user["password_hash"], password
        ):
            session.clear()
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]

            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "danger")

    return render_template("login.html")


# LOGOUT

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("home"))


# DASHBOARD

@app.route("/dashboard")
@login_required
def dashboard():

    with db_connection() as db:
        comparisons = db.execute(
            """
            SELECT id, title, created_at, updated_at
            FROM comparisons
            WHERE user_id = ?
            ORDER BY updated_at DESC
            """,
            (session["user_id"],)
        ).fetchall()

    return render_template(
        "dashboard.html",
        comparisons=comparisons
    )


# CREATE COMPARISON

@app.route("/comparison/new")
@login_required
def new_comparison():
    return render_template(
        "builder.html",
        comparison=None
    )


# EDIT COMPARISON

@app.route("/comparison/<int:comparison_id>/edit")
@login_required
def edit_comparison(comparison_id):

    with db_connection() as db:
        row = db.execute(
            """
            SELECT * FROM comparisons
            WHERE id = ? AND user_id = ?
            """,
            (comparison_id, session["user_id"])
        ).fetchone()

    if not row:
        flash("Comparison not found.", "danger")
        return redirect(url_for("dashboard"))

    comparison = json.loads(row["data_json"])
    comparison["id"] = row["id"]

    return render_template(
        "builder.html",
        comparison=comparison
    )


# SAVE OR UPDATE COMPARISON

@app.route("/comparison/save", methods=["POST"])
@login_required
def save_comparison():

    try:
        payload = request.get_json(force=True)
        result = evaluate(payload)

    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
        return {"ok": False, "error": str(error)}, 400

    now = datetime.now().isoformat(timespec="seconds")
    comparison_id = payload.get("id")

    with db_connection() as db:

        if comparison_id:

            cursor = db.execute(
                """
                UPDATE comparisons
                SET title = ?, data_json = ?, updated_at = ?
                WHERE id = ? AND user_id = ?
                """,
                (
                    result["title"],
                    json.dumps(result),
                    now,
                    comparison_id,
                    session["user_id"]
                )
            )

            if cursor.rowcount == 0:
                return {
                    "ok": False,
                    "error": "Comparison not found."
                }, 404

            saved_id = comparison_id

        else:

            cursor = db.execute(
                """
                INSERT INTO comparisons
                (user_id, title, data_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session["user_id"],
                    result["title"],
                    json.dumps(result),
                    now,
                    now
                )
            )

            saved_id = cursor.lastrowid

        db.commit()

    return {
        "ok": True,
        "redirect": url_for(
            "view_comparison",
            comparison_id=saved_id
        )
    }


# VIEW RESULTS

@app.route("/comparison/<int:comparison_id>")
@login_required
def view_comparison(comparison_id):

    with db_connection() as db:
        row = db.execute(
            """
            SELECT * FROM comparisons
            WHERE id = ? AND user_id = ?
            """,
            (comparison_id, session["user_id"])
        ).fetchone()

    if not row:
        flash("Comparison not found.", "danger")
        return redirect(url_for("dashboard"))

    comparison = json.loads(row["data_json"])
    comparison["id"] = row["id"]
    comparison["created_at"] = row["created_at"]

    return render_template(
        "result.html",
        comparison=comparison
    )


# DELETE COMPARISON

@app.route("/comparison/<int:comparison_id>/delete", methods=["POST"])
@login_required
def delete_comparison(comparison_id):

    with db_connection() as db:
        db.execute(
            """
            DELETE FROM comparisons
            WHERE id = ? AND user_id = ?
            """,
            (comparison_id, session["user_id"])
        )
        db.commit()

    flash("Comparison deleted.", "success")
    return redirect(url_for("dashboard"))


# CSV EXPORT

@app.route("/comparison/<int:comparison_id>/csv")
@login_required
def export_csv(comparison_id):

    with db_connection() as db:
        row = db.execute(
            """
            SELECT * FROM comparisons
            WHERE id = ? AND user_id = ?
            """,
            (comparison_id, session["user_id"])
        ).fetchone()

    if not row:
        flash("Comparison not found.", "danger")
        return redirect(url_for("dashboard"))

    data = json.loads(row["data_json"])

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(
        ["Rank", "Alternative", "Weighted score / 10"] +
        [c["name"] for c in data["criteria"]]
    )

    for result in data["results"]:
        writer.writerow(
            [result["rank"], result["name"], result["score"]] +
            result["ratings"]
        )

    response = make_response(output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = (
        f'attachment; filename="choicecraft_{comparison_id}.csv"'
    )

    return response


@app.errorhandler(404)
def page_not_found(_error):
    return render_template(
        "error.html",
        message="The requested page could not be found."
    ), 404


initialize_database()

if __name__ == "__main__":
    app.run(debug=True)

from flask import Flask, render_template, request, redirect, url_for, flash, session
import json, random, os

app = Flask(__name__)
app.secret_key = "bankappsecret"

ADMIN_PASSWORD = "admin123"

DATA_FILE = "bank_data.json"

# ---------------------- Helper Functions ----------------------

def load_data():
    """Load or initialize the bank data safely."""
    if not os.path.exists(DATA_FILE):
        data = {"users": {}, "transactions": {}}
        save_data(data)
        return data

    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        data = {"users": {}, "transactions": {}}
        save_data(data)

    if "users" not in data:
        data["users"] = {}
    if "transactions" not in data:
        data["transactions"] = {}

    return data


def save_data(data):
    """Save to JSON file safely."""
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


def generate_acc_no():
    """Generate 14-digit random account number."""
    return str(random.randint(10**13, 10**14 - 1))


# ---------------------- Routes ----------------------

@app.route("/")
def home():
    return render_template("index.html")

from datetime import datetime

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        dob = request.form.get("dob", "").strip()
        gender = request.form.get("gender", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        username = request.form.get("username", "").strip()
        pin = request.form.get("pin", "").strip()
        confirm_pin = request.form.get("confirm_pin", "").strip()

        # --- Validation ---
        if not all([name, dob, gender, phone, email, username, pin, confirm_pin]):
            flash("⚠️ All fields are required!", "danger")
            return redirect(url_for("register"))

        # PIN confirmation
        if pin != confirm_pin:
            flash("❌ PINs do not match!", "danger")
            return redirect(url_for("register"))

        # Check age (must be 18+)
        try:
            birth_date = datetime.strptime(dob, "%Y-%m-%d")
            today = datetime.today()
            age = (today - birth_date).days // 365
            if age < 18:
                flash("❌ You must be at least 18 years old to create an account.", "danger")
                return redirect(url_for("register"))
        except ValueError:
            flash("❌ Invalid Date of Birth format!", "danger")
            return redirect(url_for("register"))

        data = load_data()

        # Ensure unique username
        for user in data["users"].values():
            if user.get("username") == username:
                flash("⚠️ Username already exists! Choose another one.", "danger")
                return redirect(url_for("register"))

        acc_no = generate_acc_no()

        # Save user details
        data["users"][acc_no] = {
            "name": name,
            "dob": dob,
            "gender": gender,
            "phone": phone,
            "email": email,
            "username": username,
            "pin": pin,
            "balance": 0.0
        }
        data["transactions"][acc_no] = []
        save_data(data)

        flash(f"✅ Account created successfully! Your account number is {acc_no}", "success")
        return redirect(url_for("login"))

    return render_template("register.html")



@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        acc_no = request.form.get("acc_no", "").strip()
        pin = request.form.get("pin", "").strip()

        data = load_data()
        user = data["users"].get(acc_no)

        if not user:
            flash("❌ Account number not found!", "danger")
        elif user.get("pin") == pin:
            session["user"] = acc_no
            flash(f"✅ Welcome, {user['name']}!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("❌ Incorrect PIN!", "danger")

    return render_template("login.html")

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        entered_password = request.form.get("password")
        if entered_password == ADMIN_PASSWORD:
            # ✅ Correct password — show admin dashboard
            data = load_data()
            users = data.get("users", {})
            total_balance = sum(user["balance"] for user in users.values())
            return render_template("admin.html", users=users, total=total_balance, locked=False)
        else:
            flash("❌ Incorrect admin password!", "danger")
            return render_template("admin.html", locked=True)

    # Always ask for password on GET
    return render_template("admin.html", locked=True)

@app.route("/admin_logout")
def admin_logout():
    flash("✅ Admin logged out successfully!", "info")
    return redirect(url_for("home"))  # 👈 Goes to index page

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))

    acc_no = session["user"]
    data = load_data()
    user = data["users"][acc_no]
    return render_template("dashboard.html", user=user, acc_no=acc_no)


@app.route("/deposit", methods=["GET", "POST"])
def deposit():
    if "user" not in session:
        return redirect(url_for("login"))

    acc_no = session["user"]
    data = load_data()
    user = data["users"][acc_no]

    if request.method == "POST":
        amount = float(request.form.get("amount", 0))
        if amount > 0:
            user["balance"] += amount
            data["transactions"][acc_no].append(f"Deposited ₹{amount:.2f}")
            save_data(data)
            flash(f"✅ Deposited ₹{amount:.2f} successfully!", "success")
        else:
            flash("Enter a valid amount!", "danger")
        return redirect(url_for("dashboard"))

    return render_template("deposit.html", user=user)


@app.route("/withdraw", methods=["GET", "POST"])
def withdraw():
    if "user" not in session:
        return redirect(url_for("login"))

    acc_no = session["user"]
    data = load_data()
    user = data["users"][acc_no]

    if request.method == "POST":
        amount = float(request.form.get("amount", 0))
        if 0 < amount <= user["balance"]:
            user["balance"] -= amount
            data["transactions"][acc_no].append(f"Withdrew ₹{amount:.2f}")
            save_data(data)
            flash(f"✅ Withdrawn ₹{amount:.2f} successfully!", "success")
        else:
            flash("❌ Invalid or insufficient balance!", "danger")
        return redirect(url_for("dashboard"))

    return render_template("withdraw.html", user=user)


@app.route("/transfer", methods=["GET", "POST"])
def transfer():
    if "user" not in session:
        return redirect(url_for("login"))

    acc_no = session["user"]
    data = load_data()
    sender = data["users"][acc_no]

    if request.method == "POST":
        target_acc = request.form.get("target_acc").strip()
        amount = float(request.form.get("amount", 0))

        if target_acc not in data["users"]:
            flash("⚠️ Invalid account number!", "danger")
        elif amount <= 0 or sender["balance"] < amount:
            flash("⚠️ Invalid amount or insufficient funds!", "danger")
        else:
            receiver = data["users"][target_acc]
            sender["balance"] -= amount
            receiver["balance"] += amount

            data["transactions"][acc_no].append(f"Transferred ₹{amount:.2f} to {target_acc}")
            data["transactions"][target_acc].append(f"Received ₹{amount:.2f} from {acc_no}")
            save_data(data)

            flash(f"✅ Transferred ₹{amount:.2f} to {receiver['name']}!", "success")
            return redirect(url_for("dashboard"))

    return render_template("transfer.html", user=sender, acc_no=acc_no)

@app.route("/delete_account", methods=["GET", "POST"])
def delete_account():
    if request.method == "POST":
        acc_no = request.form.get("acc_no", "").strip()
        pin = request.form.get("pin", "").strip()

        data = load_data()
        user = data["users"].get(acc_no)

        if not user:
            flash("❌ Account number not found!", "danger")
        elif user["pin"] != pin:
            flash("⚠️ Incorrect PIN!", "warning")
        else:
            # ✅ Delete account and its transactions
            data["users"].pop(acc_no)
            data["transactions"].pop(acc_no, None)
            save_data(data)
            flash("✅ Account deleted successfully!", "success")
            return redirect(url_for("home"))

    return render_template("delete_account.html")

@app.route('/help')
def help():
    return render_template('help.html')


@app.route("/history")
def history():
    if "user" not in session:
        flash("Please login first", "warning")
        return redirect(url_for("login"))

    account_no = str(session["user"]).strip()
    data = load_data()

    print("\n--- DEBUG ---")
    print("Active account:", account_no)
    print("Available transaction keys:", list(data["transactions"].keys()))
    print("Transactions for this account:", data["transactions"].get(account_no))
    print("--- END DEBUG ---\n")

    transactions = data["transactions"].get(account_no, [])
    transactions = list(reversed(transactions))

    return render_template("history.html", transactions=transactions)

@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("You’ve been logged out!", "info")
    return redirect(url_for("home"))  # 👈 Changed from "login" to "home"


if __name__ == "__main__":
    app.run(debug=True)

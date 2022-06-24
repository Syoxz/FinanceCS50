import os
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user = session["user_id"]
    transactions = db.execute("SELECT symbol, name, SUM(shares) AS shares , price FROM transactions WHERE user_id = ? GROUP BY symbol", user)
    cash = db.execute("SELECT cash FROM users WHERE id = ?", user)
    c = usd(cash[0]["cash"])
    return render_template("index.html", transactions=transactions, c=c)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")
    else:
        try:
            symbol = request.form.get("symbol")
            shares = int(request.form.get("shares"))

            if not symbol:
                return apology("Missing Symbol")

            stock = lookup(symbol.upper())

            if stock == None:
                return apology("Invalid Symbol")

            if shares < 0:
                return apology("Invalid Shares")

            value = shares * stock["price"]
            user = session["user_id"]
            cash_db = db.execute("SELECT cash FROM users WHERE id = ?", user)
            user_cash = cash_db[0]["cash"]

            if user_cash < value:
                return apology("Cant afford")

            update_cash = user_cash - value
            db.execute("UPDATE users SET cash = ? WHERE ?", update_cash, user)

            date = datetime.datetime.now()
            db.execute("INSERT INTO transactions(user_id, name, symbol, shares, price, date) VALUES (?,?,?,?,?,?)",
                       user, stock["name"], stock["symbol"], shares, stock["price"], date)
            flash("Bought!")
            return redirect("/")
        except:
            return apology("Something went wrong")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user = session["user_id"]
    history = db.execute("SELECT symbol, shares, price, date FROM transactions WHERE user_id = ?", user)
    return render_template("history.html", history=history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")
    else:
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Missing Symbol")

        stock = lookup(symbol.upper())
        if stock == None:
            return apology("Invalid Symbol")
        return render_template("quoted.html", name=stock["name"], price=stock["price"], symbol=stock["symbol"])


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")
    else:
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

    if not username:
        return apology("No Username")

    if not password:
        return apology("No Password")

    if not confirmation:
        return apology("No Confirmation")

    if password != confirmation:
        return apology("Password do not match")

    sec_pass = generate_password_hash(password)
    try:
        user = db.execute("INSERT INTO users (username, hash) VALUES (?,?)", username, sec_pass)
    except:
        return apology("Something went wrong")

    session["user_id"] = user

    return redirect("/")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    user = session["user_id"]
    if request.method == "GET":
        curr_stocks = db.execute("SELECT symbol FROM transactions WHERE user_id = ? GROUP BY symbol", user)
        return render_template("sell.html", curr_stocks=curr_stocks)
    else:
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))

        if not symbol:
            return apology("Missing Symbol")

        stock = lookup(symbol.upper())

        if stock == None:
            return apology("Invalid Symbol")

        if shares < 0:
            return apology("Invalid Shares")

        value = shares * stock["price"]

        user = session["user_id"]
        cash_db = db.execute("SELECT cash FROM users WHERE id = ?", user)
        user_cash = cash_db[0]["cash"]
        curr_shares = db.execute("SELECT SUM(shares) as shares FROM transactions WHERE user_id = ? AND symbol = ?", user, symbol)

        if shares > curr_shares[0]["shares"]:
            return apology("Too many shares")
        try:
            db.execute("UPDATE users SET cash = ? WHERE ?", user_cash + value, user)
            date = datetime.datetime.now()
            db.execute("INSERT INTO transactions(user_id, name, symbol, shares, price, date) VALUES (?,?,?,?,?,?)",
                       user, stock["name"], stock["symbol"], (-1) * shares, stock["price"], date)
            flash("Sold!")
        except:
            return apology("Something went wrong")
        end_shares = db.execute("SELECT SUM(shares) as shares FROM transactions WHERE user_id = ? AND symbol = ?", user, symbol)
        if end_shares[0]["shares"] == 0:
            db.execute("DELETE FROM transactions WHERE user_id =? AND symbol = ?", user, symbol)
        return redirect("/")

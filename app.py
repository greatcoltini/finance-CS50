import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

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


@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    """ account settings route """
    user = validify_login()

    if (request.method == "POST"):
        if "password_form" in request.form:
            return apology("password form")
        return redirect("/")
    else:
        return render_template("account.html", user=user)


@app.route("/change_password", methods=["POST"])
def change_password():
    """ route for changing the password -- in account """
    n_password = request.form.get("new_password")
    n_password_c = request.form.get("new_password_confirm")
    user = validify_login()

    if not n_password:
        return apology("must input a valid password")
    if not n_password_c:
        return apology("must confirm password")
    if n_password != n_password_c:
        return apology("passwords must be equal")

    new_password = generate_password_hash(n_password)

    db.execute("UPDATE users SET hash = ? WHERE username = ?", new_password, user["username"])

    return redirect("/account")


@app.route("/funds", methods=["POST"])
def funds():
    """ route for adding or withdrawing funds to an account """
    monetary_value = request.form.get("monetary_value")
    transaction_method = request.form.get("transaction")
    user = validify_login()

    try:
        monetary_int = int(monetary_value)
    except ValueError:
        return apology("withdraw/insert must be an integer")

    if transaction_method == "withdraw":
        new_funds = user["cash"] - monetary_int
        if new_funds < 0:
            return apology("cannot withdraw more than the funds in the account")
    elif transaction_method == "insert":
        new_funds = monetary_int + user["cash"]
    else:
        return apology("unknown transaction method")

    db.execute("UPDATE users SET cash = ? WHERE username = ?", new_funds, user["username"])
    return redirect("/account")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user = validify_login()
    stock_portfolio = db.execute(
        "SELECT stock, SUM(quantity) FROM purchase_history WHERE username = ? GROUP BY stock", user["username"])
    total_assets = int(user["cash"])

    # remove 0 items
    for item in stock_portfolio:
        if (number_of_stocks(item["stock"]) < 1):
            stock_portfolio.remove(item)

    # get price of stocks are current time
    for item in stock_portfolio:
        item["cost"] = usd(lookup(item["stock"])["price"])
        item["quantity"] = number_of_stocks(item["stock"])
        item["total_value"] = usd((lookup(item["stock"])["price"]) * item["quantity"])
        total_assets = total_assets + lookup(item["stock"])["price"] * item["quantity"]

    return render_template("index.html", stock_portfolio=stock_portfolio, cash=user["cash"], total_assets=total_assets)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if (request.method == "POST"):

        if not lookup(request.form.get("symbol")):
            return apology("input must be a valid stock.")

        if not (request.form.get("shares")):
            return apology("must input a number of shares.")

        try:
            shares = int(request.form.get("shares"))
        except ValueError:
            return apology("must input a valid integer")

        if not (shares > 0):
            return apology("shares either negative or 0")

        symbol = request.form.get("symbol")
        if (lookup(symbol)):
            stock = lookup(symbol)

        user_info = validify_login()

        cost = stock["price"] * shares

        # if user doesnt have enough to pay for the stocks, return apology
        if (user_info["cash"] < cost):
            return apology("not enough funds")

        new_funds = user_info["cash"] - cost

        db.execute("INSERT INTO purchase_history (username, stock, quantity, cost, purchase_type, individual_stock_price) VALUES (?, ?, ?, ?, ?, ?)",
                   user_info["username"], symbol, shares, cost, "buy", stock["price"])
        db.execute("UPDATE users SET cash = ? WHERE username = ?", new_funds, user_info["username"])

        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    user = validify_login()
    transaction_history = db.execute(
        "SELECT * FROM purchase_history WHERE username = ? ORDER BY purchase_date DESC, purchase_time", user["username"])

    return render_template("history.html", transaction_history=transaction_history)


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
    if request.method == "POST":

        symbol = request.form.get("symbol")

        if (lookup(symbol)):
            symbol_info = lookup(symbol)
        else:
            return apology("invalid symbol", 400)

        return render_template("quoted.html", symbol_info=symbol_info)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        elif not request.form.get("confirmation"):
            return apology("must provide confirmation of password", 400)

        elif not request.form.get("confirmation") == request.form.get("password"):
            return apology("must provide identical password and password-confirmation", 400)

        username = request.form.get("username")

        existing_users = db.execute("SELECT username FROM users")

        for user in existing_users:
            if user["username"] == username:
                return apology("current username already present in database")

        password = generate_password_hash(request.form.get("password"))

        # Insert user into database
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, password)

        # Redirect user to home page
        return redirect("/login")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():

    user = validify_login()

    """Sell shares of stock"""
    if (request.method == "POST"):

        if not lookup(request.form.get("symbol")):
            return apology("input must be a valid stock.")

        if not (request.form.get("shares")):
            return apology("must input a number of shares.")

        shares = int(request.form.get("shares"))

        if not (shares > 0):
            return apology("shares sold must be a positive integer")

        symbol = request.form.get("symbol")

        if (shares > number_of_stocks(symbol)):
            return apology("shares sold must be less than or equal to owned shares")

        stock = lookup(symbol)
        cost = stock["price"] * shares

        new_funds = user["cash"] + cost

        # Add one or more new tables to finance.db via which to keep track of the purchase.
        # Store enough information so that you know who sold what at what price and when.

        db.execute("INSERT INTO purchase_history (username, stock, quantity, cost, purchase_type, individual_stock_price) VALUES (?, ?, ?, ?, ?, ?)",
                   user["username"], symbol, shares, cost, "sell", stock["price"])
        db.execute("UPDATE users SET cash = ? WHERE username = ?", new_funds, user["username"])

        return redirect("/")

    else:
        stock_portfolio = db.execute(
            "SELECT stock, SUM(quantity) FROM purchase_history WHERE username = ? GROUP BY stock", user["username"])

        owned_stocks = []
        for item in stock_portfolio:
            item["quantity"] = number_of_stocks(item["stock"])

            if (item["quantity"] > 0):
                owned_stocks.append(item)

        return render_template("sell.html", stock_portfolio=owned_stocks)


def validify_login():
    """ Verify user is logged in """
    if (session.get("user_id")):
        user_id = session.get("user_id")
        user = db.execute("SELECT username, cash, hash FROM users WHERE id = ?", user_id)[0]
        return user
    else:
        return redirect("/login")


def number_of_stocks(symbol):
    """Function to determine the number of stocks, based on purchase history """
    if (lookup(symbol)):
        stock = lookup(symbol)["symbol"]
    else:
        return None

    if (session.get("user_id")):
        user = db.execute("SELECT username, cash FROM users WHERE id = ?", session.get("user_id"))[0]["username"]
    else:
        return None

    sold_stocks = 0
    bought_stocks = 0
    if (db.execute("SELECT stock, SUM(quantity) FROM purchase_history WHERE purchase_type = ? AND username = ? AND stock = ? GROUP BY stock", 'sell', user, stock)):
        sold_stocks = db.execute(
            "SELECT stock, SUM(quantity) FROM purchase_history WHERE purchase_type = ? AND username = ? AND stock = ? GROUP BY stock", 'sell', user, stock)[0]["SUM(quantity)"]
    if (db.execute("SELECT stock, SUM(quantity) FROM purchase_history WHERE purchase_type = ? AND username = ? AND stock = ? GROUP BY stock", 'buy', user, stock)):
        bought_stocks = db.execute(
            "SELECT stock, SUM(quantity) FROM purchase_history WHERE purchase_type = ? AND username = ? AND stock = ? GROUP BY stock", 'buy', user, stock)[0]["SUM(quantity)"]

    return int(int(bought_stocks) - int(sold_stocks))

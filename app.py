import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import date

from helpers import apology, login_required, lookup, usd, get_user_cash, get_user_holdings, get_user_stock_shares, validate_shares, add_balance

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


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
    username = session["user_name"]
    total = 0

    # Get user's cash balance using helper function
    balance = get_user_cash(username)
    if balance is None:
        return apology("User not found", 400)
    total += balance

    # Get user's current stock holdings using helper function
    result = get_user_holdings(username)
    if not result:
        return apology("No stocks found. Click 'Buy' to buy a stock", 404)

    # Initialize an empty list to store stock data
    stock_data = []

    # Process each stock in the result
    for stock in result:
        try:
            # Store the symbol and shares
            stock_info = {
                "symbol": stock["stock_symbol"],
                "share": stock["total_stocks"]
            }

            # Look up the latest price and other information for the stock
            latest_info = lookup(stock_info["symbol"])

            # Check if the lookup result is properly formatted
            if "price" not in latest_info or "name" not in latest_info or "symbol" not in latest_info:
                return apology(f"Invalid stock data for {stock_info['symbol']}", 400)

            # Update stock_info with the latest data
            stock_info["name"] = latest_info["name"]           # Full company name
            stock_info["price"] = latest_info["price"]         # Current stock price
            stock_info["total_value"] = float(stock_info["price"]) * int(stock_info["share"])

            # Append the stock information to the stock_data list
            stock_data.append(stock_info)

        except Exception as e:
            return apology(f"Error retrieving data for {stock_info['symbol']}: {str(e)}", 500)

    # Calculate the total value of stocks
    for item in stock_data:
        total += item["total_value"]

    # Return the rendered template with the stock data
    return render_template("index.html", stock_data=stock_data, balance=balance, total=total)



@app.route("/cash", methods=["GET", "POST"])
@login_required
def cash():
    """Give Cash to the user"""
    if request.method == "POST":
        
        code = request.form.get("code")

        if session["redeem_limit"] < 3:
            if code.upper() == "SUDOGETCASH":
                add_balance(session["user_name"], 10000)
                flash("Successfully added $10,000 to your account!")
                session["redeem_limit"] += 1
                return redirect("/")
        else:
            return apology("Thats a suspicious amount of money already", 911)
    else:
        return render_template("Cash.html")



@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        username = session["user_name"]

        # Validate input
        if not symbol or not shares:
            return apology("Please enter at least one share", 400)

        # Fetch user balance using helper function
        current_balance = get_user_cash(username)
        if current_balance is None:
            return apology("User not found", 400)

        current_date = date.today()

        stock_info = lookup(symbol.upper())

        if stock_info is None:
            return apology("Please enter a valid symbol", 400)

        # Validate shares input using helper function
        if not validate_shares(shares):
            return apology("Please enter a valid number of shares", 400)

        stock_price = float(stock_info["price"])
        total_cost = int(shares) * stock_price

        if total_cost > current_balance:
            return apology("Insufficient funds", 400)

        # Deduct total cost from balance
        current_balance -= total_cost

        # Update the database
        db.execute(
            "INSERT INTO transactions (username, stock_symbol, stock_price, n_stocks, total_price, date, type) VALUES (?,?,?,?,?,?,?)",
            username, symbol.upper(), stock_price, shares, total_cost, current_date, "buy"
        )

        db.execute("UPDATE users SET cash = ? WHERE username = ?", current_balance, username)

        flash(f"Successfully bought {shares} shares of {symbol.upper()}!")
        return redirect("/")

    else:
        # Fetch user balance using helper function
        balance = get_user_cash(session["user_name"])
        if balance is None:
            return apology("User not found", 400)
        return render_template("buy.html", balance=balance)


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    return apology("TODO")


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
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        session["user_name"] = rows[0]["username"]
        session["redeem_limit"] = 0


        flash("Successfully logged in!")
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

    flash("Successfully logged out!")
    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "POST":
        symbol = request.form.get("symbol")
        data = lookup(symbol)
        if not data or 'error' in data:
            return apology(f"Invalid symbol: {symbol}", 400)
        data["price"] = usd(data["price"])
        flash(f"Successfully retrieved quote for {symbol.upper()}!")
        return render_template("quoted.html", stock_data=[data])  # Wrap in a list for consistency

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":

        username = request.form.get("username")
        rows = db.execute("SELECT * FROM users WHERE (username) = (?)", username)
        if len(rows) > 0:
            return apology("username is already taken")

        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not password or not confirmation:
            return apology("Please enter a valid password", 400)
        elif password != confirmation:
            return apology("Passwords do not match", 400)

        try:
            hashed_password = generate_password_hash(password)
            db.execute("INSERT INTO users (username, hash) VALUES (?,?)", username, hashed_password)
        except (RuntimeError, ValueError):
            return apology("Error Adding Data to the Database", 403)

        # Automatically log the user in
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)
        session["user_id"] = rows[0]["id"]
        session["user_name"] = rows[0]["username"]
        session["redeem_limit"] = 0


        flash("Successfully registered and logged in!")
        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        username = session["user_name"]

        # Validate input
        if not symbol or not shares:
            return apology("Please enter at least one share", 400)

        # Fetch user balance using helper function
        current_balance = get_user_cash(username)
        if current_balance is None:
            return apology("User not found", 400)

        current_date = date.today()

        # Validate shares input using helper function
        if not validate_shares(shares):
            return apology("Please enter a valid number of shares", 400)

        shares = int(shares)

        stock_info = lookup(symbol.upper())
        if stock_info is None:
            return apology("Please enter a valid symbol", 400)

        stock_price = float(stock_info["price"])

        # Get total shares of the stock using helper function
        stocks_owned = get_user_stock_shares(username, symbol)
        if stocks_owned is None:
            return apology("Error fetching stock shares", 500)
        elif stocks_owned < shares:
            return apology(f"Cannot proceed, you only own {stocks_owned} shares for this company", 400)

        total = stock_price * shares

        # Update the user's balance
        current_balance += total

        # Update the database
        try:
            db.execute(
                "INSERT INTO transactions (username, stock_symbol, stock_price, total_price, date, type, n_stocks) VALUES (?,?,?,?,?,?,?)",
                username, symbol.upper(), stock_price, total, current_date, "sell", -shares
            )

            db.execute("UPDATE users SET cash = ? WHERE username = ?", current_balance, username)

            flash(f"Successfully sold {shares} shares of {symbol.upper()}!")
            return redirect("/")

        except Exception as e:
            return apology(f"Database update failed: {str(e)}", 500)

    else:
        # Fetch user balance using helper function
        balance = get_user_cash(session["user_name"])
        if balance is None:
            return apology("User not found", 400)
        return render_template("sell.html", balance=balance)

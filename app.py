import os


from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import date

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

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
    user_id = session["user_id"]
    username = session["user_name"]
    total = 0

    row = db.execute("SELECT cash FROM users WHERE username = ?", username)
    if not row:
        return apology("User not found", 400)
    balance = row[0]["cash"]
    total += balance



    #returns a list of dicts eg. [{'stock_symbol': 'nflx', 'total_stocks': 1}]
    # Execute the query to get the stock symbols and total shares for a specific user
    try:
        result = db.execute("""
            SELECT stock_symbol,
                SUM(n_stocks) AS total_stocks
            FROM transactions
            WHERE username = ? AND type = 'buy'
            GROUP BY stock_symbol
            HAVING total_stocks > 0;
        """, (session["user_name"],))

        # Convert result to a list to handle potential empty result sets
        result = list(result)
        if not result:
            return apology("No stocks found for this user.", 404)

    except Exception as e:
        return apology(f"Database query failed: {str(e)}", 500)

    print(result)

    # Initialize an empty list to store stock data
    stock_data = []

    # Process each stock in the result
    for stock in result:
        try:
            stock_info = {
                "name": stock["stock_symbol"],
                "share": stock["total_stocks"]
            }

            # Look up the latest price and other information for the stock
            latest_info = lookup(stock_info["name"])

            # Check if the lookup result is properly formatted
            if "price" not in latest_info or "name" not in latest_info or "symbol" not in latest_info:
                return apology(f"Invalid stock data for {stock_info['name']}", 400)

            # Update stock_info with the latest price and total value
            stock_info["price"] = latest_info["price"]
            stock_info["total_value"] = float(stock_info["price"]) * int(stock_info["share"])

            # Append the stock information to the stock_data list
            stock_data.append(stock_info)

        except Exception as e:
            return apology(f"Error retrieving data for {stock_info['name']}: {str(e)}", 500)

        print(stock_data)
        for i in range(len(stock_data)):
            total += stock_data[i]["total_value"]


    # Return the rendered template with the stock data
    return render_template("index.html", stock_data=stock_data, balance=balance, total=total)

    # # return render_template("print.html", text1=result, text2="")



@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        username = session["user_name"]

        # Validate input
        if not symbol or not shares:
            return apology("Please enter at least one share", 400)

        # Fetch user balance
        result = db.execute("SELECT cash FROM users WHERE username = ?", username)
        if not result:
            return apology("User not found", 400)
        current_balance = result[0]["cash"]

        current_date = date.today()

        total_cost = 0

        stock_info = lookup(symbol.upper())

        if stock_info is None:
            return apology("Please enter a valid symbol", 400)

        if not shares.isdigit() or int(shares) <= 0:
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
            username, symbol, stock_price, shares, total_cost, current_date, "buy"
        )

        db.execute("UPDATE users SET cash = ? WHERE username = ?", current_balance, username)

        return redirect("/")

    else:
        row = db.execute("SELECT cash FROM users WHERE username = ?", session["user_name"])
        if not row:
            return apology("User not found", 400)
        balance = row[0]["cash"]
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
        data = lookup(symbol)
        if not data or 'error' in data:
            return apology(f"Invalid symbol: {symbol}", 400)
        data["price"] = usd(data["price"])
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
            return apology("Passwords donot match", 400)

        try:
            hashed_password = generate_password_hash(password)
            db.execute("INSERT INTO users (username, hash) VALUES (?,?)", username, hashed_password)
        except (RuntimeError, ValueError):
            return apology("Error Adding Data to the Database", 403)

        return redirect("/")

    else:
        return render_template("register.html")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
         return apology("TODO")

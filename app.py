from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_migrate import Migrate
from models import db, User, Transaction, Goal, Message
import os

# Load environment variables from .env file

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///financial_app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app._static_folder = "static/main.css"

db.init_app(app)
migrate = Migrate(app, db)

with app.app_context():
    db.create_all()

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        # Check if the user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email address already exists', 'danger')
            return redirect(url_for('signup'))

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)  # Log in the user after successful signup
        flash('Your account has been created! Welcome to your dashboard.', 'success')
        return redirect(url_for('dashboard'))
    return render_template('signup.html')

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = current_user.id
    transactions = Transaction.query.filter_by(user_id=user_id).all()

    balance = sum(t.amount if t.type == 'income' else -t.amount for t in transactions)
    incomes = sum(t.amount for t in transactions if t.type == 'income')
    expenses = sum(t.amount for t in transactions if t.type == 'expense')

    # Prepare data for the chart
    chart_data = {
        'days': [],
        'amounts': []
    }

    # Group transactions by day
    daily_transactions = {}
    for transaction in transactions:
        day = transaction.date.day
        if day not in daily_transactions:
            daily_transactions[day] = 0
        if transaction.type == 'income':
            daily_transactions[day] += transaction.amount
        else:
            daily_transactions[day] -= transaction.amount

    # Sort days for consistent chart rendering
    sorted_days = sorted(daily_transactions.keys())
    for day in sorted_days:
        chart_data['days'].append(day)
        chart_data['amounts'].append(daily_transactions[day])

    return render_template('dashboard.html', balance=balance, incomes=incomes, expenses=expenses, chart_data=chart_data, transactions=transactions)

@app.route('/delete_transaction/<int:transaction_id>', methods=['POST'])
@login_required
def delete_transaction(transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)
    if transaction.user_id != current_user.id:
        flash('You do not have permission to delete this transaction', 'danger')
        return redirect(url_for('dashboard'))
    
    db.session.delete(transaction)
    db.session.commit()
    flash('Transaction deleted successfully!', 'success')
    return redirect(url_for('dashboard'))

from datetime import datetime, timedelta

@app.route('/leaderboard')
@login_required
def leaderboard():
    filter_type = request.args.get('filter', 'weekly')
    
    if filter_type == 'weekly':
        start_date = datetime.utcnow() - timedelta(days=7)
    elif filter_type == 'monthly':
        start_date = datetime.utcnow() - timedelta(days=30)
    elif filter_type == 'yearly':
        start_date = datetime.utcnow() - timedelta(days=365)
    else:
        start_date = datetime.utcnow() - timedelta(days=7)  # Default to weekly
    
    public_goals = Goal.query.filter(Goal.public == True, Goal.created_at >= start_date).all()
    rankings = []

    # Aggregate achievements by user
    user_goals = {}
    for goal in public_goals:
        if goal.user_id not in user_goals:
            user_goals[goal.user_id] = {'username': goal.user.username, 'achievements': 0}
        user_goals[goal.user_id]['achievements'] += 1

    # Convert to list and sort by achievements
    for user_id, data in user_goals.items():
        rankings.append({'user': data['username'], 'achievements': data['achievements']})
    
    rankings = sorted(rankings, key=lambda x: x['achievements'], reverse=True)

    return render_template('leaderboard.html', rankings=rankings, filter_type=filter_type)

@app.route('/chatbot', methods=['GET', 'POST'])
@login_required
def chatbot():
    if request.method == 'POST':
        message = request.form['message']
        # Handle and process the chat message here
    return render_template('chatbot.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))
@app.route('/add_transaction', methods=['POST'])
@login_required
def add_transaction():
    user_id = current_user.id
    type = request.form['type']
    amount = request.form['amount']
    category = request.form['category']
    description = request.form['description']
    
    try:
        amount = float(amount)
        if amount <= 0:
            flash('Amount must be greater than zero', 'danger')
            return redirect(url_for('dashboard'))
    except ValueError:
        flash('Invalid amount entered', 'danger')
        return redirect(url_for('dashboard'))
    
    new_transaction = Transaction(
        user_id=user_id,
        type=type,
        amount=amount,
        category=category,
        description=description
    )
    db.session.add(new_transaction)
    db.session.commit()
    flash('Transaction added successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/goals', methods=['GET', 'POST'])
@login_required
def goals():
    user_id = current_user.id
    goals = Goal.query.filter_by(user_id=user_id).all()
    if request.method == 'POST':
        name = request.form['name']
        target_amount = request.form['target_amount']
        deadline = request.form['deadline']
        new_goal = Goal(
            user_id=user_id,
            name=name,
            target_amount=target_amount,
            deadline=deadline
        )
        db.session.add(new_goal)
        db.session.commit()
        flash('Goal added successfully!', 'success')
        return redirect(url_for('goals'))
    return render_template('goals.html', goals=goals)

if __name__ == '__main__':
    app.run(debug=True)
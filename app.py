from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_migrate import Migrate
from models import db, User, Transaction, Goal, Message
import os
from openai import OpenAI



app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///financial_app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app._static_folder = "/static/main.css"
key = os.getenv("OPENAI_API_KEY")
db.init_app(app)
migrate = Migrate(app, db)
client = OpenAI(api_key=key)
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
        #'days': [],
        'amounts': [],
        'income': [],
        'expense':[],
        'dates':[]
    }

    # Group transactions by day
    daily_transactions = {}
    daily_income = {}
    daily_expense = {}
    for transaction in transactions:
        #day = transaction.date.day
        date = transaction.date.strftime('%Y-%m-%d')
        if date not in daily_transactions:
            """
            daily_transactions[day] = 0
            daily_income[day] = 0
            daily_expense[day] = 0"""
            daily_transactions[date] = 0
            daily_income[date] = 0
            daily_expense[date] = 0
        if transaction.type == 'income':
            """
            daily_transactions[day] += transaction.amount
            daily_income[day] += transaction.amount """
            daily_transactions[date] += transaction.amount
            daily_income[date] += transaction.amount 
        else:
            """daily_transactions[day] -= transaction.amount
            daily_expense[day] += transaction.amount """
            daily_transactions[date] -= transaction.amount
            daily_expense[date] += transaction.amount

    # Sort days for consistent chart rendering
    #sorted_days = sorted(daily_transactions.keys())
    sorted_dates = sorted(daily_transactions.keys(), key=lambda x: datetime.strptime(x, '%Y-%m-%d'))
    for date in sorted_dates:
        """chart_data['days'].append(day)
        chart_data['amounts'].append(daily_transactions[day])
        chart_data['income'].append(daily_income[day])
        chart_data['expense'].append(daily_expense[day])
        """
        chart_data['dates'].append(date)
        chart_data['amounts'].append(daily_transactions[date])
        chart_data['income'].append(daily_income[date])
        chart_data['expense'].append(daily_expense[date])
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

from datetime import datetime, timedelta, date

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

    public_goals = Goal.query.filter(Goal.public == True, Goal.completed_at >= start_date).all()
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
    if 'chat_history' not in session:
        session['chat_history'] = []

    if request.method == 'POST':
        message = request.form['message']
        session['chat_history'].append({'role': 'user', 'content': message})

        # Check if the user wants to send personal data
        if 'send_details' in request.form:
            # Extract user details from database
            user = User.query.get(current_user.id)
            transactions = Transaction.query.filter_by(user_id=current_user.id).all()
            goals = Goal.query.filter_by(user_id=current_user.id).all()

            total_income = sum(tr.amount for tr in transactions if tr.type == 'income')
            total_expenses = sum(tr.amount for tr in transactions if tr.type == 'expense')
            savings = total_income - total_expenses

            user_details = f"User: {user.username}, Balance: {savings:.2f}, Goals: {', '.join(goal.name for goal in goals)}"
            personalized_prompt = [
                {"role": "system", "content": "You are a financial advisor."},
                {"role": "user", "content": user_details},
                {"role": "user", "content": message}
            ]
        else:
            personalized_prompt = [
                {"role": "system", "content": "You are a financial advisor."},
                {"role": "user", "content": message}
            ]

        # Send message to the chatbot API
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=personalized_prompt
        )
        bot_reply = response.choices[0].message.content
        session['chat_history'].append({'role': 'system', 'content': bot_reply})

        return render_template('chatbot.html', chat_history=session['chat_history'])

    return render_template('chatbot.html', chat_history=session.get('chat_history', []))

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
    time_obj = datetime.strptime(request.form['date'], "%Y-%m-%d")

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
        description=description,
        date=time_obj
    )
    db.session.add(new_transaction)
    db.session.commit()
    flash('Transaction added successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/goals', methods=['GET', 'POST'])
@login_required
def goals():
    user_id = current_user.id
    incomplete_goals = Goal.query.filter_by(user_id=user_id, completed_at=None).all()
    completed_goals = Goal.query.filter_by(user_id=user_id).filter(Goal.completed_at.isnot(None)).all()

    if request.method == 'POST':
        name = request.form['name']
        target_amount = request.form['target_amount']
        deadline = request.form['deadline']
        public = 'public' in request.form
        
        deadline = datetime.strptime(deadline, '%Y-%m-%d') if deadline else None

        new_goal = Goal(
            user_id=user_id,
            name=name,
            target_amount=target_amount,
            deadline=deadline,
            public=public
        )
        db.session.add(new_goal)
        db.session.commit()
        flash('Goal added successfully!', 'success')
        return redirect(url_for('goals'))

    return render_template('goals.html', incomplete_goals=incomplete_goals, completed_goals=completed_goals)

@app.route('/complete_goal/<int:goal_id>', methods=['POST'])
@login_required
def complete_goal(goal_id):
    goal = Goal.query.get(goal_id)
    if goal and goal.user_id == current_user.id:
        goal.completed_at = datetime.utcnow()
        db.session.commit()
        flash('Goal marked as completed!', 'success')
    else:
        flash('Goal not found or not authorized', 'danger')
    return redirect(url_for('goals'))

if __name__ == '__main__':
    app.run(debug=True)
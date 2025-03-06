from flask import Flask, request, jsonify, render_template, redirect
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import secrets
import json

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///workers.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Worker model
class Worker(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.String(50), unique=True, nullable=False)
    token = db.Column(db.String(100), nullable=False)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    metrics = db.Column(db.Text)  # Store metrics as JSON string

    def get_metrics_json(self):
        if self.metrics:
            return json.loads(self.metrics)
        return None

# Command model
class Command(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey('worker.id'), nullable=False)
    command_text = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, running, completed, failed
    output = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    worker = db.relationship('Worker', backref=db.backref('commands', lazy=True))

# Generate a unique token
def generate_token():
    return secrets.token_hex(16)

# Register a new worker
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    worker_id = data.get('worker_id')
    
    # Check if worker_id is provided and unique
    if not worker_id:
        return jsonify({"status": "error", "message": "Worker ID missing"}), 400
    
    existing_worker = Worker.query.filter_by(worker_id=worker_id).first()
    if existing_worker:
        # Return the existing token if worker already registered
        return jsonify({"token": existing_worker.token})
    
    # Create new worker
    token = generate_token()
    worker = Worker(worker_id=worker_id, token=token)
    db.session.add(worker)
    db.session.commit()
    return jsonify({"token": token})

# Receive metrics from workers
@app.route('/metrics', methods=['POST'])
def receive_metrics():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    data = request.json
    
    worker = Worker.query.filter_by(token=token).first()
    if not worker:
        return jsonify({"status": "error", "message": "Invalid token"}), 401
    
    # Update worker metrics
    worker.metrics = json.dumps(data['metrics'])
    worker.last_seen = datetime.utcnow()
    db.session.commit()
    return jsonify({"status": "success"})

# Send commands to workers
@app.route('/commands', methods=['GET'])
def get_command():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    
    worker = Worker.query.filter_by(token=token).first()
    if not worker:
        return jsonify({"status": "error", "message": "Invalid token"}), 401
    
    # Get the next pending command for this worker
    command = Command.query.filter_by(worker_id=worker.id, status='pending').order_by(Command.id).first()
    if command:
        command.status = 'running'
        db.session.commit()
        return jsonify({"command_id": command.id, "command": command.command_text})
    
    return jsonify({"command": None})

# Receive command output
@app.route('/command_output', methods=['POST'])
def receive_output():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    data = request.json
    
    worker = Worker.query.filter_by(token=token).first()
    if not worker:
        return jsonify({"status": "error", "message": "Invalid token"}), 401
    
    command_id = data.get('command_id')
    command = Command.query.get(command_id)
    
    if not command or command.worker_id != worker.id:
        return jsonify({"status": "error", "message": "Invalid command"}), 400
    
    # Update command output and status
    command.output = data['output']
    command.status = data['status']
    command.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({"status": "success"})

# Web interface routes
@app.route('/')
def index():
    workers = Worker.query.all()
    now = datetime.utcnow()
    return render_template('index.html', workers=workers, now=now)

@app.route('/worker/<worker_id>')
def worker_details(worker_id):
    worker = Worker.query.filter_by(worker_id=worker_id).first_or_404()
    commands = Command.query.filter_by(worker_id=worker.id).order_by(Command.id.desc()).limit(10).all()
    return render_template('worker.html', worker=worker, commands=commands)

# Submit a command
@app.route('/submit_command', methods=['POST'])
def submit_command():
    worker_id = request.form['worker_id']
    command_text = request.form['command']
    
    worker = Worker.query.filter_by(worker_id=worker_id).first()
    if worker and command_text:
        command = Command(worker_id=worker.id, command_text=command_text)
        db.session.add(command)
        db.session.commit()
    
    return redirect('/')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create database tables
    app.run(host='0.0.0.0', port=5000, debug=True)

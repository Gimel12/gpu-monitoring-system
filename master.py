from flask import Flask, request, jsonify, render_template, redirect
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import secrets
import json
import os

app = Flask(__name__)

# Use environment variable for database URI if provided, otherwise use default
db_uri = os.environ.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///workers.db')
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
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

# GPU Metrics History model
class GPUMetricsHistory(db.Model):
    __tablename__ = 'gpu_metrics_history'  # Explicitly define table name
    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey('worker.id'), nullable=False)
    gpu_index = db.Column(db.Integer, nullable=False)  # Index of the GPU in the worker's system
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    temperature = db.Column(db.Float)  # GPU temperature in Celsius
    utilization = db.Column(db.Float)  # GPU utilization percentage
    memory_used = db.Column(db.Float)  # Memory used in MB
    memory_total = db.Column(db.Float)  # Total memory in MB
    power_usage = db.Column(db.Float, nullable=True)  # Power usage in Watts (if available)
    
    @property
    def memory_utilization(self):
        """Calculate memory utilization as a percentage"""
        if self.memory_total and self.memory_total > 0:
            return (self.memory_used / self.memory_total) * 100
        return 0
    
    worker = db.relationship('Worker', backref=db.backref('metrics_history', lazy=True))

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
    
    # Store historical metrics data
    current_time = datetime.utcnow()
    metrics = data['metrics']
    
    if 'gpus' in metrics:
        for gpu_index, gpu_data in enumerate(metrics['gpus']):
            # Create a new metrics history record
            metrics_history = GPUMetricsHistory(
                worker_id=worker.id,
                gpu_index=gpu_index,
                timestamp=current_time,
                temperature=gpu_data.get('temp'),
                utilization=gpu_data.get('util'),
                memory_used=gpu_data.get('memory', {}).get('used', 0),
                memory_total=gpu_data.get('memory', {}).get('total', 0),
                power_usage=gpu_data.get('power_usage') # This might be None if not available
            )
            db.session.add(metrics_history)
    
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

# API endpoint to get historical metrics data for a specific worker and GPU
@app.route('/api/metrics/history/<worker_id>/<int:gpu_index>')
def get_metrics_history(worker_id, gpu_index):
    # Get time range from query parameters (default to last 24 hours)
    hours = request.args.get('hours', 24, type=int)
    start_time = datetime.utcnow() - timedelta(hours=hours)
    
    print(f"Fetching metrics history for worker_id={worker_id}, gpu_index={gpu_index}, hours={hours}")
    
    # Get the worker
    worker = Worker.query.filter_by(worker_id=worker_id).first_or_404()
    print(f"Found worker with ID {worker.id}")
    
    # Query for metrics history
    metrics = GPUMetricsHistory.query.filter(
        GPUMetricsHistory.worker_id == worker.id,
        GPUMetricsHistory.gpu_index == gpu_index,
        GPUMetricsHistory.timestamp >= start_time
    ).order_by(GPUMetricsHistory.timestamp).all()
    
    print(f"Found {len(metrics)} metrics records for the specified time range")
    
    # Format the data for charts
    result = {
        'timestamps': [],
        'temperature': [],
        'utilization': [],
        'memory_utilization': [],
        'power_usage': []
    }
    
    for metric in metrics:
        result['timestamps'].append(metric.timestamp.isoformat())
        result['temperature'].append(metric.temperature)
        result['utilization'].append(metric.utilization)
        result['memory_utilization'].append(metric.memory_utilization)
        result['power_usage'].append(metric.power_usage)
    
    # Add debug output
    print(f"Returning {len(result['timestamps'])} data points")
    
    return jsonify(result)

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

# Submit command to multiple workers
@app.route('/submit_multi_command', methods=['POST'])
def submit_multi_command():
    worker_ids = request.form.getlist('worker_ids')
    command_text = request.form.get('command')
    
    if command_text and worker_ids:
        for worker_id in worker_ids:
            worker = Worker.query.filter_by(worker_id=worker_id).first()
            if worker:
                command = Command(worker_id=worker.id, command_text=command_text)
                db.session.add(command)
        
        db.session.commit()
    
    return redirect('/')

# Stop a running command
@app.route('/stop_command/<int:command_id>', methods=['POST'])
def stop_command(command_id):
    command = Command.query.get_or_404(command_id)
    worker = Worker.query.get(command.worker_id)
    
    # Mark the command as needing to be stopped
    command.status = 'stopping'
    db.session.commit()
    
    # Redirect back to the worker page
    return redirect(f'/worker/{worker.worker_id}')

# Get real-time command output
@app.route('/command_output/<int:command_id>', methods=['GET'])
def get_command_output(command_id):
    command = Command.query.get_or_404(command_id)
    return jsonify({
        'status': command.status,
        'output': command.output,
        'updated_at': command.updated_at.isoformat()
    })

# Delete a worker
@app.route('/delete_worker/<worker_id>', methods=['POST'])
def delete_worker(worker_id):
    worker = Worker.query.filter_by(worker_id=worker_id).first_or_404()
    
    # Delete all commands associated with this worker
    Command.query.filter_by(worker_id=worker.id).delete()
    
    # Delete the worker
    db.session.delete(worker)
    db.session.commit()
    
    return redirect('/')

# Delete multiple workers
@app.route('/delete_workers', methods=['POST'])
def delete_workers():
    worker_ids = request.form.getlist('worker_ids')
    
    if worker_ids:
        for worker_id in worker_ids:
            worker = Worker.query.filter_by(worker_id=worker_id).first()
            if worker:
                # Delete all commands associated with this worker
                Command.query.filter_by(worker_id=worker.id).delete()
                # Delete the worker
                db.session.delete(worker)
        
        db.session.commit()
    
    return redirect('/')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create database tables
    app.run(host='0.0.0.0', port=5000, debug=True)

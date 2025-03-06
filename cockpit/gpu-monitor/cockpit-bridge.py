#!/usr/bin/env python3

import os
import sys
import json
import requests
from flask import Flask, jsonify, request

# Add the parent directory to the path so we can import from the main app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import from the main app
from master import Worker, Command, db, app as master_app

# Create a new Flask app for the Cockpit bridge
app = Flask(__name__)

# Enable CORS for Cockpit
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response

# API endpoint to get all workers
@app.route('/api/workers', methods=['GET'])
def get_workers():
    with master_app.app_context():
        workers = Worker.query.all()
        result = []
        for worker in workers:
            result.append({
                'id': worker.id,
                'worker_id': worker.worker_id,
                'last_seen': worker.last_seen.isoformat(),
                'metrics': worker.metrics
            })
        return jsonify(result)

# API endpoint to get a specific worker
@app.route('/api/worker/<worker_id>', methods=['GET'])
def get_worker(worker_id):
    with master_app.app_context():
        worker = Worker.query.filter_by(worker_id=worker_id).first()
        if not worker:
            return jsonify({'error': 'Worker not found'}), 404
        
        commands = Command.query.filter_by(worker_id=worker.id).order_by(Command.created_at.desc()).all()
        commands_json = []
        for cmd in commands:
            commands_json.append({
                'id': cmd.id,
                'command_text': cmd.command_text,
                'status': cmd.status,
                'output': cmd.output,
                'created_at': cmd.created_at.isoformat(),
                'updated_at': cmd.updated_at.isoformat()
            })
        
        return jsonify({
            'id': worker.id,
            'worker_id': worker.worker_id,
            'last_seen': worker.last_seen.isoformat(),
            'metrics': worker.metrics,
            'commands': commands_json
        })

# API endpoint to submit a command to a worker
@app.route('/api/submit_command', methods=['POST'])
def submit_command():
    data = request.json
    worker_id = data.get('worker_id')
    command_text = data.get('command')
    
    if not worker_id or not command_text:
        return jsonify({'success': False, 'message': 'Worker ID and command are required'}), 400
    
    with master_app.app_context():
        worker = Worker.query.filter_by(worker_id=worker_id).first()
        if not worker:
            return jsonify({'success': False, 'message': 'Worker not found'}), 404
        
        command = Command(worker_id=worker.id, command_text=command_text)
        db.session.add(command)
        db.session.commit()
        
        return jsonify({'success': True, 'command_id': command.id})

# API endpoint to submit a command to multiple workers
@app.route('/api/submit_multi_command', methods=['POST'])
def submit_multi_command():
    data = request.json
    worker_ids = data.get('worker_ids', [])
    command_text = data.get('command')
    
    if not worker_ids or not command_text:
        return jsonify({'success': False, 'message': 'Worker IDs and command are required'}), 400
    
    with master_app.app_context():
        command_ids = []
        for worker_id in worker_ids:
            worker = Worker.query.filter_by(worker_id=worker_id).first()
            if worker:
                command = Command(worker_id=worker.id, command_text=command_text)
                db.session.add(command)
                command_ids.append(command.id)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Command sent to {len(command_ids)} workers',
            'command_ids': command_ids
        })

# Main entry point
if __name__ == '__main__':
    # Run the app on port 8000 (different from the main app)
    app.run(host='0.0.0.0', port=8000, debug=True)

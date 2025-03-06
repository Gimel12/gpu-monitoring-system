# GPU Monitoring System

A master-worker system for monitoring GPU metrics across multiple Ubuntu machines. The master server provides a web interface to view GPU metrics and execute commands on worker machines.

## System Architecture

- **Master**: A central server running a Flask web application that collects metrics from workers and provides a web interface.
- **Workers**: Ubuntu 22.04 machines that run a Python script to register with the master, send GPU metrics, and execute commands.
- **Communication**: Workers communicate with the master over HTTP using RESTful API endpoints.
- **Data Storage**: The master uses SQLite to store worker details and their latest metrics.
- **GPU Monitoring**: Workers use NVIDIA Management Library (NVML) or direct `nvidia-smi` calls to collect GPU metrics.

## Prerequisites

### Master Server:
- Python 3.x
- Required packages: `flask`, `flask-sqlalchemy`, `requests`

### Worker Machines (Ubuntu 22.04):
- Python 3.x
- NVIDIA drivers installed
- Required packages: `pynvml`, `requests`

## Setup Instructions

### 1. Setting up the Master Server

1. Clone this repository to your master server
2. Install the required packages:
   ```
   pip install -r requirements.txt
   ```
3. Run the master server:
   ```
   python master.py
   ```
   The web interface will be accessible at `http://<master-ip>:5000`

### 2. Setting up Worker Machines

1. Copy the `worker.py` script to each Ubuntu 22.04 machine
2. Install the required packages:
   ```
   pip install pynvml requests
   ```
3. Run the worker script, specifying the master server URL:
   ```
   python worker.py --master http://<master-ip>:5000
   ```

## Usage

### Web Interface

- **Dashboard**: Access the main dashboard at `http://<master-ip>:5000` to see all connected workers, their status, and GPU count.
- **Worker Details**: Click on a worker's ID to view detailed GPU metrics including temperature and utilization.
- **Running Commands**: You can run commands on workers directly from the web interface. Enter a command in the input field next to a worker and click "Run".

### Worker Script Options

The worker script accepts the following command-line arguments:

- `--master`: (Required) Master server URL (e.g., http://master-ip:5000)
- `--worker-id`: Custom worker ID (defaults to hostname)
- `--token-file`: File to store authentication token (defaults to token.txt)
- `--interval`: Interval between metric updates in seconds (defaults to 5)

Example:
```
python worker.py --master http://192.168.1.100:5000 --worker-id gpu-worker-1 --interval 10
```

## Security Considerations

This is a basic implementation intended for use within a private network. For production use, consider implementing:

- HTTPS for secure communication
- User authentication for the web interface
- Input validation for commands
- Firewall rules to restrict access to the master server

## Troubleshooting

- If a worker fails to connect, check network connectivity and firewall settings
- If GPU metrics are not showing, ensure NVIDIA drivers are properly installed
- Check the worker's output for any error messages
- Verify that the master server URL is correct and accessible from the worker machine

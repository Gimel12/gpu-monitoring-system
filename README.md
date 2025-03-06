# GPU Monitoring System

A master-worker system for monitoring GPU metrics across multiple Ubuntu machines. The master server provides a web interface to view GPU metrics and execute commands on worker machines, either individually or on multiple machines simultaneously.

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

### Option 1: Standard Setup

#### 1. Setting up the Master Server

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

#### 2. Setting up Worker Machines

1. Copy the `worker.py` script to each Ubuntu 22.04 machine
2. Install the required packages:
   ```
   pip install pynvml requests
   ```
3. Run the worker script, specifying the master server URL:
   ```
   python worker.py --master http://<master-ip>:5000
   ```

### Option 2: Docker Deployment (Recommended for Production)

#### Prerequisites

- Docker and Docker Compose installed on all machines
- NVIDIA Container Toolkit installed on worker machines

#### 1. Master Server Deployment

1. Clone this repository to your master server
2. Build and start the master container:
   ```
   docker build -f Dockerfile.master -t gpu-monitor-master .
   docker run -d --name gpu-master -p 5000:5000 -v $(pwd)/data:/app/data gpu-monitor-master
   ```
   The web interface will be accessible at `http://<master-ip>:5000`

#### 2. Worker Deployment

1. Copy the repository to each worker machine
2. Build and start the worker container with GPU access:
   ```
   docker build -f Dockerfile.worker -t gpu-monitor-worker .
   docker run -d --name gpu-worker --gpus all -e MASTER_URL=http://<master-ip>:5000 -e WORKER_ID=<unique-worker-id> gpu-monitor-worker
   ```

#### 3. Using Docker Compose (Single Machine with Both Master and Worker)

1. Clone this repository
2. Start both services with Docker Compose:
   ```
   docker-compose up -d
   ```

#### 4. Deploying as a Systemd Service

For running Docker containers as systemd services, create service files:

**Master Service (/etc/systemd/system/gpu-master.service):**
```
[Unit]
Description=GPU Monitoring Master Container
After=docker.service
Requires=docker.service

[Service]
Restart=always
ExecStart=/usr/bin/docker run --rm --name gpu-master -p 5000:5000 -v /path/to/data:/app/data gpu-monitor-master
ExecStop=/usr/bin/docker stop gpu-master

[Install]
WantedBy=multi-user.target
```

**Worker Service (/etc/systemd/system/gpu-worker.service):**
```
[Unit]
Description=GPU Monitoring Worker Container
After=docker.service
Requires=docker.service

[Service]
Restart=always
ExecStart=/usr/bin/docker run --rm --name gpu-worker --gpus all -e MASTER_URL=http://<master-ip>:5000 -e WORKER_ID=<unique-worker-id> gpu-monitor-worker
ExecStop=/usr/bin/docker stop gpu-worker

[Install]
WantedBy=multi-user.target
```

Enable and start the services:
```
sudo systemctl enable gpu-master.service
sudo systemctl start gpu-master.service
sudo systemctl enable gpu-worker.service
sudo systemctl start gpu-worker.service
```

## Usage

### Web Interface

- **Dashboard**: Access the main dashboard at `http://<master-ip>:5000` to see all connected workers, their status, and GPU count.
- **Worker Details**: Click on a worker's ID to view detailed GPU metrics including temperature and utilization.
- **Running Commands on Individual Workers**: Enter a command in the input field next to a worker and click "Run".
- **Running Commands on Multiple Workers**: Use the checkboxes to select multiple workers, then use the command panel at the bottom of the page to run a command on all selected workers simultaneously.

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

### Standard Setup
- If a worker fails to connect, check network connectivity and firewall settings
- If GPU metrics are not showing, ensure NVIDIA drivers are properly installed
- Check the worker's output for any error messages
- Verify that the master server URL is correct and accessible from the worker machine

### Docker Setup
- Ensure NVIDIA Container Toolkit is properly installed: `nvidia-smi` should work on the host
- Check Docker logs: `docker logs gpu-master` or `docker logs gpu-worker`
- Verify network connectivity between containers: `docker network inspect`
- For GPU access issues, verify that `--gpus all` flag is included in the worker container run command
- Check Docker volumes for database persistence: `docker volume ls`

## Maintenance

### Updating the Application

#### Standard Setup
1. Pull the latest code: `git pull`
2. Restart the services: `systemctl restart gpu-master.service` and `systemctl restart gpu-worker.service`

#### Docker Setup
1. Pull the latest code: `git pull`
2. Rebuild the images: `docker build -f Dockerfile.master -t gpu-monitor-master .` and `docker build -f Dockerfile.worker -t gpu-monitor-worker .`
3. Restart the containers: `docker-compose down && docker-compose up -d`

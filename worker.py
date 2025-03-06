#!/usr/bin/env python3
import os
import sys
import time
import json
import socket
import requests
import subprocess
import argparse
from datetime import datetime

# Try to import NVML for GPU monitoring
try:
    from pynvml import *
    NVML_AVAILABLE = True
except ImportError:
    NVML_AVAILABLE = False
    print("NVIDIA Management Library (NVML) not available. Will attempt to use nvidia-smi directly.")

class GPUWorker:
    def __init__(self, master_url, worker_id=None, token_file="token.txt"):
        self.master_url = master_url.rstrip('/')
        self.worker_id = worker_id if worker_id else socket.gethostname()
        print(f"Worker ID set to: {self.worker_id}")
        self.token_file = token_file
        self.token = None
        self.headers = None
        
        # Initialize NVML if available
        global NVML_AVAILABLE
        if NVML_AVAILABLE:
            try:
                nvmlInit()
                print(f"NVML initialized successfully")
            except Exception as e:
                print(f"Failed to initialize NVML: {e}")
                NVML_AVAILABLE = False
    
    def register(self):
        """Register with the master server and get a token"""
        try:
            print(f"Registering worker '{self.worker_id}' with master at {self.master_url}")
            response = requests.post(
                f"{self.master_url}/register", 
                json={"worker_id": self.worker_id},
                timeout=10
            )
            
            if response.status_code == 200:
                self.token = response.json().get("token")
                if self.token:
                    print(f"Registration successful, token received")
                    with open(self.token_file, "w") as f:
                        f.write(self.token)
                    self.headers = {"Authorization": f"Bearer {self.token}"}
                    return True
                else:
                    print("No token received in response")
            else:
                print(f"Registration failed: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Error during registration: {e}")
        
        return False
    
    def load_token(self):
        """Load token from file if it exists"""
        if os.path.exists(self.token_file):
            try:
                with open(self.token_file, "r") as f:
                    self.token = f.read().strip()
                if self.token:
                    self.headers = {"Authorization": f"Bearer {self.token}"}
                    print(f"Token loaded from {self.token_file}")
                    return True
            except Exception as e:
                print(f"Error loading token: {e}")
        
        return False
    
    def collect_gpu_metrics_nvml(self):
        """Collect GPU metrics using NVML"""
        metrics = {"gpus": []}
        
        try:
            device_count = nvmlDeviceGetCount()
            for i in range(device_count):
                handle = nvmlDeviceGetHandleByIndex(i)
                name = nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode('utf-8')
                
                temp = nvmlDeviceGetTemperature(handle, NVML_TEMPERATURE_GPU)
                util = nvmlDeviceGetUtilizationRates(handle).gpu
                
                # Get memory info
                memory = nvmlDeviceGetMemoryInfo(handle)
                mem_total = memory.total / 1024 / 1024  # Convert to MB
                mem_used = memory.used / 1024 / 1024
                mem_free = memory.free / 1024 / 1024
                
                # Get power usage if available
                power_usage = None
                try:
                    power_usage = nvmlDeviceGetPowerUsage(handle) / 1000.0  # Convert from milliwatts to watts
                except Exception as e:
                    # Power usage might not be available on all GPUs
                    print(f"Could not get power usage for GPU {i}: {e}")
                
                gpu_info = {
                    "model": name,
                    "temp": temp,
                    "util": util,
                    "power_usage": round(power_usage, 2) if power_usage is not None else None,
                    "memory": {
                        "total": round(mem_total, 2),
                        "used": round(mem_used, 2),
                        "free": round(mem_free, 2),
                        "percent_used": round((mem_used / mem_total) * 100, 2)
                    }
                }
                
                metrics["gpus"].append(gpu_info)
        except Exception as e:
            print(f"Error collecting GPU metrics via NVML: {e}")
        
        return metrics
    
    def collect_gpu_metrics_nvidia_smi(self):
        """Collect GPU metrics using nvidia-smi command"""
        metrics = {"gpus": []}
        
        try:
            # Run nvidia-smi to get GPU info
            cmd = "nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,memory.total,memory.used,memory.free,power.draw --format=csv,noheader,nounits"
            output = subprocess.check_output(cmd, shell=True).decode('utf-8').strip()
            
            for i, line in enumerate(output.split('\n')):
                if not line.strip():
                    continue
                
                parts = [part.strip() for part in line.split(',')]
                if len(parts) >= 7:  # Now we have 7 parts including power
                    model, temp, util, mem_total, mem_used, mem_free, power_draw = parts[:7]
                    
                    # Convert string values to appropriate types
                    try:
                        temp = int(temp)
                        util = int(util)
                        mem_total = float(mem_total)
                        mem_used = float(mem_used)
                        mem_free = float(mem_free)
                        
                        # Handle power usage (might be N/A on some GPUs)
                        power_usage = None
                        if power_draw.lower() != 'n/a':
                            power_usage = float(power_draw)
                        
                        gpu_info = {
                            "model": model,
                            "temp": temp,
                            "util": util,
                            "power_usage": power_usage,
                            "memory": {
                                "total": mem_total,
                                "used": mem_used,
                                "free": mem_free,
                                "percent_used": round((mem_used / mem_total) * 100, 2) if mem_total > 0 else 0
                            }
                        }
                        
                        metrics["gpus"].append(gpu_info)
                    except (ValueError, ZeroDivisionError) as e:
                        print(f"Error parsing GPU {i} data: {e}")
            
        except Exception as e:
            print(f"Error collecting GPU metrics via nvidia-smi: {e}")
        
        return metrics
    
    def collect_gpu_metrics(self):
        """Collect GPU metrics using available method"""
        if NVML_AVAILABLE:
            return self.collect_gpu_metrics_nvml()
        else:
            return self.collect_gpu_metrics_nvidia_smi()
    
    def send_metrics(self, metrics):
        """Send metrics to the master server"""
        try:
            response = requests.post(
                f"{self.master_url}/metrics", 
                json={"metrics": metrics},
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return True
            else:
                print(f"Failed to send metrics: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Error sending metrics: {e}")
        
        return False
    
    def check_commands(self):
        """Check for commands from the master server"""
        try:
            response = requests.get(
                f"{self.master_url}/commands",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                command = data.get("command")
                
                if command:
                    command_id = data.get("command_id")
                    print(f"Received command: {command}")
                    return command_id, command
            elif response.status_code != 401:  # Ignore auth errors as they're handled elsewhere
                print(f"Failed to check commands: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Error checking commands: {e}")
        
        return None, None
    
    def execute_command(self, command_id, command):
        """Execute a shell command and return the output"""
        try:
            # Start the process
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
                universal_newlines=True
            )
            
            # Initialize output
            output = ""
            status = "running"
            
            # Send initial status update
            self.send_command_output(command_id, status, "Command started...\n")
            
            # Read output line by line with timeout
            start_time = time.time()
            max_runtime = 3600  # 1 hour max runtime
            
            # Use non-blocking reads
            import select
            import fcntl
            import os
            
            # Set stdout and stderr to non-blocking mode
            for pipe in [process.stdout, process.stderr]:
                fd = pipe.fileno()
                fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
            
            # Poll for output and check command status periodically
            while process.poll() is None:
                # Check if we should stop the command
                if self.check_command_status(command_id) == "stopping":
                    process.terminate()
                    time.sleep(1)  # Give it a second to terminate
                    if process.poll() is None:  # If still running
                        process.kill()  # Force kill
                    output += "\n\nCommand was manually stopped."
                    status = "stopped"
                    break
                
                # Check for timeout
                if time.time() - start_time > max_runtime:
                    process.terminate()
                    time.sleep(1)
                    if process.poll() is None:
                        process.kill()
                    output += "\n\nCommand exceeded maximum runtime of 1 hour and was terminated."
                    status = "failed"
                    break
                
                # Check for output
                reads = [process.stdout.fileno(), process.stderr.fileno()]
                readable, _, _ = select.select(reads, [], [], 1.0)  # 1 second timeout
                
                # Read any available output
                if process.stdout.fileno() in readable:
                    line = process.stdout.readline()
                    if line:
                        output += line
                        # Send incremental updates every 5 seconds
                        if int(time.time()) % 5 == 0:
                            self.send_command_output(command_id, "running", output)
                
                if process.stderr.fileno() in readable:
                    line = process.stderr.readline()
                    if line:
                        output += "STDERR: " + line
                        # Send incremental updates every 5 seconds
                        if int(time.time()) % 5 == 0:
                            self.send_command_output(command_id, "running", output)
                
                # Short sleep to prevent CPU hogging
                time.sleep(0.1)
            
            # Get any remaining output
            remaining_stdout, remaining_stderr = process.communicate()
            if remaining_stdout:
                output += remaining_stdout
            if remaining_stderr:
                output += "\nSTDERR:\n" + remaining_stderr
            
            # Set final status if not already set
            if status == "running":
                status = "completed" if process.returncode == 0 else "failed"
            
            return status, output
        except Exception as e:
            return "failed", f"Error executing command: {e}"
    
    def check_command_status(self, command_id):
        """Check if a command should be stopped"""
        try:
            response = requests.get(
                f"{self.master_url}/command_output/{command_id}",
                headers=self.headers,
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("status")
        except Exception as e:
            print(f"Error checking command status: {e}")
        
        return "running"  # Default to running if we can't check
    
    def send_command_output(self, command_id, status, output):
        """Send command output back to the master server"""
        try:
            response = requests.post(
                f"{self.master_url}/command_output",
                json={"command_id": command_id, "status": status, "output": output},
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                print(f"Command output sent successfully")
                return True
            else:
                print(f"Failed to send command output: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Error sending command output: {e}")
        
        return False
    
    def run(self, interval=5):
        """Main worker loop"""
        # Try to load token or register
        if not self.load_token() and not self.register():
            print("Failed to register or load token. Exiting.")
            return
        
        print(f"Worker '{self.worker_id}' running, sending metrics every {interval} seconds")
        
        while True:
            try:
                # Collect and send metrics
                metrics = self.collect_gpu_metrics()
                metrics["timestamp"] = datetime.now().isoformat()
                metrics["hostname"] = self.worker_id
                
                if not self.send_metrics(metrics):
                    # If sending metrics fails, try to re-register
                    print("Re-registering with master...")
                    if not self.register():
                        print("Re-registration failed. Will try again later.")
                
                # Check for commands
                command_id, command = self.check_commands()
                if command_id and command:
                    status, output = self.execute_command(command_id, command)
                    # Final update with complete output
                    self.send_command_output(command_id, status, output)
                
            except Exception as e:
                print(f"Error in worker loop: {e}")
            
            # Wait for next iteration
            time.sleep(interval)

def main():
    # Check for environment variables (for Docker deployment)
    env_master_url = os.environ.get('MASTER_URL')
    env_worker_id = os.environ.get('WORKER_ID')
    env_token_file = os.environ.get('TOKEN_FILE')
    env_interval = os.environ.get('UPDATE_INTERVAL')
    
    parser = argparse.ArgumentParser(description='GPU Worker Client')
    parser.add_argument('--master', required=not bool(env_master_url), 
                      help='Master server URL (e.g., http://master-ip:5000)')
    parser.add_argument('--worker-id', help='Worker ID (defaults to hostname)')
    parser.add_argument('--token-file', default='token.txt', help='File to store authentication token')
    parser.add_argument('--interval', type=int, default=5, help='Interval between metric updates in seconds')
    
    args = parser.parse_args()
    
    # Use environment variables as fallbacks
    master_url = args.master or env_master_url
    worker_id = args.worker_id or env_worker_id
    token_file = args.token_file or env_token_file or 'token.txt'
    interval = args.interval or (int(env_interval) if env_interval else 5)
    
    if not master_url:
        print("Error: Master URL must be provided either via --master argument or MASTER_URL environment variable")
        sys.exit(1)
        
    # Debug print for worker ID
    if worker_id:
        print(f"Worker ID provided: {worker_id} (via {'environment' if env_worker_id and worker_id == env_worker_id else 'command line'})")
    
    worker = GPUWorker(
        master_url=master_url,
        worker_id=worker_id,
        token_file=token_file
    )
    
    worker.run(interval=interval)

if __name__ == "__main__":
    main()

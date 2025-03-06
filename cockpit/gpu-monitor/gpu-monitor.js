// GPU Monitor Cockpit Plugin

// Configuration
const API_BASE_URL = "http://localhost:5000"; // URL to your Flask API
const REFRESH_INTERVAL = 30000; // Refresh data every 30 seconds

// Initialize when document is ready
$(document).ready(function() {
    // Initial data load
    loadWorkers();
    
    // Set up auto-refresh
    setInterval(loadWorkers, REFRESH_INTERVAL);
    
    // Set up event handlers
    setupEventHandlers();
});

// Load workers data from API
function loadWorkers() {
    cockpit.spawn(["curl", "-s", `${API_BASE_URL}/api/workers`])
        .then(function(data) {
            try {
                const workers = JSON.parse(data);
                updateWorkersTable(workers);
            } catch (error) {
                console.error("Error parsing workers data:", error);
                showError("Failed to parse workers data");
            }
        })
        .catch(function(error) {
            console.error("Error fetching workers:", error);
            showError("Failed to connect to GPU Monitor API");
        });
}

// Update the workers table with data
function updateWorkersTable(workers) {
    const tableBody = $("#workers-table-body");
    tableBody.empty();
    
    if (workers.length === 0) {
        tableBody.append(`
            <tr>
                <td colspan="7" class="text-center">No workers connected yet</td>
            </tr>
        `);
        return;
    }
    
    const now = new Date();
    
    workers.forEach(function(worker) {
        const lastSeen = new Date(worker.last_seen);
        const isActive = (now - lastSeen) / 1000 < 60;
        const metrics = worker.metrics ? JSON.parse(worker.metrics) : null;
        const gpuCount = metrics && metrics.gpus ? metrics.gpus.length : 0;
        
        let gpuTypeHtml = "-";
        if (metrics && metrics.gpus && metrics.gpus.length > 0) {
            const uniqueModels = {};
            
            metrics.gpus.forEach(function(gpu) {
                const shortModel = gpu.model.replace("NVIDIA ", "").substring(0, 15);
                if (uniqueModels[shortModel]) {
                    uniqueModels[shortModel].count++;
                } else {
                    uniqueModels[shortModel] = {
                        count: 1,
                        fullModel: gpu.model,
                        memory: gpu.memory && gpu.memory.total ? Math.round(gpu.memory.total / 1024) : null
                    };
                }
            });
            
            gpuTypeHtml = "";
            let modelCount = 0;
            
            for (const model in uniqueModels) {
                if (modelCount < 2) {
                    const info = uniqueModels[model];
                    gpuTypeHtml += `
                        <div>
                            <span title="${info.fullModel}">${model}</span>
                            <span class="text-muted">(${info.memory}GB)</span>
                            ${info.count > 1 ? `<span class="badge">×${info.count}</span>` : ""}
                        </div>
                    `;
                }
                modelCount++;
                
                if (modelCount === 2 && Object.keys(uniqueModels).length > 2) {
                    gpuTypeHtml += `<div><span class="badge">+${Object.keys(uniqueModels).length - 2} more types</span></div>`;
                    break;
                }
            }
        }
        
        tableBody.append(`
            <tr>
                <td class="pf-c-table__check">
                    <input class="pf-c-check__input worker-checkbox" type="checkbox" 
                           name="worker_select" value="${worker.worker_id}" 
                           id="worker${worker.id}">
                </td>
                <td><a href="#" class="worker-details" data-worker-id="${worker.worker_id}">${worker.worker_id}</a></td>
                <td>
                    <span class="${isActive ? 'active-status' : 'inactive-status'}">
                        ${isActive ? 'Active' : 'Inactive'}
                    </span>
                </td>
                <td>${gpuCount}</td>
                <td>${gpuTypeHtml}</td>
                <td>${formatDate(lastSeen)}</td>
                <td>
                    <div class="pf-c-input-group">
                        <input type="text" class="pf-c-form-control command-input" 
                               placeholder="Enter command" data-worker-id="${worker.worker_id}">
                        <button class="pf-c-button pf-m-primary run-command-btn" 
                                data-worker-id="${worker.worker_id}">Run</button>
                    </div>
                </td>
            </tr>
        `);
    });
    
    // Reattach event handlers
    $(".worker-checkbox").on("change", updateSelectedCount);
    $(".run-command-btn").on("click", runSingleCommand);
    $(".worker-details").on("click", showWorkerDetails);
}

// Set up event handlers
function setupEventHandlers() {
    // Select all workers
    $("#selectAllWorkers").on("change", function() {
        $(".worker-checkbox").prop("checked", $(this).prop("checked"));
        updateSelectedCount();
    });
    
    // Run command on multiple workers
    $("#runMultiCommandBtn").on("click", runMultiCommand);
}

// Update selected workers count
function updateSelectedCount() {
    const selectedCount = $(".worker-checkbox:checked").length;
    const totalCount = $(".worker-checkbox").length;
    
    $("#selectedWorkersCount").text(
        selectedCount === 0 ? "No workers selected" : 
        `${selectedCount} worker${selectedCount > 1 ? 's' : ''} selected`
    );
    
    $("#runMultiCommandBtn").prop("disabled", selectedCount === 0);
    
    // Update select all checkbox state
    if (selectedCount === 0) {
        $("#selectAllWorkers").prop("checked", false);
        $("#selectAllWorkers").prop("indeterminate", false);
    } else if (selectedCount === totalCount) {
        $("#selectAllWorkers").prop("checked", true);
        $("#selectAllWorkers").prop("indeterminate", false);
    } else {
        $("#selectAllWorkers").prop("indeterminate", true);
    }
}

// Run command on a single worker
function runSingleCommand() {
    const workerId = $(this).data("worker-id");
    const command = $(`.command-input[data-worker-id="${workerId}"]`).val();
    
    if (!command) {
        showError("Please enter a command");
        return;
    }
    
    runCommand(workerId, command);
}

// Run command on multiple workers
function runMultiCommand() {
    const command = $("#multiCommand").val();
    
    if (!command) {
        showError("Please enter a command");
        return;
    }
    
    const selectedWorkers = $(".worker-checkbox:checked").map(function() {
        return $(this).val();
    }).get();
    
    if (selectedWorkers.length === 0) {
        showError("No workers selected");
        return;
    }
    
    // Call API to run command on multiple workers
    cockpit.spawn([
        "curl", "-s", "-X", "POST", 
        "-H", "Content-Type: application/json",
        "-d", JSON.stringify({
            worker_ids: selectedWorkers,
            command: command
        }),
        `${API_BASE_URL}/api/submit_multi_command`
    ])
    .then(function(response) {
        try {
            const result = JSON.parse(response);
            if (result.success) {
                showSuccess(`Command sent to ${selectedWorkers.length} worker(s)`);
                $("#multiCommand").val("");
            } else {
                showError(result.message || "Failed to send command");
            }
        } catch (error) {
            console.error("Error parsing response:", error);
            showError("Failed to parse response");
        }
    })
    .catch(function(error) {
        console.error("Error sending command:", error);
        showError("Failed to send command");
    });
}

// Run command on a single worker
function runCommand(workerId, command) {
    cockpit.spawn([
        "curl", "-s", "-X", "POST", 
        "-H", "Content-Type: application/json",
        "-d", JSON.stringify({
            worker_id: workerId,
            command: command
        }),
        `${API_BASE_URL}/api/submit_command`
    ])
    .then(function(response) {
        try {
            const result = JSON.parse(response);
            if (result.success) {
                showSuccess("Command sent successfully");
                $(`.command-input[data-worker-id="${workerId}"]`).val("");
            } else {
                showError(result.message || "Failed to send command");
            }
        } catch (error) {
            console.error("Error parsing response:", error);
            showError("Failed to parse response");
        }
    })
    .catch(function(error) {
        console.error("Error sending command:", error);
        showError("Failed to send command");
    });
}

// Show worker details
function showWorkerDetails(event) {
    event.preventDefault();
    const workerId = $(this).data("worker-id");
    cockpit.location.go(`/gpu-monitor/worker/${workerId}`);
}

// Format date
function formatDate(date) {
    return date.toISOString().replace("T", " ").substring(0, 19);
}

// Show error message
function showError(message) {
    console.error(message);
    cockpit.modal({
        title: "Error",
        body: message
    });
}

// Show success message
function showSuccess(message) {
    cockpit.modal({
        title: "Success",
        body: message
    });
}

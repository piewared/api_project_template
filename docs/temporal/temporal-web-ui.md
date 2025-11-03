# Temporal Web UI

The Temporal Web UI is a powerful management interface for monitoring, debugging, and operating workflows. This guide covers how to access and use the UI in development and production environments.

## Overview

The Temporal Web UI provides:

- 📊 **Workflow Visibility** - View all running, completed, and failed workflows
- 🔍 **Execution History** - Inspect detailed workflow execution steps
- 🐛 **Debugging** - Analyze failures, view stack traces, and inspect inputs/outputs
- 📈 **Metrics** - Monitor workflow performance and throughput
- 🔔 **Signals & Queries** - Send signals and query workflow state
- ⏸️ **Workflow Control** - Cancel, terminate, or retry workflows manually

## Accessing the UI

### Development Environment

In development, the Temporal Web UI is **publicly accessible on localhost** for easy access during development.

#### Starting the UI

The UI is automatically started when you run the development environment:

```bash
# Start all dev services (includes Temporal UI)
uv run cli dev start-env
```

The UI container (`api-template-temporal-ui-dev`) starts automatically and connects to the Temporal server.

#### Direct Access

The `docker-compose.dev.yml` file maps the UI port directly to localhost:

```yaml
temporal-web:
  container_name: api-template-temporal-ui-dev
  image: temporalio/ui:2.34.0
  ports:
    - 8082:8080  # UI publicly exposed on localhost:8082
```

**Access the UI**: Simply open your browser to:
```
http://localhost:8082
```

No port forwarding or tunneling required in development!

#### Alternative Port (If 8082 is in use)

If port 8082 is already in use, you can run the UI on a different port:

```bash
# Stop the existing UI container
docker stop api-template-temporal-ui-dev

# Run with a different port
docker run -d --name temporal-ui-custom \
  --network api_project_template3_dev-network \
  -e TEMPORAL_ADDRESS=temporal:7233 \
  -e TEMPORAL_CORS_ORIGINS=http://localhost:3000 \
  -p 8083:8080 \
  temporalio/ui:2.34.0

# Access at http://localhost:8083
```

#### Verifying UI Access

Once started, you should see:

```bash
# Check if UI container is running
docker ps | grep temporal-ui

# Should show:
# api-template-temporal-ui-dev   temporalio/ui:2.34.0   ...   0.0.0.0:8082->8080/tcp

# Check UI logs
docker logs api-template-temporal-ui-dev

# Should show:
# Temporal UI is running on port 8080
```

If you see errors about connecting to Temporal server, ensure the Temporal server is running:

```bash
# Check Temporal server status
uv run cli dev status
```

---

### Production Environment

In production, the Temporal UI is **bound to localhost only** and not exposed to external networks. The `docker-compose.prod.yml` configuration ensures the UI is only accessible from the server itself:

```yaml
temporal-web:
  container_name: api-template-temporal-ui-prod
  image: temporalio/ui:2.34.0
  ports:
    - 127.0.0.1:8081:8080  # Only accessible from localhost
  networks:
    - backend  # Internal Docker network only
```

To access the UI in production, use one of these secure access patterns:

#### Option 1: SSH Tunnel (Recommended)

Create an SSH tunnel from your local machine to the production server:

```bash
# SSH tunnel to production server
ssh -L 8082:localhost:8081 user@production-server.example.com

# Now access UI at http://localhost:8082
```

This forwards your local port 8082 to port 8081 on the production server (where Temporal UI is listening on localhost).

#### Option 2: Direct Server Access

If you have direct access to the production server (e.g., via VPN or bastion host):

1. SSH into the production server
2. Use a local browser or curl to access the UI:
   ```bash
   # On the production server
   curl http://localhost:8081
   
   # Or use a text-based browser
   lynx http://localhost:8081
   ```

**Note**: This method requires being on the server itself since the UI is bound to `127.0.0.1`.

#### Option 3: Kubernetes Port Forward

If running on Kubernetes:

```bash
# Forward to temporal-ui service
kubectl port-forward -n temporal service/temporal-ui 8082:8080

# Access at http://localhost:8082
```

#### Option 4: Reverse Proxy with Authentication (Advanced)

If you need to expose the UI to a wider internal audience, use a reverse proxy with strong authentication:

```nginx
# nginx.conf
server {
    listen 443 ssl;
    server_name temporal-ui.internal.example.com;
    
    ssl_certificate /etc/nginx/ssl/temporal-ui.crt;
    ssl_certificate_key /etc/nginx/ssl/temporal-ui.key;
    
    # Require authentication
    auth_basic "Temporal UI";
    auth_basic_user_file /etc/nginx/.htpasswd;
    
    # IP whitelist - only allow corporate network
    allow 10.0.0.0/8;
    deny all;
    
    location / {
        proxy_pass http://localhost:8081;  # Production UI on localhost
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**⚠️ Security Warning**: 
- Only expose to internal networks via VPN
- Never expose the Temporal UI to the public internet
- SSH tunnels are still the most secure option for individual access

---

## UI Features and Usage

### 1. Workflows List

The main page shows all workflows in the selected namespace.

**URL**: `http://localhost:8082/namespaces/default/workflows`

**Features**:
- Filter by workflow status (Running, Completed, Failed, Timed Out, etc.)
- Search by workflow ID or type
- Sort by start time, close time, or execution time
- View workflow input and result

**Filters**:
```
WorkflowType = "OrderProcessingWorkflow"
ExecutionStatus = "Running"
StartTime BETWEEN "2025-01-01" AND "2025-12-31"
```

### 2. Workflow Execution Details

Click on any workflow to see its detailed execution view.

**Information Available**:
- **Summary**: Workflow ID, type, status, start/end times
- **Input**: Workflow input parameters (JSON)
- **Result**: Workflow return value (JSON)
- **Events**: Detailed event history (see below)
- **Stack Trace**: For failed workflows
- **Queries**: Send queries to running workflows
- **Signals**: Send signals to running workflows

### 3. Event History

The event history shows every step the workflow took:

**Event Types**:
- `WorkflowExecutionStarted` - Workflow began
- `ActivityTaskScheduled` - Activity scheduled for execution
- `ActivityTaskStarted` - Activity began executing
- `ActivityTaskCompleted` - Activity finished successfully
- `ActivityTaskFailed` - Activity failed
- `WorkflowTaskScheduled` - Workflow decision task scheduled
- `WorkflowTaskCompleted` - Workflow processed an event
- `TimerStarted` - Timer/sleep started
- `TimerFired` - Timer elapsed
- `WorkflowExecutionCompleted` - Workflow finished successfully
- `WorkflowExecutionFailed` - Workflow failed

**Example Event History**:
```
1. WorkflowExecutionStarted
   Input: {"order_id": "ORD-12345", "amount": 99.99}

2. WorkflowTaskScheduled

3. WorkflowTaskStarted

4. WorkflowTaskCompleted
   Decisions: [ScheduleActivityTask: charge_payment]

5. ActivityTaskScheduled
   Activity: charge_payment
   Input: 99.99

6. ActivityTaskStarted
   Worker: api-worker-1

7. ActivityTaskCompleted
   Result: "txn_abc123"

8. WorkflowTaskScheduled

9. WorkflowTaskStarted

10. WorkflowTaskCompleted
    Decisions: [CompleteWorkflowExecution]

11. WorkflowExecutionCompleted
    Result: {"status": "completed", "order_id": "ORD-12345"}
```

### 4. Debugging Failed Workflows

When a workflow fails, the UI provides:

**Stack Trace**:
```python
Traceback (most recent call last):
  File "src/app/worker/workflows/order_workflow.py", line 42, in run
    payment = await self.execute_activity(charge_payment, input.amount)
  File "temporalio/workflow.py", line 123, in execute_activity
    raise ApplicationError("Payment gateway timeout")
temporalio.exceptions.ApplicationError: Payment gateway timeout
```

**Failure Details**:
- Error type: `ApplicationError`
- Error message: `Payment gateway timeout`
- Retry attempt: 3 of 5
- Next retry scheduled: 2025-11-02 15:30:00

**Actions**:
- **Reset**: Restart workflow from the beginning
- **Terminate**: Stop workflow permanently
- **Signal**: Send data to influence behavior

### 5. Sending Signals

For workflows that support signals (e.g., approval workflows):

**Steps**:
1. Navigate to workflow execution
2. Click "Send Signal" button
3. Select signal name (e.g., `approve`, `cancel`)
4. Provide signal arguments (JSON)
5. Click "Send"

**Example**:
```json
Signal: cancel_order
Arguments: {
  "reason": "Customer requested cancellation"
}
```

### 6. Querying Workflow State

Query running workflows to inspect their current state:

**Steps**:
1. Navigate to workflow execution
2. Click "Query" tab
3. Select query name (e.g., `state`, `get_status`)
4. Click "Execute"
5. View query result

**Example**:
```json
Query: state
Result: {
  "status": "processing_payment",
  "progress": 0.4,
  "current_step": "charge_payment"
}
```

### 7. Workflow Search

Use advanced search queries:

```
WorkflowType = "OrderProcessingWorkflow" 
AND ExecutionStatus = "Failed"
AND StartTime > "2025-11-01T00:00:00Z"
AND CustomKeywordField = "customer@example.com"
```

**Available Fields**:
- `WorkflowType`
- `WorkflowId`
- `RunId`
- `ExecutionStatus`
- `StartTime`
- `CloseTime`
- `ExecutionTime`
- `CustomKeywordField`, `CustomIntField`, etc. (if search attributes are configured)

### 8. Archival and History

Temporal stores workflow history indefinitely by default:

**Retention Settings** (configured in Temporal server):
```yaml
retention:
  default: 7d  # Keep history for 7 days
  maximum: 30d  # Maximum retention period
```

**Archival** (long-term storage):
- Archive completed workflows to S3, GCS, or blob storage
- Query archived workflows separately
- Reduces database size while preserving history

---

## Configuration

### UI Configuration File

The UI can be customized via environment variables:

```yaml
# docker-compose.dev.yml
temporal-web:
  image: temporalio/ui:2.34.0
  environment:
    - TEMPORAL_ADDRESS=temporal:7233  # Temporal server address
    - TEMPORAL_CORS_ORIGINS=http://localhost:3000  # CORS for web clients
    - TEMPORAL_UI_PORT=8080  # Port to listen on (inside container)
    - TEMPORAL_AUTH_ENABLED=false  # Enable auth (production only)
    - TEMPORAL_CODEC_ENDPOINT=http://codec-server:8081  # For encrypted payloads
```

### Custom Namespace

To view workflows in a different namespace:

1. Navigate to UI: `http://localhost:8082`
2. Click namespace dropdown (top-right)
3. Select or enter namespace name
4. Workflows for that namespace will be displayed

### Search Attributes

To enable custom search attributes:

```bash
# Register custom search attributes (run once)
tctl --namespace default admin cluster add-search-attributes \
  --name CustomKeywordField \
  --type Keyword

tctl --namespace default admin cluster add-search-attributes \
  --name CustomIntField \
  --type Int
```

Then use in workflows:

```python
handle = await OrderWorkflow.start_workflow(
    client,
    input=order_data,
    id="order-123",
    search_attributes={
        "CustomKeywordField": [order_data.customer_email],
        "CustomIntField": [int(order_data.amount)]
    }
)
```

---

## Troubleshooting

### UI Not Loading

**Symptom**: Browser shows "Unable to connect" or "ERR_CONNECTION_REFUSED"

**Solutions**:
1. Verify container is running:
   ```bash
   docker ps | grep temporal-ui
   ```

2. Check container logs:
   ```bash
   docker logs api-template-temporal-ui-dev
   ```

3. Ensure Temporal server is running:
   ```bash
   docker ps | grep temporal-dev
   ```

4. Verify port mapping:
   ```bash
   docker port api-template-temporal-ui-dev
   # Should show: 8080/tcp -> 0.0.0.0:8082
   ```

### UI Shows "Cannot Connect to Temporal Server"

**Symptom**: UI loads but shows error connecting to Temporal

**Solutions**:
1. Verify Temporal server is running:
   ```bash
   uv run cli dev status
   ```

2. Check if UI can reach Temporal server:
   ```bash
   docker exec api-template-temporal-ui-dev ping temporal
   ```

3. Verify network configuration:
   ```bash
   docker network inspect api_project_template3_dev-network
   ```

4. Check Temporal server logs:
   ```bash
   docker logs api-template-temporal-dev
   ```

### No Workflows Visible

**Symptom**: UI loads successfully but shows no workflows

**Solutions**:
1. Verify namespace: Check that you're viewing the correct namespace (dropdown in top-right)

2. Start a test workflow:
   ```bash
   uv run python src/app/worker/example.py
   ```

3. Check if workflows exist:
   ```bash
   docker exec api-template-temporal-dev tctl workflow list
   ```

4. Verify worker is running:
   ```bash
   # In separate terminal
   uv run python -m src.app.worker.main serve --queue orders
   ```

### Port Already in Use

**Symptom**: `docker-compose up` fails with "port 8082 already in use"

**Solutions**:
1. Find process using port:
   ```bash
   sudo lsof -i :8082
   # or
   sudo netstat -tlnp | grep 8082
   ```

2. Stop conflicting process or use different port:
   ```bash
   docker-compose -f docker-compose.dev.yml up -d temporal-web
   docker run -p 8083:8080 ...
   ```

---

## Performance Considerations

### Large Event Histories

Workflows with thousands of events can slow down the UI:

**Solutions**:
- Use pagination (UI automatically paginates event history)
- Use "Continue As New" pattern to reset workflow history
- Enable event history archival for old workflows

### Many Concurrent Workflows

Viewing thousands of workflows can be slow:

**Solutions**:
- Use filters to narrow down results
- Index search attributes for faster queries
- Use workflow pagination (UI shows 20 workflows per page)

---

## Security Best Practices

✅ **DO**:
- Access UI via SSH tunnel or VPN in production
- Restrict UI to internal networks only
- Use authentication (basic auth or OAuth)
- Audit UI access logs
- Use read-only credentials for UI database access

❌ **DON'T**:
- Expose UI to public internet
- Share UI credentials
- Allow anonymous access in production
- Store sensitive data in workflow inputs (encrypt instead)

---

## UI Alternatives

### Temporal CLI (tctl)

For command-line workflow management:

```bash
# List workflows
docker exec api-template-temporal-dev tctl workflow list

# Describe workflow
docker exec api-template-temporal-dev tctl workflow describe -w <workflow-id>

# Show workflow history
docker exec api-template-temporal-dev tctl workflow show -w <workflow-id>

# Send signal
docker exec api-template-temporal-dev tctl workflow signal -w <workflow-id> -n signal_name

# Query workflow
docker exec api-template-temporal-dev tctl workflow query -w <workflow-id> -t query_name
```

### Programmatic Access

Use Temporal SDK to list/manage workflows:

```python
from temporalio.client import Client

async def list_workflows():
    client = await Client.connect("localhost:7233")
    
    # List all workflows
    async for workflow in client.list_workflows():
        print(f"Workflow ID: {workflow.id}")
        print(f"Status: {workflow.status}")
        print(f"Type: {workflow.workflow_type}")
```

---

## Related Documentation

- [Main Overview](./main.md) - Temporal concepts and architecture
- [Configuration](./configuration.md) - Configure Temporal settings
- [Usage Guide](./usage.md) - Execute workflows from FastAPI
- [Security](./security.md) - Secure Temporal communication

## External Resources

- [Temporal Web UI Documentation](https://docs.temporal.io/web-ui)
- [Temporal CLI Reference](https://docs.temporal.io/tctl)
- [Workflow Search Syntax](https://docs.temporal.io/visibility#search-attribute)

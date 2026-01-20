# Testing Guide: Docker on EC2

This guide is specifically for running load tests when your application is running inside a **Docker container** on an **EC2 instance** (Ubuntu), and you want to run Locust from the **EC2 Host**.

## Architecture

*   **Chatbot App**: Runs inside a Docker container (Port 8000 mapped to Host 3001).
*   **Locust Script**: Runs on the EC2 Ubuntu Host (Port 5050 for callbacks).
*   **Challenge**: The App needs to send "Glific Callbacks" *out* of the container to the Locust script on the Host.

---

## Step 1: Install Locust on EC2 Host

SSH into your EC2 machine and install Locust globally or in a virtualenv:

```bash
sudo apt update
sudo apt install python3-pip -y
pip3 install locust
```

## Step 2: Configure Application Networking

The application inside Docker needs to know where to send the callbacks. Since Locust is running on the Host, we use the **Docker Bridge IP** (usually `172.17.0.1`).

1.  **Edit your `.env` file** (on the EC2 host):

    ```bash
    nano .env
    ```

2.  **Update `GLIFIC_API_URL`**:

    ```bash
    # Point to the Docker Bridge Gateway IP (172.17.0.1 is standard)
    export GLIFIC_API_URL=http://172.17.0.1:5050
    
    # Ensure these are set to dummy values
    export GLIFIC_PHONE=dummy
    export GLIFIC_PASSWORD=dummy
    ```

3.  **Restart the Container**:

    ```bash
    docker-compose down
    docker-compose up -d
    ```

    *Tip: You can verify the bridge IP with `ip addr show docker0`.*

## Step 3: Run the Load Test

Run Locust from the directory where `tests/load/locustfile.py` is located.

```bash
# 1. Export your API Key for the test script
export API_KEY="your-actual-api-key"

# 2. Run Locust (Headless Mode)
# --host http://localhost:3001 points to the Docker container's exposed port
locust -f tests/load/locustfile.py \
  --headless \
  --users 5 \
  --spawn-rate 2 \
  --run-time 10m \
  --host http://localhost:3001 \
  --html load_test_report.html
```

## Step 4: Check Results

1.  **Download the Report**:
    Copy the `load_test_report.html` from the EC2 instance to your local machine:
    ```bash
    scp -i your-key.pem ubuntu@your-ec2-ip:~/path/to/load_test_report.html ./
    ```

2.  **Verify Async Callbacks**:
    Open the report and look for **"Glific Notification"**.
    *   **Count**: Should match the number of search/file requests.
    *   **Avg Response Time**: This is your real "End-to-End Latency".

---

## Troubleshooting

**Q: I see "Glific Notification" count is 0.**
A: The Docker container fails to reach the Host on port 5050.
*   **Check IP**: Run `docker exec -it chatbot-websearch ip route` and check the `default` gateway. Use that IP in `GLIFIC_API_URL`.
*   **Firewall**: Ensure `ufw` is not blocking the docker interface.
    ```bash
    sudo ufw allow in on docker0
    ```

**Q: Locust says "Connection refused" to localhost:3001.**
A: Ensure your Docker container is actually running and port 3001 is open.
    ```bash
    docker ps

---

# Testing on Local Machine

If you want to run the load test entirely on your laptop (Mac/Linux), follow these steps.

## Scenario A: App running with Uvicorn (No Docker)

1.  **Start the App** with the Locust callback URL:
    ```bash
    export GLIFIC_API_URL="http://localhost:5050"
    export GLIFIC_PHONE="dummy"
    export GLIFIC_PASSWORD="dummy"
    
    uvicorn app.main:app --reload --port 8000
    ```

2.  **Run Locust**:
    ```bash
    # Open a new terminal
    export API_KEY="your-local-key"
    
    locust -f tests/load/locustfile.py \
        --users 10 \
        --spawn-rate 2 \
        --host http://localhost:8000
    ```
    *Note: We omitted `--headless` so you can open `http://localhost:8089` in your browser to watch the test.*

## Scenario B: App running with Docker Compose locally

1.  **Configure `.env`**:
    *   **Mac/Windows**: Use `host.docker.internal` to reach your host machine.
    ```bash
    GLIFIC_API_URL=http://host.docker.internal:5050
    ```
    *   **Linux**: Use `172.17.0.1` (Docker Bridge IP).
    ```bash
    GLIFIC_API_URL=http://172.17.0.1:5050
    ```

2.  **Start Docker**:
    ```bash
    docker-compose up -d
    ```

3.  **Run Locust**:
    ```bash
    # Ensure you target the mapped port (usually 3001 in your docker-compose)

---

# Remote Testing (Local Locust -> Remote EC2)

If you want to run the Locust script on your **Local Machine** but target the **Remote EC2 Server**, you face a networking challenge: The EC2 App needs to send callbacks back to your Laptop (which is behind a firewall/NAT).

**Solution**: Use [ngrok](https://ngrok.com/) to create a secure tunnel.

## Step 1: Start Ngrok (Locally)
1.  **Install ngrok**:
    *   Mac: `brew install ngrok/ngrok/ngrok`
    *   Windows/Linux: Download from [ngrok.com/download](https://ngrok.com/download)
2.  **Start the tunnel** on port 5050 (our Mock Server port):
    ```bash
    ngrok http 5050
    ```
3.  **Copy the Forwarding URL**:
    Look for the line that says `Forwarding`. It will look like: `https://abcd-123.ngrok-free.app`

## Step 2: Configure Remote App (On EC2)
1.  SSH into your EC2 instance.
2.  Update the `.env` file to point `GLIFIC_API_URL` to your ngrok address:
    ```bash
    GLIFIC_API_URL=https://abcd-123.ngrok-free.app
    ```
3.  Restart the remote application:
    ```bash
    docker-compose down && docker-compose up -d
    ```

## Step 3: Run Locust (Locally)
Now your local Locust script can trigger the remote app, and the remote app can "call back" to your local script via ngrok.

```bash
export API_KEY="your-remote-api-key"

locust -f tests/load/locustfile.py \
    --host https://api.your-ec2-domain.com
```

**Success!** You will see "Glific Notification" events appearing in your local Locust statistics.

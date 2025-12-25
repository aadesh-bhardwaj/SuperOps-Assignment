#!/bin/bash
# Quick fix script to get nginx working on existing instances
# Run this on each instance via Session Manager

# Determine which server this is based on IP
INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
if [[ "$INSTANCE_ID" == *"180"* ]] || [[ "$INSTANCE_ID" == *"cce"* ]]; then
    SERVER_NUM=1
else
    SERVER_NUM=2
fi

echo "Configuring as Server $SERVER_NUM"

# Create custom Hello World page
cat > /usr/share/nginx/html/index.html <<EOF
<!DOCTYPE html>
<html>
<head>
    <title>Hello World - Server $SERVER_NUM</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }
        .container {
            text-align: center;
            padding: 40px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
        }
        h1 {
            font-size: 3em;
            margin-bottom: 20px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .server-info {
            font-size: 1.5em;
            margin-top: 20px;
            padding: 15px;
            background: rgba(255, 255, 255, 0.2);
            border-radius: 10px;
        }
        .status {
            color: #4ade80;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🌍 Hello World!</h1>
        <div class="server-info">
            <p>Served by: <strong>Web Server $SERVER_NUM</strong></p>
            <p>Status: <span class="status">✅ Healthy</span></p>
            <p>Instance ID: <strong>$INSTANCE_ID</strong></p>
        </div>
    </div>
</body>
</html>
EOF

# Create health check file
echo "OK" > /usr/share/nginx/html/health

# Set proper permissions
chmod 644 /usr/share/nginx/html/index.html
chmod 644 /usr/share/nginx/html/health

# Start and enable nginx
echo "Starting nginx service..."
systemctl start nginx
systemctl enable nginx

# Wait a moment
sleep 2

# Check status
if systemctl is-active --quiet nginx; then
    echo "✅ SUCCESS: Nginx is running!"
    echo "Testing locally..."
    curl -s http://localhost/ | grep "Hello World" > /dev/null
    if [ $? -eq 0 ]; then
        echo "✅ Local test passed - Hello World page is working!"
    else
        echo "⚠️ Warning: Nginx is running but page might not be correct"
    fi
else
    echo "❌ ERROR: Nginx failed to start"
    systemctl status nginx
fi

echo ""
echo "Done! This instance should now be healthy in the target group."
echo "It may take 30-60 seconds for the health check to update."

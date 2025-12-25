#!/bin/bash
# User data script to install and configure nginx

# Log all output for debugging
exec > >(tee -a /var/log/user-data.log)
exec 2>&1
echo "Starting user data script at $(date)"

# Wait for network to be fully ready
sleep 10

# Update system
echo "Updating system packages..."
yum update -y

# Enable nginx in amazon-linux-extras FIRST
echo "Enabling nginx in amazon-linux-extras..."
amazon-linux-extras enable nginx1

# Clean metadata to ensure fresh package info
echo "Cleaning yum metadata..."
yum clean metadata

# Now install nginx
echo "Installing nginx..."
yum install -y nginx

# Verify nginx is installed
if ! command -v nginx &> /dev/null; then
    echo "ERROR: nginx installation failed, retrying..."
    # Try one more time
    yum clean all
    yum makecache
    yum install -y nginx
fi

# Create custom HTML page with server identification
cat > /usr/share/nginx/html/index.html <<'ENDHTML'
<!DOCTYPE html>
<html>
<head>
    <title>Hello World - Server ${server_id}</title>
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
            <p>Served by: <strong>Web Server ${server_id}</strong></p>
            <p>Status: <span class="status">✅ Healthy</span></p>
            <p>Instance ID: <span id="instance-id"></span></p>
        </div>
    </div>
    <script>
        // Fetch instance metadata
        fetch('http://169.254.169.254/latest/meta-data/instance-id')
            .then(response => response.text())
            .then(data => {
                document.getElementById('instance-id').textContent = data;
            })
            .catch(error => {
                document.getElementById('instance-id').textContent = 'Server ${server_id}';
            });
    </script>
</body>
</html>
ENDHTML

# Replace SERVER_ID placeholder with actual server ID
sed -i "s/Server \${server_id}/Server ${server_id}/g" /usr/share/nginx/html/index.html

# Verify nginx installation
if command -v nginx &> /dev/null; then
    echo "Nginx installed successfully"
else
    echo "ERROR: Nginx installation failed!"
    exit 1
fi

# Start and enable nginx
echo "Starting nginx service..."
systemctl start nginx
systemctl enable nginx

# Verify nginx is running
sleep 2
if systemctl is-active --quiet nginx; then
    echo "Nginx is running successfully"
else
    echo "ERROR: Nginx failed to start. Attempting restart..."
    systemctl restart nginx
fi

# Create a health check file
echo "OK" > /usr/share/nginx/html/health

# Set proper permissions
chmod 644 /usr/share/nginx/html/index.html
chmod 644 /usr/share/nginx/html/health

# Log the completion
echo "Nginx setup completed for Server ${server_id} at $(date)"
echo "Nginx status: $(systemctl is-active nginx)"

# Final verification
curl -f http://localhost/ > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "SUCCESS: Local curl test passed"
else
    echo "WARNING: Local curl test failed"
fi

#!/bin/bash
# User data script to install and configure nginx

# Update system
yum update -y

# Install nginx
amazon-linux-extras install -y nginx

# Create custom HTML page with server identification
cat > /usr/share/nginx/html/index.html <<EOF
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
EOF

# Start and enable nginx
systemctl start nginx
systemctl enable nginx

# Create a health check file
echo "OK" > /usr/share/nginx/html/health

# Log the completion
echo "Nginx setup completed for Server ${server_id}" >> /var/log/user-data.log

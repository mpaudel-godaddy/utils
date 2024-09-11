
#!/bin/bash

# Check if the correct number of arguments are provided
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 /path/to/local/file remote_user@remote.server"
    exit 1
fi

# Variables
LOCAL_FILE="$1"
REMOTE_USER_HOST="$2"
TEMP_REMOTE_PATH="/tmp/payments-api-ext"
FINAL_REMOTE_PATH="/etc/logrotate.d/payments-api-ext"

# Check if the local file exists
if [ ! -f "$LOCAL_FILE" ]; then
    echo "Error: Local file $LOCAL_FILE does not exist."
    exit 1
fi

# Copy the file to a temporary directory on the remote server
scp "$LOCAL_FILE" "$REMOTE_USER_HOST:$TEMP_REMOTE_PATH"

# Check if the SCP command was successful
if [ $? -ne 0 ]; then
    echo "Error: Failed to copy file to remote server."
    exit 1
fi

# Move the file to the final directory and change ownership and permissions
ssh "$REMOTE_USER_HOST" <<EOF
    sudo mv "$TEMP_REMOTE_PATH" "$FINAL_REMOTE_PATH"
    sudo chown root:root "$FINAL_REMOTE_PATH"
    sudo chmod 644 "$FINAL_REMOTE_PATH"
EOF

# Check if the SSH command was successful
if [ $? -eq 0 ]; then
    echo "File copied to $FINAL_REMOTE_PATH, ownership changed to root:root, and permissions set to 644 successfully."
else
    echo "Error: Failed to move file and change ownership and permissions on the remote server."
    exit 1
fi

#!/bin/bash

# Restarts the application if exit code is not 0
source venv/bin/activate

until melvonaut; do
    echo "LOG: Application crashed. Restarting ..."
    sleep 5
done

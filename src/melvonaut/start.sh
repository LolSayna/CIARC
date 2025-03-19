#!/bin/bash

until python3 __main__.py; do
    echo "LOG: Application crashed. Restarting ..."
    sleep 5
done
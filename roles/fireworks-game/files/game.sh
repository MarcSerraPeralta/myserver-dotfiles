#!/bin/bash
cd /opt/fireworks-game
source venv/bin/activate

case "$1" in
    start)
        if [ -f server.pid ] && kill -0 $(cat server.pid) 2>/dev/null; then
            echo "Fireworks game server is already running (PID: $(cat server.pid))"
            exit 0
        fi
        echo "Starting Fireworks game server..."
	nohup venv/bin/uvicorn server:app --host 127.0.0.1 --port 8082 > server.log 2>&1 &
        echo $! > server.pid
        echo "Server started (PID: $(cat server.pid))"
        ;;
    stop)
        if [ -f server.pid ]; then
            echo "Stopping Fireworks game server..."
            kill $(cat server.pid)
            rm server.pid
            echo "Server stopped."
        else
            echo "Server is not running or PID file missing."
        fi
        ;;
    status)
        if [ -f server.pid ] && kill -0 $(cat server.pid) 2>/dev/null; then
            echo "Server is running (PID: $(cat server.pid))"
        else
            echo "Server is stopped."
        fi
        ;;
    *)
        echo "Usage: $0 {start|stop|status}"
        exit 1
        ;;
esac

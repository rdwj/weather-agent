#!/bin/bash
# Start script for Weather Agent with Streamlit UI

echo "Starting Weather Agent services..."

# Start the FastAPI backend
echo "Starting API server on port 8000..."
uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4 &
API_PID=$!

# Wait for API to be ready
echo "Waiting for API to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null; then
        echo "API server is ready!"
        break
    fi
    sleep 1
done

# Start Streamlit UI
echo "Starting Streamlit UI on port 8501..."
streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0 --server.baseUrlPath / &
STREAMLIT_PID=$!

echo "Services started:"
echo "  - API Server: http://localhost:8000 (PID: $API_PID)"
echo "  - Streamlit UI: http://localhost:8501 (PID: $STREAMLIT_PID)"

# Keep the script running and handle termination
trap "echo 'Stopping services...'; kill $API_PID $STREAMLIT_PID; exit" SIGTERM SIGINT

# Wait for both processes
wait $API_PID $STREAMLIT_PID
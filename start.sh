#!/bin/sh
# Decode credentials from Railway environment variables
python -c "from auth.startup import reconstruct_credentials; reconstruct_credentials()"

# Start the FastMCP server in SSE mode, listening on the port Railway provides
exec python server.py --sse --port ${PORT:-8000} --host 0.0.0.0

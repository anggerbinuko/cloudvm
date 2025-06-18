"""
This file contains a fixed version of the handle_websocket method
that doesn't have the WebSocketState error.
"""

async def handle_websocket_fixed(
    self,
    websocket: WebSocket,
    hostname: str,
    username: str,
    password: Optional[str] = None,
    private_key: Optional[str] = None,
    port: int = 22
):
    """Handle WebSocket connection and bridge it to SSH"""
    conn = None
    try:
        # Create SSH connection
        conn = await self.connect(
            hostname=hostname,
            username=username,
            password=password,
            private_key=private_key,
            port=port
        )
        
        # Wait for initial terminal size
        try:
            size_data = await websocket.receive_json()
            term_width = size_data.get("cols", 80)
            term_height = size_data.get("rows", 24)
        except Exception:
            term_width, term_height = 80, 24
        
        # Create interactive shell with size
        async with conn.create_process(
            term_type="xterm-256color",
            term_size=(term_width, term_height)
        ) as process:
            # Handle I/O between WebSocket and SSH
            await self._handle_ssh_io(websocket, process)
            
    except Exception as e:
        logger.error(f"SSH connection error: {str(e)}")
        try:
            await websocket.send_text(f"\r\nConnection error: {str(e)}")
            await websocket.close()
        except Exception as ws_error:
            logger.error(f"Error closing websocket: {str(ws_error)}")
    finally:
        # Clean up
        if conn:
            try:
                conn.close()
                await conn.wait_closed()
            except Exception as e:
                logger.error(f"Error closing SSH connection: {str(e)}")

import asyncio
import asyncssh
import logging
import json
from typing import Dict, Optional, Any
from fastapi import WebSocket
from tempfile import NamedTemporaryFile
import os

logger = logging.getLogger(__name__)

class SSHManager:
    def __init__(self):
        self.active_connections: Dict[str, asyncssh.SSHClientConnection] = {}
        
    async def connect(
        self,
        hostname: str,
        username: str,
        password: Optional[str] = None,
        private_key: Optional[str] = None,
        port: int = 22
    ) -> asyncssh.SSHClientConnection:
        """Create SSH connection to remote host"""
        try:
            # Create temporary file for private key if provided
            key_file = None
            try:
                if private_key:
                    key_file = NamedTemporaryFile(delete=False, mode='w')
                    key_file.write(private_key)
                    key_file.close()
                    
                conn = await asyncssh.connect(
                    hostname,
                    username=username,
                    password=password,
                    client_keys=[key_file.name] if key_file else None,
                    known_hosts=None,  # In production, handle known_hosts properly
                    port=port
                )
            finally:
                # Clean up temporary key file
                if key_file:
                    os.unlink(key_file.name)
            return conn
        except Exception as e:
            logger.error(f"SSH connection failed: {str(e)}")
            raise

    async def create_session(
        self,
        conn: asyncssh.SSHClientConnection,
        term_type: str = "xterm-256color",
        width: int = 80,
        height: int = 24
    ) -> asyncssh.SSHClientSession:
        """Create interactive shell session"""
        try:
            session = await conn.create_session(
                term_type=term_type,
                term_size=(width, height)
            )
            return session
        except Exception as e:
            logger.error(f"Failed to create SSH session: {str(e)}")
            raise

    async def handle_websocket(
        self,
        websocket: WebSocket,
        hostname: str,
        username: str,
        password: Optional[str] = None,
        private_key: Optional[str] = None,
        port: int = 22
    ):
        """Handle WebSocket connection and bridge it to SSH"""
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
            if not websocket.client_state.disconnected:
                await websocket.send_text(f"\r\nConnection error: {str(e)}")
                await websocket.close()
        finally:
            # Clean up
            if 'conn' in locals():
                conn.close()
                await conn.wait_closed()
    
    async def _handle_ssh_io(self, websocket: WebSocket, process):
        """Handle bidirectional I/O between WebSocket and SSH process"""
        
        # Forward SSH output to WebSocket
        async def reader():
            try:
                while True:
                    data = await process.stdout.read(1024)
                    if not data:
                        break
                    await websocket.send_text(data.decode())
            except Exception as e:
                logger.error(f"SSH reader error: {str(e)}")
        
        # Forward WebSocket input to SSH
        async def writer():
            try:
                while True:
                    message = await websocket.receive_json()
                    
                    # Handle terminal resize
                    if message.get('type') == 'resize':
                        process.change_terminal_size(
                            width=message.get('cols', 80),
                            height=message.get('rows', 24)
                        )
                        continue
                    
                    # Handle regular input
                    if 'data' in message:
                        process.stdin.write(message['data'].encode())
                        await process.stdin.drain()
            except Exception as e:
                logger.error(f"WebSocket writer error: {str(e)}")
        
        # Run both directions concurrently
        reader_task = asyncio.create_task(reader())
        writer_task = asyncio.create_task(writer())
        
        # Wait for either task to complete
        done, pending = await asyncio.wait(
            [reader_task, writer_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        # Cancel remaining task
        for task in pending:
            task.cancel()

import asyncio
import time

import psutil
from typing import Callable, Optional
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

# Logging
from elysia.api.core.log import logger

# Objects
from elysia.api.utils.default_payloads import error_payload


async def help_websocket(
    websocket: WebSocket,
    ws_route: Callable,
    cancel_handler: Optional[Callable] = None,
):
    memory_process = psutil.Process()
    try:
        await websocket.accept()
        while True:
            try:
                data = None
                last_communication = time.time()

                # Wait for a message from the client
                while True:
                    if time.time() - last_communication > 60:
                        await websocket.send_json({"type": "heartbeat"})
                        last_communication = time.time()

                    try:
                        data = await asyncio.wait_for(
                            websocket.receive_json(), timeout=1.0
                        )
                        last_communication = time.time()

                        # Handle cancel messages
                        if data.get("type") == "cancel" and cancel_handler:
                            await cancel_handler(data, websocket)
                            continue

                        # Check if it's a disconnect request
                        if data.get("type") == "disconnect":
                            return

                        # Process the received data as a task so we can
                        # continue listening for cancel messages
                        process_task = asyncio.create_task(
                            ws_route(data, websocket)
                        )

                        # While processing, keep listening for cancel messages
                        while not process_task.done():
                            try:
                                msg = await asyncio.wait_for(
                                    websocket.receive_json(), timeout=1.0
                                )
                                last_communication = time.time()

                                if msg.get("type") == "cancel" and cancel_handler:
                                    await cancel_handler(msg, websocket)
                                elif msg.get("type") == "disconnect":
                                    process_task.cancel()
                                    return
                            except asyncio.TimeoutError:
                                if time.time() - last_communication > 60:
                                    await websocket.send_json({"type": "heartbeat"})
                                    last_communication = time.time()
                                continue

                        # Propagate any exceptions from the task
                        await process_task

                        last_communication = time.time()

                    except asyncio.TimeoutError:
                        continue

            except (WebSocketDisconnect, RuntimeError):
                raise  # Let outer handlers manage disconnect
            except Exception as e:
                error = error_payload(
                    text=str(e),
                    conversation_id=data.get("conversation_id", "") if data else "",
                    query_id=data.get("query_id", "") if data else "",
                )
                await websocket.send_json(error)
                logger.error(f"Error in websocket communication: {str(e)}")

    except (WebSocketDisconnect, RuntimeError) as e:
        if isinstance(e, RuntimeError) and (
            "Cannot call 'receive' once a disconnect message has been received"
            not in str(e)
        ):
            raise
    except Exception as e:
        logger.warning(f"Closing WebSocket: {str(e)}")
    finally:
        try:
            await websocket.close()
        except (RuntimeError, WebSocketDisconnect):
            logger.info("WebSocket already closed")

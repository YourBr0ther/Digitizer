import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from digitizer.ws import ConnectionManager


@pytest.fixture
def manager():
    return ConnectionManager()


async def test_connect_adds_client(manager):
    ws = AsyncMock()
    await manager.connect(ws)
    assert len(manager.active_connections) == 1


async def test_disconnect_removes_client(manager):
    ws = AsyncMock()
    await manager.connect(ws)
    manager.disconnect(ws)
    assert len(manager.active_connections) == 0


async def test_broadcast_sends_to_all(manager):
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    await manager.connect(ws1)
    await manager.connect(ws2)
    await manager.broadcast({"event": "test", "data": {}})
    ws1.send_json.assert_called_once_with({"event": "test", "data": {}})
    ws2.send_json.assert_called_once_with({"event": "test", "data": {}})


async def test_broadcast_removes_dead_connections(manager):
    ws_alive = AsyncMock()
    ws_dead = AsyncMock()
    ws_dead.send_json.side_effect = Exception("connection closed")
    await manager.connect(ws_alive)
    await manager.connect(ws_dead)
    await manager.broadcast({"event": "test", "data": {}})
    assert len(manager.active_connections) == 1

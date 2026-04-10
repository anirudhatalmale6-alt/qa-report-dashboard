"""
Thread-safe data pool for Locust test data consumption.

Usage:
    from core.data_pool import DataPool

    # Create pool from a list (one-time consumption)
    pool = DataPool(["user1", "user2", "user3"])

    # In your task:
    user_id = pool.get()       # Returns next item, or None if empty
    print(pool.remaining())    # How many items left
    print(pool.is_empty())     # True if no items left

    # For reusable data (random pick, never exhausted):
    pool = DataPool(["user1", "user2", "user3"], reusable=True)
    user_id = pool.get()       # Random pick, never returns None
"""

from queue import Queue, Empty
import random
import threading


class DataPool:
    def __init__(self, data_list, reusable=False):
        """
        Args:
            data_list: List of test data items (user IDs, member IDs, etc.)
            reusable: If True, items are randomly picked and never exhausted.
                      If False, items are consumed once via FIFO queue.
        """
        self._reusable = reusable
        self._original = list(data_list)
        self._lock = threading.Lock()

        if not reusable:
            self._queue = Queue()
            for item in data_list:
                self._queue.put(item)
        else:
            self._data = list(data_list)

    def get(self):
        """
        Get next data item.
        - For consumable pools: returns next item or None if empty.
        - For reusable pools: returns random item (never None unless pool was empty from start).
        """
        if self._reusable:
            with self._lock:
                if not self._data:
                    return None
                return random.choice(self._data)
        else:
            try:
                return self._queue.get_nowait()
            except Empty:
                return None

    def remaining(self):
        """Number of items remaining (for consumable pools)."""
        if self._reusable:
            return len(self._data)
        return self._queue.qsize()

    def is_empty(self):
        """Check if pool is exhausted (for consumable pools)."""
        if self._reusable:
            return len(self._data) == 0
        return self._queue.empty()

    def put_back(self, item):
        """Put an item back into the pool (for consumable pools only)."""
        if self._reusable:
            return
        self._queue.put(item)

    def size(self):
        """Total items originally loaded."""
        return len(self._original)

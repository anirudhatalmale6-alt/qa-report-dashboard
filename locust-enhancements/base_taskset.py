from locust import SequentialTaskSet
from core.session_manager import SessionManager
from core.data_pool import DataPool


class BaseTaskSet(SequentialTaskSet):
    @property
    def session(self) -> SessionManager:
        return self.user.session

    def get_next_data(self, pool: DataPool):
        """
        Get next item from a DataPool. If pool is empty, interrupt this user.

        Usage in @task:
            user_id = self.get_next_data(user_pool)
            if user_id is None:
                return  # user is already interrupted
        """
        item = pool.get()
        if item is None:
            remaining_users = self.user.environment.runner.user_count
            print(f"[DataPool] Data exhausted. Stopping this user. ({remaining_users - 1} users remain)")
            self.interrupt()
            return None
        return item

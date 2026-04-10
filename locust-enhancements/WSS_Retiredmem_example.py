#__________________________________________________________________________________________________________________________
# Example: WSS_Retiredmem with DataPool (thread-safe) + self-interrupt
#
# Changes from original:
#   1. WSS_userId wrapped in DataPool (thread-safe Queue)
#   2. self.get_next_data(pool) replaces list.pop() - auto-interrupts when empty
#   3. No need for "if not WSS_userId:" manual check
#   4. Works safely with multiple Locust users (-u 10)
#
# Run Command:
#   locust -f wss\WSS_Retiredmem.py -u 1 -r .2 --only-summary --headless --env-name UAT41
#   locust -f wss\WSS_Retiredmem.py -u 10 -r .2 --only-summary --headless -t 10m --env-name UAT41
#__________________________________________________________________________________________________________________________

from framework import *
from data.WSS_RetiredmemID_224107 import WSS_userId
from core.data_pool import DataPool

# Wrap list in thread-safe DataPool (one-time consumption)
user_pool = DataPool(WSS_userId, reusable=False)

# For random reuse (load testing with same users repeatedly):
# user_pool = DataPool(WSS_userId, reusable=True)


class miAccount_RetireStatus(BaseTaskSet):

    def __init__(self, parent):
        super().__init__(parent)
        self.jsessionid = ""
        self.secondary_sessionid = ""
        self.TOKEN = ""
        self.first_name = ""
        self.addressId = ""

    def on_start(self):
        self.user.userId = ""
        self.user.password = WSSPASSWORD

    @task
    def Org_list(self):
        # Thread-safe: get next user ID, auto-interrupts if pool empty
        user_id = self.get_next_data(user_pool)
        if user_id is None:
            return

        # Assign credentials
        self.user.userId = user_id
        self.user.password = WSSPASSWORD

        # Launch session
        resp = self.session.launch_wss_session()
        if not resp:
            return

        # Login
        self.session.login()

        self.session.add_dependent()

        self.session.logout()

        # Optional: put userId back if you want reuse
        # user_pool.put_back(self.user.userId)


class miAccount_Users(BaseUser):
    urllib3.disable_warnings()
    wait_time = between(1, 5)

    def on_start(self):
        super().on_start()
        self.client.verify = False

    tasks = [miAccount_RetireStatus]

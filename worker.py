import queue
import threading


class Worker:
    def __init__(self, api_keys):
        self.queue = queue.Queue()
        self.task_id = 0
        self.removed_tasks = set()
        self.current_tasks = set()
        for api_key in api_keys:
            threading.Thread(target=self._run_daemon, args=(api_key,)).start()

    def _run_daemon(self, api_key):
        while True:
            task_id, func, args = self.queue.get()
            args = (api_key, *args)
            if task_id in self.removed_tasks:
                self.removed_tasks.remove(task_id)
            else:
                t = threading.Thread(target=func, args=args)
                t.start()
                t.join()
                self.current_tasks.remove(task_id)

    def add_task(self, func, *args):
        tid = self.task_id
        self.task_id += 1
        self.queue.put((tid, func, args))
        self.current_tasks.add(tid)
        return tid

    def remove_task(self, task_id):
        if task_id in self.current_tasks:
            self.removed_tasks.add(task_id)

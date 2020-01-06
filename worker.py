import queue
import threading


class Worker:
    def __init__(self):
        self.queue = queue.Queue()
        self.task_id = 0
        self.removed_tasks = set()
        self.current_tasks = set()
        threading.Thread(target=self._run_daemon).start()

    def _run_daemon(self):
        while True:
            task_id, func, args = self.queue.get()
            if task_id in self.removed_tasks:
                self.removed_tasks.remove(task_id)
            else:
                print(task_id)
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

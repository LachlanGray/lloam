import threading
import os

from .prompt import Prompt
from .completions import Completion, CompletionStatus


lock = threading.Lock()

class Agent:
    def get_lloam_members(self):
        def is_desired_type(value):
            return isinstance(value, (Prompt, Agent, Completion))

        def filter_value(value, seen):
            obj_id = id(value)
            if obj_id in seen:
                return None  # Avoid processing the same object again
            seen.add(obj_id)

            if is_desired_type(value):
                return value
            elif isinstance(value, list):
                filtered_list = [filter_value(item, seen) for item in value]
                filtered_list = [item for item in filtered_list if item is not None]
                return filtered_list if filtered_list else None
            elif isinstance(value, dict):
                filtered_dict = {k: filter_value(v, seen) for k, v in value.items()}
                filtered_dict = {k: v for k, v in filtered_dict.items() if v is not None}
                return filtered_dict if filtered_dict else None
            else:
                return None

        result = {}
        seen = set()
        seen.add(id(self))  # Add self to seen to avoid self-references

        for attr_name, attr_value in vars(self).items():
            if attr_name.startswith('_'):
                continue

            filtered_value = filter_value(attr_value, seen)
            if filtered_value is not None:
                result[attr_name] = filtered_value

        return result

    def format_progress(self):
        def expand_agents(obj, seen):
            obj_id = id(obj)
            if obj_id in seen:
                return None  # Avoid processing the same object again
            seen.add(obj_id)

            if isinstance(obj, Agent):
                obj_members = obj.get_lloam_members()
                return {key: expand_agents(value, seen) for key, value in obj_members.items()}
            elif isinstance(obj, list):
                return [expand_agents(item, seen) for item in obj]
            elif isinstance(obj, dict):
                return {k: expand_agents(v, seen) for k, v in obj.items()}
            else:
                return obj  # Leave other types unchanged

        seen = set()
        seen.add(id(self))
        members = self.get_lloam_members()
        members = {key: expand_agents(value, seen) for key, value in members.items()}

        done = "■"
        waiting = "□"

        result = []

        def process_member(kk, vv):
            if isinstance(vv, dict):
                result.append(f"[")
                for k, v in vv.items():
                    process_member(k, v)

                result.append("]")

            elif isinstance(vv, list):
                result.append("[")
                for v in vv:
                    process_member(None, v)

                result.append("]")

            elif isinstance(vv, Prompt):
                n_complete, n_waiting = vv.progress()

                result.append(n_complete * done)
                result.append(n_waiting * waiting)

            elif isinstance(vv, Completion):
                status = vv.status
                if status == CompletionStatus.FINISHED:
                    return
                result.append(f"[{waiting}]")
            else:
                return

        process_member(None, members)

        return "".join(result)


    def observe(self):

        stop_event = threading.Event()

        def display_progress():
            try:
                while not stop_event.is_set():
                    # Clear the screen
                    os.system('cls' if os.name == 'nt' else 'clear')

                    # Get the progress
                    with lock:
                        progress = self.format_progress()
                        print(progress)
                        print()
                        print("(Press Enter to end observation)")

                    # Wait for 0.1 seconds or until stop_event is set
                    stop_event.wait(0.1)
            except Exception as e:
                print(f"An error occurred in the observation thread: {e}")


        def wait_for_enter():
            input()  # Wait for Enter key press
            stop_event.set()  # Set the stop event when Enter is pressed

        # Start the background thread to display progress
        observer_thread = threading.Thread(target=display_progress, daemon=True)
        observer_thread.start()

        # Start the thread to wait for Enter key press
        input_thread = threading.Thread(target=wait_for_enter, daemon=True)
        input_thread.start()


